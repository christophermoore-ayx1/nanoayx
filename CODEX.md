# NanoClaw

NanoClaw is a personal Codex assistant system. The host is a Node process that routes messages into per-session agent containers; each container runs an agent runner that calls Codex and writes responses back for delivery.

## First Rule

Run commands directly when you can. Do not ask the user to run routine build, test, search, or inspection commands unless an interactive terminal, credentials, or explicit human approval is required.

Do not run destructive git commands. In particular, do not use `git reset --hard`, `git checkout --`, or delete user files unless the user explicitly asks for that exact operation.

## Architecture

Everything is message-based. There is no stdin pipe, file watcher, or direct IPC between the host and an agent container.

The host writes inbound work to a session DB, wakes or starts a container, and later polls the outbound DB for responses. The container reads inbound messages, calls its configured provider, and writes outbound messages.

Session data lives under `data/v2-sessions/<session_id>/`:

- `inbound.db` - host writes, container reads.
- `outbound.db` - container writes, host reads.

Shared system state lives in `data/v2.db`: users, roles, agent groups, messaging groups, wirings, sessions, pending approvals, channel bridge state, and migrations.

## Key Files

| File | Purpose |
| --- | --- |
| `src/index.ts` | Host entry point: DB init, migrations, channel adapters, delivery polling, sweep, shutdown |
| `src/router.ts` | Routes inbound platform messages to agent groups and sessions |
| `src/delivery.ts` | Polls outbound DBs and delivers replies through channel adapters |
| `src/host-sweep.ts` | Periodic stale-session, due-message, and ack maintenance |
| `src/session-manager.ts` | Resolves sessions and opens per-session DBs |
| `src/container-runner.ts` | Builds mounts/env and starts per-agent-group containers |
| `src/container-runtime.ts` | Docker vs Apple container runtime abstraction |
| `src/group-init.ts` | Per-agent-group filesystem scaffold |
| `src/db/` | Central DB layer and migrations |
| `src/cli/` | `ncl` admin CLI implementation |
| `src/providers/` | Host-side provider container integration |
| `container/agent-runner/src/` | In-container poll loop, provider abstraction, formatter, destinations, CLI transport |
| `container/CODEX.md` | Shared runtime instructions for agents inside containers |
| `groups/<folder>/` | Per-agent-group workspace, memory, skills, and overlays |

Some files still have `claude` in their names because they predate the Codex provider work. Treat those as legacy compatibility surfaces unless the task is explicitly to rename or migrate them.

## Entity Model

```text
users (id "<channel>:<handle>", kind, display_name)
user_roles (user_id, role, agent_group_id)          owner | admin, global or scoped
agent_group_members (user_id, agent_group_id)       unprivileged access gate
user_dms (user_id, channel_type, messaging_group_id)

agent_groups (workspace, memory, CODEX.md/personality, container config)
messaging_groups (one chat/channel on one platform)
messaging_group_agents (agent group wiring, session mode, trigger rules, priority)
sessions (agent_group_id + messaging_group_id + thread_id)
```

Privilege is user-level, not agent-group-level. See `docs/isolation-model.md`.

## Admin CLI

Use `ncl` for central DB changes. On the host it talks to the Unix socket; inside containers it uses the session DB transport.

```bash
ncl help
ncl <resource> help
ncl <resource> <verb> [<id>] [--flags]
```

Core resources: `groups`, `messaging-groups`, `wirings`, `users`, `roles`, `members`, `destinations`, `sessions`, `user-dms`, `dropped-messages`, and `approvals`.

Prefer `ncl` over ad hoc DB writes for supported operations. For read-only ad hoc SQL, use:

```bash
pnpm exec tsx scripts/q.ts <db> "<sql>"
```

Do not assume the `sqlite3` binary exists.

## Container Config

Per-agent-group runtime config lives in the `container_configs` table and is materialized to `groups/<folder>/container.json` when spawning containers. It controls provider, model, packages, mounts, and related runtime options.

The default provider goal is Codex. Provider-specific auth should come from Codex login state or OpenAI-compatible environment configuration, not raw credentials pasted into chat.

## Codex Auth

Codex can authenticate through either:

- ChatGPT subscription login state created by `codex login`, usually `~/.codex/auth.json`.
- `OPENAI_API_KEY`, with optional `OPENAI_BASE_URL` for compatible endpoints.

Do not ask users to paste secrets into chat. If auth is missing or expired, report the exact failing surface and the least-invasive local fix.

OneCLI remains responsible for vaulted credentials for non-Codex services. Run `onecli --help` when working on that surface.

## Development Commands

```bash
# Host, Node + pnpm
pnpm install --frozen-lockfile
pnpm run build
pnpm test
pnpm run dev

# Agent runner, Bun package tree
cd container/agent-runner && bun install --frozen-lockfile
cd container/agent-runner && bun test

# Container runner typecheck from repo root
pnpm exec tsc -p container/agent-runner/tsconfig.json --noEmit

# Agent image
./container/build.sh
```

The host uses Node and pnpm. The agent runner uses Bun and has its own lockfile under `container/agent-runner/`. Do not run `pnpm install` inside `container/agent-runner/`.

When using this repo from Codex on macOS with Homebrew Node 22, a known-good command prefix is:

```bash
PATH=/opt/homebrew/opt/node@22/bin:$PATH pnpm run build
```

## Testing Expectations

For host changes, run `pnpm run build` and relevant Vitest tests. For agent-runner changes, run the container typecheck and `bun test` from `container/agent-runner/`. For Docker/runtime changes, run `./container/build.sh` and verify the expected CLI exists inside the image.

If a test cannot run because of sandboxing, network, Docker availability, or credentials, say exactly what blocked it.

## Supply Chain Rules

This repo uses pnpm supply-chain controls in `pnpm-workspace.yaml`.

- Use `pnpm install --frozen-lockfile` in automation.
- Do not bypass `minimumReleaseAge` without explicit human approval.
- Do not add to `minimumReleaseAgeExclude` without explicit human approval and an exact version.
- Do not add to `onlyBuiltDependencies` without explicit human approval.
- Pin globally installed container CLIs in `container/Dockerfile`.

## Git Hygiene

The worktree may contain user changes. Never revert changes you did not make unless explicitly requested.

Before preparing a PR, read `CONTRIBUTING.md`. Installation-specific files, local configs, and per-user group memory should not be included unless the user explicitly wants them committed.

Useful review commands:

```bash
git status --short
git diff --stat
git diff -- <path>
```

## Troubleshooting

Check these first:

| What | Where |
| --- | --- |
| Host logs | `logs/nanoclaw.error.log`, then `logs/nanoclaw.log` |
| Setup logs | `logs/setup.log`, `logs/setup-steps/*.log` |
| Session DBs | `data/v2-sessions/<session_id>/inbound.db` and `outbound.db` |
| Central DB | `data/v2.db` |
| Container build | `./container/build.sh` output |

Container logs are usually lost after container exit because containers run with `--rm`.

## Documentation Index

| Doc | Purpose |
| --- | --- |
| `docs/NANOAYX-RESUME.md` | Current NanoAYX checkpoint, decisions, verified state, and restart instructions |
| `docs/architecture.md` | Full architecture |
| `docs/db.md` | Three-DB model |
| `docs/db-central.md` | Central DB schema and migrations |
| `docs/db-session.md` | Session DB schemas and seq parity |
| `docs/agent-runner-details.md` | Agent-runner internals |
| `docs/isolation-model.md` | Channel and agent isolation |
| `docs/build-and-runtime.md` | Node/Bun split, image build, runtime invariants |
| `docs/v1-to-v2-changes.md` | v1 to v2 vocabulary and architecture changes |
| `docs/migration-dev.md` | Migration development guide |
