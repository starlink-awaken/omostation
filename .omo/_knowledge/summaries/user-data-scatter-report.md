---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: summaries/ 根目录历史快照批量归档, 当前状态以 .omo/state/system.yaml + .omo/tasks/active/ 为准"
---
# Phase 11 Wave 1 — User data scatter mapping (T1.10–T1.13)

## Outcome

This report audits the four workspace roots requested by **G11.1.3 / T1.10–T1.13**:

- `data/` — shared data substrate (durable-ish, but generally not tracked)
- `SharedBrain/` — legacy root residue (currently ignored)
- `spaces/` — tenant/user space manifests (tracked governance config)
- `runtime/` — ephemeral runtime residue (mostly ignored; boundary contracts tracked)

The goal is to make **what data lives where**, **who owns it**, **how it is (or is not) cleaned**, and **what action items close the biggest “scatter” gaps** explicit.

## Executive scatter map (current state)

| Root | Size (current) | Git tracked? | Primary contents | Owner intent | Lifecycle intent | Notes / risk |
|------|-----------------|-------------|------------------|-------------|------------------|--------------|
| `data/` | ~285MB | Mixed: policies tracked; DBs/backups ignored | `db/` SQLite organs; `backups/` backup sets | System space shared substrate (`data/README.md`) | Durable-ish, but should avoid ephemeral logs | `data/backups/` is large and ignored; retention policy is unclear vs `scripts/daily-backup.sh` |
| `SharedBrain/` | ~236KB | **Ignored** (root `.gitignore`) | Legacy SQLite DBs + cache dirs | Marked as “legacy root residue” | Unclear / legacy | Appears unused by active code; referenced mostly by archived docs/projects |
| `spaces/` | ~64KB | **Tracked** | Space registry + policy manifests + schemas | Governance / system-space (`spaces/registry.yaml`) | Durable governance config | Low volume; should not store user payloads |
| `runtime/` | ~28KB | Mixed: boundaries + READMEs tracked; residue ignored | `run-continuation/` session heartbeat markers | Runtime space; bounded by runtime boundary YAMLs | Ephemeral | No explicit TTL/GC documented for heartbeat JSON/logs |

Evidence for sizes: `du -sh data SharedBrain spaces runtime`.

---

## T1.10 — `data/` directory audit

### What is in `data/`

Declared purpose:

- `data/README.md`: “workspace home for the shared data substrate”; **do not** store `.omo` governance truth or ephemeral session logs.

Current observed subtrees:

| Path / pattern | What it stores | Producer / consumer signals | Git tracked? | Backup coverage | Cleanup / retention |
|---|---|---|---|---|---|
| `data/system-data-access-policy.yaml` | System-space data access policy referencing registries + runtime boundary | Referenced by `spaces/system-space*.yaml` bundle (e.g. `spaces/registry.yaml`) | Tracked | N/A | Governance config (no GC) |
| `data/runtime-space-access-policy.yaml` | Runtime-space data access policy referencing registry + runtime boundary | Referenced by `spaces/runtime-space*.yaml` bundle (e.g. `spaces/registry.yaml`) | Tracked | N/A | Governance config (no GC) |
| `data/db/organs/execution/execution.db` | SQLite “organ execution state” (per `layer-capability-user-planning.md`) | **No active code references found** in non-archived code; only planning docs mention | Ignored (`data/.gitignore` and root `.gitignore`) | Unclear | No explicit retention; treated as local state |
| `data/db/organs/memory/memory.db` | SQLite “organ memory state” (per planning) | Same as above | Ignored | Unclear | No explicit retention |
| `data/backups/<stamp>/...` | Backup sets (compressed tars + DB copies + manifests) | Two styles observed: (1) `20260524/manifest.txt` references `/Workspace/backups/daily/...` artifacts; (2) `20260528_104825/manifest.txt` describes “Knowledge Base + Core Infrastructure” hot backup | Ignored (`data/backups/` in root `.gitignore`) | Exists as backup payload itself | **No retention script** in-repo for `data/backups/` (contrast: `scripts/daily-backup.sh` retains 30 days in `$WORKSPACE/backups/daily/`) |

### Notable mismatch: `data/backups/` vs `scripts/daily-backup.sh`

- `scripts/daily-backup.sh` writes to `${WORKSPACE}/backups/daily/<YYYYMMDD>` and enforces `RETENTION_DAYS=30` **there**.
- `data/backups/20260524/manifest.txt` enumerates files under `/Users/xiamingxing/Workspace/backups/daily/20260524/...`, but the manifest itself lives under `data/backups/20260524/`.

This strongly suggests `data/backups/` is either:

1) a **copied/ingested snapshot** of the external `${WORKSPACE}/backups/daily/...` folder, or
2) a **second backup root** that is accumulating independently.

Either way, it is the dominant “scatter” hotspot in this audit because it is **large, ignored, and retention is unspecified**.

### Actions (recommended)

Decision needed (pick one and document as the SSOT):

- **Option A (preferred):** declare `${WORKSPACE}/backups/daily/...` as the canonical backup root; keep `data/backups/` empty (or remove it), and add a short doc note to `data/README.md` pointing to the external backup root.
- **Option B:** declare `data/backups/` canonical; add a retention/rotation script for `data/backups/` matching the 30-day policy in `scripts/daily-backup.sh`.

Regardless of option:

- Ensure manifests refer to paths that exist in the chosen canonical root (avoid “manifest points to /backups/daily but files live under data/backups”).

---

## T1.11 — `SharedBrain/` data flow audit (legacy root)

### What is in `SharedBrain/`

Root ignore signal:

- root `.gitignore` explicitly lists `SharedBrain/` and `SharedBrain/data/` under “遗留根目录残留” (legacy root residue).

Current observed contents:

| Path / pattern | What it stores | Producer / consumer signals | Git tracked? | Cleanup / retention |
|---|---|---|---|---|
| `SharedBrain/.omc/`, `.pytest_cache/`, `.ruff_cache/` | Tool/runtime caches | Generic tool residue | Ignored (via `SharedBrain/` ignore) | No policy; safe to delete/rebuild |
| `SharedBrain/data/db/core/{event_store.db,registry.db}` | Legacy SharedBrain core SQLite DBs | References found only in archived materials (e.g. `projects/_archived/eCOS/scripts/bos_bridge.py` reads `data/db/core/event_store.db`) and archived planning docs | Ignored | No current retention policy |
| `SharedBrain/data/db/organs/execution/tasks.db{,-wal,-shm}` | Legacy “tasks” organ DB | No active code references found in current (non-archived) code | Ignored | No current retention policy |
| `SharedBrain/data/db/backup/<YYYYMMDD>/{core,organs}/...` | Point-in-time DB snapshots (e.g. `20260531/core/event_store.db`) | Archive docs describe this backup pattern | Ignored | No automated retention |

### Conclusions

- The **root-level** `SharedBrain/` appears to be **legacy** and is not aligned with the monorepo layout where active project code lives under `projects/SharedBrain/`.
- The DBs under `SharedBrain/data/db/...` look like **old system-of-record state** (event store / registry) with **no current in-repo producer**.

### Actions (recommended)

- Make a single ownership decision:
  - either (a) formally **deprecate** root `SharedBrain/` and migrate any needed state into `data/` or `projects/SharedBrain/` controlled storage, or
  - (b) formally **reactivate** it (remove ignore, document lifecycle, and wire active producers/consumers).

Given the current `.gitignore` labeling (“legacy residue”), the safest near-term action is **deprecate + document**.

---

## T1.12 — `spaces/` tenant/user manifest audit

### What is in `spaces/`

`spaces/README.md` defines `spaces/` as the home for **space manifests and boundary metadata**, explicitly excluding DBs/snapshots and runtime logs.

Key tracked artifacts:

| File / pattern | Purpose | Owner / boundary signals | Sensitivity | Cleanup |
|---|---|---|---|---|
| `spaces/registry.yaml` | Workspace-level registry of known spaces | `manifest_root: spaces`; entries for `system-space` and `runtime-space`; roots include `.omo`, `spaces`, `data`, `runtime` | Low (governance config) | Durable config |
| `spaces/system-space.yaml`, `spaces/runtime-space.yaml` | Space manifests (roots + routing + owners) | `system-space` routes to capability roots in `projects/*`; `runtime-space` owned by control-plane/operators | Low | Durable config |
| `spaces/_schema/*.schema.yaml` | Schema contracts for manifests/admission | Enforces required fields | Low | Durable config |
| `spaces/*identity-admission*.yaml`, `spaces/*capability-taxonomy*.yaml`, `spaces/*admission-matrix*.yaml`, `spaces/*rollout-policy*.yaml`, `spaces/*cross-root-rule-registry*.yaml` | Admission + authorization + rollout + cross-root rule bundles | Bind to `data/*access-policy.yaml` and `runtime/*boundary.yaml` | Low (uses generic actor IDs like `system-operator`) | Durable config |

### Scatter risks

- Low volume, tracked, schema’d: `spaces/` is not a scatter hotspot.
- The main risk is **misuse**: accidentally storing user payloads or high-volume exports under `spaces/` (explicitly disallowed by `spaces/README.md`).

---

## T1.13 — `runtime/` ephemeral data audit

### What is in `runtime/`

Declared purpose:

- `runtime/README.md`: workspace home for **ephemeral runtime residue** (logs, temp state, pid/socket files, session residue).

Tracked boundary contracts:

| File | Key point |
|---|---|
| `runtime/system-runtime-boundary.yaml` | Allows only `runtime/run-continuation` and `runtime/logs` for `system-space` runtime roots |
| `runtime/runtime-space-boundary.yaml` | Same allowed roots for `runtime-space` |

Session continuation markers:

| Path / pattern | What it stores | Tracked? | Example fields | Cleanup |
|---|---|---|---|---|
| `runtime/run-continuation/README.md` | Documentation for the heartbeat directory | Tracked (explicit allow in root `.gitignore`) | N/A | Durable doc |
| `runtime/run-continuation/ses_*.json` | Heartbeat/continuation state for recent sessions | **Ignored** (`runtime/run-continuation/*`) | `sessionID`, `updatedAt`, per-source state (`active`/`idle`) | **No TTL specified** in current docs |

### Actions (recommended)

- Add an explicit TTL/GC note for `runtime/run-continuation/ses_*.json` and `runtime/logs/` (even a simple “delete >N days” policy), and implement via a small cleanup script (or document a `find ... -mtime +N -delete` recipe).

---

## Cross-root findings & quick wins

1. **Backups are scattered across multiple roots** (`data/backups/*` vs `${WORKSPACE}/backups/daily/*`). Decide one canonical SSOT and enforce retention there.
2. **Legacy SharedBrain root is a confusion magnet**: it is explicitly ignored as residue, but still contains DB artifacts. Either delete/migrate it or clearly mark it as deprecated/forensics-only.
3. **Runtime residue is well-bounded, but lacks TTL**: the boundary contracts are present, but lifecycle/GC for the actual residue files is not.

## Evidence (files and commands)

Referenced files (non-exhaustive):

- `data/README.md`
- `data/system-data-access-policy.yaml`, `data/runtime-space-access-policy.yaml`
- root `.gitignore` (ignores `SharedBrain/`, `data/backups/`, `data/**/*.db`, most of `runtime/*`)
- `scripts/daily-backup.sh`, `scripts/restore-from-backup.sh`
- `spaces/README.md`, `spaces/registry.yaml`, `spaces/system-space.yaml`, `spaces/runtime-space.yaml`, `spaces/_schema/*`
- `runtime/README.md`, `runtime/*boundary*.yaml`, `runtime/run-continuation/README.md`
- Backup manifests sampled: `data/backups/20260524/manifest.txt`, `data/backups/20260528_104825/manifest.txt`

Commands used to sample footprints:

- `du -sh data SharedBrain spaces runtime`
- `du -sh data/* runtime/* SharedBrain/*` (top-level)
