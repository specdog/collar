#!/usr/bin/env python3
"""Output stripper — removes filler from assistant replies before history storage.
No LLM call. Regex-based. Lossless for meaning, lossy for verbosity.
Saves ~15-25% of output tokens from entering conversation history.
"""
import re

# Filler sentence starters — standalone sentences that are model self-talk
FILLER_STARTERS = (
    r"I should|I need to|I will|I.ll|Let me|I can|I.d better|I must|"
    r"I have to|I want to|I.m going to|I notice|I observe|I see|I realize|"
    r"I understand|It seems|It appears|I think|I believe|I found|"
    r"Looking at this|From this|This tells me|This means|That means|"
    r"Now I|First,|Next,|Finally,"
)

# Standalone politeness — entire line of just this
POLITE_ONLY = (
    r"Certainly!|Of course!|Absolutely!|Great!|Perfect!|Sure!|"
    r"Alright!|OK!|Right!|Here you go!|There you have it!|"
    r"Happy to help!|You.re welcome!|No problem!|My pleasure!"
)

# Match: a standalone line that is ENTIRELY filler/politeness
# Uses .+?[.!?](?=\s|$) to avoid matching mid-word periods (e.g., .dag)
FILLER_LINE = re.compile(
    r"(?m)^\s*(" + FILLER_STARTERS + r")\s.+?[.!?](?=\s|$)\s*$"
)

POLITE_LINE = re.compile(
    r"(?m)^\s*(" + POLITE_ONLY + r")\s*$"
)

# Markdown formatting (keep text, drop syntax)
MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
MD_ITALIC = re.compile(r"\*(.+?)\*")
MD_HEADER = re.compile(r"(?m)^#{1,6}\s+")

# Multiple blank lines
MULTI_NL = re.compile(r"\n{3,}")


def strip_output(text: str) -> tuple[str, int, int]:
    """Strip filler from assistant output. Returns (stripped_text, original_len, stripped_len)."""
    original = len(text)

    # Strip standalone filler lines (entire line is just self-talk)
    text = FILLER_LINE.sub("", text)

    # Strip standalone polite lines
    text = POLITE_LINE.sub("", text)

    # Strip markdown syntax (keep content)
    text = MD_BOLD.sub(r"\1", text)
    text = MD_ITALIC.sub(r"\1", text)
    text = MD_HEADER.sub("", text)

    # Collapse excessive blank lines
    text = MULTI_NL.sub("\n\n", text)

    # Clean up orphan blank lines at edges
    text = text.strip()

    return text, original, len(text)


if __name__ == "__main__":
    import sys
    text = sys.stdin.read()
    stripped, orig, now = strip_output(text)
    saved = orig - now
    print(f"Original: {orig} chars", file=sys.stderr)
    print(f"Stripped: {now} chars ({saved} saved, {saved/orig*100:.0f}%)", file=sys.stderr)
    print(stripped)
