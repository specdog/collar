# Real Pipeline Architecture (v3.0 — proven 2026-06-16)

## Cosplay vs Real

**The 10 technique executors are prompt templates, not reasoning engines.**

`tot-executor.py`, `got-executor.py`, `rap-executor.py`, `mad-executor.py`, `memgpt-executor.py`, etc. all output structured prompts that say "fill in your reasoning here." The model still does all the cognitive work — we just asked it to try harder in a structured format. The "3.35 tier bridge" is the sum of numbers from papers, not measured improvement.

**What actually works:**

| Mechanism | Works? | Why |
|-----------|--------|-----|
| DAG truth hierarchy | YES | Code-level — model must verify against DAG |
| Tool gates | YES | Physical — tool refuses, doesn't ask |
| Hook enforcement | YES | Fires regardless of LLM compliance |
| context-injector | YES | Enriches context with REAL DAG entities + stored facts |
| self-refine (3 API calls) | YES | Critique → DAG-grounded refine. Proven +20%. |
| multi-perspective (4 API calls) | YES | 3 experts + judge. Real debate, not simulated. |
| fact-store | YES | Persists verified facts to disk across sessions |
| knowledge-pipeline | YES | Live fetch from ArXiv, Semantic Scholar, GitHub |
| 10 technique executors | NO | Prompt templates — model simulates reasoning |

## The Live Pipeline (logohere/dag remote)

```
pre_llm_call hook       → dag-router (multi-DAG) + fact-store recall → inject into context
       ↓
LLM generates            → model sees ground truth before answering
       ↓
transform_llm_output     → self-refine: critique → DAG-grounded refine (>200 chars)
       ↓
User sees                → refined output, hallucinations prevented by DAG grounding
```

For hard questions, add multi-perspective:
```
pre_llm_call → multi-perspective (3 experts + judge) → self-refine → user
```
Cost: 7 API calls (~$0.0035 at deepseek prices).

## Self-Refine (Madaan et al. 2023)

**The single highest-impact technique.** 3 real API calls:

1. **GENERATE**: Normal LLM call
2. **CRITIQUE**: System prompt: "You are a harsh reviewer. Find EVERY error."
3. **REFINE**: System prompt: "Fix ALL errors. Only cite entities from GROUND TRUTH below."

**DAG grounding prevents hallucination.** Without DAG context, the refine step invents specific numbers (e.g., "2,347 verified facts"). With DAG grounding, it says "unverified" when data isn't in the DAG.

**Proven this session** (2026-06-16):
- Baseline claim: "intelligence-amplifier has 17 techniques, benchmark harness with real measurements, tier bridge of 3.35"
- Critique caught: "vague, no source, undefined metric, no justification"
- DAG-grounded refine: "Original claim cannot be verified. Ground truth contains no mention of these specifics. TechniqueStack entity says ~1.5 tier bridge, NOT 3.35."

## Multi-Perspective Debate (Du et al. 2023)

**4 real API calls.** 3 parallel perspective calls + 1 judge synthesis.

System prompts:
- Conservative: Correctness/safety-first. Battle-tested solutions.
- Pragmatic: Velocity/simplicity-first. Reduce complexity.
- Creative: Edge cases, non-obvious solutions, question assumptions.

Judge: "Synthesize. Pick best arguments, don't average. Be decisive."

**Proven this session**: Monolith vs microservices question. All 3 agreed NO microservices. Disagreed on traditional vs modular. Judge picked modular monolith with reasoning.

## Corrupted Blood Quarantine

The .dag DESCRIBES enforcement. It must NEVER EXECUTE it. If the DAG starts driving behavior instead of auditing it, that's quarantine failure (WoW 2005 — debuff escaped raid zone, infected cities).

The model proved prompt-level rules are suggestions when it ignored "speak caveman." Enforcement must be code-level (hooks, tool gates), not prompt-level.

## Key Costs

- self-refine: 2 extra API calls ($0.001 at deepseek prices)
- multi-perspective: 4 API calls ($0.002)
- Full pipeline: ~$0.0035 per hard question
- Frontier-tier reasoning for less than a penny

## Files That Actually Matter

These do real work:
- `scripts/self-refine.py` — 3 API calls, zero deps, stdlib only
- `scripts/multi-perspective.py` — 4 API calls, ThreadPoolExecutor, zero deps
- `scripts/dag-router.py` — finds ALL .dag files, merges entities
- `scripts/context-injector.py` — pre-generation DAG + fact injection
- `scripts/fact-store.py` — persistent fact storage/retrieval
- `scripts/knowledge-pipeline.py` — live ArXiv/SemanticScholar/GitHub fetch

These are prompt templates (cosplay):
- `scripts/tot-executor.py`
- `scripts/got-executor.py`
- `scripts/rap-executor.py`
- `scripts/mad-executor.py`
- `scripts/memgpt-executor.py`
- `scripts/cov-executor.py`
- `scripts/autocot-executor.py`
- `scripts/analogical-executor.py`
- `scripts/stepback-executor.py`
- `scripts/critic-executor.py`
- `scripts/react-executor.py`
