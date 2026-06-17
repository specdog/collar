# dag-router Rust Rewrite — Implementation Plan

> **For Deepsuck:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Rewrite dag-router.py core DAG parsing and compaction logic in Rust for <10ms startup, zero Python dependency, embeddable.

**Architecture:** Single Rust binary that reads .dag JSON files, filters/scopes entities, and outputs compact DAG-path text (or JSON with --all). Drop-in replacement for `python3 dag-router.py`.

**Current:** Python subprocess → ~80ms per invocation
**Target:** Rust binary → ~5ms

---

### Task 1: Scaffold Rust project
```
cd /Users/dico/deepsuck && cargo init dag-router-rust --name dag-router
# Add serde_json to Cargo.toml
# Hello-world main.rs
# cargo run → prints "dag-router rust"
```

### Task 2: DAG file discovery
- Replicate `find_all_dags()` — scan ~/deepsuck/projects, ~/projects, ~/specdog/projects
- Read directory entries, find `{name}/{name}.dag` files
- Skip SKIP_DAGS = {"deepsuck-harness"}

### Task 3: Parse .dag JSON → Entity struct
```rust
struct Entity {
    dag: String,
    name: String,
    edges: Vec<String>,  // "Target→verb(card)" format
}
```
- Handle both positional array format (deepsuck-harness) and dict format (intelligence-amplifier)
- Build ID→name map for edge resolution
- compact_card(): "1:many" → "1m", "many:many" → "mm"

### Task 4: Edge cap + sort
- Filter entities with 0 edges
- Sort by edge count descending
- Cap at MAX_ENTITIES (8)
- Cap edges per entity at MAX_EDGES (5)

### Task 5: Compact output
- Group by DAG, abbreviate headers: intelligence-amplifier → [ia]
- Abbreviate verbs to 5 chars: wired_through→wired, poll→polls
- Format: `Entity→ Target:verb(card), Target:verb(card)`
- Replicate dedup_edges() — filter dead-end edges

### Task 6: CLI args
```
dag-router --cwd /path --query "text" --all
```
- --cwd: scope DAGs to current project
- --query: keyword match (OR matching)
- --all: JSON output (for debugging)
- Default: compact text output

### Task 7: Replace hook call
- Update pre-llm-call-intel.py DAG_ROUTER path to Rust binary
- Build release: `cargo build --release`
- Verify output matches Python exactly
- Measure: `time` should show <10ms total

---

## Verification
- [ ] Entity count matches Python dag-router --all
- [ ] Compact output chars match Python
- [ ] --cwd scoping identical
- [ ] --all JSON structure identical
- [ ] Release binary sub-5ms
