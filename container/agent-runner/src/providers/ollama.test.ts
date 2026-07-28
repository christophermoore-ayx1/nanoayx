import { afterEach, describe, expect, it, mock } from 'bun:test';

import { OllamaProvider } from './ollama.js';

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe('OllamaProvider', () => {
  it('returns local chat text without exposing tools', async () => {
    globalThis.fetch = mock(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const request = JSON.parse(String(init?.body)) as {
        model: string;
        stream: boolean;
        messages: Array<{ role: string; content: string }>;
      };
      expect(request.model).toBe('lfm2.5:8b');
      expect(request.stream).toBe(false);
      expect(request.messages).toEqual([
        { role: 'system', content: 'Summarize accurately.' },
        { role: 'user', content: 'A long report' },
      ]);
      return new Response(JSON.stringify({ message: { content: '<think>private</think>Short summary' } }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    }) as typeof fetch;

    const provider = new OllamaProvider({ model: 'lfm2.5:8b' });
    const query = provider.query({
      prompt: 'A long report',
      cwd: '/workspace/agent',
      systemContext: { instructions: 'Summarize accurately.' },
    });
    query.end();

    const events = [];
    for await (const event of query.events) events.push(event);

    expect(events.some((event) => event.type === 'result' && event.text === 'Short summary')).toBe(true);
  });

  it('surfaces Ollama failures as retryable provider errors', async () => {
    globalThis.fetch = mock(
      async () =>
        new Response(JSON.stringify({ error: 'model unavailable' }), {
          status: 503,
          headers: { 'content-type': 'application/json' },
        }),
    ) as typeof fetch;

    const provider = new OllamaProvider();
    const query = provider.query({ prompt: 'summarize', cwd: '/workspace/agent' });
    query.end();

    const events = [];
    for await (const event of query.events) events.push(event);

    expect(
      events.some(
        (event) =>
          event.type === 'error' &&
          event.retryable === true &&
          event.message === 'model unavailable',
      ),
    ).toBe(true);
  });
});
