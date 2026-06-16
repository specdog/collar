#!/usr/bin/env python3
"""
memgpt-executor.py -- MemGPT (Packer et al. 2023)
LLM as operating system with virtual memory management for unbounded context.
Usage: echo "context to manage" | python3 memgpt-executor.py
"""
import sys, json

MEMGPT_PROMPT = """MEMGPT -- VIRTUAL MEMORY MANAGEMENT

CURRENT TASK: {task}

Manage context as virtual memory. Keep working memory small (<2000 tokens).
Offload less-relevant context to external storage. Retrieve on demand.

--- MEMORY HIERARCHY ---

MAIN MEMORY (working set, <2000 tokens):
  [Current task context, recent observations, active reasoning]

EXTERNAL MEMORY (offloaded, retrieved on demand):
  PAGE 1: [topic/summary] -- last accessed: [timestamp] -- relevance: [0-1]
  PAGE 2: [topic/summary] -- last accessed: [timestamp] -- relevance: [0-1]
  PAGE 3: [topic/summary] -- last accessed: [timestamp] -- relevance: [0-1]

--- MEMORY OPERATIONS ---

PAGE FAULT: When information is needed but not in main memory:
  RETRIEVE: [page_id] because [reason]

EVICTION: When main memory is full, evict least-recently-used:
  EVICT: [page_id] -> external memory as PAGE [N+1]

STORE: Save new information:
  STORE: [content summary] as PAGE [N+1]

--- CURRENT REASONING ---
[Work with main memory contents. Request pages as needed.]

MAIN MEMORY CONTENTS:
{main_memory}

PAGE FAULTS THIS TURN:
  [list of pages retrieved]

EVICTIONS THIS TURN:
  [list of pages evicted]

--- FINAL ANSWER ---
[Answer synthesized from all retrieved context]
CONFIDENCE: [1-10]
PAGES USED: [list of page IDs consulted]
"""

def build_memgpt_prompt(task):
    return MEMGPT_PROMPT.format(task=task[:8000], main_memory="[Initialize with relevant context]")

if __name__ == "__main__":
    task = sys.stdin.read().strip()
    if not task:
        print(json.dumps({"error": "no input"}))
        sys.exit(1)
    print(json.dumps({
        "technique": "memgpt",
        "source": "Packer et al. 2023",
        "tier_bridge": 0.2,
        "prompt": build_memgpt_prompt(task),
        "instruction": "Feed this prompt. Manage context as virtual memory pages."
    }, indent=2))
