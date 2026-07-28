# NanoAYX Resume Checkpoint

Updated: 2026-07-27

## Canonical Worktree

```text
/Users/christopher.moore/Projects/NanoAYX/nanoclaw
```

Branch: `codex-provider-stabilization`

Repository: `https://github.com/christophermoore-ayx1/nanoayx`

The old checkout under `/Users/christopher.moore/Documents/NanoAYX/nanoclaw`
is rollback-only. `/Users/christopher.moore/nanoclaw-v2` remains an upstream
comparison checkout.

## Operational Architecture

- A macOS LaunchAgent runs the trusted host supervisor.
- Per-session GPT-5.4 agents run in isolated Docker containers.
- Telegram is provided by the supervisor's installed adapter.
- The knowledge service runs in Docker on `nanoayx-runtime`.
- Google Drive Desktop provides the host filesystem source boundary.
- Ollama runs natively and provides `embeddinggemma` embeddings.
- No application container receives the Docker socket.

The LaunchAgent label is `com.nanoclaw-v2-2f3dfabc`. Its plist points at the
canonical worktree and sets `NANOCLAW_DOCKER_NETWORK=nanoayx-runtime`.

## Knowledge Base

```text
Drive folder ID: 1B5BMKeFQiSquksNZh9J8iAam3Cl40CS8
Drive URL: https://drive.google.com/drive/folders/1B5BMKeFQiSquksNZh9J8iAam3Cl40CS8
Host path: /Users/christopher.moore/Library/CloudStorage/GoogleDrive-christopher.moore@alteryx.com/My Drive/NanoAYX Knowledge Base
Service: http://127.0.0.1:8787
Agent service name: http://nanoayx-knowledge:8787
```

The Drive folder contains canonical source documents and reviewable outputs.
The derived SQLite vector index lives in the `nanoayx-kb-data` Docker volume.

## Model Routing

The current coordinator config is pinned to:

```text
provider=codex
model=gpt-5.4
effort=high
```

Ollama is installed natively with `embeddinggemma:latest` for retrieval and
`lfm2.5:8b` for low-complexity text workers. The Ollama provider is intentionally
stateless and tool-free: it is suitable for delegated summarization,
classification, extraction, and drafting. The Telegram coordinator uses
GPT-5.4.

Current agent topology:

| Agent | Provider | Model | Role |
| --- | --- | --- | --- |
| Naya | `codex` | `gpt-5.4`, high | Telegram coordinator, retrieval, synthesis |
| Forge | `codex` | `gpt-5.4`, high | Complex implementation and Alteryx work |
| Scribe | `ollama` | `lfm2.5:8b` | Tool-free text transformations |

## Recovery

From the canonical worktree:

```bash
docker start onecli-postgres-1 onecli
docker compose --env-file .env.knowledge up -d knowledge
PATH=/opt/homebrew/opt/node@22/bin:$PATH pnpm run build
/bin/zsh -lc 'launchctl kickstart -k gui/$(id -u)/com.nanoclaw-v2-2f3dfabc'
```

Health checks:

```bash
docker ps --filter name=nanoayx-knowledge
curl http://127.0.0.1:8787/health
/bin/zsh -lc 'launchctl print gui/$(id -u)/com.nanoclaw-v2-2f3dfabc'
```

Do not commit `.env`, `.env.knowledge`, `data/`, `groups/`, logs, credentials,
or Drive contents.

## Verified

- The canonical LaunchAgent runs from the new worktree.
- Host typecheck and focused container-runtime tests pass.
- The knowledge image builds and its unit tests pass.
- Drive ingestion, Ollama embeddings, semantic retrieval, citations, deletion,
  and restricted generated-output writes are implemented.
- A real Drive source was indexed and retrieved through the HTTP service.
- Agent MCP tools exist for search, ingestion, stats, and generated outputs.
- The rebuilt agent image can reach the knowledge service on the private
  runtime network and use its MCP tools.
- Telegram delivered a GPT-5.4 retrieval response with a Drive citation.
- Naya created Forge and Scribe through the normal agent-to-agent workflow.
- Fresh child containers materialized the expected provider/model settings.
- Scribe completed an Ollama agent-to-agent round trip with clean output.
- Provider failures on agent routes are suppressed instead of bouncing
  recursively between agents.

## Final Provider Validation

On 2026-07-28, after the account limit reset, a fresh Naya request spawned a
new Forge container with `codex/gpt-5.4/high`. Forge returned exactly
`FORGE READY`, the reply routed back to Naya, and Naya delivered the result to
Telegram.

## Deferred Governance Decisions

- Move the knowledge folder to an Alteryx Shared Drive if it needs
  organization ownership instead of user ownership.
- Add a Google Drive API exporter if native Google Docs, Sheets, and Slides
  must be indexed. Drive Desktop pointer files alone do not contain document
  bodies.
