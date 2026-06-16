#!/usr/bin/env python3
"""
got-executor.py -- Graph of Thoughts (Besta et al. 2024)
Reasoning as a directed graph. Nodes merge, branch, form DAGs.
Usage: echo "complex problem" | python3 got-executor.py
"""
import sys, json

GOT_PROMPT = """GRAPH OF THOUGHTS -- DAG-BASED REASONING

PROBLEM: {problem}

Construct a reasoning DAG. Unlike ToT (3 parallel paths), GoT allows:
- BRANCHING: one thought -> multiple children
- MERGING: multiple thoughts -> one synthesis
- REFINING: thought -> improved thought

--- REASONING DAG ---
NODE 0 (ROOT): [problem restatement]
  Children: [N1, N2]

NODE 1: [first approach]
  Parent: N0 | Confidence: [1-10] | Children: [N3]

NODE 2: [second approach]
  Parent: N0 | Confidence: [1-10] | Children: [N3, N4]

NODE 3 (MERGE): [synthesis of N1+N2]
  Parents: N1, N2 | Confidence: [1-10] | Children: [N5]

NODE 4: [explore edge case from N2]
  Parent: N2 | Children: [N5]

NODE 5 (MERGE): [final synthesis of N3+N4]
  Parents: N3, N4

--- GRAPH ANALYSIS ---
Node count: [N]
Merge nodes: [which nodes combined multiple parents]
Branch factor: [avg children per node]
Critical path: [longest chain from ROOT to answer]

--- CONSENSUS ANSWER ---
[Answer from the merged reasoning DAG]
CONFIDENCE: [1-10]
"""

def build_got_prompt(problem):
    return GOT_PROMPT.format(problem=problem[:8000])

if __name__ == "__main__":
    problem = sys.stdin.read().strip()
    if not problem:
        print(json.dumps({"error": "no input"}))
        sys.exit(1)
    print(json.dumps({
        "technique": "graph_of_thoughts",
        "source": "Besta et al. 2024",
        "tier_bridge": 0.3,
        "prompt": build_got_prompt(problem),
        "instruction": "Feed this prompt to your LLM. Build a reasoning DAG, not linear paths."
    }, indent=2))
