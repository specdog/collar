# Contributing

DAG-first. `Entity→Target:verb(card)`.

## Rules

1. **NEVER read `.dog`** — agents query `.dag` via the router
2. **DAG-path notation** — all behavioral guidance in compact format
3. **Compile before commit** — run `dag-regen.sh --all` after any `.md`/`.dog` change
4. **Test harness fallback** — simulate fresh install, verify constants load from `dags/`

## Project Structure

```
dag/
  agent/                    System prompt assembly
  tools/                    Skill loader + curator
  dags/                     13 default .dag files (shipped)
  .deepsuck/skills/         Skill DAGs (auto-generated)
  rust-dag-router/           Rust source for deepsuck-hooks binary
```

## Commit Conventions

```
feat: <description>
fix: <description>
docs: <description>
```

## Author

Justin DiClemente ([@logohere](https://github.com/logohere))
