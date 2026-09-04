---
type: ssot
owner: governance-team
last_updated: 2026-09-03
---

# Vault Daily Health Workspace Owner Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single stale vault-daily-health Documents executor with the canonical Workspace owner and Workspace heartbeat.

**Architecture:** Treat the Scheduled skill as one externally managed host configuration. Use an immutable preflight backup plus exact fingerprint, apply two bounded text changes atomically, verify the owner independently, then require the fixed consumer hard gate to become green.

**Tech Stack:** Markdown Scheduled skill, system Python 3.9, SHA-256, Workspace quarantine manifest, consumer audit, GaC.

## Global Constraints

- Only `vault-daily-health/SKILL.md` may change on the host.
- No accepted release, cron, LaunchAgent, cadence, or owner-code mutation.
- No source overwrite after fingerprint drift.
- Keep backup and rollback manifest permanently recoverable.

---

### Task 1: Capture preflight and backup

**Files:**
- Read: `/Users/xiamingxing/Documents/Claude/Scheduled/vault-daily-health/SKILL.md`
- Create: `/Users/xiamingxing/Workspace/runtime/quarantine/documents-scheduled-vault-daily-health-20260830/SKILL.md.before`
- Create: `/Users/xiamingxing/Workspace/runtime/quarantine/documents-scheduled-vault-daily-health-20260830/manifest.json`

**Interfaces:**
- Consumes: current source bytes and mode.
- Produces: exact source fingerprint and recoverable backup.

- [ ] **Step 1: Record source metadata**

Run: `stat -f '%Lp %z' /Users/xiamingxing/Documents/Claude/Scheduled/vault-daily-health/SKILL.md && shasum -a 256 /Users/xiamingxing/Documents/Claude/Scheduled/vault-daily-health/SKILL.md`

Expected: one regular file, stable mode/bytes/hash.

- [ ] **Step 2: Copy and verify backup**

Run: `cmp -s /Users/xiamingxing/Documents/Claude/Scheduled/vault-daily-health/SKILL.md /Users/xiamingxing/Workspace/runtime/quarantine/documents-scheduled-vault-daily-health-20260830/SKILL.md.before && shasum -a 256 /Users/xiamingxing/Documents/Claude/Scheduled/vault-daily-health/SKILL.md /Users/xiamingxing/Workspace/runtime/quarantine/documents-scheduled-vault-daily-health-20260830/SKILL.md.before`

Expected: byte-identical hashes and exit 0.

### Task 2: Apply exact Scheduled cutover

**Files:**
- Modify: `/Users/xiamingxing/Documents/Claude/Scheduled/vault-daily-health/SKILL.md`

**Interfaces:**
- Consumes: verified preflight fingerprint.
- Produces: Workspace owner command and Workspace heartbeat command.

- [ ] **Step 1: Replace the owner command**

```markdown
1. **全量检查**：运行 `/usr/bin/python3 "$HOME/Workspace/bin/gac/documents-domain-owner-job.py" learning-control-plane all --documents-root "$HOME/Documents" --workspace-root "$HOME/Workspace" --json`
```

- [ ] **Step 2: Replace the heartbeat command**

```markdown
`mkdir -p "$HOME/Workspace/runtime/heartbeats" && touch "$HOME/Workspace/runtime/heartbeats/vault-daily-health"`
```

- [ ] **Step 3: Verify bounded diff**

Run: `diff -u /Users/xiamingxing/Workspace/runtime/quarantine/documents-scheduled-vault-daily-health-20260830/SKILL.md.before /Users/xiamingxing/Documents/Claude/Scheduled/vault-daily-health/SKILL.md`

Expected: only the owner command block and heartbeat command differ.

### Task 3: Verify owner, consumer gate, and delivery

**Files:**
- Create: `docs/reports/2026-08-30-vault-daily-health-workspace-owner-cutover.md`
- Create: `.omo/_knowledge/retros/BET-Y1Q3-T10-103.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`

**Interfaces:**
- Consumes: postflight Scheduled skill and T10-102 consumer audit.
- Produces: owner canary, green consumer receipt, host manifest, and PR evidence.

- [ ] **Step 1: Run owner canary**

Run: `/usr/bin/python3 "$HOME/Workspace/bin/gac/documents-domain-owner-job.py" learning-control-plane all --documents-root "$HOME/Documents" --workspace-root "$HOME/Workspace" --json`

Expected: JSON `status=attention`, `writes_documents=false`, no unavailable
modes, and exit 1.

- [ ] **Step 2: Run consumer hard gate**

Run: `uv run --project projects/l4-kernel python bin/gac/documents-domain-owner-job.py consumer-audit --documents-root /Users/xiamingxing/Documents --registry .omo/_truth/registry/documents-content-plane-migrations.yaml --launch-agents-root /Users/xiamingxing/Library/LaunchAgents --scheduled-root /Users/xiamingxing/Documents/Claude/Scheduled --workspace-root "$PWD" --json`

Expected: exit 0, `status=ok`, `forbidden_executors=0`, `unmatched=0`.

- [ ] **Step 3: Run repo verification and submit**

Run: `uv run --with pyyaml python bin/plan/bet-ledger.py lint`

Run: `uv run --with pyyaml python bin/ssot/doc-ssot-lint.py --json`

Run: `make gac-local-gate`

Expected: all commands exit 0; PR checks pass and merge is reachable from main.
