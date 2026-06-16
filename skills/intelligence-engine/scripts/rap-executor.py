#!/usr/bin/env python3
"""
rap-executor.py -- Reasoning via Planning (Hao et al. 2023)
LLM as planner using Monte Carlo Tree Search over reasoning space.
Usage: echo "complex reasoning problem" | python3 rap-executor.py
"""
import sys, json

RAP_PROMPT = """RAP -- REASONING VIA PLANNING (MCTS)

PROBLEM: {problem}

Use Monte Carlo Tree Search to explore the reasoning space.
Each node is a reasoning state. Each edge is a reasoning step.
MCTS balances exploration (trying new paths) with exploitation (deepening promising paths).

--- MCTS REASONING TREE ---

ROOT: [problem state]

SELECTION - traverse from root, pick child with highest UCB:
  UCB = value + c * sqrt(ln(parent_visits) / node_visits)

EXPANSION - add a new reasoning step as a child node:
  NODE 1: [reasoning step] | Value: [0-1] | Visits: [N]
  NODE 2: [reasoning step] | Value: [0-1] | Visits: [N]
  NODE 3: [reasoning step] | Value: [0-1] | Visits: [N]

SIMULATION - roll out from new node to estimate value:
  From NODE 1: [quick reasoning to conclusion] -> Score: [0-1]
  From NODE 2: [quick reasoning to conclusion] -> Score: [0-1]
  From NODE 3: [quick reasoning to conclusion] -> Score: [0-1]

BACKPROPAGATION - update ancestors with simulation results:
  NODE 1 value updated: [new_value] | Visits: [N+1]
  NODE 2 value updated: [new_value] | Visits: [N+1]

--- AFTER MCTS SEARCH (budget: 50 simulations) ---
BEST PATH: [highest-value path from root to leaf]
BEST ANSWER: [conclusion from best path]
CONFIDENCE: [1-10]
SEARCH STATS: Nodes explored: [N] | Best value: [0-1] | Convergence: yes/no
"""

def build_rap_prompt(problem):
    return RAP_PROMPT.format(problem=problem[:8000])

if __name__ == "__main__":
    problem = sys.stdin.read().strip()
    if not problem:
        print(json.dumps({"error": "no input"}))
        sys.exit(1)
    print(json.dumps({
        "technique": "rap",
        "source": "Hao et al. 2023",
        "tier_bridge": 0.25,
        "prompt": build_rap_prompt(problem),
        "instruction": "Feed this prompt. Run MCTS over reasoning space. Return best path."
    }, indent=2))
