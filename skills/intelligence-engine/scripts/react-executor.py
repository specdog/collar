#!/usr/bin/env python3
'''
react-executor.py -- ReAct (Yao et al. 2022)
Reasoning + Acting interleaved. Model alternates thought steps and tool calls.
Usage: echo "task description" | python3 react-executor.py
'''
import sys, json

REACT_PROMPT = """REACT -- REASONING + ACTING INTERLEAVED

TASK: {task}

For each step, alternate between THOUGHT and ACTION:
THOUGHT: [reason about what you need to do next]
ACTION: [specific tool call or query to execute]
OBSERVATION: [result of the action]
...repeat until task is complete...

--- REACT LOOP ---
{loop_template}

--- FINAL ANSWER ---
[After sufficient observations, synthesize the answer]

CONFIDENCE: [1-10]
SOURCES CITED: [list what actions confirmed each claim]
"""

def build_react_prompt(task: str) -> str:
    loop = ''
    for i in range(1, 6):
        loop += f'Step {i}:\\n  THOUGHT: [reasoning]\\n  ACTION: [tool/query]\\n  OBSERVATION: [result]\\n\\n'
    return REACT_PROMPT.format(task=task[:8000], loop_template=loop)

if __name__ == '__main__':
    task = sys.stdin.read().strip()
    if not task:
        print(json.dumps({'error': 'no input'}))
        sys.exit(1)
    print(json.dumps({
        'technique': 'react',
        'source': 'Yao et al. 2022',
        'tier_bridge': 0.2,
        'prompt': build_react_prompt(task),
        'instruction': 'Feed this prompt to your LLM. Fill in all steps + final answer.'
    }, indent=2))
