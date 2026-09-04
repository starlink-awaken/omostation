---
type: ssot
owner: governance-team
last_updated: 2026-09-03
---

# ZCode Workspace Runtime State Relocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relocate the complete active ZCode `.zcode` client state from Documents to durable macOS App Support through the application's native data-root contract.

**Architecture:** Deepen the existing Workspace-owned ZCode config owner with a fail-closed two-phase transaction. Copy the complete source into a temporary durable App Support target, verify and atomically publish it, restart against the target, then move the retained source into durable recovery. Recover the failed 1.0.0 runtime target from the healthy CLI DB backup and native seed without overclaiming purged data.

**Tech Stack:** Python 3.9-compatible standard library, pytest, JSON manifests, macOS `ps`/`lsof`, ZCode 3.10.1 native settings, Documents L4 audit, GaC.

## Global constraints

- Formal agent-workflow run and exact claims are required before implementation.
- No live desktop SQLite copy and no partial migration of a healthy source.
- No merge with the existing `~/.zcode/v2` state.
- No symlink, parallel launcher, or second configuration authority.
- Host mutation is reversible and must retain source, settings backup, payload backup, and manifest until post-restart finalize.

---

### Task 1: Build the transaction tool test-first

**Files:**
- Create: `lib/documents_zcode_state_relocation.py`
- Modify: `bin/gac/documents-zcode-config.py`
- Create: `tests/test_documents_zcode_state_relocation.py`
- Modify: `.github/workflows/phase-gate-enforce.yml`

- [x] Write failing tests for active-process rejection, critical-state
      completeness, target collision, insufficient disk, copy verification, settings
      preservation, apply, inspect, verify, and rollback.
- [x] Implement the smallest Python 3.9-compatible transaction module and CLI
      that make the tests pass.
- [x] Add `state-inspect/apply/verify/rollback` to the existing ZCode config
      owner and connect the focused test and Ruff surfaces to the existing
      Documents phase gate. Do not add another `bin/` entry.
- [x] Run focused pytest, Ruff, and Python 3.9 parse checks.

### Task 2: Execute the quiescent host transaction

**Host surfaces:**
- Modify: `/Users/xiamingxing/.zcode/v2/setting.json`
- Move: `/Users/xiamingxing/Documents/ZCode/.zcode`
- Create: `/Users/xiamingxing/Workspace/runtime/clients/zcode-data/.zcode`
- Create: `/Users/xiamingxing/Workspace/runtime/quarantine/documents-zcode-state-20260830/`

- [x] Capture preflight process, handle, source, target, disk, settings, and
      critical-state evidence.
- [x] Preserve CLI DB, native seed, surviving target, settings, and manifest in durable recovery before releasing the currently open deleted desktop DB inode.
- [x] Quit ZCode through its normal application lifecycle and prove quiescence.
- [x] Rebuild/publish the durable App Support target and validate its recovery manifest.
- [x] Restart ZCode normally; verify relocated handles, task/session continuity,
      no Documents writes, and an available rollback path.
- [x] Finalize by moving any retained Documents source into durable recovery; never delete it in this BET.

### Task 3: Close the Documents boundary and deliver

**Files:**
- Modify: `.omo/_truth/registry/documents-content-plane-migrations.yaml`
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Create: `docs/reports/2026-08-30-zcode-workspace-runtime-state-relocation.md`
- Create: `.omo/_knowledge/retros/BET-Y1Q3-T10-104.md`

- [x] Run consumer audit and a stable full Documents L4 audit.
- [x] Mark only `documents-client-state` complete when post-restart evidence and
      rollback evidence are both present.
- [ ] Run ledger verification, doc SSOT, focused tests, GaC, diff review, PR
      checks, squash merge, mainline ancestry, replay, and workflow closeout.
