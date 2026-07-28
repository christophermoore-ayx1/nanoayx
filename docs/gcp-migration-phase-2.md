# Phase 2: GCP Migration Implementation Plan

Status: **Planning only. Not started.**

This document records the future implementation plan for moving NanoAYX from
the local macOS Docker host to an always-on Google Cloud deployment. It does
not authorize provisioning GCP resources, changing the current local runtime,
rotating credentials, or cutting over Telegram.

## Objective

Deploy NanoAYX into the existing Alteryx GCP project in us-central1 using a
single Compute Engine VM with persistent disk storage, private administration,
managed backups, and Google Drive API access.

The first cloud deployment will:

- Run the NanoAYX supervisor and dynamically spawned Docker agent containers.
- Keep Telegram as the primary user interface.
- Use IAP-secured private administration.
- Store runtime state on persistent disk.
- Replace Google Drive Desktop with Google Drive API access.
- Use GPT-5.4 for the initial cloud deployment.
- Defer Ollama/Gemma 4 until the cloud baseline is stable.
- Keep the local deployment available as rollback until cutover is accepted.

The initial target is intentionally a single VM plus backups. GKE, Cloud Run,
multi-zone failover, Cloud SQL, GPU hosting, and durable exactly-once delivery
are later stages, not prerequisites for this migration.

## Current State

The current local deployment consists of:

- macOS LaunchAgent running the trusted NanoAYX supervisor.
- Docker agent containers created dynamically per session.
- SQLite central and per-session databases.
- Telegram adapter in the host process.
- Dockerized knowledge service.
- Google Drive Desktop as the knowledge filesystem boundary.
- Native Ollama for embeddings and the Scribe worker.
- OneCLI and PostgreSQL supporting services.

The current design favors Compute Engine because the supervisor dynamically
creates Docker containers and relies on local session directories and SQLite
single-writer semantics. Cloud Run and GKE would require a larger orchestration
and storage redesign.

## Target Architecture

~~~text
Telegram
   |
   v
Compute Engine VM: nanoayx-prod
   |
   |-- NanoAYX supervisor
   |     |-- Telegram adapter
   |     |-- router and permissions
   |     |-- session manager
   |     |-- Docker lifecycle
   |     |-- delivery and host sweep
   |     +-- systemd service
   |
   |-- Docker Engine
   |     |-- Naya session containers
   |     |-- Forge session containers
   |     |-- future Scribe/Gemma containers
   |     +-- knowledge service
   |
   |-- Persistent Disk
   |     |-- central SQLite database
   |     |-- session databases
   |     |-- agent workspaces
   |     +-- knowledge index
   |
   |-- Secret Manager
   |     |-- Telegram credentials
   |     |-- GPT-5.4 credentials
   |     |-- OneCLI credentials
   |     +-- Drive API credentials
   |
   +-- Google Drive API
         |-- source documents
         |-- generated outputs
         +-- native Workspace exports
~~~

The VM should initially have no public IP. Outbound traffic uses the VPC and
Cloud NAT. Administration uses IAP-secured SSH. Telegram remains the user
interface; no public NanoAYX admin endpoint is required for the first release.

## Prerequisites

### GCP Project

Confirm:

- Existing Alteryx GCP project ID.
- Billing account and budget owner.
- Approved us-central1 region.
- Organization approval for Compute Engine, Secret Manager, Artifact
  Registry, Cloud Storage, Monitoring, Logging, IAP, and networking.
- Project-level or delegated permissions for initial provisioning.

Enable the Compute Engine, Secret Manager, Artifact Registry, Cloud Storage,
Cloud Monitoring, Cloud Logging, IAP, and required networking APIs.

### IAM

Create separate identities for:

- Human administrators.
- The NanoAYX VM service account.
- Google Drive API access.
- Optional CI/CD deployment.

The VM identity should receive only the required Secret Manager accessor,
Artifact Registry reader, Logging Writer, Monitoring Metric Writer, and
backup-storage permissions.

Secrets must be stored in Secret Manager rather than VM environment files. The
Compute Engine instance must have the appropriate OAuth scope and IAM access
for Secret Manager.

References:

- [Secret Manager access management](https://cloud.google.com/secret-manager/docs/manage-access-to-secrets)
- [IAP access management](https://cloud.google.com/iap/docs/managing-access)

### Google Drive

The cloud VM cannot depend on Google Drive Desktop. The knowledge service must
use a Drive API source provider.

Preferred enterprise path:

- Obtain a Google Workspace service identity.
- Obtain administrator approval for domain-wide delegation with narrow scopes.
- Impersonate the approved Alteryx user or use an identity explicitly granted
  access to the knowledge folder.

Fallback path:

- Complete one-time user OAuth.
- Store the refresh token in Secret Manager.
- Restrict access to the NanoAYX folder.
- Add token expiry and authorization monitoring.

Current folder:

~~~text
Folder ID: 1B5BMKeFQiSquksNZh9J8iAam3Cl40CS8
~~~

Longer term, move the knowledge base to an Alteryx Shared Drive for
organization ownership and service access. Service accounts cannot own files
in My Drive and are better suited to Shared Drives or delegated user access.

References:

- [Google Drive API authorization scopes](https://developers.google.com/drive/api/guides/api-specific-auth)
- [Google Shared Drives](https://developers.google.com/workspace/drive/api/guides/about-shareddrives)

### External Services

Confirm production credentials and policies for:

- Telegram bot token and authorized operator IDs.
- GPT-5.4/OpenAI or Codex authentication.
- OneCLI endpoint and API key, if retained in the cloud path.
- Drive API OAuth or delegated service credentials.
- Alteryx data handling and model usage requirements.
- Telegram polling or webhook behavior.
- Egress requirements for Telegram, GPT-5.4, Drive, GitHub, and package
  registries.

## Implementation Phases

### Phase 2.1: Inventory and Freeze

Create a migration manifest containing:

- Current Git commit and branch.
- Central database backup.
- Per-session database paths.
- Agent group directories and instructions.
- Container configuration records.
- Naya, Forge, and Scribe provider settings.
- Knowledge index statistics.
- Drive folder structure.
- Telegram and OneCLI configuration.
- Local recovery procedure.

During the final export window, stop structural changes and retain the local
deployment for rollback.

Deliverables:

- Migration manifest.
- Encrypted database backup.
- Agent workspace archive.
- Knowledge index rebuild decision.
- Rollback checklist.

### Phase 2.2: GCP Foundation

Provision:

- VPC network and private subnet in us-central1.
- Compute Engine VM.
- Persistent disk.
- VM service account.
- Firewall rules with no public SSH.
- Cloud NAT for outbound access.
- IAP administration.
- Secret Manager secrets.
- Cloud Logging and Monitoring.
- Budget alerts.

Starting VM profile:

- Ubuntu LTS.
- e2-standard-4 with 4 vCPU and 16 GB RAM.
- 100–200 GB balanced persistent disk.
- Separate durable-data disk if operationally useful.

Resize to 8 vCPU/32 GB if concurrent agent containers require it. Do not add
a GPU for the initial GPT-5.4-only deployment.

Add a startup script or systemd unit to install/start Docker and NanoAYX.
Compute Engine supports startup scripts executed during VM boot.

Reference:

- [Compute Engine startup scripts](https://cloud.google.com/compute/docs/instances/startup-scripts)

Exit criteria:

- VM recovers Docker and NanoAYX after reboot.
- IAP SSH works for authorized administrators.
- No public SSH or unintended ingress exists.
- Required outbound connections work.
- Logs are visible in Cloud Logging.

### Phase 2.3: Container and Repository Delivery

Support Linux/GCE deployment without changing the local deployment:

- Replace macOS absolute paths with configurable Linux paths such as
  /opt/nanoayx and /var/lib/nanoayx.
- Make DATA_DIR, GROUPS_DIR, and runtime paths explicit.
- Remove LaunchAgent assumptions from the cloud path.
- Add systemd units for the supervisor and knowledge service.
- Preserve dynamic child-container lifecycle.
- Keep Docker socket access limited to the trusted supervisor.
- Keep agent and knowledge containers socket-free.

Recommended image delivery:

- GitHub remains the source repository.
- CI builds images tagged by Git commit SHA.
- Artifact Registry stores immutable images.
- Production never deploys an unqualified latest tag.

Exit criteria:

- A clean VM can deploy from a pinned commit.
- Supervisor creates and destroys child containers.
- Agent sessions survive supervisor restart.
- Images are traceable to Git commits.

### Phase 2.4: Persistent State Migration

Move durable state to the persistent disk:

- data/v2.db.
- data/v2-sessions/.
- Agent group workspaces.
- Runtime configuration.
- Knowledge service derived index.
- In-flight inbox/outbox state.

Controlled migration:

1. Stop local message intake.
2. Drain or checkpoint active sessions.
3. Stop the local supervisor.
4. Back up central and session databases.
5. Copy state to the VM.
6. Verify SQLite integrity.
7. Start the cloud supervisor in migration mode.
8. Verify agent groups, sessions, destinations, and pending messages.
9. Preserve the local installation for rollback.

The knowledge index is derived state and can be rebuilt from Drive.

Exit criteria:

- SQLite integrity checks pass.
- Sessions and agent groups resolve correctly.
- Pending work is not lost or duplicated.
- Naya and Forge configuration is preserved.
- VM reboot does not lose state.

### Phase 2.5: Drive API Knowledge Migration

Refactor services/knowledge around a source-provider interface:

~~~text
KnowledgeSource
  |-- LocalFilesystemSource
  +-- GoogleDriveApiSource
~~~

The Drive provider must:

- List files below the configured folder ID.
- Track Drive file ID, MIME type, modified time, checksum, and path.
- Download binary files.
- Export Google Docs, Sheets, and Slides.
- Incrementally process changed files.
- Remove deleted files from the index.
- Preserve Drive IDs and URLs in search results.
- Restrict generated writes to 40 Generated.
- Use Drive API output creation in cloud mode.
- Persist only derived index data locally.

Exit criteria:

- Drive API authentication works without a desktop session.
- Existing source files are searchable.
- Native Workspace files are exportable and searchable.
- Changed and deleted files update the index.
- Search results contain stable Drive URLs.
- Generated outputs remain inside the approved boundary.
- Authorization and quota errors are observable.

### Phase 2.6: Secrets and Provider Migration

Move local credentials to Secret Manager:

- Telegram token.
- GPT-5.4/OpenAI or Codex credentials.
- OneCLI credentials.
- Drive OAuth or delegated service credentials.

Initial cloud routing:

| Agent | Provider | Cloud target |
| --- | --- | --- |
| Naya | Codex/GPT-5.4 | Compute Engine VM |
| Forge | Codex/GPT-5.4 | Compute Engine VM |
| Scribe | Deferred | Add after baseline stabilization |

Requirements:

- Load secrets at startup through the VM identity.
- Copy only required Codex authentication into private session directories.
- Keep secrets out of Git, images, logs, and general workspaces.
- Validate GPT-5.4 authentication from the VM.
- Keep Ollama provider code available but unassigned initially.

Future Ollama/Gemma 4 work:

- Select a GPU-capable VM or separate Ollama VM.
- Benchmark model memory and latency.
- Keep Ollama on private VPC access.
- Assign Scribe only after resource and cost validation.

### Phase 2.7: Always-On Operations

Replace the macOS LaunchAgent with:

- nanoayx-supervisor.service.
- Knowledge service systemd or Compose management.
- Docker restart policies.
- VM startup ordering.
- Health checks for supervisor, knowledge, Docker, disk, and egress.
- Cloud Monitoring alerts.

Alert on:

- Supervisor crashes.
- Knowledge service health failures.
- Repeated container spawn failures.
- GPT-5.4 authentication failures.
- Telegram delivery failures.
- Drive authorization failures.
- Disk usage thresholds.
- Database integrity or migration failures.
- Abnormally high duplicate suppression.

Backups:

- Daily persistent disk snapshot.
- Weekly retained snapshot.
- Pre-release snapshot.
- Separate central SQLite export.
- Periodic restore test to a disposable VM.
- Documented RPO and RTO.

Reference:

- [Compute Engine data protection](https://cloud.google.com/compute/docs/disks/data-protection)

### Phase 2.8: Cutover

1. Announce a maintenance window.
2. Stop local Telegram intake.
3. Drain or checkpoint local sessions.
4. Take final database and workspace backups.
5. Sync final state to the VM.
6. Start cloud services.
7. Run health checks.
8. Send a Telegram smoke test to Naya.
9. Test Naya-to-Forge and Forge-to-Naya routing.
10. Test knowledge search and Drive citation.
11. Confirm only one Telegram consumer is polling the bot.
12. Keep local services stopped but intact for rollback.

Cutover is accepted only when cloud Telegram delivery, GPT-5.4 execution,
Forge delegation, Drive retrieval, restart recovery, logging, backups, and
duplicate protection all pass.

## Security and Access

The first deployment exposes no public admin endpoint.

- Administrators use IAP-secured SSH and the GCP Console.
- The VM has outbound access but no unrestricted inbound access.
- The supervisor is the only component allowed to use the Docker API.
- Agent and knowledge containers receive no Docker socket.
- Host mounts remain narrowly scoped.
- Secrets are retrieved from Secret Manager.
- Drive access is folder-scoped and audited.
- Telegram authorization remains enforced by the host adapter.

## Testing and Acceptance

### Local Regression

- Host typecheck and tests under Node 22.
- Agent-runner provider tests.
- Knowledge service unit tests.
- Docker image build.
- Duplicate-result regression test.
- Local Telegram smoke test.

### GCP Infrastructure

- VM reboot recovery.
- Docker daemon restart recovery.
- Supervisor restart recovery.
- Persistent disk remount and ownership.
- Secret Manager access.
- IAP access control.
- No public SSH or unintended ingress.
- Cloud Logging and Monitoring delivery.

### Drive API

- Authentication.
- Folder-scoped listing.
- Markdown, text, PDF, DOCX, and native Workspace exports.
- Incremental reindexing.
- Deleted-file removal.
- Citation URLs.
- Generated-output restriction.
- Token expiry and quota failure handling.

### Agent Workflow

- Telegram to Naya.
- Naya to Forge.
- Forge to Naya.
- Naya knowledge retrieval.
- GPT-5.4 error recovery.
- Container restart during active work.
- No duplicate Telegram response.
- Single active Telegram consumer after cutover.

### Disaster Recovery

- Restore central SQLite from backup.
- Restore session databases.
- Restore agent workspaces.
- Rebuild knowledge index from Drive.
- Start a replacement VM.
- Reconnect secrets and service identities.
- Re-run Telegram and agent smoke tests.

## Milestones

| Milestone | Exit gate |
| --- | --- |
| GCP foundation | VM, IAM, IAP, secrets, logging, and backups operational |
| Container migration | Supervisor and child containers run on Linux/GCE |
| State migration | SQLite integrity and agent configuration verified |
| Drive API migration | Search, citations, exports, deletion, and writes verified |
| GPT-5.4 validation | Naya and Forge complete real workflows |
| Always-on validation | Reboots and service restarts recover automatically |
| Cutover | Only cloud Telegram consumer is active |
| Hardening | Restore test, alerts, and rollback procedure documented |

## Deferred Work

- Ollama/Gemma 4 deployment.
- Shared Drive migration.
- Multi-zone failover.
- Cloud SQL or another managed routing database.
- GKE or Cloud Run redesign.
- CI/CD production promotion pipeline.
- Durable outbound idempotency across process crashes.
- Full browser-facing private administration surface.

## Assumptions

- Existing Alteryx GCP project.
- us-central1.
- Single Compute Engine VM plus persistent disk snapshots.
- Telegram plus private IAP administration.
- Current My Drive folder through Drive API initially.
- GPT-5.4 first; Ollama/Gemma 4 later.
- Local macOS deployment retained as rollback.

