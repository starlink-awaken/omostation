# ZCode Workspace Runtime State Relocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relocate the complete active ZCode `.zcode` client state from Documents to Workspace runtime through the application's native data-root contract.

**Architecture:** Add one Workspace-owned, fail-closed transaction tool around ZCode's existing `dataBaseDir` setting. Test its pure inspection and transaction invariants first, quiesce ZCode, use a same-volume atomic rename, restart, and prove the process/file-handle cutover before updating the migration registry.

**Tech Stack:** Python 3.9-compatible standard library, pytest, JSON manifests, macOS `ps`/`lsof`, ZCode 3.10.1 native settings, Documents L4 audit, GaC.

## Global constraints

- Formal agent-workflow run and exact claims are required before implementation.
- No live SQLite copy and no partial file selection.
- No merge with the existing `~/.zcode/v2` state.
- No symlink, parallel launcher, or second configuration authority.
- Host mutation is reversible and must retain a settings backup plus manifest.

---

### Task 1: Build the transaction tool test-first

**Files:**
- Create: `lib/documents_zcode_state_relocation.py`
- Create: `bin/gac/documents-zcode-state-relocation.py`
- Create: `bin/_registry/scripts/governance/documents-zcode-state-relocation.yaml`
- Create: `tests/test_documents_zcode_state_relocation.py`
- Modify: `.github/workflows/phase-gate-enforce.yml`

- [ ] Write failing tests for active-process rejection, critical-state
      completeness, target collision, cross-device rejection, settings
      preservation, apply, inspect, verify, and rollback.
- [ ] Implement the smallest Python 3.9-compatible transaction module and CLI
      that make the tests pass.
- [ ] Register the CLI and connect the focused test and Ruff surfaces to the
      existing Documents phase gate.
- [ ] Run focused pytest, Ruff, and Python 3.9 parse checks.

### Task 2: Execute the quiescent host transaction

**Host surfaces:**
- Modify: `/Users/xiamingxing/.zcode/v2/setting.json`
- Move: `/Users/xiamingxing/Documents/ZCode/.zcode`
- Create: `/Users/xiamingxing/Workspace/runtime/clients/zcode-data/.zcode`
- Create: `/Users/xiamingxing/Workspace/runtime/quarantine/documents-zcode-state-20260830/`

- [ ] Capture preflight process, handle, source, target, disk, settings, and
      critical-state evidence.
- [ ] Quit ZCode through its normal application lifecycle and prove quiescence.
- [ ] Run the guarded apply transaction and validate its manifest.
- [ ] Restart ZCode normally; verify relocated handles, task/session continuity,
      no Documents writes, and an available rollback path.

### Task 3: Close the Documents boundary and deliver

**Files:**
- Modify: `.omo/_truth/registry/documents-content-plane-migrations.yaml`
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Create: `docs/reports/2026-08-30-zcode-workspace-runtime-state-relocation.md`
- Create: `.omo/_knowledge/retros/BET-Y1Q3-T10-104.md`

- [ ] Run consumer audit and a stable full Documents L4 audit.
- [ ] Mark only `documents-client-state` complete when post-restart evidence and
      rollback evidence are both present.
- [ ] Run ledger verification, doc SSOT, focused tests, GaC, diff review, PR
      checks, squash merge, mainline ancestry, replay, and workflow closeout.
