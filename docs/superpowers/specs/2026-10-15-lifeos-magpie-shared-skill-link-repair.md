---
schema_version: specification/v1
spec_version: 1.0.4
title: LifeOS and Magpie shared skill source recovery
bet_id: BET-Y2Q4-T10-253
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-15
---



# LifeOS and Magpie shared skill source recovery

## Background and problem

The 2026-10-15 static audit showed conflicting Bailian skill roots and cyclic `Browser`/`Utilities` links. A read-only source comparison found the Magpie Library copies are version 2.2.1 and the agent-local `.bailian` copies are 2.1.0. The Library is the shared source assigned by Magpie and is the correct single source for its clients.

## Invariants and scope

- Use the Magpie Library as the shared source for `bailian-cli`, `bailian-finetune`, `bailian-gen`, `bailian-managed-agent`, `bailian-protocol`, `bailian-sandbox`, and `bailian-web-search`.
- For every conflicting client, use Magpie's supported `library skill use-library <name> <agent>` operation. Preserve the displaced client-local source in Magpie's timestamped backup. Do not leave an agent with two active roots for one skill.
- The target scope is ten unique shared Library entries: the seven Bailian skills above plus `Browser`, `Utilities`, and `kems-gate-integrity-audit`. `Browser` and `Utilities` resolve through the stable recovered `Utilities` tree; `kems-gate-integrity-audit` resolves through its own stable recovered tree under `~/.config/magpie/library/recovered/`. Keep the original backup sources intact.
- Canonical source files remain unchanged; verified copies of `Investigation`, `Media`, `bailian-cli`, and `bailian-gen` were restored under `~/.config/magpie/library/recovered/`. The five old cyclic Library link payloads are archived as text and a tar snapshot under a dated Magpie backup; they are not rollback targets. The repair also restored the `Browser`, lowercase `browser`, and KEMS skill file entries.
- The latest static audit is `/Users/xiamingxing/Documents/Codex/2026-10-07/new-chat/outputs/magpie-integration-snapshots/mp015-recovered-sources-20261015.json`: 40 clients, zero rendered `FAIL`, 36 `UNKNOWN_NOT_RUN`, 3 `UNRESOLVED_MAPPING`, and 1 `DISABLED_BY_POLICY`. The derived summary separates the 12 entries in this repair scope (158 `PASS` observations) from two supplemental Bailian skills outside the scope (38 `PASS` observations). Loaded and usable are `UNKNOWN_NOT_RUN` for all 40 clients; this is not runtime success evidence.
- Preserve the unique LifeOS 7.40.4 core, USER, and MEMORY. Do not read, copy, hash, print, or submit credentials.
- No MCP settings were edited. Do not change unrelated skills, MCP definitions, client model settings, permissions, startup state, or user data. Do not commit or push.
- Static detection and path resolution do not prove that any client loaded or can use the skills.

## Acceptance criteria

| ID | Assertion | Evidence type |
|---|---|---|
| ISC-1 | All seven Bailian skills have one active Magpie Library source and resolve for every assigned client; the former client-local copies remain recoverable in Magpie backups. | Fresh static audit and backup readback |
| ISC-2 | Browser, Utilities, and KEMS shared targets resolve to the managed recovery area and match the recorded source hashes; no repaired path traverses a symlink loop. | Link readback, source hashes, cycle check |
| ISC-3 | The latest static audit reports 40 clients, zero rendered FAIL, 36 UNKNOWN_NOT_RUN, 3 UNRESOLVED_MAPPING, and 1 DISABLED_BY_POLICY; its derived summary lists 158 PASS observations for this scope and 38 supplemental PASS observations outside it. Unresolved mappings remain separate and do not become PASS by assumption. | `mp015-recovered-sources-20261015.json` and `mp015-selected-source-summary-20261015.json` under `/Users/xiamingxing/Documents/Codex/2026-10-07/new-chat/outputs/magpie-integration-snapshots/` |
| ISC-4 | Loaded and usable remain `UNKNOWN` for all 40 clients unless native client evidence proves otherwise. | Runtime-stage audit fields |
| ISC-5 | Receipt lists every modified shared pointer, the Magpie client/skill migration, preserved backups, and a safe recovery path that does not recreate the known loops. | Receipt and independent review |
| ISC-6 | Workflow doctor, SSOT guardian, GaC local gate, and workflow compliance outcomes are recorded. Pre-existing governance failures are not modified as part of this BET. | Command output |

## Non-goals

- Proving native session load or skill execution for all 40 clients.
- Resolving MCP mappings for `agy`, `claude`, or `cline`.
- Completing the broader Magpie P0–P4 redesign and implementation roadmap.
- Runtime rollout or reload, client restart, model inference, credentials, MCP settings changes, editing skill contents, external calls, commit, or push.

## Verification plan

- Compare each shared Library target to its verified recovery source hash.
- Run a fresh static capability audit; separately inspect rendered, loaded, and usable states.
- Run `uv run --python 3.13 --with pyyaml python bin/agent-workflow.py doctor`, SSOT guardian, `make gac-local-gate`, and workflow compliance.
- Independently review the receipt and rollback directions.

## Decision Log

| # | Fork | Decision | Reason |
|---|---|---|---|
| 1 | Treat `.bailian` copies as the root or use Magpie's shared Library | Use the Magpie Library v2.2.1 as the single source | The audit showed v2.1.0 native copies conflicted with the newer assigned Library source. |
| 2 | Manually overwrite client skill directories or use Magpie migration | Use `library skill use-library` | It preserves the displaced local source in backups and restores one active root. |
| 3 | Link production Library entries directly into dated backup storage or recover into a managed Library area | Recover verified skill trees under `library/recovered/` and point Library entries there | This avoids tying live agent paths to backup retention. |
| 4 | Promote static path evidence to runtime readiness | Keep loaded/usable unproven | Static configuration cannot show that an agent loaded or executed a skill. |
