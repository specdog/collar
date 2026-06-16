#!/usr/bin/env python3
"""
stepback-executor.py -- Step-Back Prompting (Zheng et al. 2024)
Abstract before diving in. Ask broader principles first.
Usage: echo "specific problem" | python3 stepback-executor.py
"""
import sys, json

STEPBACK_PROMPT = """STEP-BACK PROMPTING -- ABSTRACT THEN DIVE

SPECIFIC PROBLEM: {problem}

--- STEP 1: STEP BACK - IDENTIFY BROADER PRINCIPLES ---
What is the general category of this problem?
PRINCIPLE 1: [broader concept or pattern this problem belongs to]
PRINCIPLE 2: [another relevant general principle]
PRINCIPLE 3: [underlying concept that governs solutions]

--- STEP 2: GENERAL SOLUTION PATTERNS ---
For each principle, what are the known solution approaches?
PRINCIPLE 1 -> APPROACHES: [list solution patterns]
PRINCIPLE 2 -> APPROACHES: [list solution patterns]
PRINCIPLE 3 -> APPROACHES: [list solution patterns]

--- STEP 3: APPLY GENERAL PRINCIPLES TO SPECIFIC PROBLEM ---
APPLICATION: [how principle 1 solves the specific problem]
APPLICATION: [how principle 2 solves the specific problem]
APPLICATION: [how principle 3 solves the specific problem]

--- STEP 4: SPECIFIC SOLUTION ---
SOLUTION: [the concrete answer, grounded in general principles]
WHY IT WORKS: [causal chain from principle to solution]
CONFIDENCE: [1-10]
"""

def build_stepback_prompt(problem):
    return STEPBACK_PROMPT.format(problem=problem[:8000])

if __name__ == "__main__":
    problem = sys.stdin.read().strip()
    if not problem:
        print(json.dumps({"error": "no input"}))
        sys.exit(1)
    print(json.dumps({
        "technique": "stepback_prompting",
        "source": "Zheng et al. 2024",
        "tier_bridge": 0.15,
        "prompt": build_stepback_prompt(problem),
        "instruction": "Feed this prompt. Abstract first, then apply general principles."
    }, indent=2))
