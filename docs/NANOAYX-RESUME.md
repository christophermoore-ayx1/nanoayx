# NanoAYX Resume Checkpoint

Updated: 2026-07-26

## Resume Here

Use this worktree as the implementation source:

```text
/Users/christopher.moore/Documents/NanoAYX/nanoclaw
```

Current branch:

```text
codex-provider-stabilization
```

The intended GitHub destination is:

```text
https://github.com/christophermoore-ayx1/nanoayx
```

The target repository currently contains only a two-line initial README. Keep
the NanoClaw upstream history and merge the target's initial commit later so
updating `main` does not require a force push.

## Objective

Build a Docker-isolated, Codex-first NanoClaw fork for internal Alteryx work:

- Telegram is the user-facing channel.
- GPT-5.4 handles complex reasoning, coding, Alteryx work, and final synthesis.
- Ollama handles routine text, ingestion summaries, tagging, and other lower
  complexity work.
- Agent groups provide coordinator and specialist/sub-agent isolation.
- A designated Alteryx Google Drive folder is the read/write document boundary.
- Source, runtime databases, secrets, and vector indexes remain outside Drive.

## Local Implementations

### Canonical candidate

`/Users/christopher.moore/Documents/NanoAYX/nanoclaw`

This is the most complete NanoClaw-based implementation. It contains the
in-progress Codex provider, Telegram adapter, agent-to-agent changes, Codex
instruction composition, and tests.

### Upstream reference

`/Users/christopher.moore/nanoclaw-v2`

This is a clean NanoClaw v2 clone with a smaller, incomplete Codex provider
change set. Preserve it as an upstream comparison source.

### Running legacy prototype

`/Users/christopher.moore/nanoayx`

This Python/FastAPI implementation currently runs `nanoayx-api` and
`nanoayx-worker` containers. It has configured Telegram, Ollama, and Alteryx
MCP settings, but it lacks NanoClaw's per-agent container isolation and only
returns a textual Codex handoff. Do not stop or remove it until the NanoClaw
fork passes an end-to-end cutover test.

## Verified State

In the canonical candidate:

- Host TypeScript build passes with Node 22.
- Agent-runner TypeScript typecheck passes.
- All 13 Codex provider tests pass under Bun.
- The host suite reported 380 passing tests.
- Seven `scripts/q.test.ts` failures were caused by sandbox-denied TSX IPC;
  all seven pass when rerun outside the sandbox.
- A full parallel Vitest run also hit the macOS open-file limit in Telegram
  pairing tests. Rerun with constrained workers before release.
- The launch agent `com.nanoclaw-v2-2f3dfabc` is not currently active and last
  reported `EX_CONFIG`; inspect current logs and run a foreground smoke test.
- Ollama is installed at `/usr/local/bin/ollama`, but its daemon was not
  listening on port 11434 at checkpoint time.
- Codex host authentication exists. Never commit or print its contents.

Known-good build prefix:

```bash
PATH=/opt/homebrew/opt/node@22/bin:$PATH pnpm run build
```

## Google Drive Plan

The user is installing Google Drive for Desktop and will restart the Mac.

After restart:

1. Confirm Google Drive Desktop is signed into the Alteryx account.
2. Decide whether the knowledge base is private in My Drive or
   organization-owned in a Shared Drive.
3. Create one top-level folder named `NanoAYX Knowledge Base`.
4. Mark the folder **Available offline**.
5. Record its local path under `/Users/christopher.moore/Library/CloudStorage`.
6. Add only that exact path to NanoClaw's mount allowlist.
7. Mount it read/write at `/knowledge/drive` for the knowledge agent.

Recommended Drive layout:

```text
NanoAYX Knowledge Base/
  00 Inbox/
  10 Sources/
  20 Notes/
  30 Projects/
  40 Generated/
  90 Archive/
```

Do not place SQLite databases, vector indexes, lock files, credentials, Git
worktrees, or NanoClaw runtime state in Google Drive. Store derived indexes in
a local Docker volume and treat Drive files as canonical source documents and
human-readable outputs.

## Journey Knowledge Base Kit

Requested source:

```text
https://www.journeykits.ai/browse/kits/matt-clawd/knowledge-base-raginstall
```

Canonical kit reference:

```text
matt-clawd/knowledge-base-rag
```

Do not install the current kit unchanged. The Codex install manifest was
inspected and has material inconsistencies:

- It defaults to Anthropic Claude instead of GPT-5.4.
- It describes SQLCipher but the bundled implementation uses Supabase.
- It imports missing `../../../shared/embeddings` and `shared/event-log`
  modules.
- `@supabase/supabase-js` is imported but absent from `package.json`.
- The bundled `source_links` schema does not match the application queries.
- The `match_chunks` SQL function does not accept all parameters sent by the
  application.
- The package declares scripts that are not all present in the manifest.
- It includes external install/outcome telemetry instructions. Do not send
  internal Alteryx installation or usage telemetry without explicit approval.

Adaptation target:

- Vendor reviewed source into the NanoAYX repository rather than executing a
  remote install blindly.
- Use GPT-5.4 for complex synthesis and grounded final answers.
- Use Ollama for routine summaries, tagging, extraction cleanup, and preferably
  local embeddings.
- Keep one embedding provider/model/dimension fixed for both ingest and query.
- Replace missing shared modules with NanoAYX-owned interfaces.
- Choose and implement one storage backend consistently.
- Add file hashing, incremental re-indexing, source citations, deletion, and
  retrieval evaluation tests.
- Add a Drive scanner for supported documents under `/knowledge/drive`.

## Recommended Agent Topology

- `Naya`: coordinator, GPT-5.4.
- `Forge`: complex coding, Alteryx, and workflow work, GPT-5.4.
- `Scribe`: summaries, drafting, tagging, and ingestion cleanup, Ollama.
- One Telegram bot routes explicit mentions and allows Naya to delegate using
  NanoClaw agent-to-agent destinations.

This topology is recommended but still needs explicit confirmation.

## Decisions Needed After Restart

1. Confirm this NanoClaw worktree is the canonical project.
2. Confirm My Drive versus Shared Drive and provide the local folder path.
3. Confirm the approved OpenAI credential path:
   - Alteryx-managed API key protected through OneCLI, preferred for internal
     use; or
   - existing ChatGPT/Codex subscription authentication.
4. Confirm the Naya/Forge/Scribe topology.
5. Select the Ollama chat and embedding models after starting Ollama and
   listing locally available models.
6. Choose local storage for the RAG index versus a governed Supabase project.
   Prefer local storage unless Alteryx has approved Supabase for this data.

## Next Execution Steps

1. Re-read this checkpoint and inspect `git status`.
2. Verify Google Drive's local folder and offline availability.
3. Start Ollama and list installed models.
4. Repair the launch-agent failure and complete a Codex CLI smoke test.
5. Finish the Codex provider security review, especially credential exposure
   inside containers.
6. Stabilize the Telegram round trip and agent-to-agent delivery.
7. Implement the Drive mount and knowledge-base adaptation.
8. Add targeted tests and run constrained full-suite validation.
9. Build the agent image and run end-to-end Telegram tests.
10. Merge the target repository's initial commit, update `main`, and document
    upstream synchronization.
