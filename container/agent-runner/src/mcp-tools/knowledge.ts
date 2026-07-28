import { registerTools } from './server.js';
import type { McpToolDefinition } from './types.js';

const KNOWLEDGE_SERVICE_URL = (
  process.env.KNOWLEDGE_SERVICE_URL || 'http://nanoayx-knowledge:8787'
).replace(/\/+$/, '');

function ok(value: unknown) {
  return {
    content: [{ type: 'text' as const, text: JSON.stringify(value, null, 2) }],
  };
}

function err(message: string) {
  return {
    content: [{ type: 'text' as const, text: `Knowledge service error: ${message}` }],
    isError: true,
  };
}

async function request(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(`${KNOWLEDGE_SERVICE_URL}${path}`, {
    ...init,
    signal: AbortSignal.timeout(120_000),
    headers: {
      'content-type': 'application/json',
      ...init?.headers,
    },
  });
  const body = (await response.json()) as unknown;
  if (!response.ok) {
    const detail =
      typeof body === 'object' && body !== null && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return body;
}

export const knowledgeSearch: McpToolDefinition = {
  tool: {
    name: 'knowledge_search',
    description:
      'Search the shared NanoAYX Google Drive knowledge index. Results include source paths, Drive citations, and relevance scores.',
    inputSchema: {
      type: 'object' as const,
      properties: {
        query: { type: 'string', description: 'Question or semantic search query' },
        limit: {
          type: 'integer',
          description: 'Maximum results, from 1 to 20 (default 5)',
          minimum: 1,
          maximum: 20,
        },
      },
      required: ['query'],
    },
  },
  async handler(args) {
    const query = String(args.query || '').trim();
    if (!query) return err('query is required');
    try {
      return ok(
        await request('/search', {
          method: 'POST',
          body: JSON.stringify({ query, limit: Number(args.limit) || 5 }),
        }),
      );
    } catch (error) {
      return err(error instanceof Error ? error.message : String(error));
    }
  },
};

export const knowledgeIngest: McpToolDefinition = {
  tool: {
    name: 'knowledge_ingest',
    description: 'Run an incremental scan of the shared NanoAYX knowledge folders.',
    inputSchema: { type: 'object' as const, properties: {} },
  },
  async handler() {
    try {
      return ok(await request('/ingest', { method: 'POST' }));
    } catch (error) {
      return err(error instanceof Error ? error.message : String(error));
    }
  },
};

export const knowledgeStats: McpToolDefinition = {
  tool: {
    name: 'knowledge_stats',
    description: 'Report the shared knowledge index health, indexed documents, and embedding model.',
    inputSchema: { type: 'object' as const, properties: {} },
  },
  async handler() {
    try {
      return ok(await request('/stats'));
    } catch (error) {
      return err(error instanceof Error ? error.message : String(error));
    }
  },
};

export const knowledgeWriteOutput: McpToolDefinition = {
  tool: {
    name: 'knowledge_write_output',
    description:
      'Write a Markdown or text artifact beneath the shared Google Drive 40 Generated folder.',
    inputSchema: {
      type: 'object' as const,
      properties: {
        relative_path: {
          type: 'string',
          description: 'Safe relative path beneath 40 Generated, ending in .md or .txt',
        },
        content: { type: 'string', description: 'Artifact content' },
      },
      required: ['relative_path', 'content'],
    },
  },
  async handler(args) {
    const relativePath = String(args.relative_path || '').trim();
    const content = String(args.content || '');
    if (!relativePath || !content) return err('relative_path and content are required');
    try {
      return ok(
        await request('/outputs', {
          method: 'POST',
          body: JSON.stringify({ relative_path: relativePath, content }),
        }),
      );
    } catch (error) {
      return err(error instanceof Error ? error.message : String(error));
    }
  },
};

registerTools([knowledgeSearch, knowledgeIngest, knowledgeStats, knowledgeWriteOutput]);
