---
schema_version: specification/v1
spec_version: 1.0.0
title: HITL Proposal System — Adoption Runbook for BET Owners
bet_id: BET-Y1Q4-T1-12
status: accepted
lifecycle: spec
type: integration-runbook
owner: omo-platform-team
created: 2026-09-04
last-reviewed: 2026-09-04
---

# HITL Proposal System — Adoption Runbook

> **Audience**: BET owners adding new L2/L0 risk BETs that need human approval before execution.
> **Prerequisite**: BET-Y1Q4-HITL-01 has merged (PR #3077 + #129 + #3119).

## 1. When to Use HITL on a BET

Add `human_gate: true` to a BET entry when:

- ✅ Risk level is **L0** or **L2** (per ADR-0444)
- ✅ Action involves **execution, mutation, or production-affecting change**
- ✅ Principal should review before agent proceeds
- ❌ NOT for read-only analysis (use observation/audit instead)
- ❌ NOT for L1/L3 risks (existing claim/verify pattern suffices)

## 2. Minimal Setup (3 steps)

### Step 1: Mark the BET as human-gated

In `docs/plans/3y-bet-ledger.yaml`:

```yaml
- id: BET-YOUR-ID
  title: Your BET title
  risk_level: L2              # or L0
  human_gate: true             # ← add this
  # ... other fields
```

### Step 2: Verify the gate fires locally

```bash
python3 bin/hitl-proposal.py check --bet-id BET-YOUR-ID
# Output should be: HITL_REQUIRED
```

If it returns nothing, the BET entry is malformed. Re-check YAML.

### Step 3: Test the full flow

```bash
# 1. Create proposal (what harness will do)
python3 bin/hitl-proposal.py create \
  --bet-id BET-YOUR-ID \
  --run-id "manual-test" \
  --title "Test execution" \
  --description "Verifying HITL flow"

# 2. List as principal
bin/cockpit decide list
# → shows your proposal

# 3. Approve
bin/cockpit decide approve <proposal-id>

# 4. Verify
python3 bin/hitl-proposal.py get <proposal-id> | grep "status:"
# → status: approved
```

## 3. Integration Points

### 3.1 Harness auto-detects (no code change)

`bin/harness stage_execute` already checks `human_gate` and creates proposal automatically:

```bash
bin/harness run --bet BET-YOUR-ID --profile governance-agent --objective "..."
# Output: "HITL proposal created: hitl-..."
# Then: "Run: cockpit decide approve hitl-..."
```

### 3.2 Optional: enable blocking wait (v1.0 opt-in, v1.1 default)

```bash
bin/harness run --bet BET-YOUR-ID --profile governance-agent --objective "..." \
  --hitl-wait --hitl-timeout 86400
# → blocks until proposal is approved/rejected/expired
# → 24h default timeout (matches TTL)
```

### 3.3 Cockpit CLI (native after PR #129 + #3119 merge)

```bash
bin/cockpit decide list                    # shows pending HITL proposals
bin/cockpit decide approve <proposal-id>   # approves via cockpit-internal path
bin/cockpit decide reject <proposal-id>    # rejects
bin/cockpit decide status                  # adds HITL counts to inbox status
```

### 3.4 Actor auto-capture (zero-config)

By default, `response_actor` is auto-captured from `git config user.name/email`. No need to pass `--actor` flag unless you want to override.

## 4. Circuit Breaker Behavior

| Failure | Behavior |
|---------|----------|
| `check_human_gate_needed` throws | direct execution (no HITL) |
| `create_proposal` fails (disk/perm) | direct execution, stderr warn |
| Proposal 24h TTL expires | system actor auto-`expired`, agent continues |
| `fcntl.flock` fails (NFS) | in-process lock fallback |
| Cockpit submodule unmerge | subprocess delegation to `bin/hitl-proposal.py` |

In all cases, **agent never deadlocks** — HITL is "best effort approval", not a hard gate.

## 5. Observability

### Per-proposal audit trail

```bash
python3 bin/hitl-proposal.py get <proposal-id>
```

Returns full YAML with:
- `created_at` / `expires_at` (TTL)
- `responded_at` (when principal acted)
- `response_actor` (git user or override)
- `response_option` (approve/reject)

### Harness run evidence

`bin/harness run` records each stage including `hitl_proposal` check:
```json
"hitl_proposal": {
  "ok": true,
  "proposal_id": "hitl-..."
}
```

See `.omo/_delivery/harness-runs/<run-id>.json`.

### Cross-BET status

```bash
python3 bin/hitl-proposal.py list --status pending    # all pending
python3 bin/hitl-proposal.py list --status approved   # all approved
python3 bin/hitl-proposal.py list --status expired    # circuit-breaker hits
```

## 6. Migration Checklist (for existing L2 BETs)

- [ ] Add `human_gate: true` to the BET entry
- [ ] Run `python3 bin/hitl-proposal.py check --bet-id <id>` → must return `HITL_REQUIRED`
- [ ] Test E2E: create → list → approve → status check
- [ ] Update BET retro to mention HITL adoption
- [ ] (Optional) Update BET's `done_when` to require "HITL proposal approved before completion"

## 7. v1.1 Coming Soon (BET-Y1Q4-HITL-02)

- Slack/email notification when proposal created
- `--hitl-wait` becomes default (no flag needed)
- Distributed lock (etcd/redis) for multi-node
- `notified_at` field on proposal

Until v1.1 lands, you must manually `bin/cockpit decide list` to find pending proposals.

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `check` returns nothing | BET entry missing `human_gate: true` or wrong risk_level | Add `human_gate: true` |
| `list` shows nothing but I just created one | proposals dir mismatch | Check `HITL_PROPOSALS_DIR` env var |
| `approve` returns "Proposal not found" | Wrong ID (full vs prefix) | Use prefix or full ID |
| `cockpit decide list` doesn't show HITL | Submodule pointer not on PR #129 merge commit | Run `scripts/wait-and-bump-cockpit.sh` |
| 24h timeout fired and action proceeded | TTL circuit breaker (intended) | Principal didn't approve in time; review retro |

## 9. Related

- Spec: `docs/superpowers/specs/2026-09-04-hitl-proposal-system-design.md`
- ADR: `.omo/_knowledge/decisions/0460-hitl-proposal-system.md`
- Retro: `.omo/_knowledge/retros/BET-Y1Q4-HITL-01.md`
- Patterns: P97 / P98 / P99 (in `.omo/_knowledge/patterns/`)
- Helper: `scripts/wait-and-bump-cockpit.sh`
