# collar — DAG-first agent harness

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![DAG savings](https://img.shields.io/badge/dag-95%25_smaller-green)](https://github.com/specdog/collar)

> **Entity→Target:verb(card)** — ground truth via `.dag` files.

Created by **Justin DiClemente** ([@logohere](https://github.com/logohere)) under [specdog](https://github.com/specdog).

Forked from NousResearch/hermes-agent. Rebuilt as a DAG-first harness.

## Install

```bash
git clone https://github.com/specdog/collar.git
cd collar
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Requires Python >= 3.11.

## Quick Start

```bash
collar              # interactive chat
collar chat -q "..." # single query
collar setup         # first-time setup wizard
```

## Architecture

| Layer | Source | Format | Loader |
|-------|--------|--------|--------|
| System prompt | `dags/*.dag` (13 defaults) | DAG-path plain text | `_load_dag_text()` |
| Skills | `skills/*/SKILL.dag` (auto-gen) | DAG-path plain text | `skill_view()` |
| Projects | `*.dag` (dotdog compiled) | JSON v2/v3 | MCP dotdog |

## Key Numbers

- **95%** compression: 383k → 17k (skills)
- **74%** compression: 15k → 4k (system prompt)
- **0** deepsuck refs: 6974+ renamed

## Related

- [dotdog](https://github.com/specdog/dotdog) — `.dog` spec format + compiler
- [specdog](https://github.com/specdog) — the org

## Dogfood

Collar's own behavioral guidance is written in `.dog` and compiled to `.dag` via dotdog:

```
dags/*.dog   →  dotdog compile  →  dags/*.dag   →  collar loads
```

The harness that reads `.dag` files uses `.dag` files itself.
