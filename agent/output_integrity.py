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

    Checks ~/.dag/output-integrity.dag first (user override), then falls
    back to the system default in dags/output-integrity.dag.
    Users add project-specific patterns in their own config file.
    The system default contains only universal patterns.

    Returns (forbidden_strings, entity_corrections).
    """
    forbidden: List[str] = []
    entities: Dict[str, str] = {}

    # 1. Try user override: ~/.dag/output-integrity.dag
    user_path = Path.home() / ".dag" / "output-integrity.dag"

    # 2. Fall back to system default
    system_path = Path(__file__).parent.parent / "dags" / "output-integrity.dag"

    dag_path = user_path if user_path.exists() else system_path
    if not dag_path.exists():
        return forbidden, entities

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
                forbidden.append(re.escape(line))
            elif section == "entities":
                if "→" in line:
                    wrong, right = line.split("→", 1)
                    entities[wrong.strip()] = right.strip()
    except Exception:
        pass

    return forbidden, entities


_FORBIDDEN_STRINGS, _ENTITY_SPELLING = _parse_dag_patterns()

# Compile forbidden strings into a single regex for efficiency
_FORBIDDEN_RE = None
if _FORBIDDEN_STRINGS:
    _FORBIDDEN_RE = re.compile(
        "(" + "|".join(_FORBIDDEN_STRINGS) + ")",
        re.IGNORECASE,
    )


def sanitize(text: str) -> str:
    """Run integrity checks on the text. Returns sanitized text.

    Pattern-driven — reads forbidden strings and entity spellings from
    the .dag config file.  Users define their own patterns.
    The engine only enforces.
    """
    if not text or not isinstance(text, str):
        return text

    # 1. Entity spelling corrections (exact match, case-insensitive)
    if _ENTITY_SPELLING:
        for wrong, right in _ENTITY_SPELLING.items():
            pattern = re.compile(re.escape(wrong), re.IGNORECASE)
            if pattern.search(text):
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

    return text


__all__ = ["sanitize"]
