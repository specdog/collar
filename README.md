# dag — DAG-first agent harness

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![Rust router](https://img.shields.io/badge/router-rust-orange)](https://github.com/specdog/dag)
[![DAG savings](https://img.shields.io/badge/dag-95%25_smaller-green)](https://github.com/specdog/dag)

> **Entity→Target:verb(card)** — ground truth via `.dag` files. Rust router at 3ms.

Created by **Justin DiClemente** ([@logohere](https://github.com/logohere)).

## Install

```bash
git clone https://github.com/specdog/dag.git
cd dag
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Requires Python >= 3.11. Rust router pre-compiled for macOS arm64.

## Quick Start

```bash
dag-router              # merged DAG context (system + skills + projects)
dag-router --facts      # project entities only (2ms)
dag-router --context    # full context for system prompt injection
```

## Architecture

Three layers, one format:

| Layer | Source | Format | Loader |
|-------|--------|--------|--------|
| System prompt | `dags/*.dag` (13 defaults) | DAG-path prose | `_load_dag_text()` |
| Skills | `skills/*/SKILL.dag` (auto-gen) | DAG-path prose | `skill_view()` |
| Projects | `*.dag` (dotdog compiled) | JSON v2/v3 | Rust router |

All `.dag` files use the same `Entity→Target:verb(card)` notation. The Rust router merges all three sources into one 21k char context block in 80ms (cold) / 3ms (warm).

## Key Features

- **DAG-first loading** — `_load_dag_text()` reads `.dag`, falls back to harness defaults shipped in `dags/`
- **Skills curator** — auto-generates `SKILL.dag` on `skill_manage` create/edit/patch (95% compression, 383k→17k)
- **Rust router** — single binary, 2ms `--facts`, 21k char `--context` merged from all sources
- **Stripped fallbacks** — 82k→65k in prompt_builder.py, no baked-in prose strings
- **CI-safe** — fresh clone with zero user `.dag` files → loads harness defaults, no crashes

## Commands

| Command | Description |
|---------|-------------|
| `dag-router` | Merged DAG context (system + skills + projects) |
| `dag-router --facts` | Project entity facts only (2ms) |
| `dag-router --all` | Full JSON debug output |
| `dag-regen.sh --skills` | Regenerate all SKILL.dag files |
| `dag-regen.sh --all` | Regenerate skills + system DAGs |

## File Formats

### `.dag` : Agent-First Graph

Plain text DAG-path notation. No JSON, no YAML. Parsed by humans and routers alike.

```
[memory]
Save→ Facts:durable(11), Prefs:always(11), Tasks:never(11)
Write→ Declare:fact(11), Instruct:never(11), Stale:never(11)
Recall→ Session:search(11), Proced:skills(11), State:forget(11)
```

### `.dog` : Human-Written Spec

Markdown prose. Humans write `.dog`. Agents read `.dag`. Never mix.

## Related

- [dotdog](https://github.com/specdog/dotdog) — `.dog` spec format + compiler
- [specdog](https://github.com/specdog) — the org
- [intelligence-amplifier](https://github.com/logohere/dag-harness) — DAG grounding engine
