---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-10
last-reviewed: 2026-09-10
value_indicator_policy: false
title: Agent workflow doctor strict-gate timeout recovery waiver
type: doc
---

# Agent Workflow Doctor Strict-Gate Timeout Recovery Waiver

## Human authority and exact scope

Initial authority, verbatim:

> 授权给你延迟到24点，继续

Extended authority, verbatim:

> 授权窗口，继续延长吧，延到9月15日24点之前。

The delegation is interpreted in Asia/Shanghai and expires at
`2026-09-16T00:00:00+08:00`. It authorizes this reversible repository-only
mechanism repair so the already merged Claims Authority Bridge WP1 1.1.0
binding can complete local post-merge verification. It does not authorize any
Ledger/BET, completion/value, Spec, Claims implementation, gitlink, CI
workflow, branch protection, service, database, timer or user-configuration
change.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the fresh unbound
`project-code-change` start
`20260910T075526Z-project-code-change-595427c9`. All subsequent claims, edits,
tests, verification, Git, CI and closeout use default policy. The official
process-local `AGENT_WORKFLOW_ALLOWED_LANES=governance_code,governance_state`
may be used only for this code/test/waiver transaction and does not add a path
or skip a gate.

The only tracked paths are:

1. `bin/gac/gac-local-gate.py`
2. `tests/unit/gac/test_gac_local_gate_timeouts.py`
3. this waiver

## Root cause and predecessor evidence

Claims WP1 binding PR #3509 merged as
`c6fd8d7bbdabc37cf9acdcf453fa267db538218a`. Its required and replacement
post-merge GitHub workflows passed. A fresh full clone pinned exactly to that
merge ran local strict GaC: every check passed except
`agent-workflow-doctor`, which timed out after 45 seconds. The exact doctor
then returned `ok=true` in 49.35 seconds, proving a false outer timeout for
that run rather than an integration failure.

The first 60-second repair attempt stopped before commit when remote main
advanced through unrelated Cockpit gitlink PR #3510. It created no tag, push
or PR and released all five locks.

The immutable second 60-second attempt reproduced TDD RED and GREEN and passed
focused tests, workflow verify and compliance. Local strict GaC nevertheless
timed out the doctor after 60 seconds while every other strict check passed.
Both digest-bound reviewers blocked staged digest
`b0be9433c8f94759accf6d43c8273a501d374804119663ff9790feb95d684a98`.
The run closed blocked with five locks zero and no commit, tag, push or PR.

Read-only recalibration measured a successful clean full-clone doctor at 46.87
seconds. A separate exact GaC runner calibration returned in 51.883 seconds
with return code 1 because it ran after that predecessor workflow had closed;
it supplies duration only, not a successful doctor verdict. Raw timing and
JSON outputs remain outside the clones under the corresponding predecessor
attempt `evidence/` directories.

The immutable third attempt introduced the 120-second aggregate boundary and
reproduced RED/GREEN. Its exact three-path digest
`9c4606ef2602da3098f166eb38497fa759c069b1ce92d14995944795950e8840`
passed workflow verification, compliance, two read-only reviews and local
strict GaC with 75 checks ALL GREEN. Before commit, two independent reads found
remote main had advanced from `9e8e9183` to `7547dd22`; GitHub object reads
proved none of the three authorized paths changed. Immutable-writer policy
therefore stopped it without commit, tag, push or PR and released all locks.

## Current immutable successor and repair contract

- Frozen main: `7547dd22da83f5dd88de4603b6975fe1610cdbae`.
- Managed full clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/agent-workflow-doctor-timeout-recovery-20260910-04/ws`.
- Provenance: `ready /
  1a44e7d2c6fbc24f7717377818373602cc1d0f91cd2bd00d6009e9d097fe37dd`.
- Readiness: `ready /
  f189466d7cda8acf712e9c04ba6dff6c45b2be9a4b9b1b12aa397fae932e0249`.
- Affected graph:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`.
- Transport: self-contained, non-authoritative local acceleration with no
  persistent alternates; root and all 16 selected gitlinks matched authority.

The default doctor runs 23 registry `doctor_checks` plus its separate AGCP
drift probe sequentially. Its strict-GaC timeout is an independent 120-second
end-to-end outer boundary: more than double the successful 46.87-second
clean-run duration and still a finite fail-closed limit. It does not promise
that every nested probe may consume its own 120-second timeout; the aggregate
outer boundary may stop the doctor first. No command, ordering, strictness,
nested timeout, soft/broken classification or other timeout changes.

The accepted predecessor TDD proof is reproduced in this successor before
publication. RED changes only the existing test to require exactly 120 and
must fail against 45; GREEN changes only the doctor default and must pass.

## Verification, publication and rollback

Before publication, the exact three-path patch must pass focused tests,
default workflow verify/compliance, local default GaC, local strict GaC and two
digest-bound read-only reviews. Any different failure stops. The standard v1
changeset path must run; a fixed claims-authority rejection is disclosed rather
than called verified.

Publication permits one ordinary non-force push and one unique PR with all
hooks enabled. Required contexts must be green before squash merge. Cloud CI
skips this local-only doctor, so cloud green cannot substitute for local strict
proof. Post-merge, the Claims binding digests and local strict GaC are rechecked
before Wave A starts. This recovery is mechanism evidence only, never
completion or value.

The exact post-merge replay is:

```bash
test "$(shasum -a 256 docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md | awk '{print $1}')" = "032957ededf4b7ade8e9543ae38f322083908a99c840d7e8a52f7300dc2e16cf"
uv run --with pyyaml python -c 'import runpy,sys; m=runpy.run_path(sys.argv[1]); print(m[sys.argv[2]](sys.argv[3], require_startable=False)[sys.argv[4]])' bin/plan/bet-ledger.py prepare_bet_execution BET-Y1Q4-T10-145 work_packet_hash | grep -Fx sha256:09395b02d0c917e3aa1bf25809de27b52c0d82e6395552547d613a45fe53f1ab
uv run --with pyyaml python bin/gac/gac-local-gate.py --strict
```

Rollback is an ordinary reviewed PR restoring 45 and its exact test assertion.
It does not rewrite history or hide measured evidence. Rollback knowingly
reopens the local strict timeout blocker, so it cannot support a claim that
Claims Wave A is unblocked. Its exact verification is:

```bash
uv run --with pyyaml --with pytest python -m pytest tests/unit/gac/test_gac_local_gate_timeouts.py -q
uv run --with pyyaml python -c 'import importlib.util, pathlib; p=pathlib.Path("bin/gac/gac-local-gate.py"); s=importlib.util.spec_from_file_location("gac_rollback", p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); assert m._DEFAULT_CHECK_TIMEOUTS["agent-workflow-doctor"] == 45'
make gac-local-gate
```
