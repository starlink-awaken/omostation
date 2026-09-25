---
type: human-gate-decision-board
status: active
refreshed_at: 2026-09-20T08:48:30Z
scope: AgentOS recovery and observability closeout
---

# Agent OS human gate decision board

## Authoritative snapshot

- Remote main: `25adbd70cd9c67f78276f390a03a15b97bad2765`
- A4 recovery: `PASS` on origin/main via #4093; clean replay reports `drift=0`, `orphan=0`, `known_orphan=1`.
- A4 host deployment: host `code-main` registry matches #4093 bytes; focused scheduler check is `PASS`. Backup SHA `f8ee9d9e...`.
- Managed code-main: fully aligned to `25adbd70...`; `dirty_count=0`; scheduler replay PASS; `OMO_SINGLE_CONTROL_PLANE=PASS`.
- Workflow: no active run, `locks=0`, `stale_locks=0`
- Claims observation: `413/1440`, errors `0`, max gap `60.22s`, `shadow-active`; 4h diagnostic PASS; 6h SUSTAINED diagnostic PASS
- Latest execution snapshot: `2026-09-20-agent-os-execution-environment-snapshot-20260920T083400Z.json` SHA-256 `4a1377b269250d0ace1c1b77fe513e27f458f2fa9b00e686f10592d9aee2090c`; it records all gates PASS and Claims `419/1440`.
- Latest execution snapshot: `2026-09-20-agent-os-execution-environment-snapshot-20260920T084600Z.json` SHA-256 `26ce57374ade05609eee1847d9459cba5b8c1496b71fca525288e425de0e918d`; it records Claims `435/1440`, code health PASS, and the safely restored T10-170 projection gap.
- High alert triage: `Submodule Freshness Gatekeeper` is real debt, not a stale fixture. Root origin pin `022ba300...` is behind merged child main `d7feb927...`; OMO PR #182 is merged and reachable in target. Execution waits for exact T10-172 approval.
- Execution gates: live Panorama now reports A1–A9, RF0, and RC-DL all `PASS`. Canonical shared Workspace remains `WARN` because local `main` is divergent (`2 ahead / 1 behind`) with resident and `projects/omo` edits. Host A1.3 warning is limited to an uninitialized host cockpit-ui checkout, not remote corruption.
- Business value: `NOT_PROVEN`; v2 qualifying `0/30`; legacy qualifying `1` is history only
- Known display debt: the running 43191 process still returns v1 readiness with `29` remaining; canonical Panorama v2 correctly reports `30` remaining. T10-171 fixes this after merge, deployment, and separate restart approval.

## Decision 1 — approve T10-170 implementation

Package: `t10-170-current-run-projection-package`

```text
批准 T10-170 Draft Spec SHA-256 d52e3e1fe22fa047bc103b897a6d38df9043032ef5e9a02a8ebd8f9e3ca5feba 转 accepted 并授权实施；创建 BET-Y1Q4-T10-170；仅限 README 六个 write surfaces；按 collector patch 64275d... 与 test patch 5987e5... 执行；默认门禁拒绝即停止。
```

Ready state: apply `PASS`, focused tests `4 passed`, latest-main target drift `none`.

## Decision 2 — approve T10-171 implementation

Package: `t10-171-live-value-readiness-v2-package`

```text
批准 T10-171 Draft Spec SHA-256 fe7bc2866848f9ffc38599e9385269341566cb99d5b8f373582128efa38dd7ed 转 accepted 并授权实施；创建 BET-Y1Q4-T10-171；仅限 README write surfaces；按 live-server patch c3a33ed... 和 test b99d91f... 执行；批准合并后的 host-sync restore；43191 restart 仍需单独明确授权；默认门禁拒绝即停止。
```

Ready state: apply `PASS`, focused tests `3 passed`, latest-main target drift `none`.
Separate restart package: `restart-runbook.md`
SHA-256 `d343e64ef05386922f31748663e4e1d47efaad92e0fe0a3e449dfcd57ac614ac`.

## Decision 3 — promote Claims lifecycle runbook v2

Package: `2026-09-20-claims-lifecycle-runbook-v2-reconciliation-package`

```text
批准 Claims lifecycle runbook v2 candidate SHA-256 21c5005d76712fe504e06a414e864e18682ddd2a191298ef22f621d2388dc438 成为唯一执行 runbook；仅修正 stale draft/review binding 和 status；不授权 lifecycle 执行、authority mutation、push、PR、merge 或 restart。
```

Reason: the existing runbook `f188b766...` contains stale draft/review bindings and must not be executed.

## Decision 4 — separate Claims lifecycle execution

This remains blocked until Decision 3 completes. Then the operator must approve the exact lifecycle quote in `lifecycle-authorization-review.md` and provide:

- `principal_decision_id`
- `decision_timestamp_utc`
- `decision_expires_at_utc`

Hard limits remain one external effect per operation, no force push, no `--no-verify`, no automatic retry after unknown outcome, no historical receipt mutation, and no instruction capability.

## Decision 5 — approve T10-172 OMO gitlink freshness repair

Package: `t10-172-omo-gitlink-freshness-package`

```text
批准 T10-172 Draft Spec SHA-256 f9dc4bafdf3834cbe56554361ebf1b8d2e5a2855718a16fb0087e40608990b5f 转 accepted 并授权实施；创建 BET-Y1Q4-T10-172；仅将 projects/omo 从 022ba300... 前进到 d7feb927...，若 child main 已变化则停止并重新准备；使用隔离 worktree、默认门禁、唯一 PR；required checks 全绿后 squash merge、exact-gitlink 验证并退役 clone；不改其他 gitlink、实现代码或运行态。
```

This clears the two high CI alerts from `Submodule Freshness Gatekeeper` and
`Submodule Auto-Bump`. The child change is merged OMO PR #182; focused tests
passed `133` at exact target commit `d7feb927...` in a clean temporary clone.

## Decision 6 — approve T10-173 promotion helper binding repair

Package: `t10-173-promotion-helper-binding-package`

```text
批准 T10-173 Draft Spec SHA-256 15d90aceb6231bfad7d1d4fef8dbc10fbc9d496176c80cbc8aff1e241791dada 转 accepted 并授权实施；创建 BET-Y1Q4-T10-173；仅修改 OMO promotion helper 的 standalone binding；使用隔离 child worktree、默认门禁、唯一 child PR；required checks 全绿后 merge；root gitlink bump 另立独立事务；不改 audit/mutation 语义、Claims 状态、runtime 或其他 gitlink。
```

This fixes a pre-existing standalone-import `NameError` found during T10-172
baseline comparison. It reproduces at both old and target OMO pins.

## Decision 7 — T10-174 already resolved on main

Package: `t10-174-adr-numbering-regression-package`

```text
批准 T10-174 Draft Spec SHA-256 319c0b2eada7c2d4eedbd6c0e7f897762f8a44e0075e0b5e74217ff674651b74 转 accepted 并授权实施；创建 BET-Y1Q4-T10-174；仅将误编号的 ADR-0402 多尺度信号决策重编号为 ADR-0453，补 INDEX，并将 DECL_EXEC_GAP 新证据引用改为 ADR-0453；使用隔离 worktree、默认门禁、唯一 PR；required checks 全绿后 squash merge；不改 ADR 结论、authority state、runtime、gitlink 或其他 governance policy。
```

`PR #4087` / `d96be316a4d52fafd60aa2a75c436e333fb32dc0` already renumbered the
decision to `ADR-0453`, updated `INDEX.md`, and updated `DECL_EXEC_GAP.yaml`.
No duplicate implementation approval or PR is required. The stale local
Workspace checkout can still show the old duplicate; use `origin/main` as truth.

## Human-only action — business value

Collect real, post-baseline `value-evidence/v2` records through the local operator flow. Agents must not synthesize, proxy, backfill, replay, or count legacy records. Current target: 30 qualifying v2 samples.

## Explicitly not blocked

- Continue the Claims observation window naturally.
- Keep the dashboard refreshed.
- Preserve all approved packages and evidence.
- Do not retry a guarded transaction after a gate rejection.
- Triage the `projects/omo` freshness alert only through T10-172; do not self-heal the canonical Workspace.
