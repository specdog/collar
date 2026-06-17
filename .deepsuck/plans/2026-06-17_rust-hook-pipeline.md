# Full Rust Hook Pipeline — Implementation Plan

**Goal:** Replace Python pre_llm_call hook + dag-router + fact-store with one Rust binary. <5ms, zero Python.

**Architecture:** `deepsuck-hooks --context` → outputs JSON `{"context": "DAG\nFACTS: ..."}`. Drop-in for pre-llm-call-intel.py.

**Current:** 3 Python processes = ~35ms
**Target:** 1 Rust binary = ~3ms

---

### Task 1: Add fact-store recall to Rust
- `dag-router-rust/src/facts.rs` — port fact-store.py recall
- Read ~/.deepsuck/facts.json, filter by keyword, return top 4

### Task 2: Combine DAG + facts into single output
- `main.rs` — add `--context` flag
- Output format: `{"context": "[ia]\nEntity→...\nFACTS: text | text"}`
- Python hook calls: `deepsuck-hooks --context --query "..." --cwd "..."`

### Task 3: Replace Python hook with Rust binary
- Update hook config to call Rust binary instead of Python
- Re-approve hook
- Remove pre-llm-call-intel.py

### Task 4: Add --store command
- Port fact-store.py --store to Rust
- Write facts to ~/.deepsuck/facts.json
- Remove fact-store.py Python dependency

### Task 5: Benchmark
- Speed: target <5ms (was 35ms)
- Output: identical context text
- Token count: unchanged (452 chars)

---

## Files
- `dag-router-rust/src/main.rs` — add --context, --store
- `dag-router-rust/src/facts.rs` — new module
- `~/.deepsuck/config.yaml` — update hook command

## Stays Python
- self-refine (API-bound, not CPU)
- transform hook (orchestrates API calls)
- metrics hooks (trivial, run rarely)
