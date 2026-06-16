#!/usr/bin/env python3
"""
tot-executor.py — Tree of Thoughts (Yao et al. 2023, Princeton/DeepMind)
Explores 3 reasoning paths, self-evaluates each step, outputs consensus.

Usage: echo "complex problem" | python3 tot-executor.py
"""
import sys, json

TOT_PROMPT = """TREE OF THOUGHTS — 3 PATH EXPLORATION

PROBLEM: {problem}

─── PATH A (direct approach) ───
Step A1: [first reasoning step]
Self-eval: [confidence 1-10, reasoning]
Step A2: [next step, continuing from A1]
Self-eval: [confidence 1-10]
Step A3: [continue to conclusion]
FINAL ANSWER A: [conclusion from this path]

─── PATH B (alternative approach) ───
Step B1: [first reasoning step — different angle than A]
Self-eval: [confidence 1-10, reasoning]
Step B2: [next step]
Self-eval: [confidence 1-10]
Step B3: [continue to conclusion]
FINAL ANSWER B: [conclusion from this path]

─── PATH C (edge-case-first approach) ───
Step C1: [first reasoning step — focus on what could go wrong]
Self-eval: [confidence 1-10, reasoning]
Step C2: [next step]
Self-eval: [confidence 1-10]
Step C3: [continue to conclusion]
FINAL ANSWER C: [conclusion from this path]

─── SELF-CONSISTENCY CHECK ───
Agreement: [how many paths agree? 2/3? 3/3? 1/3?]
If 3/3: HIGH CONFIDENCE. Consensus answer is robust.
If 2/3: MEDIUM CONFIDENCE. Majority answer, flag the dissenting path's concern.
If 1/3: LOW CONFIDENCE. Paths diverged. Flag uncertainty to user.

─── CONSENSUS ANSWER ───
[The answer that 2+ paths agree on, with surviving reasoning]

UNCERTAIN: true/false
"""

def build_tot_prompt(problem: str) -> str:
    return TOT_PROMPT.format(problem=problem[:8000])

if __name__ == "__main__":
    problem = sys.stdin.read().strip()
    if not problem:
        print(json.dumps({"error": "no input"}))
        sys.exit(1)
    print(json.dumps({
        "technique": "tree_of_thoughts",
        "source": "Yao et al. 2023, Princeton/Google DeepMind",
        "paths": 3,
        "input_chars": len(problem),
        "prompt": build_tot_prompt(problem),
        "instruction": "Feed this prompt to your LLM. Fill in all 3 paths + self-evals + consensus."
    }, indent=2))
