#!/usr/bin/env python3
"""
cov-executor.py -- Chain of Verification (Dhuliawala et al. 2024)
Generate answer, then verify each factual claim independently.
Usage: echo "question" | python3 cov-executor.py
"""
import sys, json

COV_PROMPT = """CHAIN OF VERIFICATION -- SELF-VERIFICATION LOOP

QUESTION: {question}

--- PHASE 1: GENERATE BASELINE ANSWER ---
BASELINE: [your initial answer]

--- PHASE 2: EXTRACT VERIFIABLE CLAIMS ---
Extract every factual claim from the baseline:
CLAIM 1: [specific claim - entity name, version, date, API, concept]
CLAIM 2: [specific claim]
CLAIM 3: [specific claim]
...continue for all factual claims...

--- PHASE 3: VERIFICATION CHAIN ---
For each claim, independently verify:
CLAIM 1: [claim text]
  VERIFICATION: [check against tools/DAG/external sources]
  VERDICT: CORRECT / INCORRECT / UNCERTAIN
  EVIDENCE: [what confirmed or refuted it]

CLAIM 2: [claim text]
  VERIFICATION: [check]
  VERDICT: CORRECT / INCORRECT / UNCERTAIN
  EVIDENCE: [source]

CLAIM 3: [claim text]
  VERIFICATION: [check]
  VERDICT: CORRECT / INCORRECT / UNCERTAIN
  EVIDENCE: [source]

--- PHASE 4: REVISED ANSWER ---
[Answer with incorrect claims removed/corrected, uncertain claims flagged]
HALLUCINATED: [list of incorrect claims]
UNCERTAIN: [list of unverifiable claims]
CORRECT: [list of verified claims]
CONFIDENCE: [1-10]
"""

def build_cov_prompt(question):
    return COV_PROMPT.format(question=question[:8000])

if __name__ == "__main__":
    question = sys.stdin.read().strip()
    if not question:
        print(json.dumps({"error": "no input"}))
        sys.exit(1)
    print(json.dumps({
        "technique": "chain_of_verification",
        "source": "Dhuliawala et al. 2024",
        "tier_bridge": 0.2,
        "prompt": build_cov_prompt(question),
        "instruction": "Feed this prompt. Verify EVERY factual claim independently."
    }, indent=2))
