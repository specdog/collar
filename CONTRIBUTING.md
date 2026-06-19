# Contributing

DAG-first. `Entity→Target:verb(card)`.

## Rules

1. **Query `.dag` first** — agent behavior comes from `.dag` routes, not prose
2. **Keep dotdog in the loop** — compile/spec changes through the dotdog path
3. **Use the PR template** — every PR should use `.github/pull_request_template.md`
4. **DAG-path notation** — all behavioral guidance in compact format
5. **Compile before commit** — run `dag-regen.sh --all` after any `.md`/`.dog` change
6. **Test harness fallback** — simulate fresh install, verify constants load from `dags/`

## Project Structure

```
dag/
  agent/                    System prompt assembly
  tools/                    Skill loader + curator
  dags/                     13 default .dag files (shipped)
  .dag-harness/skills/         Skill DAGs (auto-generated)
  rust-dag-router/           Rust source for dag-router binary
```

## Commit Conventions

```
feat: <description>
fix: <description>
docs: <description>
```

## Author

Justin DiClemente ([@logohere](https://github.com/logohere))
