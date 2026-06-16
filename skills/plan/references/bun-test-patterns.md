# Bun Test Patterns — dotdog

## CLI integration tests with `$`

```typescript
import { describe, test, expect } from 'bun:test';
import { $ } from 'bun';

const BUN = '/Users/dico/.bun/bin/bun';  // absolute path required

describe('CLI', () => {
  test('smoke', async () => {
    // CRITICAL: separate interpolations for binary vs each arg
    // `${BUN} cli.ts --version` would quote the whole thing as one command
    const out = await $`${BUN} packages/dotdog/src/cli.ts --version`.text();
    expect(out.trim()).toMatch(/^\d+\.\d+\.\d+/);
  });
});
```

## Parser unit tests

Tests must live inside the package directory for module resolution:
- Correct: `packages/dotdog/__tests__/parser.test.ts` → `import from '../src/parser'`
- Wrong: `/tmp/test.ts` → can't resolve `./packages/dotdog/src/parser`

## Parser gotcha

Files without `##` headings cause root section to capture ALL blocks, doubling entity counts.
Always include a `##` heading in test fixtures when testing structured blocks.

## Snapshot testing

Bun supports `expect(value).toMatchSnapshot()`. First run with `--update-snapshots` to generate.
Snapshots stored in `__snapshots__/` alongside test files.
