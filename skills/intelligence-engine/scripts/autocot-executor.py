#!/usr/bin/env python3
"""
autocot-executor.py -- Auto-CoT (Zhang et al. 2022)
Automatic chain-of-thought generation. Clusters questions, generates diverse chains.
Usage: echo "problem" | python3 autocot-executor.py
"""
import sys, json

AUTOCOT_PROMPT = """AUTO-COT -- AUTOMATIC CHAIN OF THOUGHT

PROBLEM: {problem}

Generate diverse reasoning chains automatically. Cluster similar problems,
sample from each cluster, generate chains with diversity.

--- STEP 1: PROBLEM CLUSTERING ---
What type of problem is this?
CATEGORY: [classification, debugging, architecture, implementation, design]
SIMILAR PROBLEMS: [list 2-3 similar problems you have seen]

--- STEP 2: DIVERSE CHAIN GENERATION ---
Generate 3 reasoning chains with different approaches:

CHAIN 1 (Step-by-step deduction):
  Step 1: [first reasoning step]
  Step 2: [second step]
  Step 3: [third step]
  CONCLUSION: [result from this chain]

CHAIN 2 (Analogy-based):
  ANALOGY: [similar problem from a different domain]
  MAPPING: [how the analogy maps to this problem]
  SOLUTION: [adapted from the analogy]
  CONCLUSION: [result from this chain]

CHAIN 3 (Decomposition-based):
  SUB-PROBLEM 1: [easiest part]
  SUB-PROBLEM 2: [next part]
  SUB-PROBLEM 3: [hardest part]
  COMPOSE: [combine sub-solutions]
  CONCLUSION: [result from this chain]

--- STEP 3: CHAIN DIVERSITY CHECK ---
Are the 3 chains genuinely different approaches?
DIVERSITY SCORE: [1-10]
If <5: regenerate the most similar chain.

--- STEP 4: AGGREGATION ---
AGREEMENT: [how many chains agree?]
FINAL ANSWER: [consensus or majority answer]
CONFIDENCE: [1-10]
"""

def build_autocot_prompt(problem):
    return AUTOCOT_PROMPT.format(problem=problem[:8000])

if __name__ == "__main__":
    problem = sys.stdin.read().strip()
    if not problem:
        print(json.dumps({"error": "no input"}))
        sys.exit(1)
    print(json.dumps({
        "technique": "autocot",
        "source": "Zhang et al. 2022",
        "tier_bridge": 0.15,
        "prompt": build_autocot_prompt(problem),
        "instruction": "Feed this prompt. Generate 3 diverse chains, check diversity, aggregate."
    }, indent=2))
