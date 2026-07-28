# NanoAYX Knowledge Base

## Boundary

Google Drive is the canonical source and human-readable output boundary:

```text
Name: NanoAYX Knowledge Base
Folder ID: 1B5BMKeFQiSquksNZh9J8iAam3Cl40CS8
URL: https://drive.google.com/drive/folders/1B5BMKeFQiSquksNZh9J8iAam3Cl40CS8
Host: /Users/christopher.moore/Library/CloudStorage/GoogleDrive-christopher.moore@alteryx.com/My Drive/NanoAYX Knowledge Base
```

```text
NanoAYX Knowledge Base/
  00 Inbox/
  10 Sources/
  20 Notes/
  30 Projects/
  40 Generated/
  90 Archive/
```

The scanner reads the source folders. API and MCP writes are restricted to
Markdown or text files beneath `40 Generated`.

## Service

`services/knowledge` is a FastAPI service deployed by the root `compose.yaml`.
It:

- scans configured folders on startup and every five minutes;
- hashes files for incremental re-indexing;
- extracts plain text, Markdown, PDF, and DOCX content;
- chunks text and calls host Ollama's `/api/embed`;
- stores documents, chunks, vectors, and errors in SQLite;
- removes records for deleted files;
- returns source paths, Drive item IDs when available, and Drive URLs;
- writes generated files atomically within `40 Generated`.

The service listens only on `127.0.0.1:8787` from the host and is reachable by
agent containers as `http://nanoayx-knowledge:8787` on `nanoayx-runtime`.

## Deploy

Create the ignored local configuration from
`config/knowledge.env.example`, then:

```bash
docker compose --env-file .env.knowledge build knowledge
docker compose --env-file .env.knowledge run --rm --no-deps knowledge \
  python -m unittest discover -s tests -v
docker compose --env-file .env.knowledge up -d knowledge
curl http://127.0.0.1:8787/health
```

The durable index is stored in the `nanoayx-kb-data` Docker volume. It is
derived state and can be rebuilt from Drive.

## API

```text
GET  /health
GET  /stats
POST /ingest
POST /search   {"query":"...", "limit":5}
POST /outputs  {"relative_path":"project/note.md", "content":"..."}
```

Agents use the corresponding MCP tools:

```text
knowledge_search
knowledge_ingest
knowledge_stats
knowledge_write_output
```

Knowledge retrieval and complex grounded synthesis use the GPT-5.4
coordinator. The tool-free Ollama provider can process text delegated to it,
but it does not search the index itself.

## Supported Content

Supported directly: `.txt`, `.md`, `.markdown`, `.rst`, `.csv`, `.tsv`,
`.json`, `.yaml`, `.yml`, `.log`, `.html`, `.htm`, `.pdf`, and `.docx`.

Native `.gdoc`, `.gsheet`, and `.gslides` pointer files are recorded as
ingestion errors because they contain metadata rather than document bodies.
Indexing native Google files requires a future authenticated Drive API export
adapter.

## Security and Storage

Do not put credentials, runtime databases, session queues, vector indexes,
lock files, or Git worktrees in Drive. The exact Drive root is allowlisted in
`~/.config/nanoclaw/mount-allowlist.json`; broader Google Drive paths must not
be allowlisted.

The knowledge container has no Docker socket. Agent containers have no Docker
socket. The host supervisor validates mounts and owns container lifecycle.
