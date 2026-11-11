#!/usr/bin/env bash
set -euo pipefail

ROOT="${CODEX_OPT_ROOT:-$PWD}"
CODEX_BIN="${CODEX_OPT_CODEX_BIN:-codex}"

exec "${CODEX_OPT_PYTHON_BIN:-python3}" -m dag_cli.codex_broker \
  --root "$ROOT" \
  --codex-bin "$CODEX_BIN" \
  -- "$@"
