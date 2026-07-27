import fs from 'fs';
import os from 'os';
import path from 'path';

import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';

const originalHome = process.env.HOME;
const tempHome = fs.mkdtempSync(path.join(os.tmpdir(), 'nanoclaw-mount-security-'));
const allowedRoot = path.join(tempHome, 'NanoAYX Knowledge Base');

beforeAll(() => {
  fs.mkdirSync(path.join(tempHome, '.config', 'nanoclaw'), { recursive: true });
  fs.mkdirSync(allowedRoot);
  fs.writeFileSync(
    path.join(tempHome, '.config', 'nanoclaw', 'mount-allowlist.json'),
    JSON.stringify({
      allowedRoots: [
        {
          path: allowedRoot,
          allowReadWrite: true,
          description: 'test knowledge base',
        },
      ],
      blockedPatterns: [],
    }),
  );
  process.env.HOME = tempHome;
  vi.resetModules();
});

afterAll(() => {
  if (originalHome === undefined) {
    delete process.env.HOME;
  } else {
    process.env.HOME = originalHome;
  }
  fs.rmSync(tempHome, { recursive: true, force: true });
});

describe('mount security', () => {
  it('allows an explicitly writable root at a nested relative container path', async () => {
    const { validateMount } = await import('./index.js');

    expect(
      validateMount({
        hostPath: allowedRoot,
        containerPath: 'knowledge/drive',
        readonly: false,
      }),
    ).toMatchObject({
      allowed: true,
      realHostPath: fs.realpathSync(allowedRoot),
      resolvedContainerPath: 'knowledge/drive',
      effectiveReadonly: false,
    });
  });
});
