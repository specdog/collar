"""Logit bias + stop sequences — ban forbidden tokens before generation.

Reads forbidden strings from output_integrity config (single parse).
Provides two defenses:
  - logit_bias: token-level ban (OpenAI-compat, tiktoken required)
  - stop_sequences: string-level cutoff (ALL providers, zero dependencies)
"""

import logging
from typing import Dict, List, Optional

from agent.output_integrity import get_forbidden_strings

log = logging.getLogger(__name__)


def _strings() -> List[str]:
    """Forbidden strings from the unified config parser."""
    return get_forbidden_strings()


def build_logit_bias() -> Optional[Dict[int, int]]:
    """Tokenize forbidden strings and return {token_id: -100}.

    Requires tiktoken. Returns None if unavailable.
    Only used for OpenAI-compatible APIs.
    """
    strings = _strings()
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


def build_stop_sequences() -> Optional[List[str]]:
    """Return forbidden strings as stop sequences.

    Works on ALL providers. Zero dependencies.
    When the model starts generating a forbidden string,
    the API cuts generation at that token.
    """
    strings = _strings()
    return strings if strings else None


__all__ = ["build_logit_bias", "build_stop_sequences"]
