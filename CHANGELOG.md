# Changelog

## v1.0.0 — 2026-06-17

### Added
- DAG-first loading via `_load_dag_text()` with harness fallback
- 13 default `.dag` files shipped in `dags/` directory
- Skills curator auto-generates `SKILL.dag` on create/edit/patch
- Rust router (`deepsuck-hooks`) — 2ms `--facts`, 21k char `--context`
- `dag-regen.sh` regeneration script for batch DAG updates
- `PLATFORM_HINTS` parsed from DAG with Python dict fallback
- `SKILL.dag` priority check in `skill_view()` and `_serve_plugin_skill()`
- Single-file `.dog→.dag` compilation in dotdog (`compile foo.dog`)

### Changed
- `prompt_builder.py`: 82k→65k, fallback strings stripped, 13 constants DAG-first
- `skill_manager_tool.py`: `_regenerate_dag()` wired into create/edit/patch hooks
- `skills_tool.py`: SKILL.dag checked before SKILL.md in all load paths
- `system_prompt.py`: PLATFORM_HINTS loaded from DAG with built-in dict fallback

### Security
- Path traversal protection: hardcoded constant names, no user input in paths
- Content injection surface: DAG-path text only, no eval/exec/imports
- CI-safe: fresh install with zero `.dag` files → loads harness defaults, no crashes

### Author
Justin DiClemente ([@logohere](https://github.com/logohere))
