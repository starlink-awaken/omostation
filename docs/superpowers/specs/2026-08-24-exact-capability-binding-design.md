---
schema_version: specification/v1
spec_version: 1.1.2
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-24
last-reviewed: 2026-08-26
bet_id: BET-Y1Q3-T1-12
risk_level: L2
human_gate: false
type: ssot
last_updated: 2026-09-03
---

# Wave B Exact Capability Binding 设计

## 1. 目的

把当前彼此分离的四条强能力链收敛为一个可执行、可重放、可拒绝的默认路径：

```text
accepted Spec
  → BET / WorkPacket v2
  → exact capability requirements
  → find / inspect / load
  → admission / assignment / dispatch
  → native execution receipt
  → independent verification
```

本设计只解决工程执行面能力绑定，不把供给侧工程事件、PR、测试、Agent 自评或 maturity 分数提升为个人价值。
Golden Slice、Human Verdict、principal-bound decision_outcome 与连续价值观测属于后续独立 Wave。

## 2. 当前事实

### 2.1 已存在并复用

1. `bin/agent-workflow.py` 已在 start 时绑定 `bet_id`、`spec_binding`、`instruction_binding`、
   `work_packet` 与 `work_packet_hash`；Spec/Instruction drift 会 fail-closed。
2. `bin/capability-sync.py` 已有单一 generated projection、exact ID resolution、ambiguous/not-found
   拒绝、native inspection 和 Agora gateway load/invoke。
3. `lib/capability_trace_binding.py` 已定义八字段因果信封：correlation、workflow run、packet、
   packet hash、assignment、dispatch、actor、delivery attempt。
4. `lib/capability_native_execution_receipt.py` 已有 material、marker、completed receipt、cleanup、
   replay 与 value firewall 的纯函数合同。
5. OMO 已有 accepted Spec 校验、worker admission、required capability matching、health/approval gate、
   policy digest、request identity、Workflow Mesh 与 worker ACK。

### 2.2 尚未闭合

1. WorkPacket/agent-workflow 没有把任务所需 exact native capability IDs 编译为默认执行约束。
2. skill/workflow 可以 exact inspect，但未与 MCP/BOS 共用统一 find/load 消费链。
3. `capability-sync load/invoke` 不强制 trace binding；Cockpit BOS invoke 不透传 binding。
4. B4-D execution receipt 只有库与测试，没有生产消费者。
5. OMO `StepDispatched` 前没有重新核对持久化 admitted state、admission id 与 policy digest。
6. Cockpit KEMS 裸 dispatch 已 fail-closed 但成为死入口；agent-runtime、runtime registry 和候选
   AGE-v2 Agent Cell 仍可能成为平行派工面。

### 2.3 Phase8 root bypass 事实（2026-08-25 scope amendment 1.1.1）

1. Cockpit 子仓 PR #78（分支 `codex/t1-12-cockpit-parallel-entry-retire-20260825`，
   source head `43dbf115db0fece980d3ffe2d8339e4fbc1b5b59`，child main merge
   `82dddbc926cc4377808fe530bf135f08213cd213`，2026-08-25）已删除
   `cockpit/commands/daemon.py` 并退役 `_subcommands.py`、`cli.py`、`commands/governance.py`、
   `tui/swarm_collector.py` 中的未绑定入口面，以 `test_parallel_entrypoints_retired.py` 锁定。
2. ~~根仓 main 的 `bin/omostation` 仍暴露 `daemon` / `watchdog` / `scenario` / `top` / `run <module>` 五条旁路命令~~ → **已完成 (PR #2260 / ADR-0428)**。`bin/omostation` 已退役，root wrapper bypass commands 全部移除。统一人类入口收敛至 `cockpit`。
3. `bin/gac/daemon-watchdog.py` 的自愈路径 `restart_daemon()` 同样 import child 已删除的 `cockpit.commands.daemon.restart_daemon_service`，且以 zero-human-intervention 方式直接重启服务，绕过 admission 与 capability receipt。 → **已处理**：相关旁路入口随 `bin/omostation` 一并移除。
4. `bin/ssot/real-scenario-runner.py` 直接向 Agora Bus 发布 A2A 事件并写 resident decision 提案，不经 accepted WorkPacket、admission 或 trace binding。 → **已处理**：该脚本不再作为 root wrapper 旁路暴露。
5. 上述两脚本仍登记为 `script-registry/v1` 条目... → **待 follow-up**：registry truth 条目需同步更新 `maturity` 状态（当前仍为 `draft`）。
6. 截至 2026-08-25，根仓 gitlink 仍指向 `d8af11c2`（child main 为 `82dddbc9`），root 尚未跟进 child 的入口退役，形成 child-first/root-follow-up 缺口。 → **已解决**：PR #2260 已同步更新 cockpit 子模块指针并合并入 main。

### 2.4 Task 6B canonical consumer 事实（2026-08-26 scope amendment 1.1.2）

1. 根仓 `a0d0648555c447f985d4b3fc161e08fa3e9e8306` 与后续 `a9ed961a4585fb713a44003006da3bc94b4244eb`
   的 Cockpit gitlink 均为 `e60d068a0cd88a1abfd012f1ce8fb6c725732200`；Cockpit child `origin/main`
   已为 `a271a0d39e5bb59aff54aa56970b00b170d9cf42`，且前者是后者祖先。此前基于 `a271a0d`
   的审议不能冒充 root pointer 已完成集成，Task 6B 必须从 child main 实施，再由 root follow-up 前进 gitlink。
2. `a271a0d` 已让 BOS forwarder 接受完整五字段 bundle、KEMS dispatch 返回 410，并给 HTTP/MCP
   增加 presence gate；但 canonical parser 尚未声明五个 flags，KEMS 仍在 410 前读取 body，HTTP/MCP
   把任意非空 mapping 当作已验证 binding，MCP `chat` 没有 gate。
3. 根仓 `native-execution-material/v1` 已冻结完整 trace、exact capability、inspection、operation、
   request digest 与 admission projection；不得为 Task 6B 添加平行 material schema。
4. OMO `WorkflowMeshStore` 已能只读投影 `WorkflowAdmitted`、StepRun 与 worker context；
   `WorkflowAdmitted.proof` 覆盖 admission grant（含 `policy_digest`），是 verifier 必须复用的持久化权威。
5. Orca run `run_0d064c36fd0d` 的 Task 6B 与 stale-PR 双审计支持受限 C-lite；BDSK live 调用仍为
   `NOT_PROVEN / compute_unavailable`，不得把它写成 board consensus 或执行授权。

## 3. 自举授权证据

```text
waiver: user-explicit
when: 2026-08-24T12:34:56Z
who: xiamingxing
quote: "本次 Wave B Exact Capability Binding 自举跳过 workflow start，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限 docs/superpowers/specs/2026-08-24-exact-capability-binding-design.md 与 docs/plans/3y-bet-ledger.yaml 中新增 BET-Y1Q3-T1-12 条目，并把本句写入 waiver 证据。"
scope: docs/superpowers/specs/2026-08-24-exact-capability-binding-design.md; docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T1-12
reason: start --bet requires an already-existing accepted Spec and BET, creating a self-bootstrap cycle
risk: these two files have no workflow run or claims during bootstrap
residual: every implementation file, test, submodule and closeout must use the new BET run and claims
gate_bypass: 1
no-run-id: true
```

该 waiver 不适用于任何实现文件、测试、子模块、运行态、PR 合并或其他 BET；constitution waiver 也不能复用。

## 4. 方案比较

### 方案 A：只在 workflow start 检查 capability

拒绝。start 时真实 worker、assignment、dispatch、health 与 admission 尚不存在；该门既无法验证真实执行身份，
也覆盖不了 Cockpit、Runtime 或 Agent Cell 的带外入口。

### 方案 B：start 声明与预检，dispatch 用真实 identity/receipt 再验证

采用。start 绑定 exact requirements 与 WorkPacket；dispatch 使用真实 assignment/dispatch identity 构造
trace、inspection、admission 和 execution receipts。所有入口复用既有 registry、digest、Workflow Mesh 与
gateway，不新增调度器或状态库。

### 方案 C：新增中央 capability broker/registry

拒绝。会形成新的权威、调度和运行状态面，与现有 generated registry、Agora gateway、OMO admission 和
WorkPacket 并列，增加跨仓漂移与维护成本。

## 5. 核心合同

### 5.1 CapabilityRequirement

任务侧必须声明有序、去重的 exact requirements。每项包含：

```yaml
capability_id: "skill:git-discipline"
operation: "load"
effect: "read_only"
```

合法 kind/operation：

| Kind | find/inspect | load | invoke |
|---|---:|---:|---:|
| `skill:<name>` | 必须 | 必须 | 禁止 |
| `workflow:<id>` | 必须 | 必须 | 仅由 workflow-controller |
| `mcp-server:<id>` | 必须 | 必须 | 禁止 |
| `mcp-tool:<server>:<tool>` | 必须 | 必须 | 仅由 mcp-pep |
| `bos-service:bos://...` | 必须 | 必须 | 仅由 bos-pep |

禁止 query first-match、通配符、未证明的 legacy invoke string 和调用方自报 adapter。

### 5.2 Start binding

`agent-workflow start` 必须：

1. 从 accepted BET/WorkPacket 取得 exact requirements；
2. 对每项执行 deterministic find/inspect；
3. 保存 capability ID、operation、source digest、inspection receipt digest 与 requirements digest；
4. 把这些字段加入 run delivery identity，并随 parent/child run 精确继承；
5. 缺失、歧义、重复 authority、source drift 或不支持 operation 时，在写 run/lock/ledger 前拒绝。

start receipt 只证明声明和源码，不声称 invoked/evidenced/independently_verified。

### 5.3 Dispatch binding

dispatch 必须使用真实八字段 trace binding，不接受调用方缩减字段：

```text
correlation_id
workflow_run_id
packet_id
packet_hash
assignment_id
dispatch_id
actor_id
delivery_attempt_id
```

dispatch 前重新验证：

- WorkPacket hash 与 run/assignment/dispatch 一致；
- capability requirements digest 与 start 记录一致；
- native source/inspection digest 未漂移；
- persisted run 为 admitted；
- admission id 与 policy digest 等于 WorkflowAdmitted 事件；
- worker capabilities 覆盖要求，health/approval/lease 仍有效。

### 5.4 Load/invoke 与执行回执

`capability-sync invoke` 必须接收并验证 binding；缺失时非零退出且 provider/router 调用次数为 0。
`load` 对传入的 binding 同样校验；任务驱动生产路径必须传入 binding。

执行产生 `native-execution-receipt/v1`：

- material 内嵌 binding、capability、inspection、admission、operation 与 request digest；
- invocation id 从完整 material 派生；
- durable marker 先于 effect；
- uncertain transport 不重放 effect；
- confirmed/failed 都有 cleanup proof；
- fallback.used 恒为 false；
- `value_indicator_policy=false`，不得出现 human verdict、decision outcome 或个人价值字段。

### 5.5 入口收敛

1. Cockpit BOS invoke 必须透传 binding 与 receipt，不构造第二套 identity。
2. Cockpit KEMS 裸 `dispatch_task` 改走 admission-bound 路径，或在无消费者时显式下线。
3. agent-runtime 与 runtime registry 在未接入本门前保持 isolated/non-authoritative，不允许注册为生产派工入口。
4. AGE-v2 Agent Cell 在合并前必须把 `cell_execute/cell_govern` 等路径接到同一 WorkPacket、admission、
   capability receipt 与 OMO dispatch identity；否则 defer。
5. 根仓统一 wrapper（`bin/omostation`）必须 compatibility-only：`daemon`、`watchdog`、
   `scenario`、`top` 与任意 `run <module>` 直通执行五类入口退休，直到对应能力被 Mesh-bound
   （accepted WorkPacket + OMO admission + capability receipt + dispatch identity）；wrapper
   只保留对已收敛入口的透传，不成为第四条执行面或新调度面。退役命令必须非零退出、零写入、
   零 provider/router/gateway 调用；拒绝路径只允许无副作用的标准库与 `env_resolver` 初始化，
   必须在任何项目专用 import、subprocess、provider/router/gateway 调用或文件写入之前退出。

### 5.6 Task 6B C-lite admission verifier

Task 6B 不新增 OMO query service、Cockpit admission cache 或第二 validator。唯一新能力是根仓
`capability-sync verify-material` 的一次性只读进程：从 bounded stdin 读取一个 exact JSON envelope，
调用既有纯函数验证 `native-execution-material/v1`，再只读比较 OMO Workflow Mesh snapshot。

Envelope 必须且只能包含：

```yaml
schema: capability-admission-verification-request/v1
material: <native-execution-material/v1>
request: <bounded canonical request projection>
expected:
  capability_id: <exact mcp-tool or bos-service id>
  operation_id: <exact endpoint operation id>
  effect_classification: read_only|effectful
```

Verifier 必须在任何 provider/router/gateway 调用前完成以下检查：

1. material 的 trace、capability、inspection、operation、request、admission、authorization 与 value
   firewall 通过现有 validator；`canonical_digest(request) == material.request_digest`；`expected`
   三字段与 material 完全一致。
2. snapshot 的 run 等于 `binding.workflow_run_id`；admission id、packet id/hash 与 binding/material 一致；
   `material.admission.receipt_digest == "sha256:" + WorkflowAdmitted.proof`，从而把既有 material
   间接绑定到包含 `policy_digest` 的原始 admission grant，不修改 frozen material schema。
3. `step_run_id` 属于 admitted StepRun；effectful 路径只接受 `dispatched|running`，要求 bound worker，
   并逐字段匹配 dispatch/worker/step/admission/packet；read-only 路径可接受 `admitted|dispatched|running`。
4. admission 未过期，snapshot 非 terminal/cancelled/unknown；任何缺失、歧义、跨 run、伪造、过期、
   wrong operation/effect/capability、request drift 或 worker mismatch 均非零退出。

成功只返回脱敏 `capability-admission-verification-receipt/v1`：verified 状态、material/admission digest、
exact capability/operation/effect 与 `authority=omo-workflow-mesh`。失败只返回稳定 failure code；两者都不得
回显 request、绝对路径、事件正文或底层错误，不得写 marker/Mesh/registry/cache，不得启动 subprocess、
provider、router 或 gateway。

Cockpit 只通过一个共享 fixed-argv subprocess adapter 调用该 verifier，HTTP 与 MCP 不复制验证规则、
不注入 root `lib/`。`/run-task`、HTTP chat tools、MCP `run_task` 与 MCP `chat` 必须在构造 runtime、
tool schemas 或执行 tool call 之前得到 verified receipt；verifier 缺失/不可用即 fail-closed。
无 verified receipt 的 chat 只能返回 `authority_state=non_authoritative` 且 tools 为空。
canonical BOS parser 必须暴露五个既有 bundle flags；KEMS 410 必须在 body read 前返回。

## 6. 数据流

```mermaid
sequenceDiagram
    participant S as Accepted Spec/BET
    participant W as Agent Workflow
    participant C as Capability Sync
    participant O as OMO Admission
    participant G as Agora Gateway
    participant R as Receipt/Verifier

    S->>W: WorkPacket + exact requirements
    W->>C: find/inspect exact IDs
    C-->>W: source + inspection digests
    W->>O: run/packet/requirements identity
    O->>O: persist WorkflowAdmitted
    O->>C: real assignment/dispatch binding
    C->>G: load/invoke after binding validation
    G-->>C: gateway result + action receipt
    C-->>R: native execution receipt + cleanup proof
    R->>R: replay, digest, scope and admission verification
```

## 7. 实施波次与跨仓顺序

### Wave A：Root contract 与 B4 消费

1. WorkPacket/ledger projection增加 exact requirements；
2. `capability-sync` 对 skill/workflow/MCP/BOS 完成 exact find/inspect/load 语义；
3. invoke mandatory binding；
4. B4-D receipt 接入生产路径；
5. root negative tests 与 replay tests 全绿。

### Wave B：OMO dispatch integrity

1. admitted state/admission id/policy digest 回验；
2. 删除不可达 legacy 空 capability grant；
3. worker/mesh/compensation 回归；
4. OMO 子仓先独立 PR、CI、merge、tag。

### Wave C：Cockpit/Agora consumer

1. 先在 root 合入 `capability-sync verify-material` 与 zero-call negative tests；该动作只读且不改变 gitlink；
2. Cockpit 从 child `origin/main` 实施一个共享 subprocess adapter、BOS 五 flags、KEMS body-unread 410、
   HTTP/MCP/chat pre-effect gates 与七类负例；
3. Agora 已在 child main 透传 `binding_digest`，本 slice 默认不修改；只有新证据证明 carrier 字段缺失才重审；
4. Cockpit child commit/tag/PR/CI/merge 后，root 才把 `projects/cockpit` 前进到包含该 merge 的可达 main SHA。

### Wave D：生产拓扑 canary

使用一个低风险、无外发、可撤销的真实任务：

1. canonical Spec/BET/WorkPacket start；
2. exact skill + workflow + MCP/BOS capability load；
3. one admitted dispatch；
4. one confirmed read-only invocation；
5. replay receipt；
6. wrong digest、missing binding、wrong admission、ambiguous selector、uncertain transport 五类负例；
7. rollback/cleanup 与 clone lifecycle receipt。

### Wave E：Phase8 root recovery（scope amendment 1.1.1）

排序契约为 child-first / root-follow-up，任何一步不得倒置：

1. child main 先行：Cockpit PR #78（`43dbf115` → merge `82dddbc9`）已退役 unbound
   entrypoints，是既成事实；root 不得在其前重写、复刻或重新暴露这些入口；
2. root gitlink 跟进：仅在 child main merge SHA 可达后前进根仓 pointer；
3. root wrapper 收敛：与 pointer 前进同一批或紧随其后的 root 变更里，把 `bin/omostation`
   的 `daemon` / `watchdog` / `scenario` / `top` / `run` 五条旁路命令全部退休为
   compatibility-only（§5.5.5），同步退役 `bin/gac/daemon-watchdog.py` 与
   `bin/ssot/real-scenario-runner.py` 的执行面，将两个 `maturity: draft` registry 条目
   转为 schema-valid `maturity: deprecated`，并同步文档投影（CLI-REFERENCE / INDEX-MCP /
   capability-registry）；
4. 每步配 negative no-write 测试：被退役命令非零退出、零文件写入、provider/router/gateway 调用为 0，
   且不产生 human verdict、decision outcome 或个人价值字段（value firewall）；
5. host LaunchAgent 清理不属于 Task8 repo write 或 code-PR completion prerequisite，必须作为
   独立的 governed post-merge ops follow-up 执行；目标为 service
   `com.omostation.agora.daemon` 与 plist
   `~/Library/LaunchAgents/com.omostation.agora.daemon.plist`，先只读采集
   `launchctl list com.omostation.agora.daemon` 和 `lsof -nP -iTCP:7432 -sTCP:LISTEN`，不得在
   Task8 执行 unload/bootout、rm、kill 或其他 mutation；在该 follow-up 单独执行前，T1
   operational cleanup 保持 pending，避免半退役状态下服务自拉起。

## 8. Rollout

新门禁遵循三段式：

1. `shadow`：记录现有 production path 中缺 binding、空 capability、旁路入口；不阻断既有流量；
2. `warning`：对新 WorkPacket/Agent Cell 入口报警，并给出 exact remediation；
3. `fail`：存量清零且 canary 通过后，生产入口默认拒绝无 binding 调用。

不新增独立 shadow daemon、数据库或 workflow；使用既有 run/mesh/receipt 和 gate reporting。

## 9. 验收标准

1. accepted Spec、BET、WorkPacket hash、run 与 claims 可重复读取且完全一致。
2. skill/workflow/MCP/BOS exact ID 均可 find/inspect/load；歧义和 first-match 执行被拒绝。
3. invoke 缺/错 binding 时 provider 调用为 0，CLI 非零退出且回执脱敏。
4. B4-D execution receipt 至少有一个真实生产消费者，marker/replay/uncertain/cleanup 负例全绿。
5. Cockpit/Agora 不丢失 binding/receipt digest，不构造第二 identity。
6. OMO 在 StepDispatched 前回验 persisted admission，伪造 grant 或跨 run admission 被拒绝且零副作用。
7. legacy 空 capability grant 与 KEMS 裸派工路径被删除、接线或显式下线。
8. agent-runtime HTTP/MCP/chat 的 effectful 路径只有在 `verify-material` 返回 verified receipt 后才构造
   runtime/tool schemas；missing、empty、malformed、wrong digest、wrong operation/effect、untrusted、
   non-admitted 与 verifier unavailable 均证明 runtime/tool/provider 调用为 0。
9. root、OMO、Cockpit、Agora targeted tests、cross-repo negative tests、GaC、SSOT、reachability 与
   production-topology canary 全绿。
10. 子仓 commit/tag/PR/CI/merge 后才更新根仓 gitlink；所有 writer clone 由 lifecycle receipt 退役。
11. 每 2–3 个 PR 或一次跨仓 wave 后重放全增量纠偏，不让并行分支改变主线优先级。
12. `bin/omostation` 的 `daemon`/`watchdog`/`scenario`/`top`/`run` 五条旁路被退休为非零退出的
    compatibility-only 拒绝路径；退役命令零写入、零 provider/router/gateway 调用，script registry
    条目由 `maturity: draft` 转为 schema-valid `maturity: deprecated`，capability projection
    不再把它们列为可用能力；`com.omostation.agora.daemon` 的 LaunchAgent cleanup 属于独立
    post-merge ops follow-up，在单独执行前 operational cleanup 保持 pending。

## 10. 反指标

本 BET 不以以下项目作为成功：

- maturity score、ADR 数、雷达轴数、BET done 数；
- PR、测试、Token、Agent、MCP 或 capability 数量；
- fixture-only、静态 schema、文件存在或 worker 自报完成；
- agent 自动生成的 verdict、估算节省时长或 synthetic decision_outcome；
- daemon/list/health 存在但没有 per-operation receipt。

## 11. 回滚与断路器

立即停止并重新审议的条件：

- 需要新 registry writer、scheduler、database 或第二 dispatch truth；
- 必须放宽 WorkPacket、Spec、claim、author、admission 或 receipt digest 校验；
- 需要自动外发、自动 Human Verdict 或把执行回执提升为个人价值；
- 子仓 main 不可达、gitlink rewind、无法保留旧消费者兼容窗口；
- production canary 只能由 fixture/synthetic 数据替代。
- verifier 需要写 OMO/Mesh/marker/cache、启动 provider/router/gateway/第二 subprocess，或从 Cockpit 复制
  root validation rules；
- effectful positive path 无法逐字段绑定 persisted admission、StepRun 与 worker context，或任一负例无法
  证明 runtime/tool/provider 调用为 0。

回滚以单仓 PR revert 为单位；append-only mesh/receipt 不做数据迁移，错误新入口直接恢复 isolated 状态。

## 12. Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|---|---|---|
| 1 | start-only / start+dispatch / new broker | start+dispatch | 真实身份在 dispatch 才完整，且不新增权威 |
| 2 | worker capability labels / native asset receipts | 两层都保留并显式区分 | 二者语义不同，不能同名冒充完成 |
| 3 | one giant cross-repo PR / staged PRs | staged PRs | 保持 child-first reachability，降低 main 红窗 |
| 4 | hard fail immediately / shadow-warning-fail | 三段式 | 新门禁先测存量，不用治理误伤锁死主干 |
| 5 | industrial threat model / bounded personal-system model | bounded model | 复用现有 digest/admission，不新增重型密码学与平台 |
| 6 | root wrapper 保留 `top`/`run` 兼容 / compatibility-only 收敛 | compatibility-only | PR #78 后 child main 无 `daemon_cli` 且从未有 `swarm_dashboard`，root 幽灵 import 无法恢复；Mesh-bound 前不允许第四条执行面 |
| 7 | Cockpit-local validator / frozen material v2 / root C-lite verifier | root C-lite verifier | 复用 material v1 与 OMO proof，避免第二规则面和无必要 schema 分叉 |
