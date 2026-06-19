# AGENTS.md — collar

> Forked from NousResearch/hermes-agent. Rebuilt as DAG-first harness.

## Quick Start

**NEVER read prose config directly.** Query `.dag` files. `.dog` is human format. `.dag` is agent format. `.md` is last resort.

- **.dag**: always query first — source of truth. **NEVER modify without explicit user direction.**
- **.dog**: human writes, agent never touches
- **.md**: read for context only

## Key Rules

1. **DAG-first** — `Entity→Target:verb(card)` notation
2. **Zero deepsuck** — 6974+ refs renamed to `dag_*` / `collar_*`
3. **Skills auto-compile** — `_regenerate_dag()` fires on create/edit/patch
4. **Stripped fallbacks** — prompt_builder.py has no baked-in prose (82k→65k)
5. **Harness fallback** — `dags/` directory ships 13 defaults for CI/fresh installs

## Architecture

```
collar/
  agent/               System prompt assembly, model routing
  tools/               Skill loader, curator, file ops
  dags/                13 default .dag files
  dag_cli/             CLI commands, config, setup
  dag_constants.py     Config paths (~/.dag/)
  dag_state.py         SQLite session store
  dag-router            Rust binary (3ms context merge)
  rust-dag-router/     Rust source
```

## Commits

```
feat: <description>
fix: <description>
chore: <description>
refactor: <description>
```

## DAG Context Injection

Collar injects DAG-path context before every LLM call via the `pre-llm-call-intel.py` hook.
The compact format is token-optimized:

```
[abbreviated-dag-name]
Entity→Target:abbreviated_verb(card)>Target:verb(card)
```

**Format rules:**
- DAG names abbreviated to 2 chars: `deepsuck-harness` → `[dh]`
- Verbs abbreviated to 5 chars: `references` → `refer`
- `→` between entity and its edges, `>` between edges
- Cards compacted: `1:1`→`11`, `1:many`→`1m`, `many:many`→`mm`
- No `!` required markers, no `[verb]` brackets
- dotdog-compiled `.dag` files carry a pre-built `compact` field for zero-parse fast path

**Tests:** `pytest tests/test_dag_router.py`

## Attribution

Forked from NousResearch/hermes-agent. MIT license.
