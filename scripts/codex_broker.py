#!/usr/bin/env python3
"""Stateless local-first broker for Codex CLI.

Optimizations:
- exact response cache keyed by repo fingerprint + normalized prompt
- local short-circuit for common read/search/status requests
- compact prompt packing from relevant file snippets, with git state opt-in

This wrapper is intentionally stateless per turn. It is safe to cache final
answers because it does not rely on Codex app-server's hidden thread memory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


LOCAL_PREFIXES = ("git ", "rg ", "find ", "ls", "sed ", "cat ", "pwd", "date")
MAX_RELEVANT_FILES = 4
MAX_SNIPPET_LINES = 40
MAX_CACHE_ENTRIES = 400
CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
INCLUDE_GIT_STATE = os.environ.get("CODEX_BROKER_INCLUDE_GIT_STATE") == "1"


def _run(cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return 127, ""
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    if out and err:
        return proc.returncode, out + "\n" + err
    return proc.returncode, out or err


def _run_shell(cmd: str, cwd: str) -> int:
    return subprocess.run(cmd, cwd=cwd, shell=True, check=False).returncode


def _git_root(root: str) -> str:
    code, out = _run(["git", "-C", root, "rev-parse", "--show-toplevel"])
    if code == 0 and out:
        return out.splitlines()[0]
    return root


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_prompt(prompt: str) -> str:
    return re.sub(r"\s+", " ", prompt.strip().lower())[:1200]


def _repo_fingerprint(root: str) -> str:
    root = _git_root(root)
    head_code, head = _run(["git", "-C", root, "rev-parse", "HEAD"])
    status_code, status = _run(["git", "-C", root, "status", "--short"])
    payload = "\n".join(
        [root, head if head_code == 0 else "", status if status_code == 0 else ""]
    )
    return _sha(payload)


def _cache_dir(root: str) -> Path:
    d = Path(root) / ".codex-broker"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(root: str) -> Path:
    return _cache_dir(root) / "responses.json"


def _load_cache(root: str) -> dict[str, dict]:
    path = _cache_path(root)
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_cache(root: str, payload: dict[str, dict]) -> None:
    items = sorted(
        payload.items(),
        key=lambda item: float(item[1].get("ts") or 0),
        reverse=True,
    )[:MAX_CACHE_ENTRIES]
    _cache_path(root).write_text(json.dumps(dict(items), indent=2))


def _cache_key(root: str, fingerprint: str, prompt: str) -> str:
    return _sha("\n".join([root, fingerprint, _normalize_prompt(prompt), "v1"]))


def _keywords(prompt: str) -> list[str]:
    seen: list[str] = []
    for token in re.findall(r"[A-Za-z0-9_./-]{4,}", prompt.lower()):
        if token not in seen:
            seen.append(token)
        if len(seen) >= 8:
            break
    return seen


def _read_file_prompt(prompt: str, root: str) -> str | None:
    m = re.match(r"^(?:read|show|open|cat)\s+(.+)$", prompt.strip(), re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).strip().strip("\"'")
    path = raw if os.path.isabs(raw) else str(Path(root) / raw)
    if not os.path.isfile(path):
        return f"Missing file: {path}"
    _, out = _run(["sed", "-n", "1,200p", path])
    return f"--- {path}\n{out}"


def _search_prompt(prompt: str, root: str) -> str | None:
    m = re.match(r"^(?:search|find text|grep)\s+(.+)$", prompt.strip(), re.IGNORECASE)
    if not m:
        return None
    pattern = m.group(1).strip().strip("\"'")
    if not pattern:
        return ""
    _, out = _run(["rg", "-n", "-g", "!node_modules", "-g", "!.git", pattern, root])
    return out


def _diagnostic_prompt(prompt: str) -> list[str] | None:
    low = prompt.strip().lower()
    if low in {"status", "git status"}:
        return ["git", "status", "--short", "--branch"]
    if low in {"branch", "git branch"}:
        return ["git", "branch", "--show-current"]
    if low in {"changed files", "git diff", "diff"}:
        return ["git", "diff", "--stat"]
    if low in {"list files", "files"}:
        return ["rg", "--files", "."]
    if low == "pwd":
        return ["pwd"]
    if low == "date":
        return ["date"]
    return None


def _should_run_local(prompt: str, root: str) -> bool:
    low = prompt.strip().lower()
    if prompt.startswith("!"):
        return True
    if low.startswith(LOCAL_PREFIXES):
        return True
    if _read_file_prompt(prompt, root) is not None:
        return True
    if _search_prompt(prompt, root) is not None:
        return True
    return _diagnostic_prompt(prompt) is not None


def _handle_local(prompt: str, root: str) -> int:
    if prompt.startswith("!"):
        return _run_shell(prompt[1:].strip(), root)
    file_view = _read_file_prompt(prompt, root)
    if file_view is not None:
        print(file_view)
        return 0
    search_view = _search_prompt(prompt, root)
    if search_view is not None:
        print(search_view)
        return 0
    diagnostic = _diagnostic_prompt(prompt)
    if diagnostic is None:
        return 0
    if diagnostic == ["pwd"]:
        print(root)
        return 0
    code, out = _run(diagnostic, cwd=root)
    if out:
        print(out)
    return code


def _resolve_candidate_files(root: str, prompt: str) -> list[str]:
    root_path = Path(root)
    files: list[str] = []
    seen: set[str] = set()
    explicit_tokens = re.findall(r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+", prompt)
    for token in explicit_tokens:
        path = token if os.path.isabs(token) else str(root_path / token)
        if os.path.isfile(path) and path not in seen:
            seen.add(path)
            files.append(path)
        if len(files) >= MAX_RELEVANT_FILES:
            return files
    for key in _keywords(prompt):
        _, out = _run(["rg", "-l", "-g", "!node_modules", "-g", "!.git", key, root])
        for line in out.splitlines():
            if line and line not in seen and os.path.isfile(line):
                seen.add(line)
                files.append(line)
            if len(files) >= MAX_RELEVANT_FILES:
                return files
    return files


def _pack_context(root: str, prompt: str) -> str:
    root = _git_root(root)
    parts = [
        f"WORKSPACE: {root}",
        f"GOAL: {prompt}",
        "RULE: do the cheapest useful work locally first.",
        "RULE: keep context tight.",
        "RULE: prefer direct commands and minimal diffs.",
    ]
    if INCLUDE_GIT_STATE:
        _, git_status = _run(["git", "-C", root, "status", "--short", "--branch"])
        _, git_diff = _run(["git", "-C", root, "diff", "--stat", "--", ".", ":(exclude)node_modules", ":(exclude).git"])
        parts.extend(
            [
                "",
                "GIT_STATUS:",
                git_status,
                "",
                "GIT_DIFFSTAT:",
                git_diff,
            ]
        )
    for path in _resolve_candidate_files(root, prompt):
        parts.extend(["", f"--- {path}"])
        _, snippet = _run(["sed", "-n", f"1,{MAX_SNIPPET_LINES}p", path])
        parts.append(snippet)
    return "\n".join(parts).strip() + "\n"


def _lookup_cached_response(root: str, prompt: str) -> str | None:
    fingerprint = _repo_fingerprint(root)
    key = _cache_key(root, fingerprint, prompt)
    cache = _load_cache(root)
    entry = cache.get(key)
    if not entry:
        return None
    if (time.time() - float(entry.get("ts") or 0)) > CACHE_TTL_SECONDS:
        cache.pop(key, None)
        _save_cache(root, cache)
        return None
    return str(entry.get("response") or "")


def _store_cached_response(root: str, prompt: str, response: str) -> None:
    cache = _load_cache(root)
    key = _cache_key(root, _repo_fingerprint(root), prompt)
    cache[key] = {
        "prompt": _normalize_prompt(prompt),
        "response": response,
        "ts": time.time(),
    }
    _save_cache(root, cache)


def _invoke_codex(codex_bin: str, prompt: str) -> tuple[int, str]:
    proc = subprocess.run(
        [codex_bin, prompt],
        capture_output=True,
        text=True,
        check=False,
    )
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    if out and err:
        return proc.returncode, out + "\n" + err
    return proc.returncode, out or err


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--root", default=os.getcwd())
    ap.add_argument("--codex-bin", default=os.environ.get("CODEX_BIN", "codex"))
    ap.add_argument("--pack-only", action="store_true")
    ap.add_argument("--cache-status", action="store_true")
    ap.add_argument("prompt", nargs=argparse.REMAINDER)
    ns = ap.parse_args()

    prompt_parts = ns.prompt
    if prompt_parts and prompt_parts[0] == "--":
        prompt_parts = prompt_parts[1:]
    prompt = " ".join(prompt_parts).strip()
    root = _git_root(os.path.abspath(ns.root))

    if ns.cache_status:
        cache = _load_cache(root)
        print(json.dumps({"root": root, "entries": len(cache)}))
        return 0
    if ns.pack_only:
        sys.stdout.write(_pack_context(root, prompt))
        return 0
    if not prompt:
        print("prompt required", file=sys.stderr)
        return 2
    if _should_run_local(prompt, root):
        return _handle_local(prompt, root)
    cached = _lookup_cached_response(root, prompt)
    if cached:
        print(cached)
        return 0
    packed = _pack_context(root, prompt)
    code, out = _invoke_codex(ns.codex_bin, packed)
    if out:
        print(out)
    if code == 0 and out.strip():
        _store_cached_response(root, prompt, out.strip())
    return code


if __name__ == "__main__":
    raise SystemExit(main())
