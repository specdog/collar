# specdog/dotdog Monorepo Structure

## Location
- `/Users/dico/specdog` (NOT /Users/dico/dev/dotdog)
- Public repo: `specdog/dotdog`
- npm package: `dotdog` v0.3.5

## Architecture

```
specdog/
├── packages/
│   ├── dotdog/          ← THE SHIPPED PACKAGE (self-contained, npm)
│   │   ├── src/cli.ts   ← ALL commands + parser + grammar + serve inlined
│   │   ├── src/parser.ts ← OWN parser (diverged from spec-engine)
│   │   ├── src/grammar.ts
│   │   ├── src/index.ts  ← TF-IDF search index
│   │   ├── src/serve.ts  ← MCP server (built-in, no external deps)
│   │   └── kits/         ← erc20, nft, defi, hackathon
│   ├── spec-engine/     ← Internal shared lib (parser + types + zod schemas)
│   │   └── src/parser.ts ← DIFFERENT from dotdog's (no Prediction support)
│   ├── spec-cli/        ← ORIGINAL CLI, replaced by dotdog. Dead code.
│   └── spec-mcp/        ← Separate MCP server using @modelcontextprotocol/sdk
├── projects/spec-platform/ ← Dogfood specs (7 .dog files, 8 entities, 5 rels)
└── templates/            ← .dog file templates
```

## Key facts

1. **dotdog is self-contained by design** — ships as a single npm package. Has its own parser, grammar, CLI, and MCP server. No workspace dependencies. This is INTENTIONAL, not duplication.

2. **spec-engine parser ≠ dotdog parser** — They diverged. dotdog has Prediction support. spec-engine doesn't. Don't try to de-duplicate.

3. **spec-cli is dead** — Original platform CLI (June 12 morning). Replaced by dotdog rewrite (June 12 evening). Different dir layout (`specs/project/specs/`). Nothing imports it.

4. **spec-mcp compiles fine** — Uses `@modelcontextprotocol/sdk` + `zod`. Separate from dotdog's built-in MCP.

## Commands

```bash
# Run CLI (Bun required at ~/.bun/bin/bun)
PATH="$HOME/.bun/bin:$PATH" bun packages/dotdog/src/cli.ts <command>

# Build for npm
cd packages/dotdog && bun build src/cli.ts --outdir dist --target node

# Test (run from repo root)
bun test

# CI pipeline
node packages/dotdog/dist/cli.js --version
node packages/dotdog/dist/cli.js --help
node packages/dotdog/dist/cli.js validate
node packages/dotdog/dist/cli.js analyze
node packages/dotdog/dist/cli.js staleness
node packages/dotdog/dist/cli.js list
```

## Git
- NEVER commit/push to shared repos without asking
- Repo has pre-push hooks
