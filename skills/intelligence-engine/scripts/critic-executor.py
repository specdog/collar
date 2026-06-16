#!/usr/bin/env python3
"""
critic-executor.py -- CRITIC (Gou et al. 2024)
Self-critique by verifying claims against external tools.
Usage: echo "answer to critique" | python3 critic-executor.py
"""
import sys, json

CRITIC_PROMPT = """CRITIC -- SELF-CRITIQUE WITH TOOL USE

OUTPUT TO CRITIQUE: {output}

--- PHASE 1: CLAIM EXTRACTION ---
Extract every verifiable claim from the output:
CLAIM 1: [specific factual assertion]
CLAIM 2: [specific factual assertion]
...continue...

--- PHASE 2: EXTERNAL VERIFICATION ---
For each claim, search for evidence:
CLAIM 1: [text]
  TOOL: [which tool would verify this - search/read_file/terminal/browser]
  QUERY: [specific query to run]
  RESULT: [tool output that confirms or refutes]
  VERDICT: SUPPORTED / REFUTED / UNVERIFIABLE

CLAIM 2: [text]
  TOOL: [which tool]
  QUERY: [specific query]
  RESULT: [tool output]
  VERDICT: SUPPORTED / REFUTED / UNVERIFIABLE

--- PHASE 3: CRITIQUE SYNTHESIS ---
SUPPORTED CLAIMS: [list - these are fine]
REFUTED CLAIMS: [list - these are WRONG, remove or fix]
UNVERIFIABLE CLAIMS: [list - flag as uncertain]
HALLUCINATION DETECTED: yes/no

--- PHASE 4: CORRECTED OUTPUT ---
[Rewritten output with refuted claims removed, unverifiable claims flagged]
CONFIDENCE: [1-10, penalized for each refuted claim]
"""

def build_critic_prompt(output):
    return CRITIC_PROMPT.format(output=output[:8000])

if __name__ == "__main__":
    output = sys.stdin.read().strip()
    if not output:
        print(json.dumps({"error": "no input"}))
        sys.exit(1)
    print(json.dumps({
        "technique": "critic",
        "source": "Gou et al. 2024",
        "tier_bridge": 0.2,
        "prompt": build_critic_prompt(output),
        "instruction": "Feed this prompt. Verify each claim against external tools."
    }, indent=2))
