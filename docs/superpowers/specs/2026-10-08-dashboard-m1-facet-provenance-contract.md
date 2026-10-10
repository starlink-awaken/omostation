---
schema: spec/v1
status: draft
lifecycle: design
owner: dashboard-convergence
version: 1.0.0
implementation_authorized: false
created_at: 2026-10-08T09:34:00Z
updated_at: 2026-10-08T09:42:00Z
---

# Dashboard M1 分面来源与新鲜度合同

## 1. 目的

Cockpit BFF 当前把七个 Panorama 分面标记为 `PARTIAL`。本合同把“投影中有字段”“字段有权威来源”“来源刚被观察”“底层业务事实成立”分开表达，避免空数据、数字零、快照租约或派生摘要被误读成健康、完整或实时。

产品入口仍为 Cockpit `/panorama`。本合同只定义服务端只读投影与质量状态；不授权部署、服务重启、投影发布、写操作、或通过未接受的 Zhixing operation 读取数据。

## 2. 当前分面与证据边界

| Facet | 当前 producer / 证据 | 允许表达 | 禁止推断 |
|---|---|---|---|
| `evolution` | `panorama-collect.py::collect_evolution()`；扫描 evolution proposal 文件名与数量 | 某次观察扫描到的文件数和最近名称 | 提案状态、审批、价值或是否已经采纳 |
| `workspace` | `collect_workspace_hygiene()`；`git worktree list --porcelain` 与 workflow lock 路径枚举 | 观察到的 worktree 与 lock 文件路径/数量 | “孤儿锁”“陈旧 worktree”或可安全清理结论；现有实现未验证这些语义 |
| `launchd_health` | `collect_launchd_health()`；登记的 active/installed launchd job 与 `launchctl print` | 单个登记任务的加载、状态、pid、最近退出码及检查结果 | 将读取错误一律解释为 unloaded；用投影 lease 替代 job 观察时间 |
| `agent_visibility` | `collect_agent_visibility(payload)`；由同一 `build_payload()` 中的 gates、workflows、agent-cell 与 claims 等输入派生 | 摘要属于哪个 projection generation，以及各输入自身的证据状态 | 将摘要新鲜等同 Agent 在线；将其中 `UNPROVABLE` 输入提升为已证明 |
| `posture` | 当前聚合投影不存在该字段；虽有 health KPI、gates、agent-cell 等邻近数据，但无统一公式或源契约 | `UNKNOWN` 与“未定义/未接线”原因 | 临时拼接 health、gate 通过率和 Agent 数量作为整体健康或合规分 |
| `guardian` | 当前投影无该字段；探针、health 心跳与 gates 是不同契约 | `UNKNOWN` 与“无 guardian producer”原因 | 由 gate 通过或探针正常推断 Guardian 在线/健康 |
| `topology` | 当前投影无该字段；`topology_engine` 有独立查询面，ASD overview 的 `health_green: true` 为硬编码值 | 在 DCP-20 获准前保持 `UNKNOWN` | 将硬编码 overview、submodule 清单或未授权查询当作有效拓扑/依赖健康 |

表中三个直接来源面已有 producer 函数，但目前 compact observation 尚未为它们存储本合同要求的 envelope 与摘要；“已有来源”不代表已符合 M1。`agent_visibility` 是第四个来源面，但由 projection generation 派生，遵循独立 envelope。字段存在不自动移除 facet 的 `partial_facets`。只有经验证的 source observation 满足本合同后，才可把对应事实显示为 LIVE；facet 内的单个结论仍可保持 UNKNOWN。

## 3. Observation envelope

三个直接读取的 facet（`evolution`、`workspace`、`launchd_health`）使用 `panorama-compact-observation/v1` 的向后兼容扩展，每条记录至少包含：

```json
{
  "observation_status": "OBSERVED | STALE | UNKNOWN",
  "observed_at": "RFC3339 UTC timestamp or null",
  "last_attempt_at": "RFC3339 UTC timestamp",
  "last_success_at": "RFC3339 UTC timestamp or null",
    "duration_ms": 0,
  "overrun": false,
  "error_class": null,
  "provenance": {
    "kind": "direct-read",
    "source_ref": "module::collector",
    "collector_sha256": "sha256 hex",
    "source_digest": "sha256 hex or null"
  },
  "value": {}
}
```

`observation_status` describes the collector attempt/last-good record. Cockpit separately derives a user-facing `facet_state` (`LIVE`, `PARTIAL`, `STALE`, `UNKNOWN`) and a semantic `verdict` (`PASS`, `DEGRADED`, `FAILED`, `UNKNOWN`) where the facet has a health meaning. Freshness and health are separate dimensions.

`agent_visibility` does not use the direct-observation envelope's timing fields. Its projection-derived record has `observation_status`, `observed_at`, `last_attempt_at`, and `last_success_at` equal to the enclosing `generation.generated_at`; `duration_ms=null` means no independently timed observation is available. Its provenance kind is `projection-derived`, with `source_ref=collect_agent_visibility` and the collector digest for that producer. Its `source_digest` covers the normalized derived `value`, and it must include the exact `source_generation_id` and `source_revision_id` bindings below. A generation older than 21,600 seconds is STALE even if its projection lease was renewed.

For an `OBSERVED` value, `source_digest` is mandatory and equals SHA-256 over the exact normalized `value` object encoded as UTF-8 canonical JSON (`ensure_ascii=false`, sorted keys, separators `,` and `:`, finite numbers only). For `evolution`, `value` is the normalized sorted list of observed proposal paths plus the collector-reported count, so `source_digest` is also the digest of that enumerated input set; no second input-set digest is implied. This digest binds the value to the observation envelope; it does not claim that source files were signed. `STALE` may retain the prior value and digest with the original observation time. `UNKNOWN` without a last-good value uses `value=null`, `observed_at=null`, and `source_digest=null`.

Use a fixed 300-second TTL for the three direct observations (`evolution`, `workspace`, `launchd_health`). Their M1 scheduled observation interval is 240 seconds, leaving a 60-second scheduling margin; the existing compact-observation job does not yet collect these facets. Projection-derived `agent_visibility` uses a 21,600-second TTL because its only producer is the full projection generation, currently refreshed every six hours. Its freshness means “current to this source generation”; it is never evidence that an Agent is online. Projection lease renewal does not refresh it. `overrun=true` does not extend any TTL. `OBSERVED` means the latest collection succeeded; a failed latest attempt with a last-good value is `STALE` observation status and yields BFF quality `PARTIAL` while that last-good observation is within its TTL, then `STALE` quality after expiry. With no last-good value it yields `UNKNOWN`. These rules make collection-attempt status distinct from value age.

For `launchd_health`, add `registry_sha256` beside `source_digest` in `provenance`; it is SHA-256 over the canonical normalized selected-job registry records before invoking `launchctl`. The envelope's `value` includes, for each selected job, its exact label, uid, command result class, parsed result, and observation time, so `source_digest` is recomputed over the complete per-job result. Both digests are required for an observed facet; a missing or malformed registry digest makes the facet UNKNOWN.

Only projection-derived `agent_visibility` has a `source_generation_id` and `source_revision_id`; both must equal the enclosing projection's `generation_id` and `state_revision`, and its `observed_at` must equal that generation's timestamp. Direct observations are sampled independently and must not be bound to an unrelated projection generation. Collector identity for the three direct-source facets is `source_ref` plus `collector_sha256`; projection-derived `agent_visibility` uses its distinct `source_ref` and producer `collector_sha256`. Each stored value includes the required `source_digest`.

Admission and state rules:

- `OBSERVED` requires a valid facet schema, successful collection, non-future `observed_at`, non-empty producer reference, collector digest, source digest matching the normalized value, and an observation within the facet TTL.
- A failed attempt preserves the previous value only as last-good data with its original `observed_at`; it never advances `last_success_at` or freshness.
- Missing, malformed, future-dated, digest-mismatched, generation-mismatched, or unsupported fields are `UNKNOWN`; expired direct observations are `STALE`.
- A facet is `LIVE` only when the latest collection succeeded and all required values and provenance are present and fresh. It is `PARTIAL` when at least one required value is known and usable but another is missing, stale, or unproven, or when a failed latest attempt has a still-within-TTL last-good value. It is `STALE` when it has last-good evidence but none of its required values are within TTL. It is `UNKNOWN` when no valid current or last-good evidence exists.
- Overall `data_state` precedence is: `UNKNOWN` on transport, identity, or schema validation failure; otherwise `STALE` when the aggregate projection has expired and no required facet has usable within-TTL evidence; otherwise `LIVE` only when the aggregate projection is fresh and every required facet is LIVE; in all other cases `PARTIAL`. Fresh direct facets remain individually LIVE when the aggregate projection is stale, but cannot make overall `data_state` LIVE.
- A service lease or HTTP 200 proves transport/revision availability only. It never renews a facet observation.
- Collection is read-only, bounded by per-facet timeout and total budget, single-flight, and atomically published. One collector failure cannot erase another facet's last-good value.

## 4. Facet-specific requirements

### 4.1 `evolution`

Bind to `collect_evolution()`, record the scan time, collector digest, and digest of the enumerated input set. Preserve the current limited meaning (proposal file enumeration). Do not infer proposal lifecycle or impact.

### 4.2 `workspace`

Bind to the worktree and lock-file enumeration. Rename or clarify `orphan_locks` as an observed lock-file list/count unless an independently verified orphan predicate is added. Preserve the distinction between enumeration and diagnosis; no cleanup action is in scope.

### 4.3 `launchd_health`

Record observation metadata per job, including registry digest, resolved launchd label, uid, command result class, and parsed fields. A successful `launchctl print` with a parseable loaded state is an observed job. A nonzero result is confirmed unloaded only when exit code is `113` and stderr contains both `Could not find service` and the exact requested launchd label; all other nonzero results, missing parse fields, and parse errors are UNKNOWN. The collector must preserve stdout and stderr as separate fields for this command rather than using the shared `run()` helper's `stdout or stderr` combined value. On the supported macOS runtime, record a fixture from a deliberately nonexistent test label showing exit 113 and the exact stderr predicate; do not probe by unloading a real registered job. A nonzero last exit from a successfully loaded job is a semantic `FAILED` verdict, not a freshness failure. No selected jobs yields facet `UNKNOWN` with `no_registered_jobs`; some known and some unknown jobs yields `PARTIAL`; all selected jobs unknown yields `UNKNOWN`; all jobs observed yields `LIVE` quality with an independent PASS/DEGRADED/FAILED verdict.

### 4.4 `agent_visibility`

Treat as a projection-derived view, not an independent live collector. Bind it to the exact source `generation_id`/revision and producer digest. `source_digest` is the canonical digest of the normalized derived object. Preserve each input facet's status and provenance. A generation mismatch makes the facet UNKNOWN. The derived view may be current to its generation while still PARTIAL or UNPROVABLE; it cannot upgrade input evidence or claim Agent liveness.

### 4.5 `posture`, `guardian`, `topology`

Keep these fields explicitly UNKNOWN and avoid numeric-zero or empty-success defaults. Their producers, schemas, formulas, ownership, and TTLs require a separately reviewed contract. `topology` remains unavailable until DCP-20's exact accepted specification authorizes the required read operations and the producer is proven read-only. No substitute source is admitted by this document.

## 5. Cockpit BFF and UI behavior

- BFF returns explicit `facet_state`, `observation_status`, and (where applicable) semantic `verdict`, plus observed time, producer/source, source digest, and reason codes. The state mapping in §3 applies consistently to the API and page.
- Full and compact projection paths must both verify that the artifact's source revision exactly equals `/health.state_revision`; the full artifact must also bind any generation-derived field to that same artifact generation. A gate is `LIVE` only when its own producer reference, source revision, and observed time are present and match the bound artifact. Without that field evidence, preserve its identity/detail but return `verdict=UNKNOWN` and `live=false`.
- The page shows unavailable metrics as `—`/`UNKNOWN`, never as zero or a healthy empty collection.
- The UI parser must accept a structurally valid `PARTIAL` payload when unsupported facets are null, keep independently evidenced gates/alerts visible, and preserve each facet's UNKNOWN/STALE reason. It must not reject the whole payload and fall back to synthetic zeros/offline/empty arrays.
- A facet may be LIVE only when its required value schema and provenance are complete and fresh. A fresh aggregate snapshot cannot make missing field provenance LIVE.
- Overall status follows §3 precedence; the UI must not relabel `STALE`/`UNKNOWN` as `PARTIAL` or green. No gate, compliance claim, or business outcome is promoted from these facets.
- The UI presents the difference between transport health, source freshness, data completeness, and semantic verification in the facet detail view.

## 6. Verification and acceptance

Implementation must add isolated fixtures proving:

1. The three direct-source facets (`evolution`, `workspace`, `launchd_health`) retain `source_ref`, `collector_sha256`, a recomputable `source_digest`, observed time, and measured duration. Projection-derived `agent_visibility` retains its producer identity, recomputable `source_digest`, observation time equal to `generated_at`, `duration_ms=null`, and exact generation/revision binding to the enclosing projection.
2. Missing/invalid/future timestamps, digest mismatch, collector failure, and stale last-good data yield UNKNOWN/STALE/PARTIAL as specified and never green.
3. Workspace lock enumeration does not label a lock orphaned without a verified predicate.
4. Launchd fixtures cover exit 0/parseable loaded state, exit 113 with the exact missing-service markers/label, other nonzero errors, empty registry, all unknown jobs, mixed known/unknown jobs, and known failed last-exit verdicts. The expected observation/facet state and semantic verdict must match §4.3.
5. `agent_visibility` preserves input statuses and does not claim Agent liveness from generated time.
6. The three undefined facets render UNKNOWN and do not expose placeholder zeros or empty arrays as complete results.
7. No test calls a production mutation route, writes outside its temporary root, refreshes the live projection, or restarts a service.
8. Full projection revision mismatch and missing gate provenance fail closed; the UI keeps independently evidenced data while rendering unknown facets without synthetic values.

Operational acceptance requires four consecutive scheduled direct-observation cycles, with no failed write or false freshness advance. Collect at least 100 sequential samples each for `/api/health` and `/api/governance/panorama`, over at least 30 minutes, and require BFF p95 below 2 seconds as set by the execution plan; report p50, p95, maximum, sample count, and failures. Do not require overall `data_state=LIVE`: the three facets without producers must remain UNKNOWN, and the projection-derived agent view cannot promote overall health. The real-browser check on the managed `8090/panorama` entry must inspect the global status and each of the seven facet details, including source/time/reason, and verify source-backed LIVE direct observations plus fixture-driven STALE/UNKNOWN/partial-job states and an expired `agent_visibility` generation. Capture DOM assertions, console/network errors, and screenshots without credentials or private values. Passing unit tests or measuring only the page shell does not close M1.

## 7. Sequencing and gates

1. Independently review and accept this exact specification digest; register a dedicated M1 BET and bind its write surfaces before implementation.
2. Before M0, only isolated fixture/contract work is allowed after BET claim; do not connect it to live services or claim M1 acceptance. M1 integrated operation and acceptance follows the plan's M0 milestone.
3. Implement observation metadata for `evolution`, `workspace`, and `launchd_health`; bind `agent_visibility` to the source generation with subordinate evidence preserved, and correct unknown-value presentation for all seven facets.
4. Define and separately review the producer contracts for `posture`, `guardian`, and `topology`; topology implementation also requires exact DCP-20 spec acceptance and read-only operation proof.
5. M1 evidence is not production release authorization. Any production release or projection refresh requires M0 complete, G0 satisfied, clean code identity, workflow authorization, and independent verification. Topology remains closed until DCP-20 is accepted and its read-only operation proof passes.

No step in this specification authorizes altering existing Workflow Runs/Locks, bypassing a gate, or claiming the Dashboard/whitepaper complete.
