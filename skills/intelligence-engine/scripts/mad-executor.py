#!/usr/bin/env python3
"""
mad-executor.py -- Multi-Agent Debate (Du et al. 2023)
Multiple instances of the model debate answers. Consensus via argument.
Usage: echo "question to debate" | python3 mad-executor.py
"""
import sys, json

MAD_PROMPT = """MULTI-AGENT DEBATE -- CONSENSUS VIA ARGUMENT

QUESTION: {question}

Three independent agents debate this question. Each argues from a different perspective.
After each round, agents refine their positions based on opponents'' arguments.
Maximum 3 rounds.

--- ROUND 1: INITIAL POSITIONS ---

AGENT A (Conservative/Correctness-first):
POSITION: [Agent A''s initial answer with reasoning]
CONFIDENCE: [1-10]

AGENT B (Pragmatic/Efficiency-first):
POSITION: [Agent B''s initial answer with reasoning]
CONFIDENCE: [1-10]

AGENT C (Innovative/Novelty-first):
POSITION: [Agent C''s initial answer with reasoning]
CONFIDENCE: [1-10]

--- ROUND 2: REBUTTALS ---

AGENT A rebuts B and C:
[What A thinks B and C got wrong]

AGENT B rebuts A and C:
[What B thinks A and C got wrong]

AGENT C rebuts A and B:
[What C thinks A and B got wrong]

Refined positions after rebuttals:
AGENT A REVISED: [position after considering rebuttals]
AGENT B REVISED: [position after considering rebuttals]
AGENT C REVISED: [position after considering rebuttals]

--- ROUND 3: CONVERGENCE ---

Areas of agreement across all 3 agents:
[List what they agree on]

Areas of remaining disagreement:
[List what they still disagree on]

--- CONSENSUS ---
AGREEMENT LEVEL: FULL / MAJORITY (2/3) / NONE (all disagree)
FINAL ANSWER: [consensus answer or majority answer with dissenting view noted]
CONFIDENCE: [1-10]
DISSENTING VIEW: [if 2/3, what the dissenter argued]
"""

def build_mad_prompt(question):
    return MAD_PROMPT.format(question=question[:8000])

if __name__ == "__main__":
    question = sys.stdin.read().strip()
    if not question:
        print(json.dumps({"error": "no input"}))
        sys.exit(1)
    print(json.dumps({
        "technique": "multi_agent_debate",
        "source": "Du et al. 2023",
        "tier_bridge": 0.25,
        "prompt": build_mad_prompt(question),
        "instruction": "Feed this prompt. Run 3 debate rounds. Report consensus or flag disagreement."
    }, indent=2))
