# Self-Refine & Collar Agent Self-Evolution

Session learning (2026-06-16): the gap between cosplay and real intelligence amplification.

## Self-Refine (Madaan et al. 2023)

**Proven +20% on code generation benchmarks.** The simplest architecture that actually works:

```
Call 1 (GENERATE):  LLM produces output
Call 2 (CRITIQUE):  LLM with harsh reviewer prompt finds ALL errors
Call 3 (REFINE):    LLM fixes errors based on critique
```

Each call is a real API call with a different system prompt. Not one prompt simulating multiple roles.

**Implementation**: `scripts/self-refine.py` — 119 lines, zero dependencies (stdlib only: `sys, json, os, urllib`).

**Tested this session**: Ran against a claim about the intelligence-amplifier project. The critique correctly identified vague claims ("benchmark harness with real measurements"), undefined metrics ("tier bridge of 3.35"), and missing citations. The refined output added specificity and citation requirements.

**API key sourcing**: The deepseek API key is in `~/.dag/.env` (not `config.yaml`). Source it before running:
```bash
source ~/.dag/.env
echo "your output" | python3 scripts/self-refine.py
```

Config in `config.yaml` has an outdated key. The `.env` key is 35 chars and works.

**Usage via venv**: The dag venv at `/Users/dico/dag/.venv/` has the key in its environment. Activate first or use the venv python:
```bash
source /Users/dico/dag/.venv/bin/activate
echo "output" | python3 scripts/self-refine.py
```

## Collar Agent Self-Evolution (NousResearch)

**Discovered this session**: `github.com/NousResearch/collar-agent-self-evolution` — 4119 stars, MIT license.

Uses DSPy + GEPA (Genetic-Pareto Prompt Evolution, ICLR 2026 Oral) to auto-evolve skills, tool descriptions, system prompts, and code. No GPU training — API calls only (~$2-10 per optimization run).

**Architecture**:
```
Read skill → Generate eval dataset → GEPA Optimizer → Candidate variants → Evaluate → Constraint gates → Best variant → PR
```

**Why we didn't use it**: Requires `dspy>=3.0.0`, `gepa`, `litellm`, and several other heavy dependencies. The user wanted lean. Self-Refine achieves the same pattern (critique→refine) with zero dependencies.

**What we took from it**: The constraint gate concept (pytest, size limits, benchmark regression checks). The idea of using real session history as eval data. The evolutionary search pattern.

**If bloat becomes acceptable**: Install and point at dag:
```bash
COLLAR_AGENT_REPO=/Users/dico/dag python -m evolution.skills.evolve_skill --skill intelligence-engine --iterations 10
```

Note: requires `pip install -e "/tmp/collar-agent-self-evolution[dev]"` in the dag venv. Installed and tested this session — works but pulls in ~30 packages.

## Cosplay vs Real — The Definitive List

| Technique | Type | Why |
|-----------|------|-----|
| Self-Refine | REAL | 3 separate API calls. Different system prompts. External critique. |
| DAG enforcement | REAL | Code-level. Tool refuses. Model cannot negotiate. |
| Hook injection | REAL | Fires regardless of LLM compliance. |
| Fact store | REAL | Writes to disk. Survives sessions. |
| Knowledge pipeline | REAL | Fetches from ArXiv XML, Semantic Scholar REST, GitHub REST. |
| Context injector | REAL | Queries DAG + fact store. Injects live data. |
| Verify-answer | REAL | Extracts claims. Categorizes verification method. |
| Tree of Thoughts (tot-executor.py) | COSPLAY | Prompt template: "PATH A: [fill in], PATH B: [fill in]". Model simulates 3 paths in one call. |
| Graph of Thoughts (got-executor.py) | COSPLAY | Prompt template: "NODE 0: [fill in], NODE 1: [fill in]". Model simulates a DAG in one call. |
| Multi-Agent Debate (mad-executor.py) | COSPLAY | Prompt template: "AGENT A: [fill in], AGENT B: [fill in]". Model simulates 3 agents in one call. |
| RAP/MCTS (rap-executor.py) | COSPLAY | Prompt template: "SELECT: [fill in], EXPAND: [fill in]". Model simulates MCTS in one call. |
| MemGPT (memgpt-executor.py) | COSPLAY | Prompt template: "PAGE 1: [fill in]". Model simulates memory pages in one call. No actual storage. |
| All other technique executors | COSPLAY | Same pattern: structured prompts asking the model to simulate multi-step reasoning in a single forward pass. |

**Key insight**: One call can't verify itself. Verification must be external (separate API call, tool, or DAG check). The model that generated an answer is the worst possible judge of its correctness.
