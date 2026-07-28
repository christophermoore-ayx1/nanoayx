# NanoAYX Ollama Provider

NanoAYX uses native Ollama for local inference while agent execution remains
inside Docker. Native Ollama preserves Apple Metal acceleration and provides
one shared model server.

## Installed Models

- `embeddinggemma:latest`: knowledge-base embeddings.
- `lfm2.5:8b`: low-complexity text transformations.

Confirm availability with:

```bash
ollama list
curl http://127.0.0.1:11434/api/tags
```

## Provider Design

The `ollama` provider calls Ollama's `/api/chat` endpoint directly. It is:

- stateless across turns;
- configured with `think: false`;
- stripped of any residual `<think>...</think>` output;
- intentionally unable to use MCP tools;
- appropriate for summarization, classification, extraction, and drafting.

Complex reasoning, coding, Alteryx work, retrieval, file operations, and final
synthesis stay on the `codex` provider with GPT-5.4.

The host-side provider contribution supplies:

```text
OLLAMA_BASE_URL=http://host.docker.internal:11434
NO_PROXY=host.docker.internal,127.0.0.1,localhost
```

Agent containers reach native Ollama through Docker's host gateway. OneCLI is
not involved in local Ollama requests.

## Assign an Agent

Provider settings are stored in `container_configs` and materialized at spawn:

```bash
ncl groups config update \
  --id <agent-group-id> \
  --provider ollama \
  --model lfm2.5:8b
ncl groups restart --id <agent-group-id>
```

Scribe is the deployed Ollama worker. Naya should send it the complete source
text and a self-contained transformation request; Scribe does not fetch
missing context.

## Validation

```bash
docker run --rm \
  --network nanoayx-runtime \
  --entrypoint sh \
  nanoclaw-agent-v2-7166243d:latest \
  -lc 'curl -fsS http://host.docker.internal:11434/api/tags >/dev/null'
```

The final operational check is an agent-to-agent message from Naya to Scribe
and a clean response back to Naya.
