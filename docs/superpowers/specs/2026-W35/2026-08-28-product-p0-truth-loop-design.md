---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last_updated: 2026-08-28
bet_id: BET-Y1Q3-T4-02
risk_level: L3
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Product P0 Truth Loop 总体设计

## 1. 决策与目标

本设计把六个已经直接证明的 Product P0 缺口收敛为一条不自欺的个人数字分身真值链：

```text
honest Scene gate
  + authority-bound principal
  -> admitted execution with durable effect receipt
  -> leased/idempotent event outbox publication
  -> real human adjudication
  -> durable decision_outcome
  -> principal-bound value observation
  + independently measured physical recovery
```

目标是让每一个“成功”都有可重放、可拒绝、可回滚的直接证据，而不是继续用命令退出码、测试数、PR、Agent 自报或模拟回执替代真实产品结果。

## 2. 现状反证

当前主线同时存在六个不可接受的反例：

1. `make scene-card-check` 统计 blockers 后仍因最后一条 `echo` 返回成功。
2. `projects/omo/src/omo/resident/executor.py` 对多个 effectful action 返回固定 `ok: true`，却没有真实效果和持久回执。
3. event ledger 只有 outbox 存储和手工 mark，没有唯一的 lease/retry/backoff publisher。
4. `principal:alice` 只通过格式检查和 fixture，未绑定真实 credential/membership authority。
5. 可关联的非测试 human adjudication 和 qualifying `decision_outcome` 没有直接证据。
6. physical recovery 仅是 dry-run 计划，没有真实隔离恢复、完整性和重放测量。

任一反例仍存在时，父 BET 不得进入 `done`，价值轴不得超过 `NOT_PROVEN`。

## 3. Canonical 建模：一个父 BET，六个 child BET/WorkPacket

现有 `bin/plan/bet-ledger.py` 强制每个 BET 恰好一个 `accepted_specifications` binding，并把一个 BET 编译为一个 `WP-{BET-ID}`。它没有一个 BET 下的 canonical child-packet identity。因此使用下列映射，不扩展台账 schema，不新增 registry 或第二工作流引擎：

| 角色 | BET | Canonical WorkPacket | 责任 |
|---|---|---|---|
| Parent | `BET-Y1Q3-T4-02` | `WP-BET-Y1Q3-T4-02` | 六包编排、全链验收和 root-last 收口 |
| WP1 | `BET-Y1Q3-T4-03` | `WP-BET-Y1Q3-T4-03` | honest Scene Card gate |
| WP4 | `BET-Y1Q3-T4-04` | `WP-BET-Y1Q3-T4-04` | principal authority binding |
| WP2 | `BET-Y1Q3-T4-05` | `WP-BET-Y1Q3-T4-05` | Agent Cell effect receipt |
| WP3 | `BET-Y1Q3-T4-06` | `WP-BET-Y1Q3-T4-06` | canonical outbox publisher |
| WP5 | `BET-Y1Q3-T4-07` | `WP-BET-Y1Q3-T4-07` | human adjudication to value |
| WP6 | `BET-Y1Q3-T4-08` | `WP-BET-Y1Q3-T4-08` | physical recovery drill |

父 BET 只是编排、canonical completion-policy 前置修正和集成锚点，不复制 child 运行状态，不写第二份 value truth。每个 child 都有自己的 Spec、workflow run、write surfaces、PR、验收证据和 rollback。

### 3.1 Value-exempt completion 前置合同

当前 completion matrix 只有在 engineering=`VERIFIED`、operational=`PROVEN`、value=`ACCEPTED` 时才能推导 `outcome_accepted`并把 BET 标记为 `done`。如果直接把这条规则用于 WP1/WP2/WP3/WP4/WP6，就会迫使纯工程/运行包伪造个人价值，或让 child `depends_on` 永久无法解锁。

因此父 BET 在 Wave A 前必须先对现有 `bin/plan/bet-ledger.py` 做最小合同扩展：

- 未声明 `value_indicator_policy` 的历史 BET 默认保持现有 value-required 语义。
- `value_indicator_policy=false` 的 BET 必须保持 value=`NOT_PROVEN`；当 engineering=`VERIFIED` 且 operational=`PROVEN` 时，overall 推导为 `delivery_accepted`。
- `delivery_accepted` 可以让这类非价值 BET 进入 `done`，但不能产生、复制或提升价值证据。
- `value_indicator_policy=true` 继续使用现有 `outcome_accepted` 规则和 credential-bound human attestation。
- 本扩展只修改现有 canonical ledger validator/complete command 及其测试，不新增 schema file、registry、writer 或状态库。

这个前置合同未通过 RED/GREEN 和独立审查前，Wave A 不得启动。

## 4. 依赖与并行波次

```text
Wave A
  T4-03 / WP1 ──────────────────────────────┐
  T4-04 / WP4 principal authority ─┐         │
                                      v         │
Wave B                             T4-05 / WP2  │
                                      │         │
                                      v         │
                                   T4-06 / WP3  │
                                      │         │
                           ┌──────────┴──────┐  │
                           v                 v  v
Wave C                  T4-07 / WP5       T4-08 / WP6

Parent T4-02 holds the integration done_when for T4-03 through T4-08.
```

硬约束：

- Wave A 是 `T4-03 + T4-04`，两者可并行。
- `T4-05` 依赖 `T4-04`；先证明 principal authority，再允许 effectful execution。
- `T4-06` 依赖 `T4-05`；publisher 只消费已有真实效果回执的 canonical ledger 事件。
- `T4-07` 依赖 `T4-03`、`T4-04`、`T4-06`。
- `T4-08` 依赖 `T4-06`，以便恢复后对 durable event/outbox 做 replay 验证。
- 父 `T4-02` 的 ledger `depends_on` 保持为空，以便先实施 value-exempt completion 前置合同；它的 `done_when` 和 verify 必须拒绝任一 child 未 `done` 的完成请求。
- 每波最多两个 writer；coordinator 只做策略、范围冻结、验收、PR 与清理。
- 并行 writer 只能持有互不重叠的实现写面；`docs/plans/3y-bet-ledger.yaml`、root gitlink、completion evidence 和 retro 的最终变更由 coordinator 按 child 顺序串行写入。
- Wave B 属于同一交付波次但不同时写 OMO：WP2 的 receipt contract 合并后才启动 WP3。Wave A 和 Wave C 才各有两个可真正并行的实现 writer。
- 任何子仓改动必须 child PR/CI/main ancestry 先成立，root gitlink 和 generated projection 最后单独收口。

## 5. 权威边界

- Root 拥有 Scene Card 聚合门、BET/Spec 绑定、跨仓验收和最终 gitlink。
- OMO 仍是唯一 admission、effect receipt、event ledger/outbox、principal authority verification、adjudication 和 value truth writer。
- Cockpit 是唯一人机入口和读模型/projection，只有明确的 human adjudication command 可委派 OMO 写入。
- Agora 只转运已准入的能力请求和已验证的 authority digest，不成为身份、决策或价值权威。
- ECOS WorkPacket v2 和已有 OMO workflow/Blueprint control 是任务合同，不新增平行 task envelope。

## 6. 价值防火墙

- WP1、WP2、WP3、WP4、WP6 的 `value_indicator_policy=false`，价值轴固定为 `NOT_PROVEN`，只能以 `delivery_accepted` 完成。
- WP5 是唯一可以推进价值轴的 WorkPacket。
- Parent 的 `value_indicator_policy=true`，但它只能引用 WP5 已验证的不可变 value receipts 进入 `outcome_accepted`，不得创建第二份价值样本。
- WP5 必须同时有真实非测试 signal、authority-bound principal、human verdict、durable `decision_outcome`、revision 和 time-burden 证据，才能进入 `ACCEPTED`。
- PR、merge、测试、CI、运输回执、Agent `worker_done`、signed engineering attestation、synthetic 或 `user_provided` 样本均不计个人价值。
- 单个真实 outcome 只证明链路成立，不自动证明长期价值。

## 7. 执行与验收协议

每个 child 使用独立 clone，严格执行：

```text
bootstrap -> start --bet -> claim -> RED -> minimal implementation
-> GREEN -> independent review -> verify -> child PR/CI/main
-> root pointer when required -> closeout -> clone retirement receipt
```

### 7.1 Implementation plan artifacts

Writing-plans 阶段由父 BET workflow 一次性产出一份总控计划和六份独立 child 计划，不在计划阶段修改实现代码：

- `docs/superpowers/plans/2026-08-28-product-p0-truth-loop.md`
- `docs/superpowers/plans/2026-08-28-product-p0-wp1-honest-scene-gate.md`
- `docs/superpowers/plans/2026-08-28-product-p0-wp2-honest-agent-cell-receipt.md`
- `docs/superpowers/plans/2026-08-28-product-p0-wp3-canonical-outbox-publisher.md`
- `docs/superpowers/plans/2026-08-28-product-p0-wp4-principal-authority-binding.md`
- `docs/superpowers/plans/2026-08-28-product-p0-wp5-human-adjudication-value.md`
- `docs/superpowers/plans/2026-08-28-product-p0-wp6-physical-recovery-drill.md`

总控计划只编排 completion-policy 前置、Wave A/B/C、串行 SSOT/root-pointer 收口和验收；每份 child 计划独立定义 RED/GREEN、精确写面、子仓 PR、回滚、canary 和清理。

验收必须分开六个维度：

1. implementation 是否存在；
2. canonical registration/Spec binding 是否一致；
3. RED/GREEN 测试是否覆盖真实拒绝和成功路径；
4. child/root mainline 和 gitlink reachability 是否成立；
5. live operational canary/replay/cleanup 是否有直接回执；
6. principal-bound value 是否有真实 human adjudication。

前五项全绿也不能代替第六项。

## 8. 故障、停机与回滚

- 身份未绑定、Spec/work-packet digest drift、越界 write surface、重放不一致或无法证明零副作用时立即停机。
- 子仓 SHA 未进入 child main 时不得更新 root gitlink。
- outbox 不确定传输保持 pending/uncertain，不删除、不伪造 sent。
- 效果回执不能持久化时不得返回 success。
- recovery 任一 digest 不等立即停止，不覆盖源数据。
- 回滚只撤销当前 child 的局部修改；已持久的 event、adjudication 和 audit receipt 保持 append-only。

## 9. 非目标

- 不新增顶级人机入口、dispatcher、workflow engine、event bus、outbox、identity registry、value writer 或数据库。
- 不扩展 WorkPacket schema 来表达 child packet；直接复用一 BET 一 Spec 一 WorkPacket 合同。
- 不修复 Product P0 以外的历史 ledger/completion evidence 债务。
- 不在 Spec bootstrap 中改实现代码、测试、gitlink、运行态或价值证据。
- 不为工业级多租户、远程高可用或全面密码体系扩大范围；单用户路径优先。

## 10. 总体完成判据

父 BET 只能在以下条件全部成立后由人类审议进入完成候选：

- value-exempt completion 合同已合并，其负例阻止 value 伪造和无声状态改变；
- WP1-WP6 全部为 `done`，且 WP1/WP2/WP3/WP4/WP6 为 `delivery_accepted`、WP5 为 `outcome_accepted`；
- Scene gate 不再 false-green；
- 所有 effect success 都可回放到 durable receipt；
- outbox 只有一个 canonical publisher，并发、崩溃和重试不重复交付；
- principal authority digest 在 OMO/Cockpit/Agora 全链一致；
- 至少一条非测试 human adjudication 产生 durable `decision_outcome`；
- 至少一次隔离 backup/restore/integrity/replay 真实执行且有人工确认；
- child-first/root-last 、必需 CI、main ancestry、focused canary 和 clone cleanup 均有回执；
- 价值状态由 WP5 的真实样本决定，不从工程结果推测。

## 11. 书面 Spec 审阅门

本 Spec 与六份 child Spec 虽已根据用户批准的概念设计编写为 `accepted`，但在人类完成书面审阅前，不得进入 implementation plan 或 Wave A 代码实施。

## 12. 自举 waiver

```text
waiver: user-explicit
date: 2026-08-28
quote: "本次 Product P0 父 BET 与六个 child Spec/WorkPacket 自举跳过 workflow start，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限七份已列明的 Product P0 Spec、docs/plans/3y-bet-ledger.yaml 仅新增 BET-Y1Q3-T4-02 至 BET-Y1Q3-T4-08，以及 .omo/_truth/governance-evidence/waiver-2026-08-28-product-p0-spec-bootstrap.md 记录本句；不得修改其他 BET、completion/value evidence、实现代码、gitlink 或运行态。"
reason: workflow start requires an already-existing accepted Spec and BET
gate_bypass: AGCP_REQUIREMENT_ITERATION_GATE=0
bootstrap_value_indicator_policy: false
```
