# dag — DAG-first agent harness

`Entity→Target:verb(card)` — ground truth via `.dag` files, Rust router at 3ms.

Created by **Justin DiClemente** ([@logohere](https://github.com/logohere)).

## What it is

A modified fork of [Deepsuck Agent](https://github.com/NousResearch/deepsuck-agent) that replaces verbose prose system prompts with compact DAG-path notation. All behavioral guidance lives in `.dag` files (13 shipped as defaults), loaded at 3ms by a Rust binary.

## Key changes

- **DAG-first loading**: `_load_dag_text()` reads `.dag` files, falls back to harness defaults
- **Skills curator**: auto-generates `SKILL.dag` on create/edit/patch (95% compression)
- **Rust router**: 2ms `--facts`, 21k char `--context` merged from system + skills + projects
- **Stripped fallbacks**: 82k→65k in prompt_builder.py

## Install

```bash
git clone https://github.com/specdog/dag.git
cd dag
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Related

- [dotdog](https://github.com/specdog/dotdog) — `.dog` spec format
- [specdog](https://github.com/specdog) — the org
