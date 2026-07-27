# NanoAYX Knowledge Base

## Canonical Source

NanoAYX uses a dedicated Google Drive folder as the canonical source-document
and human-readable output boundary:

```text
Name: NanoAYX Knowledge Base
Drive folder ID: 1B5BMKeFQiSquksNZh9J8iAam3Cl40CS8
Drive URL: https://drive.google.com/drive/folders/1B5BMKeFQiSquksNZh9J8iAam3Cl40CS8
Location: Alteryx My Drive
```

Google Drive Desktop exposes it on the current host at:

```text
/Users/christopher.moore/Library/CloudStorage/GoogleDrive-christopher.moore@alteryx.com/My Drive/NanoAYX Knowledge Base
```

The host path is installation-specific. Resolve and verify it again when
NanoAYX is installed on another machine.

## Folder Layout

```text
NanoAYX Knowledge Base/
  00 Inbox/
  10 Sources/
  20 Notes/
  30 Projects/
  40 Generated/
  90 Archive/
```

- `00 Inbox` receives unclassified material.
- `10 Sources` holds canonical reference documents.
- `20 Notes` holds curated notes and durable summaries.
- `30 Projects` holds project-specific working knowledge.
- `40 Generated` receives agent-created, human-readable outputs.
- `90 Archive` holds retired material that should remain discoverable.

## Container Boundary

The exact Drive root is the only Google Drive path allowlisted in:

```text
~/.config/nanoclaw/mount-allowlist.json
```

The active `nanoayx` agent group requests the mount through its
`container_configs.additional_mounts` row. NanoClaw validates the real host
path against the external allowlist and exposes it read/write at:

```text
/workspace/extra/knowledge/drive
```

Do not allowlist the Google Drive account root, `My Drive`, `Shared drives`, or
the parent `CloudStorage` directory. Agent groups that do not need knowledge
access must not request this mount.

## Storage Policy

Drive contains canonical documents and reviewable outputs. It must not contain:

- credentials, `.env` files, API tokens, or authentication state;
- NanoClaw source code or Git worktrees;
- SQLite databases, lock files, session state, or queues;
- vector indexes, embedding caches, or other frequently rewritten derived
  state.

Keep the RAG index and ingestion state in a local Docker volume. Store the Drive
file ID, relative path, content hash, modified time, parser version, embedding
model, and embedding dimension in the index so changes can be reconciled
incrementally.

## Verified State

On 2026-07-26:

- Drive metadata and the Desktop item ID matched.
- Drive Desktop reported the folder downloaded, recursively downloaded, and
  available offline.
- The six canonical child folders existed in Drive and on the local mount.
- NanoClaw's mount validator approved the exact host path for read/write.
- A disposable `node:22-alpine` container read the folder hierarchy and
  confirmed write permission at `/workspace/extra/knowledge/drive`.

## Remaining Work

1. Add a Drive scanner that hashes supported source files and queues changed
   documents.
2. Implement one consistent local vector-store backend.
3. Select and pin one Ollama embedding model and dimension for ingest and
   retrieval.
4. Use Ollama for routine extraction, tagging, and summaries.
5. Use GPT-5.4 for complex synthesis and grounded final answers.
6. Emit citations containing the Drive file ID and relative source path.
7. Add deletion handling and retrieval evaluation fixtures.
8. Revisit moving the folder to an Alteryx Shared Drive if the knowledge base
   should be organization-owned instead of user-owned.
