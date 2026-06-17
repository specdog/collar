# Implemented Techniques (was: New Techniques Pipeline)

All 10 techniques are now implemented as of 2026-06-16. Status changed from
"researched" to "implemented" in the intelligence-amplifier.dag spec.

| # | Technique | Source | Script | Tier Bridge |
|---|-----------|--------|--------|-------------|
| 1 | ReAct | Yao et al. 2022, Princeton/DeepMind | react-executor.py | 0.20 |
| 2 | Graph of Thoughts | Besta et al. 2024, ETH Zurich | got-executor.py | 0.30 |
| 3 | Chain of Verification | Dhuliawala et al. 2024, Meta AI | cov-executor.py | 0.20 |
| 4 | Step-Back Prompting | Zheng et al. 2024, DeepMind | stepback-executor.py | 0.15 |
| 5 | CRITIC | Gou et al. 2024, Microsoft | critic-executor.py | 0.20 |
| 6 | Multi-Agent Debate | Du et al. 2023, MIT/Google | mad-executor.py | 0.25 |
| 7 | RAP (MCTS) | Hao et al. 2023, Microsoft | rap-executor.py | 0.25 |
| 8 | MemGPT | Packer et al. 2023, UC Berkeley | memgpt-executor.py | 0.20 |
| 9 | Auto-CoT | Zhang et al. 2022, Amazon | autocot-executor.py | 0.15 |
| 10 | Analogical Prompting | Yasunaga et al. 2024, DeepMind | analogical-executor.py | 0.15 |

**Total additional tier bridge:** 2.05
**Combined with existing 6 techniques:** 3.35 (target: 1.50 for Opus tier)

## Implementation Pattern

Each script follows the same pattern:
1. Read problem/task from stdin
2. Build a structured prompt template with explicit reasoning phases
3. Output JSON: `{technique, source, tier_bridge, prompt, instruction}`
4. The LLM consumes the prompt and fills in the reasoning phases

Scripts are in `~/.dag/skills/intelligence-engine/scripts/`.
All are standalone — `echo "input" | python3 script.py` for any of them.
