#!/usr/bin/env python3
"""
analogical-executor.py -- Analogical Prompting (Yasunaga et al. 2024)
Draw analogies from related domains before solving.
Usage: echo "problem" | python3 analogical-executor.py
"""
import sys, json

ANALOGICAL_PROMPT = """ANALOGICAL PROMPTING -- ANALOGY-FIRST REASONING

PROBLEM: {problem}

Before solving, generate relevant analogies from 3 different domains.
Analogies help the model transfer solution patterns across domains.

--- ANALOGY 1 (Software Engineering) ---
DOMAIN: [specific sub-domain: compilers, databases, networking, OS]
PROBLEM IN THAT DOMAIN: [similar problem pattern]
SOLUTION IN THAT DOMAIN: [how it was solved]
MAPPING TO CURRENT PROBLEM: [what maps 1:1, what maps with adaptation]

--- ANALOGY 2 (Systems/Infrastructure) ---
DOMAIN: [distributed systems, concurrency, caching]
PROBLEM IN THAT DOMAIN: [similar problem pattern]
SOLUTION IN THAT DOMAIN: [how it was solved]
MAPPING TO CURRENT PROBLEM: [what maps, what needs adaptation]

--- ANALOGY 3 (Mathematics/Logic) ---
DOMAIN: [graph theory, formal logic, algorithms]
PROBLEM IN THAT DOMAIN: [similar problem pattern]
SOLUTION IN THAT DOMAIN: [how it was solved]
MAPPING TO CURRENT PROBLEM: [what maps, what needs adaptation]

--- SYNTHESIS ---
Patterns that appear across multiple analogies:
  PATTERN 1: [recurring solution pattern]
  PATTERN 2: [recurring solution pattern]

Solution adapted from analogies:
  APPROACH: [how to solve this problem using patterns from analogies]
  ADAPTATIONS: [what needed to change from the analogy solutions]

--- FINAL ANSWER ---
SOLUTION: [the adapted solution]
CONFIDENCE: [1-10]
MOST USEFUL ANALOGY: [which analogy provided the best transfer]
"""

def build_analogical_prompt(problem):
    return ANALOGICAL_PROMPT.format(problem=problem[:8000])

if __name__ == "__main__":
    problem = sys.stdin.read().strip()
    if not problem:
        print(json.dumps({"error": "no input"}))
        sys.exit(1)
    print(json.dumps({
        "technique": "analogical_prompting",
        "source": "Yasunaga et al. 2024",
        "tier_bridge": 0.15,
        "prompt": build_analogical_prompt(problem),
        "instruction": "Feed this prompt. Generate 3 analogies from different domains, synthesize patterns."
    }, indent=2))
