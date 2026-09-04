---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract

bet_id: BET-Y1Q3-T4-01
owner: human-principal
last_updated: 2026-08-24

risk_level: L2
human_gate: true
accepted_at: 2026-08-20T04:10:00Z
accepted_authority: delegated-strategic-director
type: ssot
last_updated: 2026-09-03
---

# 真实个人价值证据脊柱与战略事实重基线设计

## 1. 一句话结论

停止把“系统产出了很多”当成“系统对本人有价值”，把所有已有能力压到一条可证伪链上：

```text
真实低敏信号
  → 受治理 Episode / WorkPacket
  → never-send 候选
  → 本人接受、修改、拒绝、延后或忽略
  → RevisionReceipt + OutcomeFeedback
  → 独立验证
  → 周度价值门
```

这条链没有直接人类裁决时，价值状态只能是 `NOT_PROVEN`。

## 2. 背景与问题定义

### 2.1 当前反证

- 工程台账全部为绿，不等于个人价值为绿。
- NorthStar 直接读数仍为零，MOS decision outcome 仍为零。
- WorkPacket、VerificationReceipt、Agent Workflow、clone guard、ACP 设计和 capability registry 都已存在，但没有共用同一默认身份链。
- Spec Binding、Capability projection、Workflow registry 和 transport 声明存在多种编码或多个 writer。
- 表面积仍增长；继续增加顶级模块、协议、场景和 dashboard 会增加不可持有性。

### 2.2 根因

```text
供给侧能力快速增加
  → 默认调用链没有同步切换
  → 工程完成、运行完成、价值完成被混为一谈
  → 台账/文档提前宣称完成
  → 后续 Agent 把声明当作事实
  → 系统继续扩容而不是收敛
```

### 2.3 设计目标

1. 用一条身份链连接 BET、Spec、Workflow Run、WorkPacket、Changeset、PR、Verification 和 Outcome。
2. 将完成语义拆为工程、运行、价值三轴。
3. 首先产生一个真实、低敏、可撤销的个人价值样本。
4. 通过删除重复 writer、提前完成声明和硬编码报告实现净减法。
5. 保留 OMO/ECOS/Cockpit 现有权威，不建设第二平台。

## 3. 权威边界

| 责任 | 唯一权威 | 禁止替代物 |
|---|---|---|
| 战略优先级 | `docs/plans/3y-bet-ledger.yaml` | 新 roadmap DB、外部任务板 |
| 规范正文 | Git 中 accepted Spec | 聊天摘要、临时 prompt |
| 执行契约 | ECOS WorkPacket v2 | 平台私有任务对象 |
| 生命周期 | OMO Agent Workflow + Workflow Mesh | Orca ready、进程 exit 0 |
| 多仓变更 | cross-repo changeset + Git/PR | 手工复制 SHA |
| 能力事实 | 已有 registries | 第二份手工 capability 清单 |
| 本地 Agent 控制 | ACP | MCP、A2A、Orca 自动 fallback |
| 工具与上下文 | MCP / native adapter | 万能调度中心 |
| 算力 | AetherForge + omlxc | 任务真相、战略状态 |
| 跨域互操作 | A2A，当前 deferred shadow | 业务主链 |
| 价值事实 | OutcomeFeedback + Human Adjudication | PR 数、Token、mtime、health 分 |

## 4. 统一身份链

```text
BET-ID
  └─ accepted SpecificationBinding
       └─ workflow_run_id
            └─ packet_id + packet_hash
                 └─ assignment_id + dispatch_id
                      └─ cross_repo_changeset_id
                           └─ subrepo PR(s) + root gitlink PR
                                └─ verification_receipt_hash
                                     └─ outcome_id + adjudication_id
```

Canonical Spec Binding：

```yaml
spec_ref: repo://docs/superpowers/specs/<name>.md
spec_version: 1.0.0
content_digest: sha256:<64-lowercase-hex>
decision_ref: decision://accepted/<BET-ID>
```

任何一环缺失、漂移或歧义，都不能靠猜测继续执行。

## 5. 三轴完成语义

| 轴 | 最低直接证据 | 可用状态 |
|---|---|---|
| Engineering | merged reachable commit、tests、diff、rollback | `NOT_STARTED/IN_PROGRESS/VERIFIED` |
| Operational | live canary、fresh receipt、replay、cleanup | `NOT_PROVEN/DEGRADED/PROVEN` |
| Value | real signal、human verdict、revision、time burden | `NOT_PROVEN/REJECTED/ACCEPTED` |

整体状态规则：

```text
engineering=VERIFIED && operational=PROVEN && value=ACCEPTED
  => outcome_accepted

otherwise
  => evaluating | blocked | revise | rejected
```

`PR merged`、`worker_done`、`turn_completed`、`tests pass` 都不能单独关闭 BET。

## 6. 目标架构

```text
Human Principal
      │ verdict / revision / time burden
      ▼
Cockpit ──────────────── Value Projection
      │                          ▲
      │ SignalReceipt            │ OutcomeFeedback
      ▼                          │
OMO Agent Workflow / Mesh ── EvidenceRecorded ── WorkflowVerified
      │
      │ WorkPacket hash + admission + scope
      ▼
ACP Local Agent Control ── MCP/native tools ── AetherForge compute
      │
      ├─ CompletionManifest
      └─ Git changeset / receipts

A2A: deferred shadow only
Orca: observation and explicit human break-glass only
```

## 7. 工作流

### 7.1 Phase 0：事实重基线

1. 冻结新顶级项目、协议权威、场景和 Dashboard。
2. 修正 Spec Binding 编码与启用时点。
3. 把 WorkPacket 接入通用 start/claim/dispatch。
4. 修复 clone lifecycle 的根仓 scope、claim fail-open、dependency init 和 unsafe retire。
5. 选择唯一 capability registry writer；其他变兼容投影或退役。
6. 对 ACP、A2A、知识归并、Outcome、Cartridge、Truth Canvas 逐项标记 `EXISTS/PARTIAL/NOT_PROVEN/DEFERRED`。
7. 删除或降级硬编码价值/成本/复利报告。
8. 修正 runtime projection 的事实标签：过期 claim 不得显示为 live，BDSK 不得把直连模型或规则 fallback 标成 AetherForge 实证。

### 7.2 Phase 1：首个真实价值样本

1. 用户投放一条低敏、可撤销的真实事项。
2. 产生脱敏 SignalReceipt；正文与绝对路径不进入 Git、Ledger 或 HTTP。
3. 建立 Episode、责任和受治理 WorkPacket。
4. Agent 只能输出本地 `never_send=true` 候选。
5. 用户给出五态 verdict，并记录 review time、estimated time saved 和修订 diff。
6. 生成 RevisionReceipt 与 OutcomeFeedback。
7. 独立 verifier 直接读取同一真相，才允许 WorkflowVerified。

### 7.3 Phase 2：14–45 日习惯门

- 每周至少 3 个真实裁决样本；未达到时不提高自治。
- 采纳、修改、拒绝全部进入分母；不得只统计正样本。
- 用户负担大于节省时间时，场景降级或关停。
- 连续两周无新增真实 Outcome 时，停止功能新增，回到信号/判断校准。

### 7.4 Phase 3：90 日稳定门

- 连续四周每周至少 3 条接受的真实委托结果。
- 可追溯到角色、责任、Episode、Mandate、Evidence 和 Human Adjudication。
- 无越权外部动作、无敏感数据外泄、无历史丢失。
- 至少一项无价值资产完成退役。

## 8. Capability find/load 收敛

目标链：

```text
find(query)
  → exact capability ID(s)
  → resolve authoritative registry record
  → admission and health
  → native load/invoke adapter
  → privacy-safe receipt
```

约束：

- 多候选返回 `CAPABILITY_AMBIGUOUS`，不能 first-match。
- discovery 不能推导 admission。
- skill、workflow、MCP tool、plugin、CLI 保留原生生命周期，不全部包装成 MCP。
- 生成 registry 只能有一个 writer；其他入口只能读或生成独立兼容投影。

## 9. Spec collaboration 收敛

OpenSpec、BMAD、GSD/gstack、grill-me 的角色：

| 工具 | 允许角色 | 不允许角色 |
|---|---|---|
| OpenSpec | 规范入口与变更提案 | BET/运行真相 |
| BMAD | 产品/Agent 需求结构化 | 独立任务数据库 |
| GSD/gstack | 记忆、交接、执行纪律；缺失时降级 | 完成判定 |
| grill-me | 需求澄清与反证 | 人工审批替代物 |

所有外部规范先规范化为 canonical binding，再进入 OMO；不得各自生成一套 task truth。

## 10. 多仓与多 Agent 集成顺序

```text
accepted spec
  → parent WorkPacket
  → child packet per repository
  → child workflow/claim
  → child tests + PR + merge
  → reachable commit proof
  → root gitlink transaction
  → root PR + independent verification
  → retire only after clean/merged/reachable/no lease
```

同一文件只能有一个 writer；Verifier 不得修改候选；不同模型族优先承担独立验证。

## 11. 错误矩阵

| 错误码 | 触发 | 行为 |
|---|---|---|
| `SPEC_BINDING_INVALID` | spec 缺失、未接受、digest 漂移 | 禁止 start |
| `SPEC_ENCODING_DRIFT` | 根仓与 ECOS 编码不同 | 禁止兼容猜测 |
| `PACKET_HASH_MISMATCH` | packet 身份漂移 | 隔离候选 |
| `SCOPE_MISMATCH` | claim/packet/changeset 不一致 | 拒绝写入与集成 |
| `CHANGESET_UNPROVABLE` | 根文件或 gitlink 未纳入 | 阻断 PR |
| `SUBREPO_UNREACHABLE` | child commit 未合并或不可达 | 阻断 root gitlink |
| `CAPABILITY_AMBIGUOUS` | find 多候选 | 返回候选列表 |
| `CAPABILITY_UNAVAILABLE` | admission/health 失败 | 仅显式 fallback 可重派 |
| `TRANSPORT_UNCERTAIN` | ACP EOF/timeout/未知 | 回收；不自动降级 Orca |
| `VERIFIER_NOT_INDEPENDENT` | verifier 非直接/独立 | 拒绝 receipt |
| `OUTCOME_MISSING` | 工程完成无真实裁决 | BET 保持 evaluating |
| `RETIRE_UNSAFE` | dirty/unpushed/unmerged/active lease | 仅报告，不删除 |
| `RUNTIME_LABEL_MISMATCH` | 状态、路由或风险标签与直接事实不符 | 拒绝晋升，标 unverified |

## 12. 验收标准

验收以 Ledger BET 的 `AC-01` 至 `AC-11` 为唯一清单。本 Spec 不复制另一套完成状态。

附加负例必须覆盖：

- 缺 Spec、digest drift、错误 decision_ref。
- 根仓越权文件、子仓越权 gitlink、不可达 commit。
- capability 歧义和 provider unhealthy。
- ACP timeout/EOF、重复 dispatch、Orca 自动 fallback。
- 只有 PR/tests/worker_done、没有 human verdict。
- negative verdict 被排除分母、自报 consumer=human。
- dirty clone 或活 lease 下 retire。

## 13. 两周实施顺序

| 日 | 目标 | 出口证据 |
|---|---|---|
| D1 | truth baseline、状态标记、冻结 | baseline report |
| D2 | canonical Spec Binding lint + migration | schema/tests |
| D3 | workflow start/claim → WorkPacket | packet hash receipt |
| D4 | changeset root/subrepo fail-closed | integration fixture |
| D5 | capability single writer + exact find | drift/load receipt |
| D6 | NorthStar/Outcome truth 修复 | negative-case tests |
| D7 | ACP 默认事实校准、Orca break-glass | transport matrix |
| D8 | 真实低敏 sample ingest/draft | SignalReceipt |
| D9 | human verdict/revision/outcome | OutcomeFeedback |
| D10 | independent verify、文档、PR | verification receipt |

若 D8–D9 需要用户提供真实输入或裁决，工程可继续完成，但价值轴必须保持 `NOT_PROVEN`。

## 14. 回滚

- Spec/Workflow：恢复旧入口只读兼容，不恢复假绿。
- Capability：保留旧投影只读，对唯一 writer 回滚。
- ACP：若 live canary 不成立，Codex 保留 supervised manual transport 并标 `NOT_PROVEN`。
- Outcome：失败样本保留脱敏 receipt；不保留正文。
- Git：child PR 未合并时不得 bump root；inverse patch 与 baseline tree hash 必须可验证。

## 15. B.D.S.K. 裁决

### Builder

现有构件足够，主工作是把默认调用链接通并删掉重复 writer。

### Devil

最便宜的伪完成是补一组 fixture、把 119 个 done 当价值证据、或只记录接受样本。验收必须有真实反例与用户裁决。

### Sage

价值脊柱优先于完整控制面。控制机制只修到足以保护这条脊柱，不继续横向扩容。

### Keeper

OMO、ECOS、Cockpit、Git 和 Documents 的权威边界保持不变；新产物都是可重建投影或证据，不建第二真相。

### 共识

先做事实重基线与一条真实价值链；没有 Outcome，就不允许用工程完成推进愿景。

## 16. 停止规则

- 需要新项目、新数据库、新协议权威或自动外发。
- 需要绕过人工审批、clone guard、claim、independent verifier。
- 无法在两周内获得真实低敏输入和明确 verdict。
- 只能通过 mock/fixture/代理量让 gate 变绿。
- 迁移无法回放、补偿或恢复 baseline tree hash。

触发后：停止扩面、标记 `blocked/not_proven`，保留直接证据并回到上游校准。
