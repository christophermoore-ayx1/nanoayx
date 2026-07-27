import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    alias: {
      'bun:test': new URL('./test/vitest-bun-test-shim.ts', import.meta.url).pathname,
    },
  },
  test: {
    // container/agent-runner tests run under Bun (they depend on bun:sqlite).
    // See container/agent-runner/package.json "test" script.
    include: [
      'src/**/*.test.ts',
      'setup/**/*.test.ts',
      'scripts/**/*.test.ts',
      'container/agent-runner/src/providers/codex.factory.test.ts',
    ],
  },
});
