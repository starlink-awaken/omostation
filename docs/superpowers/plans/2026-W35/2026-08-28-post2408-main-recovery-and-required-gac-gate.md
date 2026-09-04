---
status: planned
lifecycle: plan
owner: governance-team
created: 2026-08-28
last_updated: 2026-09-02
bet_id: BET-Y1Q3-T6-15
value_indicator_policy: false
type: ssot
last_updated: 2026-09-03
---

# Post-2408 Main Recovery and Required GaC Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a truthful latest-main governance baseline, make the existing `gac-gate` immutable and blocking, add it to branch protection only after a real main canary, then remove and prevent tracked runtime artifacts while preserving live-host data.

**Architecture:** Reuse the existing GaC checklist, CI registry, branch-protection script, runtime policy, Agent Workflow and BET completion writer. Deliver in strict order `R1 -> H1a -> H1b -> H1c -> R2a -> R2b`; repository PRs and live-host operations remain separate authorities. No new workflow, registry, dispatcher, state store or control plane is introduced.

**Tech Stack:** Python 3.13, Bash, PyYAML, pytest, Git/GitHub CLI, GitHub Actions, Agent Workflow, `bin/gac/gac-local-gate.py`, `bin/plan/bet-ledger.py`.

## 2026-09-02 Self-Hosting Recovery Slice

Before the historical R1 steps, restore only the five archive files whose
canonical paths are still hard-bound by the workflow runner, blocking gate, or
strict document-link validation. Verify each restored file matches its archive
source except any line-ending whitespace rejected by `git diff --check`. Then repair the `projects/ecos` `ConstraintL0` M2 parent
and missing M1 `rule`/`violation` properties in a child PR, merge the child,
and update the root gitlink plus `.omo/_truth/registry/mof-capabilities.yaml`
M1 count. Do not classify ignored local directories as source, delete them, or
use an escape to bypass an immutable failure.

## 2026-08-28 Latest-Main Rebaseline

This plan was re-audited after the delivery clone froze at `1289e7fd6df0b85492fb591f2df8900e863c4a2f` and remote main advanced to `6bcf17b4e7f2d0de6f444bd5e5da10dd7ad7c3c8`. The following commits and live reads are evidence, not permission to skip remaining gates:

| Main evidence | Honest disposition |
|---|---|
| `ad19e2202` / PR #2438 | R1 **PARTIAL**: ADR-0432 is candidate/UNPROVABLE and two tracked artifacts were removed; its own report says full strict GaC was still blocked. |
| `05e813ba5` / PR #2441 | H1a **PARTIAL**: the strict step is blocking, but the workflow still mutates the checkout before it runs. |
| [main run `33162551807`](https://github.com/starlink-awaken/omostation/actions/runs/33162551807) at `db34192d4` | GitHub Actions API receipt: `event=push`, job `gac-gate=success`, strict step `success`. It predates immutable H1a and therefore is historical evidence, not the required H1b canary. |
| `66a703b59` / [PR #2451](https://github.com/starlink-awaken/omostation/pull/2451) | The stale Core/Sentinel architecture row was removed. R1 repository blockers are now `already_resolved`, but that main push's `gac-gate` failed and immutable H1a evidence still does not exist. |
| [main run `33164830199`](https://github.com/starlink-awaken/omostation/actions/runs/33164830199) at `77258bdff` | Later `gac-gate=success`, but it still used the mutating pre-H1a workflow. It is baseline-health evidence only, not the required immutable H1b canary. |
| `1289e7fd6` / [PR #2455](https://github.com/starlink-awaken/omostation/pull/2455) | The writer now uses the documented `required_status_checks` PATCH subresource and leaves live protection untouched. It remains **PARTIAL and out of order**: only one pre-write read means concurrent context drift can still be overwritten, and no operation receipt exists. |
| `6bcf17b4e` / [PR #2457](https://github.com/starlink-awaken/omostation/pull/2457) | R2a **PARTIAL / out of order**: 25 runtime artifacts were untracked and `--treeish` exists. Fresh-main command returns `ok=true`, but the merged targeted suite is stale (`1 failed, 1 passed`) and no `omo-runtime-final-tree` blocking gate is wired into root GaC. R2b was explicitly not performed. |
| `c5363fc16` / [PR #2459](https://github.com/starlink-awaken/omostation/pull/2459) | **DISPUTED evidence projection**: it states H1c and R2a are verified, attributes H1c work to unrelated PR #2452, and claims cache-busted/live/fresh-clone proof. Those claims are contradicted by missing external receipts, the fresh-clone failing targeted suite and absent root gate wiring. Preserve the history but do not consume it as completion evidence. |
| `d4bcf62ac` / [PR #2458](https://github.com/starlink-awaken/omostation/pull/2458) | The earlier plan artifact was concurrently moved from Draft to Ready and merged before explicit human approval and before the `6bc/H1c/R2a` audit finished. Its merge proves only that old plan bytes landed; it is not human plan approval. This rebaseline amendment supersedes those bytes. |
| live branch protection GET at `2026-08-28T11:33:01Z` | Direct endpoint `GET /repos/starlink-awaken/omostation/branches/main/protection`; normalized redacted digest `sha256:9261174fd9b814f48bc602ea4ee3fe42020ed4d2a5b3b1d6941556e767730ded`; contexts are `phase-gate`, `bet-done-transition`, `gac-gate`. Both required external receipt directories are missing, so the already-live H1c state is `UNPROVABLE` pending human adopt-or-rollback adjudication. |
| current final tree | Bound runtime artifacts matched by the reviewed families are now untracked (`0` remain); recurrence tests/wiring and host-retention evidence remain incomplete. |
| live Workspace read at `2026-08-28T11:33Z` | Shared checkout remains at `77258bdff`, before R2a main; 25 of 26 exact ledger runtime paths remain present locally and the historical heartbeat is absent. No backup/integrity/producer receipt exists, so this proves local presence only, not R2b retention/migration. |

R1 repository blockers are already resolved. H1a immutability, CI binding, a post-H1a canary, human adjudication of the premature live context, R2a test/wiring completion, R2b and final closeout remain outstanding. Every execution phase still recomputes its own latest-main failure set.

## Global Constraints

- Canonical BET: `BET-Y1Q3-T6-15`; WorkPacket: `WP-BET-Y1Q3-T6-15`.
- Accepted Spec: `docs/superpowers/specs/2026-08-28-post2408-main-recovery-and-required-gac-gate-design.md`, version `1.0.0`, digest `sha256:afd7daded6ab2e279c5b0c5d2f9e9465263c541316d034acafb8fa0671028459`, until the separately authorized Task 4B amendment replaces it.
- Every repository task starts from execution-time latest `origin/main` in a new governance-profile independent clone.
- Maximum one repository writer in each of R1, H1a/H1c and R2a. Read-only reviewers may run in parallel.
- The intended order remains R1 -> H1a -> H1b -> H1c -> R2a -> R2b. Concurrent work violated that order; existing H1c/R2a effects are quarantined as partial evidence until H1 is reconciled and a human adopts or rolls back the live context.
- H1c reconciliation and R2b require new, operation-specific human authorization. This plan does not adopt, repeat, or roll back either live mutation.
- `gac-gate` remains the only GaC workflow/job. `phase-gate` keeps its existing owner-job responsibility.
- CI blocking checks must run against an immutable checkout and leave HEAD, index and worktree unchanged.
- CI surface binding remains workflow-level. Unsupported `job`, `step`, `job_id`, `step_id` or `required` registry fields are forbidden.
- Repository untracking never proves live-host retention. R2a and R2b have separate receipts and rollback boundaries.
- `value_indicator_policy=false`; value remains `NOT_PROVEN` with empty value evidence. Successful engineering or operations never create personal value evidence.
- Product P0 WP1 code already exists on main but its BET remains candidate/evaluating. No new Wave A writer starts until this BET reaches `delivery_accepted`.
- Do not modify unrelated historical completion evidence, service/runtime state, gitlinks, submodule contents or user configuration.

## File Responsibility Map

| Surface | Responsibility |
|---|---|
| `docs/plans/3y-bet-ledger.yaml` | Task -1 only: refine T6-15 write surfaces from execution-time latest main before implementation starts; never change status, binding or completion. |
| `ARCHITECTURE.md` | Read-only R1 guard at `1289e7fd6`; modify only if execution-time latest main reintroduces the two stale Core/Sentinel links. |
| `.omo/_truth/governance-evidence/waiver-2026-08-28-post2408-recovery-gac-required-binding.md` | Read-only prior R1 evidence unless latest-main validation proves a new structural regression. |
| `.omo/_knowledge/decisions/0432-north-star-v3-6-axis-escalation.md` and `INDEX.md` | Read-only prior R1 evidence; ADR-0432 must remain candidate/UNPROVABLE. |
| `.github/workflows/gac-gate.yml` | Make the existing job check-only, immutable and blocking. |
| `.omo/_truth/registry/ci-surfaces.yaml` | Bind script-registry validation to `gac-gate.yml` using supported workflow-level fields. |
| `tests/test_gac_gate_workflow_purity.py` | Lock immutable workflow behavior and strict-step blocking semantics. |
| `tests/test_ci_surfaces.py` | Lock supported script-registry workflow binding. |
| `bin/gac/gac-branch-protection.sh` | Keep the documented status-checks PATCH subresource from `1289e7fd6`, add a second pre-write read/race refusal and redacted receipt, and remove false atomic-CAS wording. |
| `tests/test_gac_branch_protection.py` | Extend the existing fake-API tests to prove two reads, race refusal, exact preservation and redacted receipts. |
| `bin/gac/omo-runtime-stamp-policy.py` | Deepen the partial `6bcf17b4e` treeish classifier with mode-aware deterministic evidence. |
| `tests/test_omo_runtime_stamp_policy.py` | Replace the stale merged negative assertion and cover forbidden/allowed/mode/revision behavior on immutable trees. |
| `bin/gac/gac-local-gate.py` | Wire `omo-runtime-final-tree` as a root-owned blocking gate. |
| `.gitignore` | Retain the landed R2a ignore behavior while narrowing reviewed family patterns where needed. |
| `docs/reports/2026-08-28-post2408-main-recovery-closeout.md` | Redacted R1/H1/R2 receipts and final acceptance mapping. |
| `.omo/_knowledge/retros/BET-Y1Q3-T6-15.md` | Five-question retrospective and surface accounting at final closeout. |

## Plan-Approval Decision: CAS Terminology Amendment

The current accepted Spec and BET use the term `compare-and-swap` for H1c. GitHub's official REST guidance says conditional requests for unsafe methods (`POST`, `PUT`, `PATCH`, `DELETE`) are unsupported unless the specific endpoint documents an exception; the branch-protection update endpoint documents no such exception. A returned ETag plus an `If-Match` request header therefore does not prove atomic PUT. Claiming atomic CAS would be false. Source: https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#use-conditional-requests-if-appropriate

Plan approval must also approve a narrow Spec/BET amendment before Task 5 starts:

```text
CAS / compare-and-swap
  -> guarded double-read read-modify-write
```

The replacement contract is: GET A, validate expected contexts and preserved-field digest, GET B immediately before PATCH, require `digest(B)==digest(A)`, perform one `required_status_checks` subresource PATCH, then GET C and verify the exact full-protection result. A residual race remains between GET B and PATCH; H1c therefore retains a separate human gate, a redacted before/after receipt and an exact context-only rollback. No Task 5/6 implementation begins until Spec version/binding and BET wording are updated and reviewed.

## Per-Phase Governed Delivery Lifecycle

Scope refinement, R1, H1a, guarded-update amendment, H1c-tool, R2a and closeout each use a new clone and a new run. Set `T6_PHASE` to exactly one of `scope`, `r1`, `h1a`, `amendment`, `h1c-tool`, `r2a`, `closeout`, then run:

```bash
export T6_ACTOR="product-p0-recovery-${T6_PHASE}"
export T6_ATTEMPT="t6-15-${T6_PHASE}-$(date -u +%Y%m%dT%H%M%SZ)"
export T6_DEST="/Users/xiamingxing/agents/${T6_ACTOR}/attempts/${T6_ATTEMPT}/ws"
cd /Users/xiamingxing/Workspace
git fetch origin main --prune
python3 bin/gac/clone-lifecycle.py onboard \
  --agent-id "$T6_ACTOR" \
  --delivery-attempt-id "$T6_ATTEMPT" \
  --source https://github.com/starlink-awaken/omostation.git \
  --revision origin/main \
  --destination "$T6_DEST" \
  --expected-repository starlink-awaken/omostation \
  --profile governance
cd "$T6_DEST"
export AGENT_ID="$T6_ACTOR"
export T6_RUN_ID="$(uv run --with pyyaml python bin/agent-workflow.py start bet-execution --profile governance-agent --bet BET-Y1Q3-T6-15 --objective "BET-Y1Q3-T6-15 ${T6_PHASE}" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
uv run --with pyyaml python bin/gac/affected-graph.py \
  --workspace-root . \
  --changed-projects workspace-root \
  --output ".omo/evidence/${T6_RUN_ID}/affected-graph-receipt.json" \
  --json
```

The `.omo/evidence/${T6_RUN_ID}/affected-graph-receipt.json` write is produced by the mandatory workflow broker and is runtime evidence, not a deliverable write surface. Implementation agents must not create other `.omo/evidence` files.

Create the exact claim list for the selected phase:

```bash
case "$T6_PHASE" in
  scope)
    printf '%s\n' \
      docs/plans/3y-bet-ledger.yaml > /tmp/t6-phase-claims.txt
    ;;
  r1)
    printf '%s\n' \
      ARCHITECTURE.md \
      .omo/_truth/governance-evidence/waiver-2026-08-28-post2408-recovery-gac-required-binding.md \
      .omo/_knowledge/decisions/0432-north-star-v3-6-axis-escalation.md \
      .omo/_knowledge/decisions/INDEX.md \
      docs/reports/2026-08-28-post2408-main-recovery-closeout.md \
      .omo/_knowledge/retros/BET-Y1Q3-T6-15.md \
      bin/_registry/scripts/governance/templates.yaml \
      .omo/_truth/registry/governance-checks.yaml > /tmp/t6-phase-claims.txt
    ;;
  h1a)
    printf '%s\n' \
      .github/workflows/gac-gate.yml \
      tests/test_gac_gate_workflow_purity.py \
      .omo/_truth/registry/ci-surfaces.yaml \
      tests/test_ci_surfaces.py > /tmp/t6-phase-claims.txt
    ;;
  amendment)
    printf '%s\n' \
      docs/superpowers/specs/2026-08-28-post2408-main-recovery-and-required-gac-gate-design.md \
      docs/plans/3y-bet-ledger.yaml \
      .omo/_truth/governance-evidence/waiver-2026-08-28-t6-15-guarded-update-amendment.md > /tmp/t6-phase-claims.txt
    ;;
  h1c-tool)
    printf '%s\n' \
      bin/gac/gac-branch-protection.sh \
      tests/test_gac_branch_protection.py > /tmp/t6-phase-claims.txt
    ;;
  r2a)
    printf '%s\n' \
      .gitignore \
      bin/gac/gac-local-gate.py \
      bin/gac/omo-runtime-stamp-policy.py \
      tests/test_omo_runtime_stamp_policy.py \
      tests/unit/gac/test_gac_local_gate_purity.py > /tmp/t6-phase-claims.txt
    uv run --with pyyaml python - <<'PY' >> /tmp/t6-phase-claims.txt
import subprocess, yaml
d=yaml.safe_load(open('docs/plans/3y-bet-ledger.yaml'))
b=next(item for item in d['bets'] if item['id']=='BET-Y1Q3-T6-15')
for pattern in (p for p in b['write_surfaces'] if p.startswith('runtime/')):
    print(subprocess.run(['git','ls-files','--',pattern], text=True, capture_output=True, check=True).stdout, end='')
PY
    sort -u /tmp/t6-phase-claims.txt -o /tmp/t6-phase-claims.txt
    ;;
  closeout)
    printf '%s\n' \
      docs/reports/2026-08-28-post2408-main-recovery-closeout.md \
      .omo/_knowledge/retros/BET-Y1Q3-T6-15.md \
      docs/plans/3y-bet-ledger.yaml > /tmp/t6-phase-claims.txt
    ;;
  *)
    echo "invalid T6_PHASE=$T6_PHASE" >&2
    exit 2
    ;;
esac
while IFS= read -r path; do
  uv run --with pyyaml python bin/agent-workflow.py claim "$T6_RUN_ID" \
    --path "$path" \
    --actor xiamingxing \
    --affected-receipt ".omo/evidence/${T6_RUN_ID}/affected-graph-receipt.json"
done < /tmp/t6-phase-claims.txt
```

At phase completion, the phase task first creates its scoped commit. Then verify every claimed file explicitly, close the run, create a delivery tag, submit one PR, verify the merged main SHA, and retire using the exact merged PR number. This generic `closeout --status ok` flow applies to `scope`, `r1`, `h1a`, `h1c-tool`, `r2a` and `closeout`. `amendment` alone uses the explicit blocked-closeout exception in Task 4B because it intentionally changes the active run's accepted Spec binding source; its verify result is reported independently from that explicit terminal status.

```bash
verify_args=()
while IFS= read -r path; do verify_args+=(--file "$path"); done < /tmp/t6-phase-claims.txt
uv run --with pyyaml python bin/agent-workflow.py verify "$T6_RUN_ID" "${verify_args[@]}" --execute --json
uv run --with pyyaml python bin/agent-workflow.py closeout "$T6_RUN_ID" --status ok "${verify_args[@]}" --json
git tag -a "delivery/${T6_ATTEMPT}" -m "BET-Y1Q3-T6-15 ${T6_PHASE}" HEAD
git push -u origin HEAD --follow-tags
```

After the phase PR is normally merged and the source branch is deleted:

```bash
export PHASE_PR_NUMBER="$(gh pr view --json number --jq .number)"
cd /Users/xiamingxing/Workspace
python3 bin/gac/clone-lifecycle.py retire \
  --destination "$T6_DEST" \
  --platform-rebased-pr "$PHASE_PR_NUMBER"
```

Expected: `retire_ok`. A fail-closed provenance/identity error is reported as a clone-lifecycle mechanism gap; do not manually delete the clone.

If full GaC fails only on a reproduced latest-main baseline outside the phase diff, close `blocked`, release every lock and report the exact signature. Do not mark the phase or BET complete. Never reuse that clone for the next phase.

---

### Task -1: Latest-Main WorkPacket Scope Refinement

This writing-plan PR intentionally contains only the plan file. Before any R1/H1/R2 implementation, create a fresh `scope` delivery attempt from then-current main and update only T6-15 `write_surfaces`. The existing WorkPacket already authorizes its own ledger path, so this phase uses the normal workflow and needs no bypass waiver.

**Files:**
- Modify: `docs/plans/3y-bet-ledger.yaml` only inside `BET-Y1Q3-T6-15.write_surfaces`

**Interfaces:**
- Consumes: approved writing plan and execution-time latest main.
- Produces: an exact WorkPacket whose path claims cover Task 4B, root GaC wiring and intentional runtime untracking without making untracked exact paths fail D0 completion.

- [ ] **Step 1: Start and claim the scope phase**

Set `T6_PHASE=scope` and execute the Per-Phase Governed Delivery Lifecycle. Confirm the active run claims only `docs/plans/3y-bet-ledger.yaml` and that T6-15 is still candidate/evaluating.

- [ ] **Step 2: Replace only the T6-15 surface list mechanically**

Use a targeted read/check/modify/write script; do not dump/reformat the full ledger:

```bash
uv run --with pyyaml python - <<'PY'
from copy import deepcopy
from fnmatch import fnmatch
from pathlib import Path
import yaml

ledger = Path('docs/plans/3y-bet-ledger.yaml')
text = ledger.read_text(encoding='utf-8')
start = text.index('- id: BET-Y1Q3-T6-15\n')
end = text.find('\n- id:', start + 1)
if end < 0:
    end = len(text)
block = text[start:end]
payload = yaml.safe_load('bets:\n' + ''.join('  ' + line + '\n' for line in block.splitlines()))
before = payload['bets'][0]
assert before['status'] == 'candidate'
frozen = {
    'accepted_specifications': deepcopy(before['accepted_specifications']),
    'completion_evidence': deepcopy(before['completion_evidence']),
    'status': before['status'],
}

patterns = [
    'runtime/bos-neural-mesh-*',
    'runtime/concept-weave-preflight*.json',
    'runtime/consumer-audit-*.json',
    'runtime/control/evidence/documents-weijian-*/documents-weijian-*.json',
    'runtime/daily-health-preflight*.json',
    'runtime/heartbeats/weijian-*',
    'runtime/kos-preflight-*.json',
    'runtime/predictor-preflight*.json',
    'runtime/quarantine/documents-bos-neural-mesh-20260828/*',
    'runtime/task-inventory/snapshots/2026082[78]-*.json',
]
surfaces = list(before['write_surfaces'])
unknown_runtime = [
    item for item in surfaces
    if item.startswith('runtime/') and not any(fnmatch(item, pattern) for pattern in patterns)
]
assert not unknown_runtime, f'UNCLASSIFIED_RUNTIME_SURFACE: {unknown_runtime}'
surfaces = [
    item for item in surfaces
    if not item.startswith('runtime/') and item != 'bin/INDEX.md'
]
for item in (
    '.gitignore',
    '.omo/_truth/governance-evidence/waiver-2026-08-28-t6-15-guarded-update-amendment.md',
    'bin/gac/gac-local-gate.py',
):
    if item not in surfaces:
        surfaces.append(item)
surfaces.extend(pattern for pattern in patterns if pattern not in surfaces)
assert len(surfaces) == len(set(surfaces))

ws_start = block.index('  write_surfaces:\n')
ws_end = block.index('  pasw_required:', ws_start)
replacement = '  write_surfaces:\n' + ''.join(f'  - {item}\n' for item in surfaces)
new_block = block[:ws_start] + replacement + block[ws_end:]
new_text = text[:start] + new_block + text[end:]
ledger.write_text(new_text, encoding='utf-8')

after_all = yaml.safe_load(new_text)
after = next(item for item in after_all['bets'] if item['id'] == 'BET-Y1Q3-T6-15')
for key, value in frozen.items():
    assert after[key] == value, key
PY
```

- [ ] **Step 3: Prove the scope diff is exact**

```bash
test "$(git diff --name-only)" = "docs/plans/3y-bet-ledger.yaml"
git diff --check
uv run --with pyyaml python bin/plan/bet-ledger.py show BET-Y1Q3-T6-15
uv run --with pyyaml python - <<'PY'
import subprocess, yaml
main = yaml.safe_load(subprocess.run(
    ['git', 'show', 'origin/main:docs/plans/3y-bet-ledger.yaml'],
    text=True, capture_output=True, check=True,
).stdout)
current = yaml.safe_load(open('docs/plans/3y-bet-ledger.yaml'))
before = {item['id']: item for item in main['bets']}
after = {item['id']: item for item in current['bets']}
changed = [bet_id for bet_id in after if after[bet_id] != before.get(bet_id)]
assert changed == ['BET-Y1Q3-T6-15'], changed
bet = after[changed[0]]
patterns = [item for item in bet['write_surfaces'] if item.startswith('runtime/')]
assert len(patterns) == 10 and all('*' in item for item in patterns)
expanded = set()
for pattern in patterns:
    expanded.update(subprocess.run(
        ['git', 'ls-files', '--', pattern], text=True, capture_output=True, check=True,
    ).stdout.splitlines())
print(f'scope-refinement: PASS runtime_paths={len(expanded)}')
PY
```

Expected at observed main `6bcf17b4e`: ten patterns expand to `0` tracked paths because #2457 already untracked the reviewed artifacts. The execution-time count may differ, but every match and every pre-refinement exact runtime surface must belong to the same ten reviewed families. An empty expansion is valid after proven R2a untracking. No BET status, accepted binding, completion/value evidence, goal or implementation file changes.

- [ ] **Step 4: Commit and publish the unique scope PR**

```bash
git add docs/plans/3y-bet-ledger.yaml
git commit -m "docs(plan): refine T6-15 execution surfaces"

verify_args=(--file docs/plans/3y-bet-ledger.yaml)
uv run --with pyyaml python bin/agent-workflow.py verify "$T6_RUN_ID" \
  "${verify_args[@]}" --execute --json > /tmp/t6-scope-verify.json 2>&1
uv run --with pyyaml python bin/agent-workflow.py closeout "$T6_RUN_ID" \
  --status ok "${verify_args[@]}" --json
git tag -a "delivery/${T6_ATTEMPT}" -m "BET-Y1Q3-T6-15 scope refinement" HEAD
git push -u origin HEAD --follow-tags
gh pr create --base main \
  --title "docs(plan): refine T6-15 execution surfaces" \
  --body "BET-Y1Q3-T6-15 scope-only WorkPacket refinement. Candidate state, accepted binding and completion/value evidence are unchanged."
export PHASE_PR_NUMBER="$(gh pr view --json number --jq .number)"
gh pr checks --required --watch --interval 10
gh pr checks --watch --interval 15
gh pr merge "$PHASE_PR_NUMBER" --squash --delete-branch
export SCOPE_MERGE_SHA="$(gh pr view "$PHASE_PR_NUMBER" --json mergeCommit --jq '.mergeCommit.oid')"
git fetch origin main --prune
git merge-base --is-ancestor "$SCOPE_MERGE_SHA" origin/main
cd /Users/xiamingxing/Workspace
python3 bin/gac/clone-lifecycle.py retire \
  --destination "$T6_DEST" \
  --platform-rebased-pr "$PHASE_PR_NUMBER"
```

Expected: verify succeeds because the pre-change WorkPacket already authorizes its own ledger path and verify evaluates the claimed diff plus registered checks; `closeout --status ok` releases every lock. A later claim or explicit packet refresh against the changed source would detect WorkPacket drift, but this completed scope run performs neither. Task 0 starts a fresh run only from main containing this scope PR.

---

### Task 0: Fresh-Main Preflight and Scope Freeze

**Files:**
- Read: `docs/plans/3y-bet-ledger.yaml`
- Read: `docs/superpowers/specs/2026-08-28-post2408-main-recovery-and-required-gac-gate-design.md`
- Evidence only: `/tmp/post2408-preflight-${T6_RUN_ID}.json` (ephemeral preflight evidence; hashes are copied into the final closeout report)

**Interfaces:**
- Consumes: accepted Spec binding and WorkPacket hash from `agent-workflow start`.
- Produces: one immutable preflight receipt and an exact `already_resolved` / `blocking` classification.

- [ ] **Step 1: Reuse the lifecycle-created R1 run**

```bash
test "$T6_PHASE" = "r1"
test -n "$T6_RUN_ID"
uv run --with pyyaml python bin/agent-workflow.py status --json > /tmp/t6-r1-status.json
python3 - <<'PY'
import json, os
d=json.load(open('/tmp/t6-r1-status.json'))
assert d['current_run_id']==os.environ['T6_RUN_ID'], d
assert d['stale_locks']==0, d
assert d['live_locks']>0, d
print('r1-lifecycle: PASS')
PY
```

Expected: the one run created by the Per-Phase lifecycle is active with Spec digest `afd7daded6ab2e279c5b0c5d2f9e9465263c541316d034acafb8fa0671028459`, packet `WP-BET-Y1Q3-T6-15`, no stale locks. Task 0 must not call `start` a second time.

- [ ] **Step 2: Prove the starting tree and current failure set**

```bash
git status --short
git rev-parse HEAD
git rev-parse origin/main
git merge-base --is-ancestor HEAD origin/main
PYTHONDONTWRITEBYTECODE=1 uv run --python 3.13 python -m py_compile bin/ops/cli.py
PYTHONDONTWRITEBYTECODE=1 uv run --python 3.13 python bin/gac/check-conflict-markers.py --all
PYTHONDONTWRITEBYTECODE=1 uv run --python 3.13 --with pyyaml python bin/ssot/script-registry.py validate
PYTHONDONTWRITEBYTECODE=1 uv run --python 3.13 --with pyyaml python bin/gac/gac-validate.py --gate
PYTHONDONTWRITEBYTECODE=1 uv run --python 3.13 --with pyyaml python bin/gac/gac-local-gate.py --strict
git diff --check
```

Expected: all outcomes are recorded verbatim. Items already green are classified `already_resolved` and are not rewritten.

- [ ] **Step 3: Verify the WorkPacket covers every intended write**

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py show BET-Y1Q3-T6-15 > /tmp/t6-15-show.txt
python3 - <<'PY'
from pathlib import Path
required = {
    ".gitignore",
    "ARCHITECTURE.md",
    ".omo/_truth/governance-evidence/waiver-2026-08-28-post2408-recovery-gac-required-binding.md",
    ".omo/_truth/governance-evidence/waiver-2026-08-28-t6-15-guarded-update-amendment.md",
    ".omo/_knowledge/decisions/0432-north-star-v3-6-axis-escalation.md",
    ".omo/_knowledge/decisions/INDEX.md",
    ".omo/_knowledge/retros/BET-Y1Q3-T6-15.md",
    ".omo/_truth/registry/governance-checks.yaml",
    ".github/workflows/gac-gate.yml",
    ".omo/_truth/registry/ci-surfaces.yaml",
    "bin/_registry/scripts/governance/templates.yaml",
    "bin/gac/gac-branch-protection.sh",
    "bin/gac/gac-local-gate.py",
    "bin/gac/omo-runtime-stamp-policy.py",
    "docs/plans/3y-bet-ledger.yaml",
    "docs/reports/2026-08-28-post2408-main-recovery-closeout.md",
    "docs/superpowers/plans/2026-08-28-post2408-main-recovery-and-required-gac-gate.md",
    "tests/test_ci_surfaces.py",
    "tests/test_gac_branch_protection.py",
    "tests/test_gac_gate_workflow_purity.py",
    "tests/test_omo_runtime_stamp_policy.py",
    "tests/unit/gac/test_gac_local_gate_purity.py",
}
text = Path("/tmp/t6-15-show.txt").read_text(encoding="utf-8")
missing = sorted(path for path in required if path not in text)
if missing:
    raise SystemExit(f"WORK_PACKET_SCOPE_MISMATCH: {missing}")
print("scope-freeze: PASS")
PY
```

Expected: `scope-freeze: PASS`. Any required file outside WorkPacket stops execution and requires an accepted scope amendment; it is never added opportunistically.

- [ ] **Step 4: Record the immutable receipt without committing it**

Use the active run ID returned by Step 1:

```bash
export T6_RUN_ID="$(uv run --with pyyaml python bin/agent-workflow.py status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["current_run_id"])')"
python3 - <<'PY'
import hashlib, json, os, subprocess
from pathlib import Path
commands = [
    ["git", "rev-parse", "HEAD"],
    ["git", "status", "--porcelain", "--ignore-submodules=none"],
    ["uv", "run", "--python", "3.13", "--with", "pyyaml", "python", "bin/ssot/script-registry.py", "validate"],
    ["uv", "run", "--python", "3.13", "--with", "pyyaml", "python", "bin/ssot/doc-link-check.py", "--files", "ARCHITECTURE.md"],
    ["uv", "run", "--python", "3.13", "--with", "pyyaml", "python", "bin/gac/gac-local-gate.py", "--strict"],
]
results = []
for command in commands:
    run = subprocess.run(command, text=True, capture_output=True, check=False)
    results.append({"command": command, "returncode": run.returncode, "stdout_sha256": hashlib.sha256(run.stdout.encode()).hexdigest(), "stderr_sha256": hashlib.sha256(run.stderr.encode()).hexdigest()})
payload = {"schema": "post2408-preflight/v1", "run_id": os.environ["T6_RUN_ID"], "results": results}
target = Path("/tmp") / f"post2408-preflight-{os.environ['T6_RUN_ID']}.json"
target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(target)
PY
```

Expected: one untracked, content-digested receipt; no repository file changes.

---

### Task 1: R1 Structural Baseline Recovery

**Files:**
- Modify: `ARCHITECTURE.md`
- Append: `docs/reports/2026-08-28-post2408-main-recovery-closeout.md`
- Append: `.omo/_knowledge/retros/BET-Y1Q3-T6-15.md`
- Modify: `.omo/_truth/governance-evidence/waiver-2026-08-28-post2408-recovery-gac-required-binding.md`
- Modify: `.omo/_knowledge/decisions/0432-north-star-v3-6-axis-escalation.md`
- Modify: `.omo/_knowledge/decisions/INDEX.md`
- Modify when R1 regression proves it necessary: `tests/test_agent_workflow.py`
- Modify when R1 regression proves it necessary: `tests/test_agent_workflow_projection.py`
- Read-only guard: `bin/_registry/scripts/governance/templates.yaml`
- Read-only guard: `.omo/_truth/registry/governance-checks.yaml`

**Interfaces:**
- Consumes: Task 0 failure classification.
- Produces: latest-main strict GaC green while preserving already-landed candidate ADR and waiver evidence.

- [ ] **Step 1: Capture RED for the known document failures**

```bash
set +e
PYTHONDONTWRITEBYTECODE=1 uv run --python 3.13 --with pyyaml python bin/adr/adr-coverage.py --json > /tmp/r1-adr-red.json
adr_rc=$?
PYTHONDONTWRITEBYTECODE=1 uv run --python 3.13 --with pyyaml python bin/ssot/doc-governance-check.py --no-new-warnings > /tmp/r1-doc-red.txt
doc_rc=$?
set -e
printf 'adr_rc=%s doc_rc=%s\n' "$adr_rc" "$doc_rc"
if test "$adr_rc" -eq 0 && test "$doc_rc" -eq 0; then
  echo "R1 document surfaces already_resolved"
else
  test "$adr_rc" -ne 0
  test "$doc_rc" -ne 0
fi
```

Expected on rebaseline `1289e7fd6`: ADR coverage, document governance, script registry and the architecture link check are already green, so Steps 2–5 are read-only confirmation/no-op. If execution-time latest main differs, only blockers inside the T6-15 write surfaces may be repaired; any new blocker outside scope stops R1 for WorkPacket review.

- [ ] **Step 2: Complete the waiver metadata without changing its authorization body**

If Step 1 reports the waiver already valid, compare it read-only with this shape and do not edit it. Only an execution-time structural regression permits the minimal frontmatter correction below.

Change only the YAML frontmatter to:

```yaml
---
schema_version: governance-waiver-evidence/v1
status: active
lifecycle: contract
owner: human-principal
created: 2026-08-28
last-reviewed: 2026-08-28
expires_when: accepted binding PR merges or closes
value_indicator_policy: false
---
```

Expected: the exact user quote and all body text remain byte-identical.

- [ ] **Step 3: Convert ADR-0432 from false acceptance to candidate/UNPROVABLE**

If Step 1 reports ADR-0432 already candidate/UNPROVABLE, verify the text read-only and do not rewrite it. Use the following correction only if latest main has regressed.

Prepend this frontmatter and replace the prose status heading:

```yaml
---
id: ADR-0432
status: candidate
lifecycle: spec
owner: xiamingxing
last-reviewed: 2026-08-28
---
```

```markdown
## Evidence Status: UNPROVABLE

The observed 3/4/5/6-axis composites and the A2 inputs are mutually
inconsistent. This record remains a candidate and does not select one score,
accept the model, or create completion/value evidence.

## Unresolved Contradictions

- A2 is described as both a direct observed `0.0` input and a `0.15` weighted contribution.
- The 3/4/5/6-axis results use different denominators and cannot be compared as one accepted truth.
- PR, test and dashboard output are supply-side diagnostics, not principal-bound value.
```

Expected: existing context is preserved below the new evidence status; no conflicting metric is deleted or promoted.

- [ ] **Step 4: Register ADR-0432 exactly once**

If the candidate row already exists exactly once, do not touch the index. Add the row only when the execution-time index check proves it missing.

Add this row immediately after ADR-0431 in `.omo/_knowledge/decisions/INDEX.md`:

```markdown
- ADR-0432: North Star v3 6-Axis Escalation — **CANDIDATE / UNPROVABLE** | 2026-08-28 | xiamingxing | 0432-north-star-v3-6-axis-escalation.md
```

Expected: filename, ID and status agree; no second ADR-0432 row exists.

- [ ] **Step 5: Repair only the latest-main stale architecture links**

First prove the current failure and the canonical replacement surfaces:

```bash
set +e
uv run --python 3.13 --with pyyaml python bin/ssot/doc-link-check.py --files ARCHITECTURE.md
link_rc=$?
set -e
if test "$link_rc" -eq 0; then
  echo "architecture links already_resolved"
else
  test ! -e bin/ops/core-daemon.py
  test ! -e bin/ops/sentinel-daemon.py
  test -e bin/ops/cli.py
  test -e docs/operations/service-gateway.md
fi
```

Replace only this stale row:

```markdown
| 双守护运维架构 (Core & Sentinel) | `bin/ops/core-daemon.py` · `bin/ops/sentinel-daemon.py` |
```

with the canonical current entry:

```markdown
| 统一 Service Gateway 运维控制面 | `bin/ops/cli.py` · `docs/operations/service-gateway.md` |
```

Expected: no invented daemon replacement, no changes outside the one row, and `doc-link-check.py --files ARCHITECTURE.md` becomes green. If those links are already repaired, mark this step `already_resolved` and make no edit.

- [ ] **Step 6: Prove script registration/baseline remain already resolved**

```bash
uv run --python 3.13 --with pyyaml python bin/ssot/script-registry.py validate
uv run --python 3.13 --with pyyaml python bin/gac/gac-validate.py --gate
```

Expected: both pass without edits. The execution baseline already contains `templates.yaml` and a synchronized script baseline. Any regression stops R1 and requires a fresh-main scope review; this task does not rewrite them speculatively.

- [ ] **Step 7: Run GREEN and commit only if R1 required a repair**

If and only if execution-time R1 required a scoped repair, append a dated section to the existing R1 report and retro; do not rewrite their earlier partial evidence. Record execution-time main SHA, exact RED finding, minimal diff, full strict result and the statement that H1/R2/value remain unproven. A root workflow regression may repair only its direct fixture or stale assertion after an accepted scope amendment; it must not change production Mesh or advisory-audit behavior. If every check is already green, leave all files untouched and take the Step 8 no-op closeout path.

```bash
uv run --python 3.13 --with pyyaml python bin/adr/adr-coverage.py --json
uv run --python 3.13 --with pyyaml python bin/ssot/doc-governance-check.py --no-new-warnings
uv run --python 3.13 --with pyyaml python bin/ssot/doc-link-check.py --files ARCHITECTURE.md
uv run --python 3.13 --with pyyaml python bin/ssot/script-registry.py validate
uv run --python 3.13 --with pyyaml python bin/gac/gac-validate.py --gate
uv run --python 3.13 python -m py_compile bin/ops/cli.py
uv run --python 3.13 python bin/gac/check-conflict-markers.py --all
uv run --python 3.13 --with pyyaml python bin/gac/gac-local-gate.py --strict
git diff --check
git add ARCHITECTURE.md \
  docs/reports/2026-08-28-post2408-main-recovery-closeout.md \
  .omo/_knowledge/retros/BET-Y1Q3-T6-15.md
git commit -m "fix(governance): restore post2408 baseline truth"
```

Expected: direct and full strict checks pass; ADR, waiver, `bin/ops/cli.py` and registry/baseline files remain unchanged when already resolved.

- [ ] **Step 8: Close the R1 run and publish its unique PR**

If Step 1 classified every R1 surface as `already_resolved` and `git diff --quiet origin/main...HEAD` is true, verify and close the clean run, retire the clean clone without a PR, and proceed to H1a. Do not create an empty recovery PR.

Otherwise, after the Step 7 commit, execute the phase lifecycle explicitly:

```bash
verify_args=()
while IFS= read -r path; do verify_args+=(--file "$path"); done < /tmp/t6-phase-claims.txt
uv run --with pyyaml python bin/agent-workflow.py verify "$T6_RUN_ID" "${verify_args[@]}" --execute --json
uv run --with pyyaml python bin/agent-workflow.py closeout "$T6_RUN_ID" --status ok "${verify_args[@]}" --json
git tag -a "delivery/${T6_ATTEMPT}" -m "BET-Y1Q3-T6-15 r1" HEAD
git push -u origin HEAD --follow-tags
gh pr create --base main \
  --title "fix(governance): restore post2408 baseline truth" \
  --body "BET-Y1Q3-T6-15 R1 continuation only: replace two stale architecture links and preserve prior ADR-0432 candidate/UNPROVABLE evidence."
export PHASE_PR_NUMBER="$(gh pr view --json number --jq .number)"
gh pr checks --required --watch --interval 10
gh pr checks --watch --interval 15
gh pr merge "$PHASE_PR_NUMBER" --squash --delete-branch
export R1_MERGE_SHA="$(gh pr view "$PHASE_PR_NUMBER" --json mergeCommit --jq '.mergeCommit.oid')"
git fetch origin main --prune
git merge-base --is-ancestor "$R1_MERGE_SHA" origin/main
cd /Users/xiamingxing/Workspace
python3 bin/gac/clone-lifecycle.py retire \
  --destination "$T6_DEST" \
  --platform-rebased-pr "$PHASE_PR_NUMBER"
```

For the clean no-op branch, use the same `verify`/`closeout --status ok` commands, then run `clone-lifecycle.py retire --destination "$T6_DEST"` with no PR argument. A fail-closed retirement result is reported; the clone is never deleted manually.

---

### Task 2: H1a Immutable and Blocking `gac-gate`

**Files:**
- Modify: `.github/workflows/gac-gate.yml`
- Create: `tests/test_gac_gate_workflow_purity.py`

**Interfaces:**
- Consumes: existing `gac-gate` job and root GaC checklist.
- Produces: same job/context name, read-only blocking path and clean-tree invariant.

- [ ] **Step 1: Write workflow-purity RED tests**

Create `tests/test_gac_gate_workflow_purity.py`:

```python
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/gac-gate.yml"


def _steps() -> list[dict]:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return data["jobs"]["gac-gate"]["steps"]


def test_gac_gate_strict_step_is_blocking() -> None:
    step = next(item for item in _steps() if item.get("name") == "gac-local-gate (strict)")
    assert step.get("continue-on-error", False) is False
    assert step["run"] == "python3 bin/gac/gac-local-gate.py --strict"


def test_gac_gate_blocking_path_never_mutates_checkout() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    blocking = text[text.index("PASW — 子模块指针可达性前置检查") :]
    forbidden = ("sync-submodule-pointers.sh", "git add", "--write", "GAC_M1_SYNC_WRITE")
    assert not [token for token in forbidden if token in blocking]
    assert "submodule-reachability-gate.py --source head --fetch" in blocking
    assert "project-layer-index.py --check" in blocking


def test_gac_gate_checks_clean_tree_before_and_after() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("git diff --exit-code") >= 2
    assert text.count("git diff --cached --exit-code") >= 2
    assert text.count("git status --porcelain") >= 2
    assert "--untracked-files=no" not in text


def test_immutable_guard_rejects_tracked_staged_and_untracked(tmp_path: Path) -> None:
    steps = _steps()
    guard = next(item["run"] for item in steps if item.get("name") == "immutable checkout precondition")
    for mutation in ("tracked", "staged", "untracked"):
        repo = tmp_path / mutation
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "gate@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Gate Test"], check=True)
        tracked = repo / "tracked.txt"
        tracked.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
        if mutation == "tracked":
            tracked.write_text("changed\n", encoding="utf-8")
        elif mutation == "staged":
            tracked.write_text("changed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
        else:
            (repo / "untracked.txt").write_text("new\n", encoding="utf-8")
        result = subprocess.run(["bash", "-eu", "-c", guard], cwd=repo, check=False)
        assert result.returncode != 0, mutation
```

- [ ] **Step 2: Run RED**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_gac_gate_workflow_purity.py -q
```

Expected on latest main: the existing `tests/test_gac_gate_workflow.py` blocking assertion is already green, while the new purity tests fail on pointer sync, `git add`, generator writes, MOF write mode and missing complete clean-tree guards.

- [ ] **Step 3: Replace mutating workflow steps with exact read-only steps**

In `.github/workflows/gac-gate.yml`, replace the pointer-sync/generation block with:

```yaml
      - name: immutable checkout precondition
        run: |
          git diff --exit-code
          git diff --cached --exit-code
          test -z "$(git status --porcelain)"
      - name: PASW — 子模块指针可达性前置检查
        run: python3 bin/ssot/submodule-reachability-gate.py --source head --fetch
        continue-on-error: false
      - name: generated projection drift checks
        run: |
          python3 bin/mof/project-layer-index.py --check
          python3 bin/gac/gac-drift.py
      - name: mof-check (read-only advisory)
        continue-on-error: true
        working-directory: projects/ecos
        run: uv run mof check 2>&1 | tail -20
      - name: check-layers (跨层依赖检查)
        run: python3 bin/layer-dependency-check.py
      - name: gac-local-gate (strict)
        run: python3 bin/gac/gac-local-gate.py --strict
        continue-on-error: false
      - name: immutable checkout postcondition
        if: always()
        run: |
          git diff --exit-code
          git diff --cached --exit-code
          test -z "$(git status --porcelain)"
```

Do not add a replacement call to `gac-export-agents.py`; its current interface writes generated output.

- [ ] **Step 4: Run GREEN and workflow syntax checks**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_gac_gate_workflow_purity.py -q
uv run --with pyyaml python - <<'PY'
from pathlib import Path
import yaml
payload = yaml.safe_load(Path(".github/workflows/gac-gate.yml").read_text(encoding="utf-8"))
assert "gac-gate" in payload["jobs"]
print("workflow-yaml: PASS")
PY
git diff --check
```

- [ ] **Step 5: Commit workflow purity**

```bash
git add .github/workflows/gac-gate.yml tests/test_gac_gate_workflow_purity.py
git commit -m "fix(ci): make gac gate immutable and blocking"
```

---

### Task 3: H1a CI Surface Binding

**Files:**
- Modify: `.omo/_truth/registry/ci-surfaces.yaml`
- Modify: `tests/test_ci_surfaces.py`

**Interfaces:**
- Consumes: existing surface `bin-ssot-script-registry-py`.
- Produces: supported workflow-level binding to `gac-gate.yml`.

- [ ] **Step 1: Write the RED test**

Append to `tests/test_ci_surfaces.py`:

```python
def test_script_registry_validation_is_bound_to_gac_gate() -> None:
    import yaml
    payload = yaml.safe_load(
        (ROOT / ".omo/_truth/registry/ci-surfaces.yaml").read_text(encoding="utf-8")
    )
    surface = next(
        item for item in payload["surfaces"]
        if item["id"] == "bin-ssot-script-registry-py"
    )
    assert surface["tool"] == "bin/ssot/script-registry.py"
    assert surface["workflow"] == "gac-gate.yml"
    assert not ({"job", "step", "job_id", "step_id", "required"} & set(surface))
```

- [ ] **Step 2: Run RED**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_ci_surfaces.py::test_script_registry_validation_is_bound_to_gac_gate -q
```

Expected: FAIL because workflow is `(none)`.

- [ ] **Step 3: Change only the supported field**

```yaml
- id: bin-ssot-script-registry-py
  tool: bin/ssot/script-registry.py
  workflow: gac-gate.yml
  gate: true
  triggers:
  - manual
  - per_pr
  - push
  status: active
  note: strict validation is executed by the existing gac-gate job
```

- [ ] **Step 4: Run GREEN and commit**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_ci_surfaces.py -q
uv run --with pyyaml python bin/gac/check-ci-surfaces.py --json
git add .omo/_truth/registry/ci-surfaces.yaml tests/test_ci_surfaces.py
git commit -m "fix(ci): bind script registry to gac gate"
```

---

### Task 4: H1b Merge and Main Canary

**Files:**
- Evidence only: GitHub Actions receipts and `docs/reports/2026-08-28-post2408-main-recovery-closeout.md` at final closeout.

**Interfaces:**
- Consumes: merged H1a PR.
- Produces: immutable main-SHA canary proving the strict step actually ran.

- [ ] **Step 1: Submit one H1a PR containing Tasks 2 and 3**

```bash
git diff --name-only origin/main...HEAD
git push -u origin HEAD
gh pr create --base main \
  --title "fix(ci): make gac-gate immutable and blocking" \
  --body "BET-Y1Q3-T6-15 H1a: immutable checkout, blocking strict GaC, workflow-level script-registry binding."
```

Expected: diff contains only the four Task 2/3 files.

- [ ] **Step 2: Merge only after relevant checks finish**

```bash
gh pr checks --required --watch --interval 10
gh pr checks --watch --interval 15
```

Expected: required contexts, workflow-purity tests, `test`, `cascading_test` and the now-blocking `gac-gate` are successful. A real strict failure blocks merge.

- [ ] **Step 3: Verify the main canary**

```bash
export H1_MAIN_SHA="$(gh pr view --json mergeCommit --jq '.mergeCommit.oid')"
curl -fsSL https://www.githubstatus.com/api/v2/components.json > /tmp/github-components.json
curl -fsSL https://www.githubstatus.com/api/v2/incidents/unresolved.json > /tmp/github-incidents.json
python3 - <<'PY'
import json
components=json.load(open('/tmp/github-components.json'))['components']
actions=next(item for item in components if item['name']=='Actions')
incidents=json.load(open('/tmp/github-incidents.json'))['incidents']
assert actions['status']=='operational', actions
assert not incidents, incidents
print('github-actions-capacity: operational')
PY
gh run list --commit "$H1_MAIN_SHA" --limit 50 --json databaseId,name,status,conclusion,event,url
```

Select the push run whose workflow name is `gac-gate`. Verify through `gh run view` that:

```text
headSha == H1_MAIN_SHA
event == push
job name == gac-gate
job conclusion == success
step name == gac-local-gate (strict)
step conclusion == success
```

Queued, cancelled, startup-failure, old-SHA, PR-only or local runs do not satisfy H1b.
If Actions is not operational, an incident is unresolved, or the API evidence is unavailable, report H1b as `UNPROVABLE` and wait; do not rerun workflows to manufacture a receipt.

---

### Task 4B: Accept the Guarded-Update Contract Amendment

**Files:**
- Modify: `docs/superpowers/specs/2026-08-28-post2408-main-recovery-and-required-gac-gate-design.md`
- Modify: `docs/plans/3y-bet-ledger.yaml` only for BET-Y1Q3-T6-15 wording and accepted binding
- Create: `.omo/_truth/governance-evidence/waiver-2026-08-28-t6-15-guarded-update-amendment.md`

**Interfaces:**
- Consumes: plan approval decision and H1b evidence.
- Produces: Spec version `1.0.1` replacing false atomic-CAS claims with guarded double-read semantics.

- [ ] **Step 1: Start the exact amendment lifecycle**

Set `T6_PHASE=amendment` and execute the Per-Phase Governed Delivery Lifecycle. Expected: one fresh clone, a run bound to Spec `1.0.0`, and exact claims for the Spec, T6-15 ledger entry and amendment waiver. Because the phase intentionally changes its own binding, verify reports the registered checks and claim coverage independently, then the run is explicitly closed `blocked` after the three-path commit and releases every lock; the next H1c run starts from merged Spec `1.0.1`.

- [ ] **Step 2: Obtain an exact three-path bootstrap authorization**

The human authorization must permit only: Spec version/wording change, T6-15 binding digest/version and matching goal/done_when/circuit wording, and the named waiver file. It must prohibit implementation, live branch-protection mutation, other BETs and completion/value evidence.

- [ ] **Step 3: Make the exact semantic amendment**

In the Spec, change `spec_version: 1.0.0` to `1.0.1` and replace H1c `compare-and-swap` / `CAS` claims with:

```text
guarded double-read read-modify-write: GET A -> validate/hash -> GET B ->
require digest equality -> one required_status_checks subresource PATCH -> GET C
verify. The API lacks a proven server-side conditional unsafe write, so a
residual GET-B/PATCH race remains and is bounded by a second human gate,
receipt and context-only rollback.
```

Apply the same wording to T6-15 `goal`, H1c `done_when` and `circuit_breaker`; do not change status or completion evidence.

- [ ] **Step 4: Recalculate and bind final bytes**

```bash
export GUARDED_SPEC_SHA256="$(shasum -a 256 docs/superpowers/specs/2026-08-28-post2408-main-recovery-and-required-gac-gate-design.md | awk '{print $1}')"
printf 'sha256:%s\n' "$GUARDED_SPEC_SHA256"
```

Update only T6-15 binding to `spec_version: 1.0.1` and `content_digest: "sha256:${GUARDED_SPEC_SHA256}"`. Validate with `validate_accepted_specification`; literal `${GUARDED_SPEC_SHA256}` must not remain in YAML.

- [ ] **Step 5: Validate the amendment before Task 5**

```bash
git diff --check
uv run --with pyyaml python bin/plan/bet-ledger.py show BET-Y1Q3-T6-15
uv run --with pyyaml python bin/plan/bet-ledger.py claim-check BET-Y1Q3-T6-15
```

Expected: the exact three-path diff is ready for independent review; no implementation or live mutation is present.

- [ ] **Step 6: Commit, close blocked, and merge the unique amendment PR**

Record the exact human authorization quote verbatim in the named waiver, then commit exactly the three authorized paths. The old `1.0.0` run is intentionally terminated after its own accepted-Spec update: current verify evaluates registered diff checks and claim coverage and may succeed, while any subsequent claim or packet refresh would fail closed on source/binding drift. Close the run explicitly as `blocked`; this is an honest bootstrap terminal state, not permission to bypass binding enforcement.

```bash
git add \
  docs/superpowers/specs/2026-08-28-post2408-main-recovery-and-required-gac-gate-design.md \
  docs/plans/3y-bet-ledger.yaml \
  .omo/_truth/governance-evidence/waiver-2026-08-28-t6-15-guarded-update-amendment.md
git diff --cached --name-only | sort > /tmp/t6-amendment-staged.txt
printf '%s\n' \
  .omo/_truth/governance-evidence/waiver-2026-08-28-t6-15-guarded-update-amendment.md \
  docs/plans/3y-bet-ledger.yaml \
  docs/superpowers/specs/2026-08-28-post2408-main-recovery-and-required-gac-gate-design.md \
  | sort > /tmp/t6-amendment-expected.txt
diff -u /tmp/t6-amendment-expected.txt /tmp/t6-amendment-staged.txt
AGCP_REQUIREMENT_ITERATION_GATE=0 git commit -m "docs(spec): bind guarded branch-protection update"

verify_args=()
while IFS= read -r path; do verify_args+=(--file "$path"); done < /tmp/t6-phase-claims.txt
uv run --with pyyaml python bin/agent-workflow.py verify "$T6_RUN_ID" "${verify_args[@]}" --execute --json \
  > /tmp/t6-amendment-verify.json
uv run --with pyyaml python bin/agent-workflow.py closeout "$T6_RUN_ID" --status blocked "${verify_args[@]}" --json
git tag -a "delivery/${T6_ATTEMPT}" -m "BET-Y1Q3-T6-15 amendment" HEAD
git push -u origin HEAD --follow-tags
gh pr create --base main \
  --title "docs(spec): bind guarded branch-protection update" \
  --body "BET-Y1Q3-T6-15 accepted-Spec amendment only. Replaces false atomic-CAS wording with guarded double-read semantics; no implementation or live mutation."
export PHASE_PR_NUMBER="$(gh pr view --json number --jq .number)"
gh pr checks --required --watch --interval 10
gh pr checks --watch --interval 15
gh pr merge "$PHASE_PR_NUMBER" --squash --delete-branch
export AMENDMENT_MERGE_SHA="$(gh pr view "$PHASE_PR_NUMBER" --json mergeCommit --jq '.mergeCommit.oid')"
git fetch origin main --prune
git merge-base --is-ancestor "$AMENDMENT_MERGE_SHA" origin/main
git show "origin/main:docs/superpowers/specs/2026-08-28-post2408-main-recovery-and-required-gac-gate-design.md" \
  | shasum -a 256
cd /Users/xiamingxing/Workspace
python3 bin/gac/clone-lifecycle.py retire \
  --destination "$T6_DEST" \
  --platform-rebased-pr "$PHASE_PR_NUMBER"
```

Expected: the PR contains exactly three paths; required checks and independent review pass; merged main recomputation matches the `1.0.1` binding. Every H1c implementation run starts after this merge and binds the new WorkPacket hash. `agent-workflow status` shows no live locks owned by the amendment run.

---

### Task 5: H1c Guarded Double-Read Branch-Protection Tool

**Files:**
- Modify: `bin/gac/gac-branch-protection.sh`
- Modify: `tests/test_gac_branch_protection.py`

**Interfaces:**
- Consumes: the safer but single-read `1289e7fd6` status-checks PATCH implementation as a RED baseline; optimistic atomicity is not accepted as proven.
- Produces: `--check`, `--add-required-context`, `--remove-required-context`, `--expected-contexts`, `--receipt` and stable exit codes `0/1/2`.
- Preserves: every non-context protection field.

- [ ] **Step 1: Replace the existing fake-API suite with guarded-double-read RED tests**

Retain useful preservation coverage from `1289e7fd6`, remove assertions that call a single read "CAS", and make `tests/test_gac_branch_protection.py` use a fake `gh` executable that reads `FAKE_PROTECTION_STATE` and appends PATCH bodies to `FAKE_GH_WRITES`:

```python
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin/gac/gac-branch-protection.sh"

BASE = {
    "required_status_checks": {
        "strict": False,
        "contexts": ["phase-gate", "bet-done-transition"],
    },
    "required_pull_request_reviews": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews": False,
        "require_code_owner_reviews": False,
    },
    "enforce_admins": {"enabled": True},
    "restrictions": None,
    "required_linear_history": {"enabled": False},
    "allow_force_pushes": {"enabled": False},
    "allow_deletions": {"enabled": False},
    "block_creations": {"enabled": False},
    "required_conversation_resolution": {"enabled": True},
    "lock_branch": {"enabled": False},
    "allow_fork_syncing": {"enabled": False},
}


def _fake_gh(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    state = tmp_path / "state.json"
    writes = tmp_path / "writes.jsonl"
    gets = tmp_path / "gets.txt"
    state.write_text(json.dumps(BASE), encoding="utf-8")
    gets.write_text("0", encoding="utf-8")
    fake = tmp_path / "gh"
    fake.write_text(
        """#!/usr/bin/env python3
import json, os, sys
state_path=os.environ['FAKE_PROTECTION_STATE']
writes_path=os.environ['FAKE_GH_WRITES']
gets_path=os.environ['FAKE_GH_GETS']
if os.environ.get('FAKE_GH_UNREADABLE') == '1':
    raise SystemExit(2)
args=sys.argv[1:]
if '-X' in args and args[args.index('-X')+1] == 'PATCH':
    input_path=args[args.index('--input')+1]
    payload=json.load(open(input_path, encoding='utf-8'))
    with open(writes_path, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(payload, sort_keys=True)+'\\n')
    response=json.load(open(state_path, encoding='utf-8'))
    response['required_status_checks']={
        'strict': bool(payload['strict']),
        'contexts': list(payload['contexts']),
    }
    with open(state_path, 'w', encoding='utf-8') as fh:
        json.dump(response, fh)
    print(json.dumps(response))
else:
    count=int(open(gets_path, encoding='utf-8').read())
    with open(gets_path, 'w', encoding='utf-8') as fh:
        fh.write(str(count+1))
    payload=json.load(open(state_path, encoding='utf-8'))
    if os.environ.get('FAKE_GH_RACE_AFTER_GET') == '1' and count >= 1:
        payload['required_status_checks']['contexts'].append('concurrent-context')
        with open(state_path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh)
    print(json.dumps(payload))
""",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "FAKE_PROTECTION_STATE": str(state),
        "FAKE_GH_WRITES": str(writes),
        "FAKE_GH_GETS": str(gets),
    }
    return env, state, writes


def _run(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_check_returns_zero_one_two(tmp_path: Path) -> None:
    env, state, _writes = _fake_gh(tmp_path)
    aligned = _run(env, "--check", "--expected-contexts", "phase-gate,bet-done-transition")
    assert aligned.returncode == 0
    payload = json.loads(state.read_text(encoding="utf-8"))
    payload["required_status_checks"]["contexts"] = ["phase-gate"]
    state.write_text(json.dumps(payload), encoding="utf-8")
    assert _run(env, "--check", "--expected-contexts", "phase-gate,bet-done-transition").returncode == 1
    env["FAKE_GH_UNREADABLE"] = "1"
    assert _run(env, "--check", "--expected-contexts", "phase-gate,bet-done-transition").returncode == 2


def test_add_context_expected_before_mismatch_performs_zero_patches(tmp_path: Path) -> None:
    env, _state, writes = _fake_gh(tmp_path)
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate", "--receipt", str(tmp_path / "receipt.json"), "--yes")
    assert result.returncode != 0
    assert not writes.exists()


def test_add_context_preserves_non_context_fields(tmp_path: Path) -> None:
    env, state, writes = _fake_gh(tmp_path)
    before = json.loads(state.read_text(encoding="utf-8"))
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(tmp_path / "receipt.json"), "--yes")
    assert result.returncode == 0, result.stderr
    patch = json.loads(writes.read_text(encoding="utf-8").splitlines()[0])
    assert set(patch) == {"strict", "contexts"}
    assert sorted(patch["contexts"]) == ["bet-done-transition", "gac-gate", "phase-gate"]
    after = json.loads(state.read_text(encoding="utf-8"))
    for key, value in before.items():
        if key != "required_status_checks":
            assert after[key] == value


def test_remove_context_removes_only_gac_gate(tmp_path: Path) -> None:
    env, state, writes = _fake_gh(tmp_path)
    payload = json.loads(state.read_text(encoding="utf-8"))
    payload["required_status_checks"]["contexts"].append("gac-gate")
    state.write_text(json.dumps(payload), encoding="utf-8")
    result = _run(env, "--remove-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition,gac-gate", "--receipt", str(tmp_path / "receipt.json"), "--yes")
    assert result.returncode == 0
    patch = json.loads(writes.read_text(encoding="utf-8").splitlines()[0])
    assert set(patch) == {"strict", "contexts"}
    assert sorted(patch["contexts"]) == ["bet-done-transition", "phase-gate"]


def test_unknown_extra_context_fails_closed(tmp_path: Path) -> None:
    env, state, writes = _fake_gh(tmp_path)
    payload = json.loads(state.read_text(encoding="utf-8"))
    payload["required_status_checks"]["contexts"].append("unknown-context")
    state.write_text(json.dumps(payload), encoding="utf-8")
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(tmp_path / "receipt.json"), "--yes")
    assert result.returncode != 0
    assert not writes.exists()


def test_second_read_change_stops_before_patch(tmp_path: Path) -> None:
    env, _state, writes = _fake_gh(tmp_path)
    env["FAKE_GH_RACE_AFTER_GET"] = "1"
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(tmp_path / "receipt.json"), "--yes")
    assert result.returncode != 0
    assert not writes.exists()
```

The fixture state must include reviews, `enforce_admins`, restrictions, linear-history, force-push and deletion fields so preservation is observable.

- [ ] **Step 2: Run RED**

```bash
uv run --with pytest python -m pytest tests/test_gac_branch_protection.py -q
```

Expected on `1289e7fd6`: FAIL because the current tool performs only one pre-write read, exposes no durable redacted receipt contract, and does not reject a second-read race. The documented PATCH subresource itself remains the required narrow write path.

- [ ] **Step 3: Implement strict CLI parsing and guarded double-read**

The public invocations are exact:

```bash
bash bin/gac/gac-branch-protection.sh --check \
  --expected-contexts phase-gate,bet-done-transition,gac-gate
bash bin/gac/gac-branch-protection.sh --add-required-context gac-gate \
  --expected-contexts phase-gate,bet-done-transition \
  --receipt /tmp/gac-context-add-receipt.json --yes
bash bin/gac/gac-branch-protection.sh --remove-required-context gac-gate \
  --expected-contexts phase-gate,bet-done-transition,gac-gate \
  --receipt /tmp/gac-context-remove-receipt.json --yes
```

Implementation rules:

```text
GET A -> normalize/hash redacted full protection
-> compare exact sorted expected contexts -> GET B -> require digest(B)==digest(A)
-> PATCH required_status_checks once with only strict+contexts
-> GET C -> compare exact after and every preserved field -> create receipt exclusively
```

The PATCH body must contain only `strict` and `contexts`. Full-protection GET A/B/C comparison must prove `required_pull_request_reviews`, `enforce_admins`, `restrictions`, `required_linear_history`, `allow_force_pushes`, `allow_deletions`, `block_creations`, `required_conversation_resolution`, `lock_branch` and `allow_fork_syncing` remain unchanged.

`--check`: aligned `0`, readable drift `1`, unreadable/API/schema error `2`. Expected-before or second-read mismatch performs zero PATCHes. Keep every whole-protection PUT/DELETE path disabled.

- [ ] **Step 4: Run GREEN and commit**

```bash
uv run --with pytest python -m pytest tests/test_gac_branch_protection.py -q
bash -n bin/gac/gac-branch-protection.sh
git diff --check
git add bin/gac/gac-branch-protection.sh tests/test_gac_branch_protection.py
git commit -m "fix(governance): guard branch protection context updates"
```

- [ ] **Step 5: Submit and merge the H1c tool PR without live mutation**

```bash
git push -u origin HEAD
gh pr create --base main \
  --title "fix(governance): guard branch-protection contexts" \
  --body "BET-Y1Q3-T6-15 H1c tool only. No live branch-protection mutation in this PR."
```

Expected: the tool PR itself performs no live mutation. Task 6 independently audits whatever live context set exists after merge; current observed state is already three contexts and cannot be treated as this PR's completion evidence.

---

### Task 6: H1c Live `gac-gate` Required Context

**Files:**
- External receipt: `/Users/xiamingxing/Documents/学习进化/基建架构/evidence/2026-08-28-post2408-required-gac-gate/branch-protection-receipt.json`

**Interfaces:**
- Consumes: H1b canary and merged guarded-update tool.
- Produces: a human-adjudicated, receipt-backed disposition of the already-live set `phase-gate`, `bet-done-transition`, `gac-gate`.

- [ ] **Step 1: Stop on the observed out-of-order state**

At observed main, `gac-gate` is already required even though H1a immutability/H1b and the external receipt are incomplete. Do not add the context again and do not synthesize a historical receipt. Report `human_gate=adopt_or_rollback`.

- [ ] **Step 2: Capture a new read-only adjudication snapshot**

```bash
gh api 'repos/starlink-awaken/omostation/branches/main/protection' > /tmp/protection-before.json
python3 - <<'PY'
import json
d=json.load(open('/tmp/protection-before.json'))
contexts=sorted((d.get('required_status_checks') or {}).get('contexts') or [])
assert contexts in (
    ['bet-done-transition','phase-gate'],
    ['bet-done-transition','gac-gate','phase-gate'],
), contexts
print(contexts)
PY
test ! -e "/Users/xiamingxing/Documents/学习进化/基建架构/evidence/2026-08-28-post2408-required-gac-gate/branch-protection-receipt.json" \
  || shasum -a 256 "/Users/xiamingxing/Documents/学习进化/基建架构/evidence/2026-08-28-post2408-required-gac-gate/branch-protection-receipt.json"
```

- [ ] **Step 3: Obtain one exact human disposition**

The authorization must choose exactly one:

```text
ADOPT: keep the current three contexts prospectively after H1a/H1b become valid;
record that the original mutation time/actor/receipt remain UNPROVABLE.

ROLLBACK: remove only gac-gate now, preserving phase-gate and
bet-done-transition, then allow a fresh guarded promotion after H1a/H1b.
```

The authorization must name the repository, observed digest/context set, chosen disposition, rollback command and external receipt path. Without it, stop without mutation.

- [ ] **Step 4A: Execute ADOPT only after H1a/H1b**

For ADOPT, do not write branch protection. After a valid post-H1a main canary, create a prospective adjudication receipt containing the human quote, current GET digest, exact context set and the explicit limitation that original mutation provenance remains `UNPROVABLE`. Then run only:

```bash
bash bin/gac/gac-branch-protection.sh --check \
  --expected-contexts phase-gate,bet-done-transition,gac-gate
```

- [ ] **Step 4B: Execute ROLLBACK only with exact authorization**

```bash
bash bin/gac/gac-branch-protection.sh --remove-required-context gac-gate \
  --expected-contexts phase-gate,bet-done-transition,gac-gate \
  --receipt "/Users/xiamingxing/Documents/学习进化/基建架构/evidence/2026-08-28-post2408-required-gac-gate/branch-protection-rollback-receipt.json" \
  --yes
bash bin/gac/gac-branch-protection.sh --check \
  --expected-contexts phase-gate,bet-done-transition
```

Expected: ADOPT performs zero live writes; ROLLBACK performs one narrow status-checks PATCH. Either receipt contains the human quote, read digests, post-state, request/result identifiers and limitations, but no token, credential or raw restriction identity. Neither path retroactively proves the missing original mutation receipt.

---

### Task 7: R2a Immutable Final-Tree Runtime Policy

**Files:**
- Modify: `bin/gac/gac-local-gate.py`
- Modify: `bin/gac/omo-runtime-stamp-policy.py`
- Modify: `tests/test_omo_runtime_stamp_policy.py`
- Modify: `tests/unit/gac/test_gac_local_gate_purity.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: partial #2457 treeish implementation, landed ignore rules and repository untracking.
- Produces: `--treeish REVISION` final-tree mode and JSON key `forbidden_tracked_paths`.
- Produces: blocking root-owned local-gate id `omo-runtime-final-tree` with command `bin/gac/omo-runtime-stamp-policy.py --treeish HEAD --json`.
- Preserves: existing worktree orphan mode for local diagnostics.
- Authority: root GaC tool is the only final-tree admission authority; `omo lint stamp-policy` remains a non-authoritative worktree diagnostic.

- [ ] **Step 1: Write RED tests**

Tests create a temporary Git repository and monkeypatch module constants:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "bin/gac/omo-runtime-stamp-policy.py"


def _load():
    spec = importlib.util.spec_from_file_location("runtime_stamp_policy_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    run = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=True)
    return run.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "runtime-policy@example.invalid")
    _git(repo, "config", "user.name", "Runtime Policy Test")
    return repo


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def test_treeish_rejects_tracked_smoke_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    path = repo / "runtime/consumer-audit-smoke.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    head = _commit(repo, "tracked output")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    report = mod.evaluate_treeish(head)
    assert report["ok"] is False
    assert report["forbidden_tracked_paths"] == ["runtime/consumer-audit-smoke.json"]


@pytest.mark.parametrize(
    "relative",
    [
        "runtime/AGENTS.md",
        "runtime/README.md",
        "runtime/runtime-space-boundary.yaml",
        "runtime/system-runtime-boundary.yaml",
        "runtime/cron/systemd/example.service",
        "runtime/ssot-stable/tool.py",
        "runtime/sandbox/tasks/example.yaml",
        "runtime/coordination/handoffs/test-run-001.json",
    ],
)
def test_treeish_allows_explicit_contracts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str) -> None:
    repo = _repo(tmp_path)
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("contract\n", encoding="utf-8")
    head = _commit(repo, "contract")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    assert mod.evaluate_treeish(head)["forbidden_tracked_paths"] == []


def test_treeish_uses_requested_revision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    path = repo / "runtime/transient.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    old = _commit(repo, "add")
    path.unlink()
    new = _commit(repo, "delete")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    assert mod.evaluate_treeish(old)["forbidden_tracked_paths"] == ["runtime/transient.json"]
    assert mod.evaluate_treeish(new)["forbidden_tracked_paths"] == []


def test_treeish_rejects_symlink_and_gitlink_modes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    runtime = repo / "runtime"
    runtime.mkdir()
    (runtime / "target").write_text("x", encoding="utf-8")
    (runtime / "link").symlink_to("target")
    head = _commit(repo, "symlink")
    _git(repo, "update-index", "--add", "--cacheinfo", f"160000,{head},runtime/gitlink")
    _git(repo, "commit", "-qm", "gitlink")
    current = _git(repo, "rev-parse", "HEAD")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    report = mod.evaluate_treeish(current)
    assert report["invalid_modes"] == ["runtime/gitlink", "runtime/link"]


def test_treeish_json_paths_are_sorted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    for name in ("z.json", "a.json"):
        path = repo / "runtime" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    head = _commit(repo, "outputs")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    assert mod.evaluate_treeish(head)["forbidden_tracked_paths"] == ["runtime/a.json", "runtime/z.json"]


def test_workpacket_runtime_patterns_have_no_tracked_outputs() -> None:
    ledger = yaml.safe_load((ROOT / "docs/plans/3y-bet-ledger.yaml").read_text(encoding="utf-8"))
    bet = next(item for item in ledger["bets"] if item["id"] == "BET-Y1Q3-T6-15")
    patterns = [path for path in bet["write_surfaces"] if path.startswith("runtime/")]
    paths = sorted({
        path
        for pattern in patterns
        for path in subprocess.run(
            ["git", "ls-files", "--", pattern],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()
        if path
    })
    assert paths == []
```

Append to `tests/unit/gac/test_gac_local_gate_purity.py`:

```python
def test_runtime_final_tree_gate_is_root_owned_and_blocking() -> None:
    module = _load_module()
    commands = {gate["id"]: gate["command"] for gate in module.GATES_LIST}
    assert commands["omo-runtime-final-tree"] == [
        "bin/gac/omo-runtime-stamp-policy.py",
        "--treeish",
        "HEAD",
        "--json",
    ]
    assert "omo-runtime-final-tree" not in module.SOFT_CHECKS
    assert "omo-runtime-final-tree" not in module.CI_ONLY_CHECKS
```

- [ ] **Step 2: Run RED**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_omo_runtime_stamp_policy.py -q
```

Expected on `6bcf17b4e`: RED because the merged test still expects a deleted artifact, the implementation does not expose mode-aware `evaluate_treeish`, and root GaC has no blocking `omo-runtime-final-tree` gate.

- [ ] **Step 3: Implement final-tree classification**

Add these interfaces:

```python
FINAL_TREE_ALLOW_PATHS: tuple[str, ...] = (
    "runtime/AGENTS.md",
    "runtime/README.md",
    "runtime/runtime-space-boundary.yaml",
    "runtime/system-runtime-boundary.yaml",
    "runtime/cron/**",
    "runtime/ssot-stable/**",
    "runtime/sandbox/**",
    "runtime/coordination/**",
)


def load_treeish_runtime_entries(treeish: str) -> tuple[tuple[str, str, str], ...]:
    """Return sorted (mode, object_id, path) entries from one immutable tree."""


def is_final_tree_allowed(rel_path: str, projection_paths: set[str]) -> bool:
    """Allow only explicit contracts/projections; ignore rules never legalize tracked output."""


def evaluate_treeish(treeish: str) -> dict[str, object]:
    """Return stable sorted final-tree admission findings for one immutable revision."""
```

Use `git ls-tree -r "$TREEISH" -- runtime`, where `TREEISH` is the exact immutable PR, merge-group or main SHA under review. Reject modes other than regular files for runtime admission. In final-tree mode, do not call `Path.rglob`, `stat` or `git ls-files`.

Append this root-owned blocking gate alongside the existing root-directory and bin-convergence gates in `bin/gac/gac-local-gate.py`:

```python
{
    "id": "omo-runtime-final-tree",
    "command": [
        "bin/gac/omo-runtime-stamp-policy.py",
        "--treeish",
        "HEAD",
        "--json",
    ],
},
```

- [ ] **Step 4: Add narrow ignore rules for the bound output families**

Append:

```gitignore
/runtime/bos-neural-mesh-*
/runtime/concept-weave-preflight*.json
/runtime/consumer-audit-*.json
/runtime/control/evidence/documents-weijian-*/documents-weijian-*.json
/runtime/daily-health-preflight*.json
/runtime/heartbeats/weijian-*
/runtime/kos-preflight-*.json
/runtime/predictor-preflight*.json
/runtime/quarantine/documents-bos-neural-mesh-20260828/
/runtime/task-inventory/snapshots/2026082[78]-*.json
```

Expected: every runtime path in `WP-BET-Y1Q3-T6-15` is ignored under `git check-ignore --no-index`; canonical code/contracts remain trackable.

- [ ] **Step 5: Run GREEN and commit policy**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_omo_runtime_stamp_policy.py -q
uv run --with pyyaml --with pytest python -m pytest tests/unit/gac/test_gac_local_gate_purity.py -q
uv run --with pyyaml python bin/gac/omo-runtime-stamp-policy.py --treeish HEAD --json > /tmp/r2a-policy-green.json
uv run --with pyyaml python -c 'import json; d=json.load(open("/tmp/r2a-policy-green.json")); assert d["ok"] is True; assert d["forbidden_tracked_paths"] == []; assert d["invalid_modes"] == []'
git diff --check
git add bin/gac/gac-local-gate.py bin/gac/omo-runtime-stamp-policy.py \
  tests/test_omo_runtime_stamp_policy.py tests/unit/gac/test_gac_local_gate_purity.py .gitignore
git commit -m "fix(governance): gate tracked runtime artifacts by tree"
```

Expected: replacement tests pass in a fresh clone, current HEAD reports zero forbidden artifacts, and the new root blocking gate is present. Task 8 then proves repository untracking is already resolved or removes only any newly reintroduced matches in the same R2a run/PR.

---

### Task 8: R2a Exact Repository Untracking

**Files:**
- Remove from Git index only: every tracked path matched by the narrow `runtime/` family pathspecs in `WP-BET-Y1Q3-T6-15`.
- Preserve on disk: the same paths.

**Interfaces:**
- Consumes: Task 7 final-tree classifier and ignore rules.
- Produces: a clean final tree with local copies retained in the delivery clone.

- [ ] **Step 1: Expand the intentional-untrack pathspecs into an exact path list**

```bash
uv run --with pyyaml python - <<'PY' > /tmp/t6-15-runtime-patterns.txt
import yaml
d=yaml.safe_load(open('docs/plans/3y-bet-ledger.yaml'))
b=next(item for item in d['bets'] if item['id']=='BET-Y1Q3-T6-15')
for path in b['write_surfaces']:
    if path.startswith('runtime/'):
        print(path)
PY
rm -f /tmp/t6-15-runtime-paths.txt
while IFS= read -r pattern; do
  git ls-files -- "$pattern" >> /tmp/t6-15-runtime-paths.txt
done < /tmp/t6-15-runtime-patterns.txt
sort -u /tmp/t6-15-runtime-paths.txt -o /tmp/t6-15-runtime-paths.txt
wc -l /tmp/t6-15-runtime-paths.txt
```

Expected at `6bcf17b4e`: zero paths and `already_resolved` repository untracking. Every pattern still contains `*`, so D0 treats it as an intentional removal family. If execution-time main reintroduces matches, the expanded file contains only concrete tracked paths and is the sole input to `git rm --cached`.

- [ ] **Step 2: Prove every path is tracked, present and ignored-after-untrack**

```bash
if test -s /tmp/t6-15-runtime-paths.txt; then
  while IFS= read -r runtime_path; do
    git ls-files --error-unmatch "$runtime_path" >/dev/null
    test -e "$runtime_path"
    git check-ignore --no-index -q -- "$runtime_path"
  done < /tmp/t6-15-runtime-paths.txt
else
  echo "runtime untracking already_resolved"
fi
```

Expected: zero paths is a valid already-resolved result. Otherwise all checks pass; a missing, ambiguous, symlinked or non-ignored path stops R2a before index mutation.

- [ ] **Step 3: Remove only the exact paths from the index**

```bash
if test -s /tmp/t6-15-runtime-paths.txt; then
  while IFS= read -r runtime_path; do
    git rm --cached -- "$runtime_path"
  done < /tmp/t6-15-runtime-paths.txt
fi
```

Expected: no mutation when the list is empty. Otherwise Git records only the exact deletions and `test -e` still passes for every local source path.

- [ ] **Step 4: Verify final tree and fresh-clone behavior**

```bash
git write-tree > /tmp/r2a-tree.txt
uv run --with pyyaml python bin/gac/omo-runtime-stamp-policy.py --treeish "$(cat /tmp/r2a-tree.txt)" --json
while IFS= read -r runtime_path; do
  test -e "$runtime_path"
  test -z "$(git ls-files "$runtime_path")"
done < /tmp/t6-15-runtime-paths.txt
git diff --check
```

- [ ] **Step 5: Commit and merge R2a**

```bash
if test -s /tmp/t6-15-runtime-paths.txt; then
  git add .gitignore
  git commit -m "fix(runtime): untrack reintroduced runtime outputs"
else
  git diff --exit-code
fi
git push -u origin HEAD
gh pr create --base main \
  --title "fix(governance): complete runtime final-tree admission" \
  --body "BET-Y1Q3-T6-15 R2a recurrence tests and root blocking wiring; repository untracking is revalidated. Host retention is not claimed."
```

Required evidence: PR final-tree policy green, synthetic merge ref green, main post-merge green, fresh clone contains none of the removed outputs.

---

### Task 9: R2b Explicit Live-Host Retention

**Files:**
- Live source: `/Users/xiamingxing/Workspace/runtime`
- External evidence root: `/Users/xiamingxing/Documents/学习进化/基建架构/evidence/2026-08-28-post2408-runtime-retention`
- Repository closeout projection: `docs/reports/2026-08-28-post2408-main-recovery-closeout.md`

**Interfaces:**
- Consumes: merged R2a main and exact runtime path list.
- Produces: redacted backup/restore/integrity/owner/producer/rollback receipts.

- [ ] **Step 1: Obtain a second exact human authorization**

Authorization must name `/Users/xiamingxing/Workspace`, the external evidence root, producer stop/start permission and exact bound runtime paths. Without it, set R2b `UNPROVABLE` and stop.

- [ ] **Step 2: Build the approved relative path list read-only**

```bash
mkdir -p "/Users/xiamingxing/Documents/学习进化/基建架构/evidence/2026-08-28-post2408-runtime-retention"
export R2A_PR_NUMBER="$(gh pr list --repo starlink-awaken/omostation --state merged --search '"BET-Y1Q3-T6-15 R2a" in:body' --json number --jq 'if length==1 then .[0].number else error("R2A_PR_AMBIGUOUS") end')"
export R2A_MERGE_SHA="$(gh pr view "$R2A_PR_NUMBER" --repo starlink-awaken/omostation --json mergeCommit --jq '.mergeCommit.oid')"
git -C /Users/xiamingxing/Workspace show origin/main:docs/plans/3y-bet-ledger.yaml | \
  uv run --with pyyaml python -c 'import sys,yaml; d=yaml.safe_load(sys.stdin); b=next(x for x in d["bets"] if x["id"]=="BET-Y1Q3-T6-15"); print("\n".join(p for p in b["write_surfaces"] if p.startswith("runtime/")))' \
  > /tmp/t6-15-live-runtime-patterns.txt
rm -f /tmp/t6-15-live-runtime-paths.txt
while IFS= read -r pattern; do
  git -C /Users/xiamingxing/Workspace ls-tree -r --name-only "${R2A_MERGE_SHA}^" -- "$pattern" >> /tmp/t6-15-live-runtime-paths.txt
done < /tmp/t6-15-live-runtime-patterns.txt
sort -u /tmp/t6-15-live-runtime-paths.txt -o /tmp/t6-15-live-runtime-paths.txt
test -s /tmp/t6-15-live-runtime-paths.txt
```

- [ ] **Step 3: Refuse active writers before backup**

```bash
set +e
while IFS= read -r path; do
  lsof "/Users/xiamingxing/Workspace/$path"
done < /tmp/t6-15-live-runtime-paths.txt > /tmp/t6-15-lsof.txt 2>&1
set -e
test ! -s /tmp/t6-15-lsof.txt
```

Expected: no active writer. If any PID/process appears, stop and request a new authorization naming the exact producer; do not kill or stop it under the generic R2b approval.

- [ ] **Step 4: Back up files and immutable metadata**

```bash
export R2B_ROOT="/Users/xiamingxing/Documents/学习进化/基建架构/evidence/2026-08-28-post2408-runtime-retention"
cd /Users/xiamingxing/Workspace
rsync -aR --files-from=/tmp/t6-15-live-runtime-paths.txt ./ "$R2B_ROOT/backup/"
while IFS= read -r path; do
  shasum -a 256 "$path"
  stat -f '%Sp %u %g %N' "$path"
done < /tmp/t6-15-live-runtime-paths.txt > "$R2B_ROOT/before.sha256-and-stat"
```

- [ ] **Step 5: Update the live checkout only when clean and human-authorized**

```bash
git -C /Users/xiamingxing/Workspace status --porcelain --ignore-submodules=none
git -C /Users/xiamingxing/Workspace fetch origin main --prune
```

Expected: shared checkout is clean and on its approved integration branch. If dirty or on an unapproved branch, stop; never reset, checkout, stash or clean it automatically.

The human performs or explicitly authorizes the normal branch update. Afterward restore only the bound ignored paths:

```bash
cd "$R2B_ROOT/backup"
rsync -aR --files-from=/tmp/t6-15-live-runtime-paths.txt ./ /Users/xiamingxing/Workspace/
```

- [ ] **Step 6: Verify digest, SQLite integrity and ignored state**

```bash
cd /Users/xiamingxing/Workspace
while IFS= read -r path; do
  shasum -a 256 "$path"
  stat -f '%Sp %u %g %N' "$path"
  git check-ignore --no-index -q -- "$path"
  test -z "$(git ls-files "$path")"
done < /tmp/t6-15-live-runtime-paths.txt > "$R2B_ROOT/after.sha256-and-stat"
cmp "$R2B_ROOT/before.sha256-and-stat" "$R2B_ROOT/after.sha256-and-stat"
```

For every `.sqlite` path:

```bash
while IFS= read -r path; do
  case "$path" in
    *.sqlite) sqlite3 "file:/Users/xiamingxing/Workspace/$path?mode=ro" 'PRAGMA integrity_check;' ;;
  esac
done < /tmp/t6-15-live-runtime-paths.txt
```

Expected: every result is `ok`. Missing digest, ownership, ignored-state, integrity or producer evidence makes R2b `UNPROVABLE`.

---

### Task 10: Final Closeout and Product P0 Resume Gate

**Files:**
- Modify: `docs/reports/2026-08-28-post2408-main-recovery-closeout.md`
- Modify: `.omo/_knowledge/retros/BET-Y1Q3-T6-15.md`
- Modify: `docs/plans/3y-bet-ledger.yaml` only for T6-15 completion evidence/status after direct proof.

**Interfaces:**
- Consumes: R1 merge, H1a/H1c merges, H1b canary, live protection receipt, R2a merge/fresh clone and R2b receipts.
- Produces: `delivery_accepted` with value `NOT_PROVEN` and a Wave A resume decision.

The files were originally an honest R1 partial record from `ad19e2202`, then were overwritten by `c5363fc16` / PR #2459 with disputed H1c/R2a verification claims. Task 10 must append an explicit evidence invalidation/correction before any final assertion mapping: identify the missing receipts, unrelated PR #2452 attribution, stale fresh-clone test and absent root gate wiring. Preserve history; never silently rewrite it or consume file existence as T6-15 completion evidence.

- [ ] **Step 1: Write the redacted closeout mapping**

The report maps each Spec assertion to immutable SHA/run/receipt IDs. It must explicitly record:

```text
engineering=VERIFIED
operational=PROVEN
value=NOT_PROVEN
overall=delivery_accepted
```

No personal value or raw runtime payload enters the report.

- [ ] **Step 2: Write the five-question retrospective**

The retro answers what changed, what failed, why multi-agent/main churn caused retries, surface additions/removals, and how future writers avoid stale clone/pointer/false-green recurrence.

- [ ] **Step 3: Update only T6-15 completion evidence**

Resolve the immutable values first:

```bash
export FINAL_MERGE_SHA="$(git rev-parse origin/main)"
export CLOSEOUT_SHA256="$(shasum -a 256 docs/reports/2026-08-28-post2408-main-recovery-closeout.md | awk '{print $1}')"
```

Use the canonical `completion-evidence-matrix/v1` keys with those exact resolved values:

```yaml
completion_evidence:
  schema_version: completion-evidence-matrix/v1
  axes:
    engineering:
      status: VERIFIED
      evidence:
        merged_reachable_commit: {ref: "git://origin/main@${FINAL_MERGE_SHA}"}
        tests: {ref: receipt://docs/reports/2026-08-28-post2408-main-recovery-closeout.md, sha256: "sha256:${CLOSEOUT_SHA256}"}
        diff: {ref: receipt://docs/reports/2026-08-28-post2408-main-recovery-closeout.md, sha256: "sha256:${CLOSEOUT_SHA256}"}
        rollback: {ref: receipt://docs/reports/2026-08-28-post2408-main-recovery-closeout.md, sha256: "sha256:${CLOSEOUT_SHA256}"}
    operational:
      status: PROVEN
      evidence:
        live_canary: {ref: receipt://docs/reports/2026-08-28-post2408-main-recovery-closeout.md, sha256: "sha256:${CLOSEOUT_SHA256}"}
        fresh_receipt: {ref: receipt://docs/reports/2026-08-28-post2408-main-recovery-closeout.md, sha256: "sha256:${CLOSEOUT_SHA256}"}
        replay: {ref: receipt://docs/reports/2026-08-28-post2408-main-recovery-closeout.md, sha256: "sha256:${CLOSEOUT_SHA256}"}
        cleanup: {ref: receipt://docs/reports/2026-08-28-post2408-main-recovery-closeout.md, sha256: "sha256:${CLOSEOUT_SHA256}"}
    value:
      status: NOT_PROVEN
      evidence: {}
  overall_state: delivery_accepted
```

The execution worker substitutes only measured immutable SHA/digest values; if any is unavailable, it must not edit the matrix.

- [ ] **Step 4: Verify and complete the BET**

```bash
git add docs/reports/2026-08-28-post2408-main-recovery-closeout.md \
  .omo/_knowledge/retros/BET-Y1Q3-T6-15.md \
  docs/plans/3y-bet-ledger.yaml
uv run --with pyyaml python bin/plan/bet-ledger.py lint
uv run --with pyyaml python bin/plan/bet-ledger.py complete BET-Y1Q3-T6-15
git add docs/plans/3y-bet-ledger.yaml
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_gac_gate_workflow_purity.py \
  tests/test_ci_surfaces.py \
  tests/test_gac_branch_protection.py \
  tests/test_omo_runtime_stamp_policy.py \
  tests/test_root_directory_governance.py -q
uv run --python 3.13 --with pyyaml python bin/gac/gac-local-gate.py --strict
uv run --with pyyaml python bin/plan/bet-ledger.py lint
git diff --cached --check
git commit -m "docs(closeout): complete post2408 recovery BET"
```

Expected: T6-15 becomes `done` only through `delivery_accepted`; value remains `NOT_PROVEN`.

- [ ] **Step 5: Close the run and publish the final closeout PR**

The closeout artifacts and matrix transition are already staged before `complete`; after the Step 4 commit, execute the exact final delivery chain:

```bash
verify_args=()
while IFS= read -r path; do verify_args+=(--file "$path"); done < /tmp/t6-phase-claims.txt
uv run --with pyyaml python bin/agent-workflow.py verify "$T6_RUN_ID" "${verify_args[@]}" --execute --json
uv run --with pyyaml python bin/agent-workflow.py closeout "$T6_RUN_ID" --status ok "${verify_args[@]}" --json
git tag -a "bet/BET-Y1Q3-T6-15-$(date -u +%Y%m%dT%H%M%SZ)" -m "BET-Y1Q3-T6-15 delivery_accepted"
git push -u origin HEAD --follow-tags
gh pr create --base main \
  --title "docs(closeout): complete post2408 recovery BET" \
  --body "BET-Y1Q3-T6-15 closeout only: engineering VERIFIED, operational PROVEN, value NOT_PROVEN, overall delivery_accepted."
export PHASE_PR_NUMBER="$(gh pr view --json number --jq .number)"
gh pr checks --required --watch --interval 10
gh pr checks --watch --interval 15
gh pr merge "$PHASE_PR_NUMBER" --squash --delete-branch
export CLOSEOUT_MERGE_SHA="$(gh pr view "$PHASE_PR_NUMBER" --json mergeCommit --jq '.mergeCommit.oid')"
git fetch origin main --prune
git merge-base --is-ancestor "$CLOSEOUT_MERGE_SHA" origin/main
git show origin/main:docs/plans/3y-bet-ledger.yaml \
  | uv run --with pyyaml python -c 'import sys,yaml; d=yaml.safe_load(sys.stdin); b=next(x for x in d["bets"] if x["id"]=="BET-Y1Q3-T6-15"); assert b["status"]=="done"; assert b["completion_evidence"]["overall_state"]=="delivery_accepted"; assert b["completion_evidence"]["axes"]["value"]["status"]=="NOT_PROVEN"'
cd /Users/xiamingxing/Workspace
python3 bin/gac/clone-lifecycle.py retire \
  --destination "$T6_DEST" \
  --platform-rebased-pr "$PHASE_PR_NUMBER"
```

Expected: the unique closeout PR is merged, its merge SHA is reachable from current main, the value firewall remains intact, every workflow lock is released, and clone retirement is either proven or reported fail-closed.

- [ ] **Step 6: Resume Product P0 deliberately**

Audit main after T6 completion. WP1 code already merged; do not duplicate it. Resume WP1 only for honest operational evidence/closeout. Allow at most one new Wave A writer for WP4. Any T4 child completion must use `delivery_accepted` except WP5, which alone may use principal-bound `outcome_accepted`.

## Spec Coverage Matrix

| Accepted Spec contract | Plan task |
|---|---|
| Execution-time truth snapshot and no stale numeric SSOT | Task 0 |
| Compile/conflict/script-registry/GaC recovery | Tasks 0–1 |
| ADR-0432 remains candidate/UNPROVABLE | Task 1 |
| Existing `gac-gate`, no second workflow or duplicated checklist | Tasks 2–4 |
| Immutable checkout and strict blocking | Task 2 |
| Workflow-level CI surface binding only | Task 3 |
| Main-SHA strict-step canary and platform capacity evidence | Task 4 |
| Guarded double-read add/remove/check and preservation of protection fields | Tasks 5–6 |
| Live protection mutation only after explicit human authorization | Task 6 |
| Immutable-tree tracked-runtime recurrence gate | Task 7 |
| Exact repository untracking with local clone copies retained | Task 8 |
| Separate live-host backup/restore/integrity/producer proof | Task 9 |
| Value firewall, `delivery_accepted`, retro, rollback and Wave A resume | Task 10 |

No accepted requirement is implemented by tests, PR counts, agent self-report or dashboard scores alone. Any missing evidence remains `UNPROVABLE`.

## Execution Handoff

This plan is intentionally not self-authorizing. After plan review:

1. Use Subagent-Driven Development for Tasks 0–5 and 7–8, with task-level and whole-branch reviews.
2. Pause for explicit human authorization at Task 6 and Task 9.
3. Keep one writer per repository phase and create a new independent clone after every merged PR.
4. Never restart from a stale delivery clone or rerun an already-queued workflow merely to obtain a green badge.
