# NanoAYX Deployment

## Native Components

These remain native because they own host-only capabilities:

- Google Drive Desktop: account authentication and offline filesystem sync.
- Ollama: Metal acceleration and one shared local model server.
- NanoAYX supervisor: Docker lifecycle, validated host mounts, Telegram
  delivery, and durable routing.

## Containerized Components

- Agent workers are ephemeral per-session containers.
- The knowledge service is an always-on container.
- The knowledge index is a named Docker volume.
- OneCLI and its PostgreSQL store run as supporting containers.

Agent providers:

- `codex` runs GPT-5.4 with MCP tools for complex, tool-heavy work.
- `ollama` runs a local model for stateless, tool-free text transformations.

This layout containerizes application work without placing the Docker socket
or broad host filesystem access inside a long-running application container.

Telegram remains an installed adapter in the trusted supervisor. Extracting it
into another gateway container would add another credential and delivery hop
without improving the current filesystem or model isolation boundary.

## Startup Order

1. Docker Desktop, Google Drive Desktop, and Ollama start through macOS.
2. OneCLI and PostgreSQL start.
3. Compose starts `nanoayx-knowledge`.
4. The LaunchAgent starts the NanoAYX supervisor and Telegram adapter.
5. The supervisor creates agent containers on demand.

```bash
docker start onecli-postgres-1 onecli
docker compose --env-file .env.knowledge up -d knowledge
/bin/zsh -lc 'launchctl kickstart -k gui/$(id -u)/com.nanoclaw-v2-2f3dfabc'
```

Use the existing pinned OneCLI containers for recovery. Do not run an
unqualified `docker compose pull` in `~/.onecli` during recovery because that
can replace the deployed version with an unreviewed `latest` image.

## Release Validation

```bash
PATH=/opt/homebrew/opt/node@22/bin:$PATH pnpm run typecheck
PATH=/opt/homebrew/opt/node@22/bin:$PATH pnpm test -- --maxWorkers=2
docker compose --env-file .env.knowledge config --quiet
docker compose --env-file .env.knowledge run --rm --no-deps knowledge \
  python -m unittest discover -s tests -v
./container/build.sh
```

Then verify health, semantic retrieval, an MCP call from the agent image, and
a Telegram round trip before pushing a release commit.

## Runtime Boundary

- Only the macOS supervisor may call the Docker API.
- The Docker socket is not mounted into knowledge or agent containers.
- Agent containers join only the validated `NANOCLAW_DOCKER_NETWORK`.
- Host mounts must pass the external mount allowlist.
- The knowledge container receives only the designated Drive root and its
  derived-data volume.
- The HTTP knowledge port binds to `127.0.0.1`; agent access uses the private
  `nanoayx-runtime` network.
