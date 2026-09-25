---
type: human-gate-decision-board
status: active
refreshed_at: 2026-09-21T06:15:00Z
scope: AgentOS recovery and observability closeout
---

# Agent OS human gate decision board

## Authoritative snapshot

- Remote main: `f96a182c53d5b64cf0438282765a8e8776be7f3b`
- A4 recovery: `PASS` on origin/main via #4093; clean replay reports `drift=0`, `orphan=0`, `known_orphan=1`.
- A4 host deployment: host `code-main` registry matches #4093 bytes; focused scheduler check is `PASS`. Backup SHA `f8ee9d9e...`.
- Managed code-main: fully aligned to `25adbd70...`; `dirty_count=0`; scheduler replay PASS; `OMO_SINGLE_CONTROL_PLANE=PASS`.
- Workflow: no active run, `locks=0`, `stale_locks=0`
- Claims observation: sampling window complete — `1440/1440`, projection state `GRADUATION_REACHED` (started `2026-09-20T01:31:06Z`, elapsed ~92973s, errors `0`). However lifecycle blockers remain: `authority_store_asymmetric_presence`, `operation_specific_host_authorization_unproven`; the 4 lifecycle-evidence classes remain unproducible: Decision 4 executed 2026-09-21 and was **TERMINATED_AT_BINDING_VALIDATION** — the approval binding is unsatisfiable (T10-145 done → no legitimate bound run; docs/reports path absent from packet write_surfaces; fence-adapter contract mismatch). Zero broker writes, zero external effects, store byte-identical to baseline. See `~/.omo-evidence/d4-lifecycle-20260921/execution-outcome-TERMINATED.md`.
- PR #4088 triage: closed by owner without merge. Its dashboard BET registration remains unmerged and must be re-prepared through a later governed transaction; no reopen or duplicate.
- PR #4090 triage: `CLOSED`; its ADR repair intent is superseded by #4092 / `b17e7e9a6`. The local branch still carries broad resident/state/ledger/OMO changes. No reopen, rerun, merge, or cleanup.
- PR #4094 triage: merged with required checks PASS; merge SHA `f728b1f589c9adc8b2c96f4626eb435204ae5f07`. The branch delivered quarterly-report automation, the registered replacement, and the `projects/omo` advance.
- Launchd cutover: complete and reversible. The stale `com.l4.gac.watchdog` plist was backed up, bootout-ed, and removed after #4094 merged. Meta-doctor reports `dead_refs=0`; A2/A5 and OMO control plane are `PASS`.
- A7 note: one collector attempt briefly showed Multica AS0 `NOT_ADMITTED`; direct read-only verifier and fresh collector projection restored `api 30/30`, `topology 7/7`, `trust 3/3`. Classified as transient adapter reachability, not admission loss.
- Latest execution snapshot: `2026-09-20-agent-os-execution-environment-snapshot-20260920T083400Z.json` SHA-256 `4a1377b269250d0ace1c1b77fe513e27f458f2fa9b00e686f10592d9aee2090c`; it records all gates PASS and Claims `419/1440`.
- Latest execution snapshot: `2026-09-20-agent-os-execution-environment-snapshot-20260920T084600Z.json` SHA-256 `26ce57374ade05609eee1847d9459cba5b8c1496b71fca525288e425de0e918d`; it records Claims `435/1440`, code health PASS, and the safely restored T10-170 projection gap.
- Gitlink reconciliation: `projects/omo` now equals `d7feb927...` on main via #4094. T10-172 was accepted/armed, but its dedicated PR was not used; do not mark done or duplicate implementation. Reconcile accepted binding, ledger entry, evidence, closeout, and provenance in a later governed transaction.
- Delivery completion: T10-172 and T10-173 are now `done` on main via #4094/#4096/#4099 and #184/#4097/#4098 respectively.
- Execution gates: live Panorama now reports A1–A9, RF0, and RC-DL all `PASS`. Canonical shared Workspace remains `WARN`: its branch head `cde5c1f2` was merged through #4094 as main `f728b1f5`, but the local cached origin/main ref is stale after a network failure, and the worktree still has resident/state edits. Do not push, reset, update, or clean it from this transaction.
- Live gate note: A2/A5 report `stale_beats=1`; cause is overdue `system_health.last_scan` maintenance plus the human weekly-review heartbeat. Agents must not fabricate the review or mutate state to hide it. Launchd dead-ref regression is separately resolved.
- Concurrent `.gitignore` edit: low-risk runtime-cache hygiene only; it adds `LADS/`. Owned by the concurrent session; no action taken here.
- Business value: `NOT_PROVEN`; v2 qualifying `0/30`; legacy qualifying `1` is history only
- Known display debt (RESOLVED): T10-171 merged as PR #4101 (`6982fc2ed`); the v2 asset is installed on the host (`fa0f9b66…`) and the 43191 process was refreshed via `ensure_local_server` respawn (PID 36955) — live `/api/v1/agent/value-proof-readiness` now reports `agent-value-proof-readiness/v2` with `qualifying=0` / `remaining=30`. No kill was needed; acceptance receipts in the package dir.

## Awaiting principal (live queue)

1. **Human weekly-review heartbeat** (>14d) — principal-only; agents must not fabricate. Principal action: `make weekly-review` (= `python3 bin/gac/weekly-review.py --generate`).
2. ~~**Decision 1 — T10-170 implementation**~~ — **DELIVERED**: approved and implemented; merged as PR #4100 (commit `2e38dbe53`), deployed to host collector (SHA-256 `01a26150…`, byte-match with merged asset), live projection verified coherent single current-run claims observation.

```text
批准 T10-170 Draft Spec SHA-256 d52e3e1fe22fa047bc103b897a6d38df9043032ef5e9a02a8ebd8f9e3ca5feba 转 accepted 并授权实施；创建 BET-Y1Q4-T10-170；仅限 README 六个 write surfaces；按 collector patch 64275d... 与 test patch 5987e5... 执行；默认门禁拒绝即停止。
```

3. ~~**Decision 2 — T10-171 implementation**~~ — **DELIVERED / LEDGER CLOSED**: approved and implemented; merged as PR #4101 (commit `6982fc2ed`), host asset installed (SHA-256 `fa0f9b66…`); the 43191 restart was satisfied by `ensure_local_server` respawn without any kill — live API now serves v2 readiness (`qualifying=0`, `remaining=30`). `BET-Y1Q4-T10-171` is `done` on main.

```text
批准 T10-171 Draft Spec SHA-256 fe7bc2866848f9ffc38599e9385269341566cb99d5b8f373582128efa38dd7ed 转 accepted 并授权实施；创建 BET-Y1Q4-T10-171；仅限 README write surfaces；按 live-server patch c3a33ed... 和 test b99d91f... 执行；批准合并后的 host-sync restore；43191 restart 仍需单独明确授权；默认门禁拒绝即停止。
```

4. ~~**Decision 3 — Claims lifecycle runbook v2 promotion**~~ — **PROMOTED** 2026-09-21T06:10Z（v2 已成为唯一执行 runbook；lifecycle 执行仍未授权）

```text
批准 Claims lifecycle runbook v2 candidate SHA-256 21c5005d76712fe504e06a414e864e18682ddd2a191298ef22f621d2388dc438 成为唯一执行 runbook；仅修正 stale draft/review binding 和 status；不授权 lifecycle 执行、authority mutation、push、PR、merge 或 restart。
```

5. ~~**Decision 4 — Claims lifecycle execution**~~ — **TERMINATED_AT_BINDING_VALIDATION**（2026-09-21 执行；授权绑定不可满足，零 broker 写、零外部效应；见 `~/.omo-evidence/d4-lifecycle-20260921/execution-outcome-TERMINATED.md`）


```text
批准 Claims Authority lifecycle authorization draft SHA-256 07d655deb0f90e8a888f8a65b634a280aa28cfec48335cbfca9f12d6e36f7682，仅授权草案中的三个 operation，每个外部效果最多一次；legacy publication 仅限 candidate report 路径 docs/reports/2026-09-20-claims-authority-lifecycle-regression-runbook.md、content SHA-256 83348338d4905d440c74ef10da6f8b6ce95f31c3ce26f2808f9743b8ed0ff127、patch SHA-256 b5f731ff86791edd3be75ceff855c26ca69ed9435fbd7bcb66127e12550b9614；WorkPacket digest 必须重算匹配 sha256:8e12e6636ac5e8b373872f281c4851c99dc67bd39cc3630d2b5cfaf2cb58cf57；执行前必须绑定 latest origin/main、run id、clone identity、remote ref、expected remote oid 和 effect process identity；禁止 force、--no-verify、unknown 后自动重试、修改 historical receipts 或启用 instruction capability；任一 stop condition 触发即停止。
```

6. **Opt-in — Agent Brief pending-approval surfacing**：提案与补丁草案已备好于 `2026-09-20-agent-brief-pending-surfacing-package/proposal.md`（DRAFT_NOT_APPLIED，锚定 asset next_actions 列表）；批准后按受治理流程 worktree→测试→PR→host-sync 落地。

> Timeline: claims sampling completes `2026-09-21T01:31:06Z`; graduation additionally requires the 4 lifecycle-evidence classes, only producible after Decision 3 → Decision 4.

## Decision 1 — approve T10-170 implementation

Package: `t10-170-current-run-projection-package`

```text
批准 T10-170 Draft Spec SHA-256 d52e3e1fe22fa047bc103b897a6d38df9043032ef5e9a02a8ebd8f9e3ca5feba 转 accepted 并授权实施；创建 BET-Y1Q4-T10-170；仅限 README 六个 write surfaces；按 collector patch 64275d... 与 test patch 5987e5... 执行；默认门禁拒绝即停止。
```

Ready state: apply `PASS`, focused tests `4 passed`, latest-main target drift `none`.
Revalidated at `25adbd70...`: focused tests `4 passed` in a disposable origin/main tree.
Expected accepted Spec SHA after the two authorized field flips: `5297bb547c38f990def022a7609648275a750a245b3acb4f04204874b4b1c741`.

Status: **DELIVERED — LEDGER CLOSED** — merged as PR [#4100](https://github.com/starlink-awaken/omostation/pull/4100) (commit `2e38dbe53`); host collector deployed at SHA-256 `01a2615077eea01afdc704ca6bb656a7de0e89e89a3f0cc93eeaa5d93fce6228` (byte-match with merged asset); live `data.json` shows a coherent single current-run `claims_observation_progress` projection (`GRADUATION_REACHED` window semantics excluded prior attempts). Retros + completion evidence merged as PR #4119 (`561a69022`); ledger `BET-Y1Q4-T10-170` is `done` (`done_at: 2026-09-21`, overall_state `delivery_accepted`) via PR #4120 (`1f67edad7`) under governed run `20260921T042502Z-project-doc-change-0aedb093` (closeout ok, worktree retired).

## Decision 2 — approve T10-171 implementation

Package: `t10-171-live-value-readiness-v2-package`

```text
批准 T10-171 Draft Spec SHA-256 fe7bc2866848f9ffc38599e9385269341566cb99d5b8f373582128efa38dd7ed 转 accepted 并授权实施；创建 BET-Y1Q4-T10-171；仅限 README write surfaces；按 live-server patch c3a33ed... 和 test b99d91f... 执行；批准合并后的 host-sync restore；43191 restart 仍需单独明确授权；默认门禁拒绝即停止。
```

Ready state: apply `PASS`, focused tests `3 passed`, latest-main target drift `none`.
Revalidated at `25adbd70...`: focused tests `3 passed` in a disposable origin/main tree.
Expected accepted Spec SHA after the two authorized field flips: `1df1f3db72b4343814861c74b688a03edd418e5f0c706158410cfa06824ae9b9`.
Separate restart package: `restart-runbook.md`
SHA-256 `d343e64ef05386922f31748663e4e1d47efaad92e0fe0a3e449dfcd57ac614ac`.

Status: **DELIVERED — LEDGER CLOSED** — merged as PR [#4101](https://github.com/starlink-awaken/omostation/pull/4101) (commit `6982fc2ed`); host asset installed at SHA-256 `fa0f9b66054f598867ecf74f01047729e05e015e40f1fea265dd49b0575dc95f` (precondition `7a6c76e0…` verified before install; backups `*.bak-20260921T032219Z`). Restart requirement satisfied without any kill: `ensure_local_server` respawn brought up PID 36955 serving `agent-value-proof-readiness/v2` (`qualifying=0`, `remaining=30`; receipts `canary-health-20260921T0518Z.json` / `canary-readiness-20260921T0518Z.json`). Canary evidence merged via PR #4130 (`8132e4a91`): engineering VERIFIED, operational PROVEN, `overall_state: delivery_accepted`. Ledger `done` via PR #4134 (`f96a182c5`); workflow run `20260921T054308Z-project-doc-change-1b01c91e` closed out ok. Value remains `NOT_PROVEN`.

## Decision 3 — promote Claims lifecycle runbook v2

Package: `2026-09-20-claims-lifecycle-runbook-v2-reconciliation-package`

```text
批准 Claims lifecycle runbook v2 candidate SHA-256 21c5005d76712fe504e06a414e864e18682ddd2a191298ef22f621d2388dc438 成为唯一执行 runbook；仅修正 stale draft/review binding 和 status；不授权 lifecycle 执行、authority mutation、push、PR、merge 或 restart。
```

Reason: the existing runbook `f188b766...` contains stale draft/review bindings and must not be executed.

Status: **PROMOTED** (2026-09-21T06:10Z) — all four precondition hashes re-verified (source `f188b766…`, draft `07d655de…`, review `331c8b46…`, candidate `21c5005d…`); stale v1 preserved as `lifecycle-execution-runbook.v1-stale-f188b766….md`; candidate atomically installed as `lifecycle-execution-runbook.md` with installed SHA equal to candidate; binding assertions PASS (stale `caf209d5…`/`ad18a8ba…` absent, `NOT_AUTHORIZED_TO_RUN` marker present). Receipt: `PROMOTION-EXECUTED-20260921T0610Z.json`. The principal authorized via direct reply ("继续吧，我给你授权，你来处理") rather than verbatim quote relay — recorded transparently in the receipt. Lifecycle execution remains unauthorized (Decision 4).

## Decision 4 — separate Claims lifecycle execution

Decision 3 is complete (v2 promoted). The operator must now approve the exact lifecycle quote in `lifecycle-authorization-review.md` (`331c8b46…`, bound by the installed v2 runbook) and provide:

- `principal_decision_id`
- `decision_timestamp_utc`
- `decision_expires_at_utc`

Hard limits remain one external effect per operation, no force push, no `--no-verify`, no automatic retry after unknown outcome, no historical receipt mutation, and no instruction capability.

Status: **TERMINATED_AT_BINDING_VALIDATION** — principal quote DEC-D4-20260921-01 已给且预检 9 项完成，但执行前绑定校验发现授权自身不可满足：
① 三操作绑定的 WP-BET-Y1Q4-T10-145 台账状态 `done`，任何公共接口（start / --parent-run / refresh-packet / mesh）都无法为其创建合法生产 run（fabrication 禁止）；
② 批准的 publication 路径 `docs/reports/…` 不在该 packet 的 write_surfaces 中，claim 精确子集校验必失败；
③ origin/main 的 clone-lifecycle.py fence 请求形态与 broker `issue-legacy-fence` 契约不匹配（且 broker 对 v2 clone identity 禁止 v1-allow observe receipt），fence 前置不可达。
按 runbook hard-stop「missing, mutated, or mismatched approval binding」终止。终审计量证明零状态变更：store sha256 与基线一致、sequence=1、0 fences/batches；graduation 复跑仍 `WP1_LIFECYCLE_EVIDENCE_INCOMPLETE`（lifecycle 缺口现已完整解释，AC-08 按草案条款保持 unproven）。修复需要：重开/新建含 docs/reports 写面的可绑定 bet、先落 fence-adapter 契约修复 PR、以及对 claims_authority.py:534 禁令的显式决策 —— 均需新的 principal 授权。

## Decision 5 — T10-172 governance reconciliation merged

Package: `t10-172-omo-gitlink-freshness-package`

```text
无需批准旧 T10-172 实现。origin/main f728b1f5... 已通过 PR #4094 使 projects/omo=d7feb927...；不要重复实现。后续只需按治理事务补齐 accepted binding、Ledger entry、retro、closeout 和 provenance。
```

This clears the two high CI alerts from `Submodule Freshness Gatekeeper` and
`Submodule Auto-Bump`. The child change is merged OMO PR #182; focused tests
passed `133` at exact target commit `d7feb927...` in a clean temporary clone.
Replayed at `d7feb927...`: focused tests `133 passed`.

Governance reconciliation proposal:
`2026-09-20-t10-172-pr4094-governance-reconciliation-proposal.md`
SHA-256 `0bbc51e5b56024f1048e62d359ec60b0c9642417607154cf61e4dc855b4d7e4f`.

Status: **merged** as PR [#4096](https://github.com/starlink-awaken/omostation/pull/4096)
with merge SHA `c033a210bbf11aa7644ffb434489d7d695c68b87`. Workflow closeout is
complete, locks are released, and the worktree is retired.

```text
批准 T10-172 PR #4094 governance reconciliation：从 f728b1f5... 创建唯一治理对账 PR；仅写 accepted Spec、T10-172 Ledger entry 和 retro 三个路径；accepted Spec SHA-256 必须保持 91e9364539def7eceaa34b2431e343a694c4fcd99098e90ea0cbdd61286ee6e8；不改 projects/omo、child repo、runtime、launchd、其他 BET 或 completion/value evidence；默认门禁拒绝即停止。
```

## Decision 6 — approve T10-173 promotion helper binding repair

Package: `t10-173-promotion-helper-binding-package`

```text
批准 T10-173 Draft Spec SHA-256 15d90aceb6231bfad7d1d4fef8dbc10fbc9d496176c80cbc8aff1e241791dada 转 accepted 并授权实施；创建 BET-Y1Q4-T10-173；仅修改 OMO promotion helper 的 standalone binding；使用隔离 child worktree、默认门禁、唯一 child PR；required checks 全绿后 merge；root gitlink bump 另立独立事务；不改 audit/mutation 语义、Claims 状态、runtime 或其他 gitlink。
```

This fixes a pre-existing standalone-import `NameError` found during T10-172
baseline comparison. It reproduces at both old and target OMO pins.
Replayed at `d7feb927...`: patch applies, patched import is safe, and broader
workflow regression is `320 passed`. The current uv environment did not
reproduce the original base-import failure, so that historical red evidence
remains unchanged and unresolved.
Expected accepted Spec SHA after the two authorized field flips: `4d2e333b565b77eb27395483c953ce3861e82df7c3ccb669ca608a7080c2cd6c`.

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


## Live sync log (consolidated)

| time (UTC) | key facts |
|---|---|
| 2026-09-20T12:43:37Z | Claims window healthy: `672/1440`, errors `0`, max gap `60.21s`; live projection on 43910 `/data.json` confirmed current. … |
| 2026-09-20T12:47:35Z | Claims window healthy: `676/1440`, errors `0`, max gap `60.21s`; projected window end `2026-09-21T01:31:06Z`. … |
| 2026-09-20T12:52:44Z | `omo state refresh` executed (dry-run first): canonical `system_health.yaml` (gitignored) refreshed, 6 services. Meta-doctor now `stale_beats=0`, hear … |
| 2026-09-20T12:55:32Z | Live gates CONFIRMED: projection `12:52:49Z` reports **A2 PASS, A5 PASS** — A1–A9, RF0, RC-DL all PASS. Launchd refresh tick had lagged; one standard  … |
| 2026-09-20T12:59:15Z | Dashboard refresh cadence measured unreliable: ticks `12:47:40Z` → `12:52:49Z`, then no projection by `13:01Z` despite StartInterval=300. Classified s … |

## Approval binding verification (2026-09-20T13:07Z)

All SHAs quoted in Decision 1/2 approvals verified against live package bytes: T10-170 spec `d52e3e1f…`, T10-171 spec `fe7bc286…`, restart runbook `d343e64e…`, collector patch `64275d2c…`, test patches `5987e531…`/`b99d91f4…`, live-server patch `c3a33ed2…` — **all MATCH**. Approvals are executable as written; no re-quote needed.
| 13:06Z–13:08Z | Brief-surfacing package delivered (proposal + anchored draft patch); projection 13:08:49Z all gates PASS; claims 698/1440. |
