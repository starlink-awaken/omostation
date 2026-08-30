---
status: active
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-30
---

# Agent Optimization Specification

> Governs five optimization mechanisms for multi-agent concurrent workspace operations.
> Source ADRs: ADR-0441 through ADR-0445.
> Related: ADR-0203 (requirement iteration workflow), ADR-0130 (P74 solidification), ADR-0128 (state generation concurrency).

## 1. Purpose

This specification defines the five mechanisms that protect the workspace from concurrency-induced data loss, numbering collisions, incomplete transactions, torn writes, and workflow bypass. Each mechanism has a defined problem, solution, verification command, and rollback path.

## 2. Mechanism Summary

| # | ADR | Mechanism | Target | Lock Type |
|---|-----|-----------|--------|-----------|
| 1 | ADR-0441 | Ledger Lock | `events.jsonl` append serialization | flock (advisory) |
| 2 | ADR-0442 | ADR Creation Protection | ADR number reservation | O_CREAT\|O_EXCL (atomic) |
| 3 | ADR-0443 | Submodule Pointer Automation | Submodule commit+push+parent transaction | Transaction script |
| 4 | ADR-0444 | High-Frequency File Write Lock | Projection file writes | temp+rename (atomic) |
| 5 | ADR-0445 | Agent Workflow Standardization | Workflow lifecycle enforcement | Gate-based (configurable) |

## 3. Mechanism Details

### 3.1 Ledger Lock (ADR-0441)

**Problem**: Concurrent agents appending to `events.jsonl` produce interleaved or lost entries.

**Solution**: File-based advisory lock (`flock`) on a sidecar `.lock` file. The wrapper `bin/ssot/ledger-append.sh` acquires the lock, appends the entry, and releases. The lock auto-releases on process exit or fd close, making it crash-safe.

**Verification**:
```bash
test -x bin/ssot/ledger-append.sh && echo "wrapper present"
bash tests/integration/ledger-concurrent-smoke.sh
wc -l /tmp/ledger-smoke.jsonl  # expect 1000 entries, zero lost
```

**Rollback**: Replace `flock` with directory-based mutex (`mkdir`/`rmdir`) in the wrapper script. No JSONL format change required.

### 3.2 ADR Creation Protection (ADR-0442)

**Problem**: Concurrent agents creating ADRs collide on the same number, producing duplicate files.

**Solution**: Atomic file creation via `open(..., O_CREAT|O_EXCL)` on a placeholder file. The helper `bin/ssot/adr-claim.sh` reserves the number atomically. The placeholder file doubles as the reservation marker visible to other agents.

**Verification**:
```bash
test -x bin/ssot/adr-claim.sh && echo "claim helper present"
bash tests/integration/adr-claim-concurrent-smoke.sh
test $(ls .omo/_knowledge/decisions/0NNN-placeholder-*.md 2>/dev/null | wc -l) -eq 1
```

**Rollback**: Fall back to directory-based mutex (`mkdir .omo/_knowledge/decisions/.adr-claim-lock`) before reading max number and creating the file.

### 3.3 Submodule Pointer Automation (ADR-0443)

**Problem**: Submodule pointer updates require three coordinated steps (submodule commit, submodule push, parent commit). Agents skip steps or execute out of order.

**Solution**: Transaction script `bin/ssot/submodule-pointer-transaction.sh` that performs all three steps with pre-conditions (stale pointer check), atomic execution, and idempotent recovery. Re-running after a partial failure completes the missing steps.

**Verification**:
```bash
test -x bin/ssot/submodule-pointer-transaction.sh && echo "script present"
bash bin/ssot/submodule-pointer-transaction.sh --dry-run --submodule projects/ecos
bash tests/integration/submodule-pointer-smoke.sh
bash bin/ssot/submodule-pointer-transaction.sh --verify --submodule projects/ecos
```

**Rollback**: Disable the script from the agent workflow `claim` path. Fall back to manual three-step process documented in AGENTS.md §6. The script does not modify git internals, so removal has no side effects.

### 3.4 High-Frequency File Write Lock (ADR-0444)

**Problem**: Concurrent writes to high-frequency projection files (`governance-data.json`, `system.yaml`) produce torn JSON/YAML and parse failures.

**Solution**: Atomic write via temp file + `rename(2)`. The helper `bin/ssot/atomic-write.sh` writes to a `.tmp` file, then renames it to the target. `rename` is atomic on POSIX local filesystems, so readers always see a complete file (old or new).

**Verification**:
```bash
test -x bin/ssot/atomic-write.sh && echo "helper present"
bash tests/integration/atomic-write-concurrent-smoke.sh
python3 -c "import json; json.load(open('.omo/_control/governance-data.json'))" && echo "valid JSON"
```

**Rollback**: For cross-filesystem cases where `rename` fails, fall back to per-file `flock` with bounded timeout. The helper script can implement both paths transparently.

### 3.5 Agent Workflow Standardization (ADR-0445)

**Problem**: Agents bypass the mandatory workflow lifecycle (ADR-0203), producing silent workflows and incomplete deliveries.

**Solution**: Tighten the existing `agent-workflow.py` runner with stricter gates:
- `verify` requires a prior `claim` (reject runs without path claims)
- `closeout` requires `bet_id` binding (reject runs without north-star linkage)
- `compliance` checks staged requirement-path edits for active runs (ADR-0204 gate)
- Evidence is diff-based, not self-reported

**Verification**:
```bash
uv run --with pyyaml python bin/agent-workflow.py compliance --json | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='pass'"
uv run --with pyyaml python bin/agent-workflow.py verify test-run-no-claim --from-diff --execute 2>&1 | grep "no claim"
uv run --with pyyaml python bin/agent-workflow.py closeout test-run-no-bet 2>&1 | grep "bet_id required"
bash tests/integration/agent-workflow-lifecycle-smoke.sh
```

**Rollback**: Set `AGCP_REQUIREMENT_ITERATION_GATE=0` as the escape hatch (ADR-0204). Adjust gate thresholds via `governance-checks.yaml` without removing gates entirely. Re-enable incrementally per workflow type.

## 4. Cross-Mechanism Interactions

| Interaction | Behavior |
|-------------|----------|
| Ledger Lock + Workflow Standardization | Workflow closeout events are appended through the ledger lock, ensuring no closeout event is lost |
| ADR Creation Protection + Workflow Standardization | ADR creation is a requirement iteration, so it must start a workflow run; the claim helper reserves the number, the workflow run tracks the delivery |
| Submodule Pointer + Atomic Write | Submodule pointer transaction uses atomic write for any state files it updates, preventing torn state |
| High-Frequency Write + Ledger Lock | Projection files use atomic write; the ledger uses flock. They do not interfere because they target different files |

## 5. Verification Suite

Run all five mechanism verifications in sequence:

```bash
# 1. Ledger lock
bash tests/integration/ledger-concurrent-smoke.sh

# 2. ADR creation protection
bash tests/integration/adr-claim-concurrent-smoke.sh

# 3. Submodule pointer automation
bash tests/integration/submodule-pointer-smoke.sh

# 4. High-frequency file write lock
bash tests/integration/atomic-write-concurrent-smoke.sh

# 5. Agent workflow standardization
bash tests/integration/agent-workflow-lifecycle-smoke.sh

# Aggregate gate
make gac-local-gate
```

## 6. Rollback Priority

If multiple mechanisms fail simultaneously, rollback in this order:

1. **Agent Workflow Standardization** (set `AGCP_REQUIREMENT_ITERATION_GATE=0`) — unblocks agents immediately
2. **High-Frequency File Write Lock** (switch to flock fallback) — restores write safety
3. **Submodule Pointer Automation** (fall back to manual three-step) — unblocks submodule updates
4. **ADR Creation Protection** (fall back to directory mutex) — unblocks ADR creation
5. **Ledger Lock** (fall back to directory mutex) — unblocks ledger appends

## 7. References

- ADR-0441: Ledger Lock Mechanism
- ADR-0442: ADR Creation Protection
- ADR-0443: Submodule Pointer Automation
- ADR-0444: High-Frequency File Write Lock
- ADR-0445: Agent Workflow Standardization
- ADR-0203: Requirement iteration mandatory workflow
- ADR-0204: Executable gate + pre-push path
- ADR-0130: P74 workflow solidification
- ADR-0128: State generation concurrency
- `.omo/standards/agent-workflow-contract.md` — workflow contract
