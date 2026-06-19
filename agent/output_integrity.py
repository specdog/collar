"""Output integrity filter — post-generation enforcement.

This runs on EVERY assistant text response before it leaves the harness.
Patterns are NOT hardcoded — they are read from dags/output-integrity.dag.
If the file or sections are missing, the filter is a no-op.

Each user/org defines their own forbidden strings and entity spellings.
The engine only provides the enforcement mechanism.
"""

import re
import logging
from pathlib import Path
from typing import List, Tuple, Dict

log = logging.getLogger(__name__)

# ── Load patterns from DAG file ─────────────────────────────────────
# Parsed once at import.  Changes require a process restart.

def _parse_dag_patterns() -> Tuple[List[str], Dict[str, str]]:
    """Parse output-integrity.dag for forbidden strings and entity spellings.

    Loads BOTH system default and user override, merging results.
    User config adds to system defaults — never replaces.
    """
    forbidden: List[str] = []
    entities: Dict[str, str] = {}

    user_path = Path.home() / ".dag" / "output-integrity.dag"
    system_path = Path(__file__).parent.parent / "dags" / "output-integrity.dag"

    # Parse both files, user overrides/adds to system
    for dag_path in (system_path, user_path):
        if not dag_path.exists():
            continue
        section = None
        try:
            for line in dag_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                if line == "[forbidden-strings]":
                    section = "forbidden"
                    continue
                if line == "[entity-spelling]":
                    section = "entities"
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = None
                    continue

                if section == "forbidden":
                    escaped = re.escape(line)
                    if escaped not in forbidden:
                        forbidden.append(escaped)
                elif section == "entities":
                    if "→" in line:
                        wrong, right = line.split("→", 1)
                        entities[wrong.strip()] = right.strip()
        except Exception:
            pass

    return forbidden, entities


_FORBIDDEN_STRINGS, _ENTITY_SPELLING = _parse_dag_patterns()

# _FORBIDDEN_STRINGS contains re.escape'd patterns for the regex.
# Build the raw list (un-escaped) for stop sequences and logit_bias.
_RAW_FORBIDDEN_STRINGS: List[str] = [
    re.sub(r'\\(.)', r'\1', s) for s in _FORBIDDEN_STRINGS
]

# Compile forbidden strings into a single regex for efficiency
_FORBIDDEN_RE = None
if _FORBIDDEN_STRINGS:
    _FORBIDDEN_RE = re.compile(
        "(" + "|".join(_FORBIDDEN_STRINGS) + ")",
        re.IGNORECASE,
    )

# Compile entity spelling patterns once
# Uses word-boundary matching (\b) to avoid corrupting substrings.
# e.g. Collat→Collar matches "Collat" but not "Collateral" or "Collation"
_ENTITY_RES: Dict[str, re.Pattern] = {}
if _ENTITY_SPELLING:
    for wrong in _ENTITY_SPELLING:
        _ENTITY_RES[wrong] = re.compile(
            r"\b" + re.escape(wrong) + r"\b", re.IGNORECASE
        )

# Compile noise-stripping patterns once
_NOISE_RES: List[re.Pattern] = [
    re.compile(r"(?i)^(Let me|I'll now|First, I need to|I will|Let's|Allow me to)\s.*?\.\s*"),
    re.compile(r"(?i)^(I('ll| will) (use|check|look|try|run|call|search|read|write|open))\s.*?\.\s*"),
    re.compile(r"(?i)^(Let me|I('ll| will)) (just |go ahead and |quickly )?.*?\.\s*"),
]


def sanitize(text: str) -> str:
    """Run integrity + polish on the text. Returns cleaned text.

    Post-generation, zero token cost. Runs after API returns, before user sees.
    Three passes: entity spelling, forbidden strings, noise stripping.
    """
    if not text or not isinstance(text, str):
        return text

    # 1. Entity spelling corrections
    if _ENTITY_SPELLING:
        for wrong, right in _ENTITY_SPELLING.items():
            pattern = _ENTITY_RES.get(wrong)
            if pattern and pattern.search(text):
                text = pattern.sub(right, text)

    # 2. Forbidden string blocking
    if _FORBIDDEN_RE:
        match = _FORBIDDEN_RE.search(text)
        if match:
            log.warning(
                "output-integrity: blocked forbidden string %r",
                match.group(0),
            )
            text = _FORBIDDEN_RE.sub("[blocked]", text)

    # 3. Noise stripping
    for pat in _NOISE_RES:
        text = pat.sub("", text, count=1)

    # 4. Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text


def get_forbidden_strings() -> List[str]:
    """Return the raw forbidden strings list from the config file.

    Used by logit_bias and stop-sequence injection.
    Parsed once at import. Returns empty list if no config.
    """
    return list(_RAW_FORBIDDEN_STRINGS)


__all__ = ["sanitize", "get_forbidden_strings"]
