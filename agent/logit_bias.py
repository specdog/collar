"""Logit bias — ban forbidden tokens at API level. Zero prompt tokens.

Works with OpenAI-compatible APIs only (OpenAI, OpenRouter, DeepSeek compat).
Anthropic/Gemini/Bedrock skip this — they fall back to prompt steering.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


def _forbidden_strings() -> List[str]:
    user = Path.home() / ".dag" / "output-integrity.dag"
    system = Path(__file__).parent.parent / "dags" / "output-integrity.dag"
    path = user if user.exists() else system
    if not path.exists():
        return []
    strings, section = [], None
    for line in path.read_text().splitlines():
        line = line.strip()
        if line == "[forbidden-strings]":
            section = "forbidden"; continue
        if line.startswith("[") and line.endswith("]"):
            section = None; continue
        if section == "forbidden" and line:
            strings.append(line)
    return strings


def build() -> Optional[Dict[int, int]]:
    strings = _forbidden_strings()
    if not strings:
        return None
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None
    banned = {}
    for s in strings:
        for tid in enc.encode(s):
            banned[tid] = -100
    return banned or None
