import fs from 'fs';
import os from 'os';
import path from 'path';

import { describe, it, expect } from 'bun:test';

import { createProvider } from './factory.js';
import { CodexProvider, resolveClaudeImports } from './codex.js';
import {
  type AppServer,
  STALE_THREAD_RE,
  attachCodexAutoApproval,
  startCodexTurn,
  writeCodexMcpConfigToml,
} from './codex-app-server.js';

function scratchDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'codex-imports-'));
}

describe('createProvider (codex)', () => {
  it('returns CodexProvider for codex', () => {
    expect(createProvider('codex')).toBeInstanceOf(CodexProvider);
  });

  it('flags stale thread errors as session-invalid', () => {
    const p = new CodexProvider();
    expect(p.isSessionInvalid(new Error('thread not found'))).toBe(true);
    expect(p.isSessionInvalid(new Error('unknown thread 123'))).toBe(true);
    expect(p.isSessionInvalid(new Error('No such thread: abc'))).toBe(true);
    expect(p.isSessionInvalid(new Error('thread_id not found'))).toBe(true);
  });

  it('does not flag unrelated errors as session-invalid', () => {
    const p = new CodexProvider();
    expect(p.isSessionInvalid(new Error('rate limit exceeded'))).toBe(false);
    expect(p.isSessionInvalid(new Error('connection reset'))).toBe(false);
    expect(p.isSessionInvalid(new Error('codex app-server exited: code=1'))).toBe(false);
    expect(p.isSessionInvalid(new Error('invalid thread_id shape'))).toBe(false);
  });

  it('declares no native slash command support', () => {
    const p = new CodexProvider();
    expect(p.supportsNativeSlashCommands).toBe(false);
  });
});

describe('codex app-server protocol helpers', () => {
  function fakeServer(onWrite?: (message: Record<string, unknown>, server: AppServer) => void): AppServer {
    const writes: string[] = [];
    const server = {
      process: {
        stdin: {
          write(line: string) {
            writes.push(line);
            const parsed = JSON.parse(line) as Record<string, unknown>;
            onWrite?.(parsed, server as AppServer);
            return true;
          },
        },
      },
      readline: { close() {} },
      pending: new Map(),
      notificationHandlers: [],
      serverRequestHandlers: [],
      writes,
    } as unknown as AppServer & { writes: string[] };
    return server;
  }

  it('sends turn/start text_elements plus model and effort overrides', async () => {
    let request: Record<string, unknown> | null = null;
    const server = fakeServer((message, appServer) => {
      request = message;
      const id = message.id as number;
      queueMicrotask(() => appServer.pending.get(id)?.resolve({ id, result: {} }));
    });

    await startCodexTurn(server, {
      threadId: 'thread-1',
      inputText: 'hello',
      model: 'gpt-test',
      effort: 'high',
      cwd: '/workspace/agent',
    });

    expect(request).toMatchObject({
      method: 'turn/start',
      params: {
        threadId: 'thread-1',
        input: [{ type: 'text', text: 'hello', text_elements: [] }],
        model: 'gpt-test',
        effort: 'high',
        cwd: '/workspace/agent',
      },
    });
  });

  it('responds to user-input and elicitation requests with generated protocol shapes', () => {
    const server = fakeServer();
    attachCodexAutoApproval(server);

    server.serverRequestHandlers[0]({
      id: 1,
      method: 'item/tool/requestUserInput',
      params: {},
    });
    server.serverRequestHandlers[0]({
      id: 2,
      method: 'mcpServer/elicitation/request',
      params: {},
    });

    expect(JSON.parse((server as AppServer & { writes: string[] }).writes[0])).toEqual({
      id: 1,
      result: { answers: {} },
    });
    expect(JSON.parse((server as AppServer & { writes: string[] }).writes[1])).toEqual({
      id: 2,
      result: { action: 'cancel', content: null, _meta: null },
    });
  });

  it('writes deterministic valid TOML for quoted MCP names and env keys', () => {
    const dir = scratchDir();
    const previousHome = process.env.HOME;
    process.env.HOME = dir;
    try {
      writeCodexMcpConfigToml({
        'server.with.dots': {
          command: '/bin/echo',
          args: ['hello "quoted"'],
          env: {
            'Z.KEY': 'last',
            'A KEY': 'first',
          },
        },
      });
      const toml = fs.readFileSync(path.join(dir, '.codex', 'config.toml'), 'utf-8');
      expect(toml).toContain('[mcp_servers."server.with.dots"]');
      expect(toml).toContain('command = "/bin/echo"');
      expect(toml).toContain('args = ["hello \\"quoted\\""]');
      expect(toml).toContain('[mcp_servers."server.with.dots".env]');
      expect(toml.indexOf('"A KEY" = "first"')).toBeLessThan(toml.indexOf('"Z.KEY" = "last"'));
    } finally {
      if (previousHome === undefined) delete process.env.HOME;
      else process.env.HOME = previousHome;
    }
  });

  it('keeps stale-thread detection narrow', () => {
    expect(STALE_THREAD_RE.test('thread_id not found')).toBe(true);
    expect(STALE_THREAD_RE.test('invalid thread_id shape')).toBe(false);
  });
});

describe('resolveClaudeImports', () => {
  it('inlines a single relative import', () => {
    const dir = scratchDir();
    fs.writeFileSync(path.join(dir, 'fragment.md'), 'FRAGMENT CONTENT');
    const resolved = resolveClaudeImports('before\n@./fragment.md\nafter', dir);
    expect(resolved).toContain('FRAGMENT CONTENT');
    expect(resolved).not.toContain('@./fragment.md');
    expect(resolved).toMatch(/before[\s\S]*FRAGMENT CONTENT[\s\S]*after/);
  });

  it('expands nested imports relative to the parent file', () => {
    const dir = scratchDir();
    fs.mkdirSync(path.join(dir, 'sub'));
    fs.writeFileSync(path.join(dir, 'sub', 'inner.md'), 'INNER');
    fs.writeFileSync(path.join(dir, 'sub', 'outer.md'), '@./inner.md');
    const resolved = resolveClaudeImports('@./sub/outer.md', dir);
    expect(resolved).toBe('INNER');
  });

  it('drops missing imports to empty text rather than leaving raw @path', () => {
    const dir = scratchDir();
    const resolved = resolveClaudeImports('before\n@./does-not-exist.md\nafter', dir);
    expect(resolved).not.toContain('@./does-not-exist.md');
    expect(resolved).toContain('before');
    expect(resolved).toContain('after');
  });

  it('breaks cycles', () => {
    const dir = scratchDir();
    fs.writeFileSync(path.join(dir, 'a.md'), '@./b.md');
    fs.writeFileSync(path.join(dir, 'b.md'), '@./a.md');
    // Just needs to terminate without a stack overflow.
    const resolved = resolveClaudeImports('@./a.md', dir);
    expect(typeof resolved).toBe('string');
  });

  it('leaves non-import @ mentions alone (only line-anchored @<path> is imported)', () => {
    const dir = scratchDir();
    const resolved = resolveClaudeImports('email @someone for details', dir);
    expect(resolved).toBe('email @someone for details');
  });
});
