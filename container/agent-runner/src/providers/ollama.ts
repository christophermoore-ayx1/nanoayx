/**
 * Minimal local Ollama provider for low-complexity text work.
 *
 * This provider intentionally does not expose MCP tools to the model. It is
 * suitable for delegated summarization, classification, extraction, and
 * drafting where the complete input is present in the prompt. Tool-heavy or
 * complex work belongs on the Codex provider.
 */
import { registerProvider } from './provider-registry.js';
import type { AgentProvider, AgentQuery, ProviderEvent, ProviderOptions, QueryInput } from './types.js';

interface OllamaChatResponse {
  message?: {
    content?: string;
    thinking?: string;
  };
  error?: string;
}

function ollamaUrl(): string {
  return (process.env.OLLAMA_BASE_URL || 'http://host.docker.internal:11434').replace(/\/+$/, '');
}

export function stripThinking(text: string): string {
  return text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
}

async function chat(model: string, input: QueryInput, prompt: string, signal: AbortSignal): Promise<string> {
  const messages: Array<{ role: 'system' | 'user'; content: string }> = [];
  if (input.systemContext?.instructions) {
    messages.push({ role: 'system', content: input.systemContext.instructions });
  }
  messages.push({ role: 'user', content: prompt });

  const response = await fetch(`${ollamaUrl()}/api/chat`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      model,
      messages,
      stream: false,
      think: false,
      keep_alive: '10m',
    }),
    signal,
  });
  const body = (await response.json()) as OllamaChatResponse;
  if (!response.ok || body.error) {
    throw new Error(body.error || `Ollama returned HTTP ${response.status}`);
  }
  const text = stripThinking(body.message?.content || '');
  if (!text) throw new Error('Ollama returned an empty response');
  return text;
}

export class OllamaProvider implements AgentProvider {
  readonly supportsNativeSlashCommands = false;

  private readonly model: string;

  constructor(options: ProviderOptions = {}) {
    this.model = options.model || process.env.OLLAMA_MODEL || 'lfm2.5:8b';
  }

  isSessionInvalid(): boolean {
    return false;
  }

  query(input: QueryInput): AgentQuery {
    const pending = [input.prompt];
    const controller = new AbortController();
    let waiting: (() => void) | null = null;
    let ended = false;
    let aborted = false;
    const model = this.model;

    const events: AsyncIterable<ProviderEvent> = {
      async *[Symbol.asyncIterator]() {
        yield { type: 'init', continuation: `ollama-stateless-${Date.now()}` };
        while (!aborted) {
          while (pending.length === 0 && !ended && !aborted) {
            await new Promise<void>((resolve) => {
              waiting = resolve;
            });
            waiting = null;
          }
          if (aborted || (ended && pending.length === 0)) return;

          const prompt = pending.shift()!;
          yield { type: 'activity' };
          try {
            const text = await chat(model, input, prompt, controller.signal);
            yield { type: 'activity' };
            yield { type: 'result', text };
          } catch (error) {
            if (aborted) return;
            yield {
              type: 'error',
              message: error instanceof Error ? error.message : String(error),
              retryable: true,
              classification: 'ollama',
            };
          }
        }
      },
    };

    return {
      push(message: string) {
        pending.push(message);
        waiting?.();
      },
      end() {
        ended = true;
        waiting?.();
      },
      abort() {
        aborted = true;
        controller.abort();
        waiting?.();
      },
      events,
    };
  }
}

registerProvider('ollama', (options) => new OllamaProvider(options));
