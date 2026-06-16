#!/usr/bin/env python3
"""
auto-reflect.py — Reflexion (Shinn et al. 2023, NeurIPS)
Applies critique→refine loop to any text. Bridge from v4 Pro to Opus-tier.

Usage: echo "your answer" | python3 auto-reflect.py
       Returns critique + refined version as JSON.
"""
import sys, json

REFLECTION_PROMPT = """APPLY REFLEXION (max 3 iterations):

INPUT: {text}

ITERATION 1 — CRITIQUE:
1. What could be wrong? 2. Edge cases missed? 3. What would a smarter engineer flag? 4. Least confident part?

ITERATION 1 — REFINED: [rewrite fixing all issues]

ITERATION 2 — CRITIQUE (only if issues remain): [remaining gaps]

ITERATION 2 — REFINED: [further improved]

ITERATION 3 — CRITIQUE (only if still needed): [final pass]

FINAL: [best version]
UNCERTAIN: true/false
UNCERTAIN_REASON: [why, if uncertain]
"""

def build_reflection_prompt(text: str) -> str:
    return REFLECTION_PROMPT.format(text=text[:8000])

if __name__ == "__main__":
    text = sys.stdin.read().strip()
    if not text:
        print(json.dumps({"error": "no input"}))
        sys.exit(1)
    print(json.dumps({
        "technique": "reflexion",
        "source": "Shinn et al. 2023, NeurIPS",
        "input_chars": len(text),
        "prompt": build_reflection_prompt(text),
        "instruction": "Feed this prompt to your LLM. The LLM fills in the critique and refinement."
    }, indent=2))
