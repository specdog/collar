# Plan Failure: dotdog Debug & Test Plan (June 16, 2026)

## What happened

User asked for a plan to debug and test the specdog/dotdog monorepo. I wrote a plan with 10 tasks that was fundamentally wrong because I made claims without verifying them.

## Wrong claims I made

1. **"Parser duplicated twice"** — I assumed dotdog/src/parser.ts and spec-engine/src/parser.ts were copies. They are NOT. They diverged: dotdog's has Prediction support, different section parsing, different lifecycle handling. A `diff` would have shown this immediately.

2. **"spec-mcp doesn't compile"** — I didn't try to compile it. Running `bun run --check` showed it compiles fine, exit 0.

3. **"CLI duplicated — dotdog vs spec-cli"** — spec-cli is the ORIGINAL codebase (commits #1-11, June 12 morning). dotdog was a ground-up rewrite (commits #123+, June 12 evening). spec-cli uses spec-engine as a shared lib. dotdog is self-contained. They're different implementations with different directory layouts.

4. **"spec-mcp broken"** — It exists and compiles. It's just a separate MCP server using the MCP SDK (not the same as dotdog's built-in serve command).

## What I should have done

Before writing the plan:
1. `diff` the two parsers
2. `grep -rn` to find what imports what
3. `git log` to understand the timeline
4. Attempt to compile/run spec-mcp
5. Actually read the CI config to see what it tests

## Root cause

I saw similar filenames (parser.ts, grammar.ts, cli.ts) across packages and assumed duplication. The repo has an intentional architecture: dotdog is the self-contained npm package, spec-engine is the internal shared lib, spec-cli is the original (replaced) CLI. The apparent duplication is by design for npm publishing.

## Lesson

**Verify before claiming.** Every factual statement in a plan must be backed by tool output. If you can't verify it with a command, don't write it in the plan.
