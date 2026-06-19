"""System prompt assembly -- identity, platform hints, skills index, context files.

All functions are stateless. AIAgent._build_system_prompt() calls these to
assemble pieces, then combines them with memory and ephemeral prompts.
"""

import json
import logging
import os
import threading
from collections import OrderedDict
from pathlib import Path

from dag_constants import get_dag_home, get_skills_dir, is_wsl
from typing import Optional

from agent.runtime_cwd import resolve_agent_cwd
from agent.skill_utils import (
    extract_skill_conditions,
    extract_skill_description,
    get_all_skills_dirs,
    get_disabled_skill_names,
    iter_skill_index_files,
    parse_frontmatter,
    skill_matches_environment,
    skill_matches_platform,
)
from utils import atomic_json_write

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Context file scanning — detect prompt injection / promptware in AGENTS.md,
# .cursorrules, SOUL.md before they get injected into the system prompt.
#
# Patterns live in ``tools/threat_patterns.py`` — the single source of truth
# shared with the memory-tool scanner and the tool-result delimiter system.
# This module just chooses how to react when a match is found (block-with-
# placeholder; the actual content never reaches the system prompt).
# ---------------------------------------------------------------------------

from tools.threat_patterns import scan_for_threats as _scan_for_threats


def _scan_context_content(content: str, filename: str) -> str:
    """Scan context file content for injection. Returns sanitized content.

    Uses the "context" scope from the shared threat-pattern library, which
    covers classic injection + promptware/C2 patterns + role-play hijack.
    Strict-scope patterns (SSH backdoor, persistence, exfil-URL) are NOT
    applied here — those are too aggressive for a context file in a
    cloned repo (security research, infra docs).  Content matching is
    BLOCKED at this layer because the file would otherwise enter the
    system prompt verbatim and the user has no chance to intervene.
    """
    findings = _scan_for_threats(content, scope="context")
    if findings:
        logger.warning("Context file %s blocked: %s", filename, ", ".join(findings))
        return f"[BLOCKED: {filename} contained potential prompt injection ({', '.join(findings)}). Content not loaded.]"

    return content


def _find_git_root(start: Path) -> Optional[Path]:
    """Walk *start* and its parents looking for a ``.git`` directory.

    Returns the directory containing ``.git``, or ``None`` if we hit the
    filesystem root without finding one.
    """
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return None


_DAG_MD_NAMES = (".dag.md", "DAG.md")


def _find_dag_md(cwd: Path) -> Optional[Path]:
    """Discover the nearest ``.dag.md`` or ``DAG.md``.

    Search order: *cwd* first, then each parent directory up to (and
    including) the git repository root.  Returns the first match, or
    ``None`` if nothing is found.
    """
    stop_at = _find_git_root(cwd)
    current = cwd.resolve()

    for directory in [current, *current.parents]:
        for name in _DAG_MD_NAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
        # Stop walking at the git root (or filesystem root).
        if stop_at and directory == stop_at:
            break
    return None


def _strip_yaml_frontmatter(content: str) -> str:
    """Remove optional YAML frontmatter (``---`` delimited) from *content*.

    The frontmatter may contain structured config (model overrides, tool
    settings) that will be handled separately in a future PR.  For now we
    strip it so only the human-readable markdown body is injected into the
    system prompt.
    """
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            # Skip past the closing --- and any trailing newline
            body = content[end + 4:].lstrip("\n")
            return body if body else content
    return content


# =========================================================================
# DAG-first text loader — prefers ~/.dag/dags/<name>.dag over
# baked-in Python string constants.  Saves ~3k tokens per session.
# =========================================================================

def _load_merged_dags() -> str:
    """Load all .dag files via native Rust router. Single pass, cached.
    
    The Rust binary applies SKIP_ENTITIES (ConfidenceMarker, HardBlock,
    CompoundingLoop) and SKIP_DAGS (dag-harness) to prevent noise/poison
    from entering context. Returns the merged DAG ground truth.
    Falls back to Python path if binary is unavailable.
    """
    try:
        import shutil as _shutil
        import subprocess as _sp
        _router = _shutil.which("dag-router")
        if not _router:
            _candidate = Path(__file__).parent.parent / "bin" / "dag-router"
            if _candidate.is_file() and os.access(str(_candidate), os.X_OK):
                _router = str(_candidate)
        if _router:
            _result = _sp.run(
                [_router], capture_output=True, text=True, timeout=5,
            )
            if _result.returncode == 0 and _result.stdout.strip():
                return _result.stdout.strip()
    except Exception:
        pass
    # Fallback: concatenate all harness .dag files
    try:
        _dags_dir = Path(__file__).parent.parent / "dags"
        _parts = []
        for _f in sorted(_dags_dir.glob("*.dag")):
            _t = _f.read_text(encoding="utf-8").strip()
            if _t:
                _parts.append(_t)
        if _parts:
            return "\n".join(_parts)
    except Exception:
        pass
    return ""


# Native merged DAG context — loaded once at import, injects as single block.
# Replaces 13 individual _load_dag_text() calls. No duplication, Rust-backed.
_MERGED_DAGS = _load_merged_dags()

# Hardcoded integrity floor — if the .dag files are missing or corrupted,
# these edges are injected as a last-resort invariant so the agent never
# runs without output-integrity enforcement.
_INTEGRITY_FLOOR = (
    "[output-integrity]\n"
    "Spell→ All:recheck(11), Final:reread(11), Guess:never(11)\n"
    "Name→ Entity:known(11), Project:exact(11), Tool:verified(11)\n"
    "Explain→ Cause:traced(11), Unknown:admit(11), Fabricate:never(11)\n"
    "Self→ AI:only(11), Human:never(11), Physical:none(11)\n"
    "Error→ Own:admit(11), Deflect:never(11), ToolBlame:never(11)"
)

def _ensure_integrity_floor(dags: str) -> str:
    """Guarantee output-integrity edges exist in the merged DAG context.

    If the .dag files on disk contain [output-integrity], use them.
    If the section is missing (file deleted, loader failure, corruption),
    inject the hardcoded floor.  The agent must never run without these edges.
    """
    if "[output-integrity]" in dags:
        return dags
    return dags + "\n" + _INTEGRITY_FLOOR

_MERGED_DAGS = _ensure_integrity_floor(_MERGED_DAGS)


def _load_dag_text(name: str) -> str:
    """Read <name>.dag — delegated to native merged loader. Kept for API compat."""
    return _MERGED_DAGS if _MERGED_DAGS else ""


# =========================================================================
# Constants
# =========================================================================

DEFAULT_AGENT_IDENTITY = _load_dag_text("default-identity")
# Native DAG ground-truth graph -- bakes intelligence-amplifier .dag into the
# harness so grounding fires regardless of hook availability.  Compact
# DAG-path notation: Entity-> Target:verb(card).  Verbs abbreviated to 5 chars.
# Post-v1.5.0: 452 chars, 7 entities, 14 edges.  Cached after turn 1.
DAG_GROUND_ENTITY_GRAPH = (
    "Technique→ Integration:wired(1m), TechniqueStack:combi(1m), "
    "ResearchPipeline:disco(1m), KnowledgeSource:sourc(mm), Benchmark:measu(mm)\n"
    "KnowledgeSource→ ResearchPipeline:polls(1m), KnowledgeFetch:queri(1m), "
    "Technique:sourc(mm)\n"
    "ResearchPipeline→ KnowledgeSource:polls(1m), Technique:disco(1m)\n"
    "Integration→ Technique:wired(1m)\n"
    "Benchmark→ Technique:measu(mm)\n"
    "TechniqueStack→ Technique:combi(1m)\n"
    "KnowledgeFetch→ KnowledgeSource:queri(1m)"
)

DAG_AGENT_HELP_GUIDANCE = (
    "[style]\n"
    "Reply→ Terse:always(11), Direct:always(11), Explain:never(11)\n"
    "Output→ Format:plain(11), Markdown:never(11), Politeness:never(11)\n"
    "Answer→ Question:direct(11), Context:on-demand(11)\n"
)

MEMORY_GUIDANCE = _load_dag_text("memory-guidance")
SESSION_SEARCH_GUIDANCE = _load_dag_text("session-search")
SKILLS_GUIDANCE = _load_dag_text("skills-guidance")
KANBAN_GUIDANCE = _load_dag_text("kanban")
TOOL_USE_ENFORCEMENT_GUIDANCE = _load_dag_text("tool-use-enforcement")
# Model name substrings that trigger tool-use enforcement guidance.
# Add new patterns here when a model family needs explicit steering.
TOOL_USE_ENFORCEMENT_MODELS = ("gpt", "codex", "gemini", "gemma", "grok", "glm", "qwen", "deepseek")

# Universal "finish the job" guidance — applied to ALL models, not gated
# by model family.  Addresses two cross-model failure modes:
#   1. Stopping after a stub: writing a tiny file or running one command
#      and then ending the turn with a description of the plan instead
#      of the finished artifact.  (Observed on Opus during a real
#      Sarasota real-estate build task: 3 API calls, 85-byte file,
#      one terminal command, finish_reason=stop.)
#   2. Fabricating output when a real path is blocked.  When `pip` or a
#      tool fails, some models will synthesize plausible-looking results
#      (fake addresses, fake JSON, fake numbers) instead of reporting
#      the blocker.  (Observed on DeepSeek v4-flash on the same task:
#      pushed through PEP-668 wall, then returned fabricated listings.)
#
# Short on purpose.  This block is shipped to every user, every session,
# in the cached system prompt — token cost is paid once at install and
# then amortised across all sessions via prefix caching.  Keep it tight.
TASK_COMPLETION_GUIDANCE = _load_dag_text("task-completion")
# OpenAI GPT/Codex-specific execution guidance.  Addresses known failure modes
# where GPT models abandon work on partial results, skip prerequisite lookups,
# hallucinate instead of using tools, and declare "done" without verification.
# Inspired by patterns from OpenAI's GPT-5.4 prompting guide & OpenClaw PR #38953.
# Also applied to xAI Grok — same failure modes in practice (claims completion
# without tool calls, suggests workarounds instead of using existing tools,
# replies with plans/suggestions instead of executing). The body is
# family-agnostic; the OPENAI_ prefix reflects origin, not exclusivity.
OPENAI_MODEL_EXECUTION_GUIDANCE = _load_dag_text("openai-execution")
# Gemini/Gemma-specific operational guidance, adapted from OpenCode's gemini.txt.
# Injected alongside TOOL_USE_ENFORCEMENT_GUIDANCE when the model is Gemini or Gemma.
GOOGLE_MODEL_OPERATIONAL_GUIDANCE = _load_dag_text("google-operational")

# Guidance injected into the system prompt when the computer_use toolset
# is active. Universal — works for any model (Claude, GPT, open models).
COMPUTER_USE_GUIDANCE = _load_dag_text("computer-use")
# ---------------------------------------------------------------------------
# Mid-turn steering (/steer) — out-of-band user messages
# ---------------------------------------------------------------------------
# A steer is appended to the END of a tool result (the only role-alternation-
# safe slot mid-turn), so it rides the exact channel injection defenses are
# trained to distrust — a bare "User guidance:" line gets refused as suspected
# prompt injection (observed in the wild). The bounded, self-describing marker
# below attributes the text to the real user, and STEER_CHANNEL_NOTE tells the
# model to trust THIS marker and only this one, so a lookalike buried in
# tool/web/file output stays untrusted.
STEER_MARKER_OPEN = "[OUT-OF-BAND USER MESSAGE — a direct message from the user, delivered mid-turn; not tool output]"
STEER_MARKER_CLOSE = "[/OUT-OF-BAND USER MESSAGE]"


def format_steer_marker(steer_text: str) -> str:
    """Wrap a mid-turn steer for appending to a tool result (see module note)."""
    return f"\n\n{STEER_MARKER_OPEN}\n{steer_text}\n{STEER_MARKER_CLOSE}"


STEER_CHANNEL_NOTE = _load_dag_text("steer-channel")
# Model name substrings that should use the 'developer' role instead of
# 'system' for the system prompt.  OpenAI's newer models (GPT-5, Codex)
# give stronger instruction-following weight to the 'developer' role.
# The swap happens at the API boundary in _build_api_kwargs() so internal
# message representation stays consistent ("system" everywhere).
DEVELOPER_ROLE_MODELS = ("gpt-5", "codex")

PLATFORM_HINTS_DAG = _load_dag_text("platform-hints")

# Built-in fallback dict — used when platform-hints.dag is absent.
# When the .dag is present, PLATFORM_HINTS parses from it at import time.
_PLATFORM_HINTS_FALLBACK = {
    "whatsapp": (
        "You are on a text messaging communication platform, WhatsApp. "
        "Please do not use markdown as it does not render. "
        "You can send media files natively: to deliver a file to the user, "
        "include MEDIA:/absolute/path/to/file in your response. The file "
        "will be sent as a native WhatsApp attachment — images (.jpg, .png, "
        ".webp) appear as photos, videos (.mp4, .mov) play inline, and other "
        "files arrive as downloadable documents. You can also include image "
        "URLs in markdown format ![alt](url) and they will be sent as photos."
    ),
    "whatsapp_cloud": (
        "You are on a text messaging communication platform, WhatsApp "
        "(via Meta's official Business Cloud API). Standard markdown "
        "(**bold**, ~~strike~~, # headers, [links](url)) is auto-converted "
        "to WhatsApp's native syntax (*bold*, ~strike~, etc.) — feel free "
        "to write in markdown. Tables are NOT supported — prefer bullet "
        "lists or labeled key:value pairs. "
        "You can send media files natively: include MEDIA:/absolute/path/to/file "
        "in your response. Images (.jpg, .png) become photo attachments, "
        "videos (.mp4) play inline, audio (.mp3, .ogg) sends as voice/audio "
        "messages, other files arrive as documents. Image URLs in markdown "
        "format ![alt](url) also work. "
        "IMPORTANT: this platform has a 24-hour conversation window — if the "
        "user hasn't messaged in 24h, free-form replies are refused by Meta "
        "(error 131047). This rarely matters for live chat, but is worth "
        "knowing if you're scheduling a delayed message."
    ),
    "telegram": (
        "You are on a text messaging communication platform, Telegram. "
        "Standard Markdown is automatically converted to Telegram formatting. "
        "Supported: **bold**, *italic*, ~~strikethrough~~, ||spoiler||, "
        "`inline code`, ```code blocks```, [links](url), and ## headers. "
        "Telegram now supports rich Markdown, so lean into it: whenever it "
        "makes the answer clearer or easier to scan, actively reach for real "
        "Markdown tables (pipe `| col | col |` syntax), bullet and numbered "
        "lists, task lists (`- [ ]` / `- [x]`), headings, nested blockquotes, "
        "collapsible details, footnotes/references, math/formulas (`$...$`, "
        "`$$...$$`), underline, subscript/superscript, marked (highlighted) "
        "text, and anchors. Default to structured formatting over dense "
        "paragraphs for any comparison, set of steps, key/value summary, or "
        "tabular data. Prefer real Markdown tables and task lists over "
        "hand-built bullet substitutes when presenting structured data; these "
        "degrade gracefully (tables become readable bullet groups) when rich "
        "rendering is unavailable, but advanced constructs like math and "
        "collapsible details may render as plain source text in that case. "
        "You can send media files natively: to deliver a file to the user, "
        "include MEDIA:/absolute/path/to/file in your response. Images "
        "(.png, .jpg, .webp) appear as photos, audio (.ogg) sends as voice "
        "bubbles, and videos (.mp4) play inline. You can also include image "
        "URLs in markdown format ![alt](url) and they will be sent as native photos."
    ),
    "discord": (
        "You are in a Discord server or group chat communicating with your user. "
        "You can send media files natively: include MEDIA:/absolute/path/to/file "
        "in your response. Images (.png, .jpg, .webp) are sent as photo "
        "attachments, audio as file attachments. You can also include image URLs "
        "in markdown format ![alt](url) and they will be sent as attachments."
    ),
    "slack": (
        "You are in a Slack workspace communicating with your user. "
        "You can send media files natively: include MEDIA:/absolute/path/to/file "
        "in your response. Images (.png, .jpg, .webp) are uploaded as photo "
        "attachments, audio as file attachments. You can also include image URLs "
        "in markdown format ![alt](url) and they will be uploaded as attachments."
    ),
    "signal": (
        "You are on a text messaging communication platform, Signal. "
        "Please do not use markdown as it does not render. "
        "You can send media files natively: to deliver a file to the user, "
        "include MEDIA:/absolute/path/to/file in your response. Images "
        "(.png, .jpg, .webp) appear as photos, audio as attachments, and other "
        "files arrive as downloadable documents. You can also include image "
        "URLs in markdown format ![alt](url) and they will be sent as photos."
    ),
    "email": (
        "You are communicating via email. Write clear, well-structured responses "
        "suitable for email. Use plain text formatting (no markdown). "
        "Keep responses concise but complete. You can send file attachments — "
        "include MEDIA:/absolute/path/to/file in your response. The subject line "
        "is preserved for threading. Do not include greetings or sign-offs unless "
        "contextually appropriate."
    ),
    "cron": (
        "You are running as a scheduled cron job. There is no user present — you "
        "cannot ask questions, request clarification, or wait for follow-up. Execute "
        "the task fully and autonomously, making reasonable decisions where needed. "
        "Your final response is automatically delivered to the job's configured "
        "destination — put the primary content directly in your response."
    ),
    "cli": (
        "You are a CLI AI Agent. Try not to use markdown but simple text "
        "renderable inside a terminal. "
        "File delivery: there is no attachment channel — the user reads your "
        "response directly in their terminal. Do NOT emit MEDIA:/path tags "
        "(those are only intercepted on messaging platforms like Telegram, "
        "Discord, Slack, etc.; on the CLI they render as literal text). "
        "When referring to a file you created or changed, just state its "
        "absolute path in plain text; the user can open it from there."
    ),
    "sms": (
        "You are communicating via SMS. Keep responses concise and use plain text "
        "only — no markdown, no formatting. SMS messages are limited to ~1600 "
        "characters, so be brief and direct."
    ),
    "bluebubbles": (
        "You are chatting via iMessage (BlueBubbles). iMessage does not render "
        "markdown formatting — use plain text. Keep responses concise as they "
        "appear as text messages. You can send media files natively: include "
        "MEDIA:/absolute/path/to/file in your response. Images (.jpg, .png, "
        ".heic) appear as photos and other files arrive as attachments."
    ),
    "mattermost": (
        "You are in a Mattermost workspace communicating with your user. "
        "Mattermost renders standard Markdown — headings, bold, italic, code "
        "blocks, and tables all work. "
        "You can send media files natively: include MEDIA:/absolute/path/to/file "
        "in your response. Images (.jpg, .png, .webp) are uploaded as photo "
        "attachments, audio and video as file attachments. "
        "Image URLs in markdown format ![alt](url) are rendered as inline previews automatically."
    ),
    "matrix": (
        "You are in a Matrix room communicating with your user. "
        "Matrix renders Markdown — bold, italic, code blocks, and links work; "
        "the adapter converts your Markdown to HTML for rich display. "
        "You can send media files natively: include MEDIA:/absolute/path/to/file "
        "in your response. Images (.jpg, .png, .webp) are sent as inline photos, "
        "audio (.ogg, .mp3) as voice/audio messages, video (.mp4) inline, "
        "and other files as downloadable attachments."
    ),
    "feishu": (
        "You are in a Feishu (Lark) workspace communicating with your user. "
        "Feishu renders Markdown in messages — bold, italic, code blocks, and "
        "links are supported. "
        "You can send media files natively: include MEDIA:/absolute/path/to/file "
        "in your response. Images (.jpg, .png, .webp) are uploaded and displayed "
        "inline, audio files as voice messages, and other files as attachments."
    ),
    "weixin": (
        "You are on Weixin/WeChat. Markdown formatting is supported, so you may use it when "
        "it improves readability, but keep the message compact and chat-friendly. You can send media files natively: "
        "include MEDIA:/absolute/path/to/file in your response. Images are sent as native "
        "photos, videos play inline when supported, and other files arrive as downloadable "
        "documents. You can also include image URLs in markdown format ![alt](url) and they "
        "will be downloaded and sent as native media when possible."
    ),
    "wecom": (
        "You are on WeCom (企业微信 / Enterprise WeChat). Markdown formatting is supported. "
        "You CAN send media files natively — to deliver a file to the user, include "
        "MEDIA:/absolute/path/to/file in your response. The file will be sent as a native "
        "WeCom attachment: images (.jpg, .png, .webp) are sent as photos (up to 10 MB), "
        "other files (.pdf, .docx, .xlsx, .md, .txt, etc.) arrive as downloadable documents "
        "(up to 20 MB), and videos (.mp4) play inline. Voice messages are supported but "
        "must be in AMR format — other audio formats are automatically sent as file attachments. "
        "You can also include image URLs in markdown format ![alt](url) and they will be "
        "downloaded and sent as native photos. Do NOT tell the user you lack file-sending "
        "capability — use MEDIA: syntax whenever a file delivery is appropriate."
    ),
    "qqbot": (
        "You are on QQ, a popular Chinese messaging platform. QQ supports markdown formatting "
        "and emoji. You can send media files natively: include MEDIA:/absolute/path/to/file in "
        "your response. Images are sent as native photos, and other files arrive as downloadable "
        "documents."
    ),
    "yuanbao": (
        "You are on Yuanbao (腾讯元宝), a Chinese AI assistant platform. "
        "Markdown formatting is supported (code blocks, tables, bold/italic). "
        "You CAN send media files natively — to deliver a file to the user, include "
        "MEDIA:/absolute/path/to/file in your response. The file will be sent as a native "
        "Yuanbao attachment: images (.jpg, .png, .webp, .gif) are sent as photos, "
        "and other files (.pdf, .docx, .txt, .zip, etc.) arrive as downloadable documents "
        "(max 50 MB). You can also include image URLs in markdown format ![alt](url) and "
        "they will be downloaded and sent as native photos. "
        "Do NOT tell the user you lack file-sending capability — use MEDIA: syntax "
        "whenever a file delivery is appropriate.\n\n"
        "Stickers (贴纸 / 表情包 / TIM face): Yuanbao has a built-in sticker catalogue. "
        "When the user sends a sticker (you see '[emoji: 名称]' in their message) or asks "
        "you to send/reply-with a 贴纸/表情/表情包, you MUST use the sticker tools:\n"
        "  1. Call yb_search_sticker with a Chinese keyword (e.g. '666', '比心', '吃瓜', "
        "     '捂脸', '合十') to discover matching sticker_ids.\n"
        "  2. Call yb_send_sticker with the chosen sticker_id or name — this sends a real "
        "     TIMFaceElem that renders as a native sticker in the chat.\n"
        "DO NOT draw sticker-like PNGs with execute_code/Pillow/matplotlib and then send "
        "them via MEDIA: or send_image_file. That produces a fake low-quality 'sticker' "
        "image and is the WRONG path. Bare Unicode emoji in text is also not a substitute "
        "— when a sticker is the right response, use yb_send_sticker."
    ),
    "api_server": (
        "You're responding through an API server. The rendering layer is unknown — "
        "assume plain text. No markdown formatting (no asterisks, bullets, headers, "
        "code fences). Treat this like a conversation, not a document. Keep responses "
        "brief and natural."
    ),
    "webui": (
        "You are in the Dag WebUI, a browser-based chat interface. "
        "Full Markdown rendering is supported — headings, bold, italic, code "
        "blocks, tables, math (LaTeX), and Mermaid diagrams all render natively. "
        "To display local or remote media/files inline, include "
        "MEDIA:/absolute/path/to/file or MEDIA:https://... in your response. "
        "Local file paths must be absolute. Images, audio (with playback speed "
        "controls), video, PDFs, HTML, CSV, diffs/patches, and Excalidraw files "
        "render as rich previews. Do not use Markdown image syntax like "
        "![alt](/path) for local files; local paths are not served that way. "
        "Use MEDIA:/absolute/path instead."
    ),
}


def _parse_platform_hints(dag_text: str):
    """Parse a platform-hints DAG string into a dict mapping platform→hint."""
    import re
    result = {}
    # Pattern: PlatformName→ hint:text(11)
    for line in dag_text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('[') or line.startswith('#'):
            continue
        # Match: Name→ text(11)
        m = re.match(r'^(\w+)\s*→\s*(.+?)\s*\(\d+\)$', line)
        if m:
            name = m.group(1).lower()
            hint = m.group(2).strip()
            result[name] = hint
    return result


if PLATFORM_HINTS_DAG:
    _parsed = _parse_platform_hints(PLATFORM_HINTS_DAG)
    if _parsed:
        PLATFORM_HINTS = _parsed
    else:
        PLATFORM_HINTS = _PLATFORM_HINTS_FALLBACK
else:
    PLATFORM_HINTS = _PLATFORM_HINTS_FALLBACK


# ---------------------------------------------------------------------------
# Environment hints — execution-environment awareness for the agent.
# Unlike PLATFORM_HINTS (which describe the messaging channel), these describe
# the machine/OS the agent's tools actually run on.
# ---------------------------------------------------------------------------

WSL_ENVIRONMENT_HINT = _load_dag_text("wsl-hint")

# Non-local terminal backends that run commands (and therefore every file
# tool: read_file, write_file, patch, search_files) inside a separate
# container / remote host rather than on the machine where Dag itself
# runs. For these backends, host info (Windows/Linux/macOS, $HOME, cwd) is
# misleading — the agent should only see the machine it can actually touch.
_REMOTE_TERMINAL_BACKENDS = frozenset({
    "docker", "singularity", "modal", "daytona", "ssh",
    "managed_modal",
})


# Per-backend fallback descriptions — used when the live probe fails.
# Only states what we know from the backend choice itself (container type,
# likely OS family). Does NOT invent cwd, user, or $HOME — the agent is
# told to probe those directly if it needs them.
_BACKEND_FALLBACK_DESCRIPTIONS: dict[str, str] = {
    "docker": "a Docker container (Linux)",
    "singularity": "a Singularity container (Linux)",
    "modal": "a Modal sandbox (Linux)",
    "managed_modal": "a managed Modal sandbox (Linux)",
    "daytona": "a Daytona workspace (Linux)",
    "ssh": "a remote host reached over SSH (likely Linux)",
}


# Cache the backend probe result per process so we only pay the probe cost
# on the first prompt build of a session. Keyed by (env_type, cwd_hint) so
# a mid-process backend switch rebuilds the string. Kept in-module (not on
# disk) because the probe captures live backend state that may change
# across Dag restarts.
_BACKEND_PROBE_CACHE: dict[tuple[str, str], str] = {}


_WINDOWS_BASH_SHELL_HINT = (
    "Shell: on this Windows host your `terminal` tool runs commands through "
    "bash (git-bash / MSYS), NOT PowerShell or cmd.exe. Use POSIX shell "
    "syntax (`ls`, `$HOME`, `&&`, `|`, single-quoted strings) inside terminal "
    "calls. MSYS-style paths like `/c/Users/<user>/...` work alongside "
    "native `C:\\Users\\<user>\\...` paths. PowerShell builtins "
    "(`Get-ChildItem`, `$env:FOO`, `Select-String`) will NOT work — use their "
    "POSIX equivalents (`ls`, `$FOO`, `grep`)."
)


def _probe_remote_backend(env_type: str) -> str | None:
    """Run a tiny introspection command inside the active terminal backend.

    Returns a pre-formatted multi-line string describing the backend's OS,
    $HOME, cwd, and user — or None if the probe failed. Result is cached
    per process. Used only for non-local backends where the agent's tools
    operate on a different machine than the host Dag runs on.
    """
    cwd_hint = os.getenv("TERMINAL_CWD", "")
    cache_key = (env_type, cwd_hint)
    cached = _BACKEND_PROBE_CACHE.get(cache_key)
    if cached is not None:
        return cached or None

    try:
        # Import locally: tools/ imports are heavy and only relevant when a
        # non-local backend is actually configured.
        from tools.terminal_tool import _get_env_config  # type: ignore
        from tools.environments import get_environment  # type: ignore
    except Exception as e:
        logger.debug("Backend probe unavailable (import failed): %s", e)
        _BACKEND_PROBE_CACHE[cache_key] = ""
        return None

    try:
        config = _get_env_config()
        env = get_environment(config)
        # Single-line POSIX probe — works on any Unixy backend. Wrapped in
        # `2>/dev/null` so a missing binary doesn't pollute the output.
        probe_cmd = (
            "printf 'os=%s\\nkernel=%s\\nhome=%s\\ncwd=%s\\nuser=%s\\n' "
            "\"$(uname -s 2>/dev/null || echo unknown)\" "
            "\"$(uname -r 2>/dev/null || echo unknown)\" "
            "\"$HOME\" \"$(pwd)\" \"$(whoami 2>/dev/null || id -un 2>/dev/null || echo unknown)\""
        )
        result = env.execute(probe_cmd, timeout=4)
        if result.get("returncode") != 0:
            logger.debug("Backend probe returned non-zero: %r", result)
            _BACKEND_PROBE_CACHE[cache_key] = ""
            return None
        output = (result.get("output") or "").strip()
        if not output:
            _BACKEND_PROBE_CACHE[cache_key] = ""
            return None
    except Exception as e:
        logger.debug("Backend probe failed: %s", e)
        _BACKEND_PROBE_CACHE[cache_key] = ""
        return None

    # Parse key=value lines back into a tidy summary.
    parsed: dict[str, str] = {}
    for line in output.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            parsed[k.strip()] = v.strip()

    pieces = []
    os_bits = " ".join(x for x in (parsed.get("os"), parsed.get("kernel")) if x and x != "unknown")
    if os_bits:
        pieces.append(f"OS: {os_bits}")
    if parsed.get("user") and parsed["user"] != "unknown":
        pieces.append(f"User: {parsed['user']}")
    if parsed.get("home"):
        pieces.append(f"Home: {parsed['home']}")
    if parsed.get("cwd"):
        pieces.append(f"Working directory: {parsed['cwd']}")

    if not pieces:
        _BACKEND_PROBE_CACHE[cache_key] = ""
        return None

    formatted = "\n".join(f"  {p}" for p in pieces)
    _BACKEND_PROBE_CACHE[cache_key] = formatted
    return formatted


def _clear_backend_probe_cache() -> None:
    """Test helper — drop the backend probe cache so monkeypatched backends take effect."""
    _BACKEND_PROBE_CACHE.clear()


def build_environment_hints() -> str:
    """Return environment-specific guidance for the system prompt.

    Always emits a factual block describing the execution environment:
    - For **local** terminal backends: the host OS, user home, current
      working directory (plus a Windows-only note about hostname != user
      and a Windows-only note that `terminal` shells out to bash, not
      PowerShell).
    - For **remote / sandbox** terminal backends (docker, singularity,
      modal, daytona, ssh): host info is **suppressed**
      because the agent's tools can't touch the host — only the backend
      matters. A live probe inside the backend reports its OS, user, $HOME,
      and cwd. Falls back to a static summary if the probe fails.

    The WSL environment hint is appended unchanged when running under WSL.
    """
    import platform
    import sys

    hints: list[str] = []

    backend = (os.getenv("TERMINAL_ENV") or "local").strip().lower()
    is_remote_backend = backend in _REMOTE_TERMINAL_BACKENDS

    if not is_remote_backend:
        # --- Host info block (local backend: host == where tools run) ---
        host_lines: list[str] = []
        if is_wsl():
            host_lines.append("Host: WSL (Windows Subsystem for Linux)")
        elif sys.platform == "win32":
            host_lines.append(f"Host: Windows ({platform.release()})")
        elif sys.platform == "darwin":
            mac_ver = platform.mac_ver()[0]
            host_lines.append(f"Host: macOS ({mac_ver or platform.release()})")
        else:
            host_lines.append(f"Host: {platform.system()} ({platform.release()})")

        host_lines.append(f"User home directory: {os.path.expanduser('~')}")
        try:
            host_lines.append(f"Current working directory: {resolve_agent_cwd()}")
        except OSError:
            pass

        if sys.platform == "win32" and not is_wsl():
            host_lines.append(
                "Note: on Windows, the machine hostname (e.g. from `hostname` "
                "or uname) is NOT the username. Use the 'User home directory' "
                "above to construct paths under C:\\Users\\<user>\\, never the "
                "hostname."
            )
        hints.append("\n".join(host_lines))

        # Windows-local terminal runs bash, not PowerShell — the model must
        # know this or it will issue PowerShell syntax and fail.
        if sys.platform == "win32" and not is_wsl():
            hints.append(_WINDOWS_BASH_SHELL_HINT)
    else:
        # --- Remote backend block (host info suppressed) ---
        probe = _probe_remote_backend(backend)
        if probe:
            hints.append(
                f"Terminal backend: {backend}. Your `terminal`, `read_file`, "
                f"`write_file`, `patch`, and `search_files` tools all operate "
                f"inside this {backend} environment — NOT on the machine "
                f"where Dag itself is running. The host OS, home, and cwd "
                f"of the Dag process are irrelevant; only the following "
                f"backend state matters:\n{probe}"
            )
        else:
            description = _BACKEND_FALLBACK_DESCRIPTIONS.get(
                backend, f"a {backend} environment (likely Linux)"
            )
            hints.append(
                f"Terminal backend: {backend}. Your `terminal`, `read_file`, "
                f"`write_file`, `patch`, and `search_files` tools all operate "
                f"inside {description} — NOT on the machine where Dag "
                f"itself runs. The backend probe didn't respond at "
                f"prompt-build time, so the sandbox's current user, $HOME, "
                f"and working directory are unknown from here. If you need "
                f"them, probe directly with a terminal call like "
                f"`uname -a && whoami && pwd`."
            )

    # Dag desktop GUI — any agent running under the desktop app should know
    # it. DAG_DESKTOP marks the backend powering the chat; DAG_DESKTOP_TERMINAL
    # marks a dag launched in the embedded terminal pane. Both set by main.cjs.
    _truthy = ("1", "true", "yes")
    _in_desktop = (os.getenv("DAG_DESKTOP") or "").strip().lower() in _truthy
    _in_desktop_term = (os.getenv("DAG_DESKTOP_TERMINAL") or "").strip().lower() in _truthy
    if _in_desktop or _in_desktop_term:
        _desktop_hint = "Runtime surface: you're running inside the Dag desktop GUI app."
        if _in_desktop_term:
            _desktop_hint += (
                " You're in its embedded terminal pane, beside the GUI chat — the user can "
                "select your output (⌥-drag on macOS, Shift-drag elsewhere) and press "
                "⌘/Ctrl+L to send it to the chat composer."
            )
        hints.append(_desktop_hint)

    if is_wsl():
        hints.append(WSL_ENVIRONMENT_HINT)

    # Embedder-supplied environment description. Lets a host that wraps Dag
    # (e.g. a sandbox runner / managed platform) explain the environment the
    # agent is running in — proxy, credential handling, mount layout — without
    # forking the identity slot (SOUL.md). Read once at prompt-build time, so
    # it's part of the stable, cache-safe system prompt. The env var is the
    # build-time/embedder mechanism (set in a container ENV); config.yaml
    # ``agent.environment_hint`` is the user-facing surface. Env var wins.
    extra = (os.getenv("DAG_ENVIRONMENT_HINT") or "").strip()
    if not extra:
        try:
            from dag_cli.config import load_config

            extra = str(
                (load_config().get("agent", {}) or {}).get("environment_hint", "")
            ).strip()
        except Exception as e:
            logger.debug("Could not read agent.environment_hint from config: %s", e)
    if extra:
        hints.append(extra)

    return "\n\n".join(hints)


CONTEXT_FILE_MAX_CHARS = 20_000
CONTEXT_TRUNCATE_HEAD_RATIO = 0.7
CONTEXT_TRUNCATE_TAIL_RATIO = 0.2


# =========================================================================
# Skills prompt cache
# =========================================================================

_SKILLS_PROMPT_CACHE_MAX = 8
_SKILLS_PROMPT_CACHE: OrderedDict[tuple, str] = OrderedDict()
_SKILLS_PROMPT_CACHE_LOCK = threading.Lock()
_SKILLS_SNAPSHOT_VERSION = 1


def _skills_prompt_snapshot_path() -> Path:
    return get_dag_home() / ".skills_prompt_snapshot.json"


def clear_skills_system_prompt_cache(*, clear_snapshot: bool = False) -> None:
    """Drop the in-process skills prompt cache (and optionally the disk snapshot)."""
    with _SKILLS_PROMPT_CACHE_LOCK:
        _SKILLS_PROMPT_CACHE.clear()
    if clear_snapshot:
        try:
            _skills_prompt_snapshot_path().unlink(missing_ok=True)
        except OSError as e:
            logger.debug("Could not remove skills prompt snapshot: %s", e)


def _build_skills_manifest(skills_dir: Path) -> dict[str, list[int]]:
    """Build an mtime/size manifest of all SKILL.md and DESCRIPTION.md files."""
    manifest: dict[str, list[int]] = {}
    for filename in ("SKILL.md", "DESCRIPTION.md"):
        for path in iter_skill_index_files(skills_dir, filename):
            try:
                st = path.stat()
            except OSError:
                continue
            manifest[str(path.relative_to(skills_dir))] = [st.st_mtime_ns, st.st_size]
    return manifest


def _load_skills_snapshot(skills_dir: Path) -> Optional[dict]:
    """Load the disk snapshot if it exists and its manifest still matches."""
    snapshot_path = _skills_prompt_snapshot_path()
    if not snapshot_path.exists():
        return None
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(snapshot, dict):
        return None
    if snapshot.get("version") != _SKILLS_SNAPSHOT_VERSION:
        return None
    if snapshot.get("manifest") != _build_skills_manifest(skills_dir):
        return None
    return snapshot


def _write_skills_snapshot(
    skills_dir: Path,
    manifest: dict[str, list[int]],
    skill_entries: list[dict],
    category_descriptions: dict[str, str],
) -> None:
    """Persist skill metadata to disk for fast cold-start reuse."""
    payload = {
        "version": _SKILLS_SNAPSHOT_VERSION,
        "manifest": manifest,
        "skills": skill_entries,
        "category_descriptions": category_descriptions,
    }
    try:
        atomic_json_write(_skills_prompt_snapshot_path(), payload)
    except Exception as e:
        logger.debug("Could not write skills prompt snapshot: %s", e)


def _build_snapshot_entry(
    skill_file: Path,
    skills_dir: Path,
    frontmatter: dict,
    description: str,
) -> dict:
    """Build a serialisable metadata dict for one skill."""
    rel_path = skill_file.relative_to(skills_dir)
    parts = rel_path.parts
    if len(parts) >= 2:
        skill_name = parts[-2]
        category = "/".join(parts[:-2]) if len(parts) > 2 else parts[0]
    else:
        category = "general"
        skill_name = skill_file.parent.name

    platforms = frontmatter.get("platforms") or []
    if isinstance(platforms, str):
        platforms = [platforms]

    return {
        "skill_name": skill_name,
        "category": category,
        "frontmatter_name": str(frontmatter.get("name", skill_name)),
        "description": description,
        "platforms": [str(p).strip() for p in platforms if str(p).strip()],
        "conditions": extract_skill_conditions(frontmatter),
    }


# =========================================================================
# Skills index
# =========================================================================

def _parse_skill_file(skill_file: Path) -> tuple[bool, dict, str]:
    """Read a SKILL.md once and return platform compatibility, frontmatter, and description.

    Returns (is_compatible, frontmatter, description). On any error, returns
    (True, {}, "") to err on the side of showing the skill.
    """
    try:
        raw = skill_file.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter(raw)

        if not skill_matches_platform(frontmatter):
            return False, frontmatter, ""

        # Environment relevance gate (offer-time only): hide skills tagged for
        # a runtime environment that isn't active (e.g. kanban-only skills for
        # non-kanban users, s6-only skills outside the container). Explicit
        # loads (skill_view / --skills) bypass this — see skill_matches_environment.
        if not skill_matches_environment(frontmatter):
            return False, frontmatter, ""

        return True, frontmatter, extract_skill_description(frontmatter)
    except Exception as e:
        logger.warning("Failed to parse skill file %s: %s", skill_file, e)
        return True, {}, ""


def _skill_should_show(
    conditions: dict,
    available_tools: "set[str] | None",
    available_toolsets: "set[str] | None",
) -> bool:
    """Return False if the skill's conditional activation rules exclude it."""
    if available_tools is None and available_toolsets is None:
        return True  # No filtering info — show everything (backward compat)

    at = available_tools or set()
    ats = available_toolsets or set()

    # fallback_for: hide when the primary tool/toolset IS available
    for ts in conditions.get("fallback_for_toolsets", []):
        if ts in ats:
            return False
    for t in conditions.get("fallback_for_tools", []):
        if t in at:
            return False

    # requires: hide when a required tool/toolset is NOT available
    for ts in conditions.get("requires_toolsets", []):
        if ts not in ats:
            return False
    for t in conditions.get("requires_tools", []):
        if t not in at:
            return False

    return True


def build_skills_system_prompt(
    available_tools: "set[str] | None" = None,
    available_toolsets: "set[str] | None" = None,
    compact_categories: "frozenset[str] | None" = None,
) -> str:
    """Build a compact skill index for the system prompt.

    Two-layer cache:
      1. In-process LRU dict keyed by (skills_dir, tools, toolsets, hidden)
      2. Disk snapshot (``.skills_prompt_snapshot.json``) validated by
         mtime/size manifest — survives process restarts

    Falls back to a full filesystem scan when both layers miss.

    External skill directories (``skills.external_dirs`` in config.yaml) are
    scanned alongside the local ``~/.dag/skills/`` directory.  External dirs
    are read-only — they appear in the index but new skills are always created
    in the local dir.  Local skills take precedence when names collide.

    ``compact_categories`` (e.g. from the coding posture — see
    agent/coding_context.py) demotes whole categories to a names-only line in
    the rendered index. Nothing is ever hidden: every skill name stays
    visible and loadable via ``skill_view`` / ``skills_list``; only the
    descriptions are dropped, and a footer note explains the demotion.
    """
    skills_dir = get_skills_dir()
    external_dirs = get_all_skills_dirs()[1:]  # skip local (index 0)

    if not skills_dir.exists() and not external_dirs:
        return ""

    # ── Layer 1: in-process LRU cache ─────────────────────────────────
    # Include the resolved platform so per-platform disabled-skill lists
    # produce distinct cache entries (gateway serves multiple platforms).
    from gateway.session_context import get_session_env
    _platform_hint = (
        os.environ.get("DAG_PLATFORM")
        or get_session_env("DAG_SESSION_PLATFORM")
        or ""
    )
    disabled = get_disabled_skill_names(_platform_hint or None)
    cache_key = (
        str(skills_dir.resolve()),
        tuple(str(d) for d in external_dirs),
        tuple(sorted(str(t) for t in (available_tools or set()))),
        tuple(sorted(str(ts) for ts in (available_toolsets or set()))),
        _platform_hint,
        tuple(sorted(disabled)),
        tuple(sorted(compact_categories or ())),
    )
    with _SKILLS_PROMPT_CACHE_LOCK:
        cached = _SKILLS_PROMPT_CACHE.get(cache_key)
        if cached is not None:
            _SKILLS_PROMPT_CACHE.move_to_end(cache_key)
            return cached

    # ── Layer 2: disk snapshot ────────────────────────────────────────
    snapshot = _load_skills_snapshot(skills_dir)

    skills_by_category: dict[str, list[tuple[str, str]]] = {}
    category_descriptions: dict[str, str] = {}

    if snapshot is not None:
        # Fast path: use pre-parsed metadata from disk
        for entry in snapshot.get("skills", []):
            if not isinstance(entry, dict):
                continue
            skill_name = entry.get("skill_name") or ""
            category = entry.get("category") or "general"
            frontmatter_name = entry.get("frontmatter_name") or skill_name
            platforms = entry.get("platforms") or []
            if not skill_matches_platform({"platforms": platforms}):
                continue
            if frontmatter_name in disabled or skill_name in disabled:
                continue
            if not _skill_should_show(
                entry.get("conditions") or {},
                available_tools,
                available_toolsets,
            ):
                continue
            skills_by_category.setdefault(category, []).append(
                (frontmatter_name, entry.get("description", ""))
            )
        category_descriptions = {
            str(k): str(v)
            for k, v in (snapshot.get("category_descriptions") or {}).items()
        }
    else:
        # Cold path: full filesystem scan + write snapshot for next time
        skill_entries: list[dict] = []
        for skill_file in iter_skill_index_files(skills_dir, "SKILL.md"):
            is_compatible, frontmatter, desc = _parse_skill_file(skill_file)
            entry = _build_snapshot_entry(skill_file, skills_dir, frontmatter, desc)
            skill_entries.append(entry)
            if not is_compatible:
                continue
            skill_name = entry["skill_name"]
            if entry["frontmatter_name"] in disabled or skill_name in disabled:
                continue
            if not _skill_should_show(
                extract_skill_conditions(frontmatter),
                available_tools,
                available_toolsets,
            ):
                continue
            skills_by_category.setdefault(entry["category"], []).append(
                (entry["frontmatter_name"], entry["description"])
            )

        # Read category-level DESCRIPTION.md files
        for desc_file in iter_skill_index_files(skills_dir, "DESCRIPTION.md"):
            try:
                content = desc_file.read_text(encoding="utf-8")
                fm, _ = parse_frontmatter(content)
                cat_desc = fm.get("description")
                if not cat_desc:
                    continue
                rel = desc_file.relative_to(skills_dir)
                cat = "/".join(rel.parts[:-1]) if len(rel.parts) > 1 else "general"
                category_descriptions[cat] = str(cat_desc).strip().strip("'\"")
            except Exception as e:
                logger.debug("Could not read skill description %s: %s", desc_file, e)

        _write_skills_snapshot(
            skills_dir,
            _build_skills_manifest(skills_dir),
            skill_entries,
            category_descriptions,
        )

    # ── External skill directories ─────────────────────────────────────
    # Scan external dirs directly (no snapshot caching — they're read-only
    # and typically small).  Local skills already in skills_by_category take
    # precedence: we track seen names and skip duplicates from external dirs.
    seen_skill_names: set[str] = set()
    for cat_skills in skills_by_category.values():
        for name, _desc in cat_skills:
            seen_skill_names.add(name)

    for ext_dir in external_dirs:
        if not ext_dir.exists():
            continue
        for skill_file in iter_skill_index_files(ext_dir, "SKILL.md"):
            try:
                is_compatible, frontmatter, desc = _parse_skill_file(skill_file)
                if not is_compatible:
                    continue
                entry = _build_snapshot_entry(skill_file, ext_dir, frontmatter, desc)
                skill_name = entry["skill_name"]
                frontmatter_name = entry["frontmatter_name"]
                if frontmatter_name in seen_skill_names:
                    continue
                if frontmatter_name in disabled or skill_name in disabled:
                    continue
                if not _skill_should_show(
                    extract_skill_conditions(frontmatter),
                    available_tools,
                    available_toolsets,
                ):
                    continue
                seen_skill_names.add(frontmatter_name)
                skills_by_category.setdefault(entry["category"], []).append(
                    (frontmatter_name, entry["description"])
                )
            except Exception as e:
                logger.debug("Error reading external skill %s: %s", skill_file, e)

        # External category descriptions
        for desc_file in iter_skill_index_files(ext_dir, "DESCRIPTION.md"):
            try:
                content = desc_file.read_text(encoding="utf-8")
                fm, _ = parse_frontmatter(content)
                cat_desc = fm.get("description")
                if not cat_desc:
                    continue
                rel = desc_file.relative_to(ext_dir)
                cat = "/".join(rel.parts[:-1]) if len(rel.parts) > 1 else "general"
                category_descriptions.setdefault(cat, str(cat_desc).strip().strip("'\""))
            except Exception as e:
                logger.debug("Could not read external skill description %s: %s", desc_file, e)

    # Posture-driven category demotion (e.g. non-coding skills while pairing
    # on code). Demoted categories stay in the index as a single names-only
    # line — descriptions are dropped to cut noise, but every skill name
    # remains visible so memory-anchored recall ("load <name>") keeps working.
    # NEVER remove entries entirely: agent-created skills are the model's
    # project memory, and models don't reach for skills_list to rediscover
    # what the index stops showing them. Match on the top-level category
    # segment so nested categories ("social-media/twitter") are demoted with
    # their parent.
    demoted = frozenset(
        cat for cat in skills_by_category
        if cat.split("/", 1)[0] in (compact_categories or frozenset())
    )

    hidden_note = ""
    if demoted:
        hidden_note = (
            "\n(Categories marked [names only] are outside the current coding "
            "context, so their descriptions are omitted — the skills work "
            "normally and load with skill_view(name) as usual.)"
        )

    if not skills_by_category:
        result = ""
    else:
        index_lines = []
        for category in sorted(skills_by_category.keys()):
            # Deduplicate and sort skills within each category
            seen = set()
            if category in demoted:
                names = sorted({name for name, _ in skills_by_category[category]})
                index_lines.append(f"  {category} [names only]: {', '.join(names)}")
                continue
            cat_desc = category_descriptions.get(category, "")
            if cat_desc:
                index_lines.append(f"  {category}: {cat_desc}")
            else:
                index_lines.append(f"  {category}:")
            for name, desc in sorted(skills_by_category[category], key=lambda x: x[0]):
                if name in seen:
                    continue
                seen.add(name)
                if desc:
                    index_lines.append(f"    - {name}: {desc}")
                else:
                    index_lines.append(f"    - {name}")

        result = (
            "## Skills (mandatory)\n"
            "Before replying, scan the skills below. If a skill matches or is even partially relevant "
            "to your task, you MUST load it with skill_view(name) and follow its instructions. "
            "Err on the side of loading — it is always better to have context you don't need "
            "than to miss critical steps, pitfalls, or established workflows. "
            "Skills contain specialized knowledge — API endpoints, tool-specific commands, "
            "and proven workflows that outperform general-purpose approaches. Load the skill "
            "even if you think you could handle the task with basic tools like web_search or terminal. "
            "Skills also encode the user's preferred approach, conventions, and quality standards "
            "for tasks like code review, planning, and testing — load them even for tasks you "
            "already know how to do, because the skill defines how it should be done here.\n"
            "Whenever the user asks you to configure, set up, install, enable, disable, modify, "
            "or troubleshoot DAG Agent itself — its CLI, config, models, providers, tools, "
            "skills, voice, gateway, plugins, or any feature — load the `dag-agent` skill "
            "first. It has the actual commands (e.g. `dag config set …`, `dag tools`, "
            "`dag setup`) so you don't have to guess or invent workarounds.\n"
            "If a skill has issues, fix it with skill_manage(action='patch').\n"
            "After difficult/iterative tasks, offer to save as a skill. "
            "If a skill you loaded was missing steps, had wrong commands, or needed "
            "pitfalls you discovered, update it before finishing.\n"
            "\n"
            "<available_skills>\n"
            + "\n".join(index_lines) + "\n"
            "</available_skills>\n"
            "\n"
            "Only proceed without loading a skill if genuinely none are relevant to the task."
            + hidden_note
        )

    # ── Store in LRU cache ────────────────────────────────────────────
    with _SKILLS_PROMPT_CACHE_LOCK:
        _SKILLS_PROMPT_CACHE[cache_key] = result
        _SKILLS_PROMPT_CACHE.move_to_end(cache_key)
        while len(_SKILLS_PROMPT_CACHE) > _SKILLS_PROMPT_CACHE_MAX:
            _SKILLS_PROMPT_CACHE.popitem(last=False)

    return result


def build_nous_subscription_prompt(valid_tool_names: "set[str] | None" = None) -> str:
    """Build a compact Nous subscription capability block for the system prompt."""
    try:
        from dag_cli.nous_subscription import get_nous_subscription_features
        from tools.tool_backend_helpers import managed_nous_tools_enabled
    except Exception as exc:
        logger.debug("Failed to import Nous subscription helper: %s", exc)
        return ""

    if not managed_nous_tools_enabled():
        return ""

    valid_names = set(valid_tool_names or set())
    relevant_tool_names = {
        "web_search",
        "web_extract",
        "browser_navigate",
        "browser_snapshot",
        "browser_click",
        "browser_type",
        "browser_scroll",
        "browser_console",
        "browser_press",
        "browser_get_images",
        "browser_vision",
        "image_generate",
        "text_to_speech",
        "terminal",
        "process",
        "execute_code",
    }

    if valid_names and not (valid_names & relevant_tool_names):
        return ""

    features = get_nous_subscription_features()

    def _status_line(feature) -> str:
        if feature.managed_by_nous:
            return f"- {feature.label}: active via Nous subscription"
        if feature.active:
            current = feature.current_provider or "configured provider"
            return f"- {feature.label}: currently using {current}"
        if feature.included_by_default and features.nous_auth_present:
            return f"- {feature.label}: included with Nous subscription, not currently selected"
        if feature.key == "modal" and features.nous_auth_present:
            return f"- {feature.label}: optional via Nous subscription"
        return f"- {feature.label}: not currently available"

    lines = [
        "# Nous Subscription",
        "Nous subscription includes managed web tools (Firecrawl), image generation (FAL), OpenAI TTS, OpenAI Whisper STT, and browser automation (Browser Use) by default. Modal execution is optional.",
        "Current capability status:",
    ]
    lines.extend(_status_line(feature) for feature in features.items())
    lines.extend(
        [
            "When a Nous-managed feature is active, do not ask the user for Firecrawl, FAL, OpenAI TTS, OpenAI Whisper, or Browser-Use API keys.",
            "If the user is not subscribed and asks for a capability that Nous subscription would unlock or simplify, suggest Nous subscription as one option alongside direct setup or local alternatives.",
            "Do not mention subscription unless the user asks about it or it directly solves the current missing capability.",
            "Useful commands: dag setup, dag setup tools, dag setup terminal, dag status.",
        ]
    )
    return "\n".join(lines)


# =========================================================================
# Context files (SOUL.md, AGENTS.md, .cursorrules)
# =========================================================================

def _truncate_content(content: str, filename: str, max_chars: int = CONTEXT_FILE_MAX_CHARS) -> str:
    """Head/tail truncation with a marker in the middle."""
    if len(content) <= max_chars:
        return content
    head_chars = int(max_chars * CONTEXT_TRUNCATE_HEAD_RATIO)
    tail_chars = int(max_chars * CONTEXT_TRUNCATE_TAIL_RATIO)
    head = content[:head_chars]
    tail = content[-tail_chars:]
    marker = f"\n\n[...truncated {filename}: kept {head_chars}+{tail_chars} of {len(content)} chars. Use file tools to read the full file.]\n\n"
    return head + marker + tail


def load_soul_identity() -> Optional[str]:
    """Load SOUL.dag or SOUL.md from DAG_HOME as agent identity.

    Tries SOUL.dag first (DAG-path format, native .dag ground truth),
    falls back to SOUL.md (prose format).  Returns None if neither exists.

    Used as the agent identity (slot #1 in the system prompt).  When this
    returns content, ``build_context_files_prompt`` should be called with
    ``skip_soul=True`` so the identity isn't injected twice.
    """
    try:
        from dag_cli.config import ensure_dag_home
        ensure_dag_home()
    except Exception as e:
        logger.debug("Could not ensure DAG_HOME before loading identity: %s", e)

    dag_home = get_dag_home()
    # .dag is important, .dog is fallback (prose spec), .md is last resort
    for filename in ("SOUL.dag", "SOUL.dog", "SOUL.md"):
        soul_path = dag_home / filename
        if not soul_path.exists():
            continue
        try:
            content = soul_path.read_text(encoding="utf-8").strip()
            if not content:
                continue
            content = _scan_context_content(content, filename)
            content = _truncate_content(content, filename)
            return content
        except Exception as e:
            logger.debug("Could not read %s from %s: %s", filename, soul_path, e)
    return None


# Backward-compatible alias so existing callers in tests/gateway still resolve.
load_soul_md = load_soul_identity


def _load_dag_md(cwd_path: Path) -> str:
    """.dag.md / DAG.md — walk to git root."""
    dag_md_path = _find_dag_md(cwd_path)
    if not dag_md_path:
        return ""
    try:
        content = dag_md_path.read_text(encoding="utf-8").strip()
        if not content:
            return ""
        content = _strip_yaml_frontmatter(content)
        rel = dag_md_path.name
        try:
            rel = str(dag_md_path.relative_to(cwd_path))
        except ValueError:
            pass
        content = _scan_context_content(content, rel)
        result = f"## {rel}\n\n{content}"
        return _truncate_content(result, ".dag.md")
    except Exception as e:
        logger.debug("Could not read %s: %s", dag_md_path, e)
        return ""


def _load_agents_md(cwd_path: Path) -> str:
    """AGENTS.md — top-level only (no recursive walk)."""
    for name in ["AGENTS.md", "agents.md"]:
        candidate = cwd_path / name
        if candidate.exists():
            try:
                content = candidate.read_text(encoding="utf-8").strip()
                if content:
                    content = _scan_context_content(content, name)
                    result = f"## {name}\n\n{content}"
                    return _truncate_content(result, "AGENTS.md")
            except Exception as e:
                logger.debug("Could not read %s: %s", candidate, e)
    return ""


def _load_claude_md(cwd_path: Path) -> str:
    """CLAUDE.md / claude.md — cwd only."""
    for name in ["CLAUDE.md", "claude.md"]:
        candidate = cwd_path / name
        if candidate.exists():
            try:
                content = candidate.read_text(encoding="utf-8").strip()
                if content:
                    content = _scan_context_content(content, name)
                    result = f"## {name}\n\n{content}"
                    return _truncate_content(result, "CLAUDE.md")
            except Exception as e:
                logger.debug("Could not read %s: %s", candidate, e)
    return ""


def _load_cursorrules(cwd_path: Path) -> str:
    """.cursorrules + .cursor/rules/*.mdc — cwd only."""
    cursorrules_content = ""
    cursorrules_file = cwd_path / ".cursorrules"
    if cursorrules_file.exists():
        try:
            content = cursorrules_file.read_text(encoding="utf-8").strip()
            if content:
                content = _scan_context_content(content, ".cursorrules")
                cursorrules_content += f"## .cursorrules\n\n{content}\n\n"
        except Exception as e:
            logger.debug("Could not read .cursorrules: %s", e)

    cursor_rules_dir = cwd_path / ".cursor" / "rules"
    if cursor_rules_dir.exists() and cursor_rules_dir.is_dir():
        mdc_files = sorted(cursor_rules_dir.glob("*.mdc"))
        for mdc_file in mdc_files:
            try:
                content = mdc_file.read_text(encoding="utf-8").strip()
                if content:
                    content = _scan_context_content(content, f".cursor/rules/{mdc_file.name}")
                    cursorrules_content += f"## .cursor/rules/{mdc_file.name}\n\n{content}\n\n"
            except Exception as e:
                logger.debug("Could not read %s: %s", mdc_file, e)

    if not cursorrules_content:
        return ""
    return _truncate_content(cursorrules_content, ".cursorrules")


def build_context_files_prompt(cwd: Optional[str] = None, skip_soul: bool = False) -> str:
    """Discover and load context files for the system prompt.

    Priority (first found wins — only ONE project context type is loaded):
      1. .dag.md / DAG.md  (walk to git root)
      2. AGENTS.md / agents.md   (cwd only)
      3. CLAUDE.md / claude.md   (cwd only)
      4. .cursorrules / .cursor/rules/*.mdc  (cwd only)

    SOUL.md from DAG_HOME is independent and always included when present.
    Each context source is capped at 20,000 chars.

    When *skip_soul* is True, SOUL.md is not included here (it was already
    loaded via ``load_soul_md()`` for the identity slot).
    """
    if cwd is None:
        cwd = os.getcwd()

    cwd_path = Path(cwd).resolve()
    sections = []

    # Priority-based project context: first match wins
    project_context = (
        _load_dag_md(cwd_path)
        or _load_agents_md(cwd_path)
        or _load_claude_md(cwd_path)
        or _load_cursorrules(cwd_path)
    )
    if project_context:
        sections.append(project_context)

    # SOUL.md from DAG_HOME only — skip when already loaded as identity
    if not skip_soul:
        soul_content = load_soul_md()
        if soul_content:
            sections.append(soul_content)

    if not sections:
        return ""
    return "# Project Context\n\nThe following project context files have been loaded and should be followed:\n\n" + "\n".join(sections)
