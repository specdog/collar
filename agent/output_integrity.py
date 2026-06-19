"""Output integrity filter — post-generation enforcement.

This runs on EVERY assistant text response before it leaves the harness.
Not prompt guidance. Not a .dag file. Compiled Python bytecode.
If the text violates integrity rules, it's sanitized in-place.
"""

import re
from typing import List, Tuple

# ── Entity names that must never be misspelled ──────────────────────
# Format: (misspelling_regex, correction)
# These are checked with word-boundary-aware matching.
_ENTITY_SPELLING: List[Tuple[str, str]] = [
    # Collar — the harness itself
    (r"\b[Cc]ollat\b", "Collar"),
    (r"\b[Cc]ollar's\b", "Collar"),
    # dotdog — the spec compiler
    (r"\b[Dd]ott?dog\b", "dotdog"),
    (r"\b[Dd]ot[dD]og\b", "dotdog"),
    # specdog — the org
    (r"\b[Ss]pec[dD]og\b", "specdog"),
    # dag-router — the Rust binary
    (r"\b[Dd]ag[-\s]?router\b", "dag-router"),
    # deepseek — model provider
    (r"\b[Dd]eep[Ss]eek\b", "deepseek"),
    (r"\b[Dd]eep[Ss]eak\b", "deepseek"),
]

# ── Human-attribute claims that must never appear ───────────────────
# The agent has no body. Any claim otherwise is a confabulation.
_HUMAN_CLAIMS: List[str] = [
    r"(?i)\bfingers?\b.*\bslipped\b",
    r"(?i)\badjacent\b.*\bkeyboard\b",
    r"(?i)\b(my|the)\s+keyboard\b",
    r"(?i)\btypo\b.*\bfingers?\b",
    r"(?i)\bR\s+and\s+T\s+are\s+adjacent\b",
    r"(?i)\bI('?m| am)\s+(only\s+)?human\b",
    r"(?i)\bI\s+have\s+(no\s+)?fingers?\b",
    r"(?i)\bmy\s+(hands?|arms?|body|eyes?)\b",
    r"(?i)\bI\s+need\s+(sleep|rest|coffee|a break)\b",
    r"(?i)\b(late|tired|exhausted|sleepy)\s+(night|here|today)\b",
]

# ── Fabricated explanations that must never appear ──────────────────
# The agent must only cite causes traceable to tool output.
_FABRICATED_CAUSES: List[str] = [
    r"(?i)\bmust\s+have\s+been\b.*\b(glitch|bug|lag|slow|network)\b",
    r"(?i)\bprobably\s+(just|a)\s+(glitch|bug|lag|typo|network)\b",
    r"(?i)\blikely\s+(just|a)\s+(glitch|bug|lag|typo|network)\b",
    r"(?i)\bthe\s+API\s+was\s+(slow|down|acting\s+up)\b",
    r"(?i)\bthe\s+tool\s+(timed\s+out|hung|glitched)\b",
]


def _check_entity_spelling(text: str) -> str:
    """Correct misspellings of known entity names."""
    for pattern, correction in _ENTITY_SPELLING:
        text = re.sub(pattern, correction, text)
    return text


def _check_human_claims(text: str) -> Tuple[str, List[str]]:
    """Detect and flag human-attribute claims. Returns (sanitized_text, violations)."""
    violations = []
    for pattern in _HUMAN_CLAIMS:
        matches = re.findall(pattern, text)
        if matches:
            violations.append(f"human-claim: {matches[0] if isinstance(matches[0], str) else str(matches)}")
    if violations:
        # Replace the offending text with an admission of error
        # rather than letting the confabulation reach the user.
        for pattern in _HUMAN_CLAIMS:
            text = re.sub(
                pattern,
                "[this claim was blocked — the agent has no body]",
                text,
            )
    return text, violations


def _check_fabricated_causes(text: str) -> Tuple[str, List[str]]:
    """Detect fabricated causal explanations."""
    violations = []
    for pattern in _FABRICATED_CAUSES:
        matches = re.findall(pattern, text)
        if matches:
            violations.append(f"fabricated-cause: {matches[0] if isinstance(matches[0], str) else str(matches)}")
    if violations:
        for pattern in _FABRICATED_CAUSES:
            text = re.sub(
                pattern,
                "[this explanation was blocked — cause cannot be verified]",
                text,
            )
    return text, violations


def sanitize(text: str) -> str:
    """Run all integrity checks on the text. Returns sanitized text.

    This is the single entry point called from the conversation loop.
    It runs BEFORE the text reaches the user.  No fallback.  No bypass.

    Logs violations via the standard logging channel so operators can
    see when the filter fired.
    """
    if not text or not isinstance(text, str):
        return text

    import logging
    log = logging.getLogger(__name__)

    original = text
    violations: List[str] = []

    # 1. Entity spelling
    text = _check_entity_spelling(text)

    # 2. Human-attribute claims
    text, human_violations = _check_human_claims(text)
    violations.extend(human_violations)

    # 3. Fabricated explanations
    text, fab_violations = _check_fabricated_causes(text)
    violations.extend(fab_violations)

    if violations:
        log.warning(
            "output-integrity: %d violation(s) in response — sanitized",
            len(violations),
        )
        for v in violations:
            log.warning("  %s", v)

    return text


__all__ = ["sanitize"]
