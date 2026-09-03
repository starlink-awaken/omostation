---
title: 织星近期架构、战略与执行体系深度复盘
date: 2026-08-20
status: active-baseline
bet_id: BET-Y1Q3-T4-01
evidence_cutoff: 2026-08-20T04:10:00Z
type: ephemeral
---

# 织星近期架构、战略与执行体系深度复盘

## 0. 执行摘要

### 一句话判断

织星已经具备大量 E2/E3 级工程与控制资产，但 E4 级个人真实价值仍未证明；下一阶段必须从“继续建设能力”切换为“修复完成语义、接通一个真实价值闭环并做净减法”。

### 当前总判定

| 维度 | 状态 | 结论 |
|---|---|---|
| 工程基础 | `PROVEN/PARTIAL` | Workflow、clone、Ledger、ECOS contracts、AetherForge 有直接资产 |
| 生产运行 | `PARTIAL` | 多数能力有代码或历史 smoke，但默认调用链、live canary 和 cleanup 不完整 |
| 个人价值 | `NOT_PROVEN` | 当前有效旅程 0、Human Outcome 0、连续观察窗未开始 |
| 真相治理 | `CONTRADICTED` | 审计前 119/119 BET done，但价值为 0；多个声明领先于运行默认值 |
| 可持有性 | `AT_RISK` | tracked src 较基线增长约 8%，bin 脚本增长约 66%，重复 writer/入口仍存在 |
| 战略方向 | `VALID` | “一个人的业务操作系统”与 Outcome 北极星仍正确，但执行顺序需重排 |

因此：

- 不推翻蓝图；
- 不再增加第二套平台；
- 不把当前系统称为“已全面落地”；
- 新建唯一主 BET `BET-Y1Q3-T4-01`；
- 以 14 日首样本、45 日习惯门、90 日价值门推进；
- 没有直接人类裁决时，价值轴保持 `NOT_PROVEN`。

## 1. 本次审计范围与证据等级

### 1.1 审计对象

- 三年战略规划；
- 数字分身总体架构蓝图；
- 多 Agent 战略执行与合规控制蓝图；
- Agent Instruction Pack；
- ECOS WorkPacket / CompletionManifest / VerificationReceipt；
- OMO Workflow、Mesh、Blueprint Controller；
- Agent clone、changeset、claim、PR 与 retire 生命周期；
- ACP、A2A、MCP、BOS、Orca、AetherForge 边界；
- Capability find/load、Skills、Workflow、MCP 的注册与消费；
- live NorthStar、Ledger、MOS outcome、Orca、Agora 运行态；
- BET 台账、表面积和文档一致性。

### 1.2 证据等级

| 等级 | 定义 |
|---|---|
| E0 | 口头声明或未绑定文档 |
| E1 | Schema、规范、静态配置 |
| E2 | 可重复单测、diff、hash、临时 fixture |
| E3 | 当前运行态、live canary、恢复/回滚证据 |
| E4 | 真实业务 Outcome + Human Adjudication |

Wave 完成必须有 E4。E2/E3 再丰富，也不能替代 E4。

### 1.3 状态标记

- `PROVEN`：当前直接证据可重复验证；
- `PARTIAL`：有实现或历史演练，但当前完整 Gate 未通过；
- `NOT_PROVEN`：缺少直接证据；
- `CONTRADICTED`：声明与当前事实冲突；
- `DEFERRED`：架构上明确后置；
- `RETIRED`：旧入口不可再自动选择。

## 2. 近期工作实际上完成了什么

### 2.1 已形成的强资产

1. ECOS 已有 WorkPacket v2、canonical hash、Spec Binding、CompletionManifest 和 VerificationReceipt。
2. OMO 已有 admission、Workflow Mesh、candidate、independent verification 和 compensation/rollback 基础。
3. 独立 clone、identity guard、私有分支和 hook 机制方向正确。
4. Agent Workflow 已能 start、claim、verify、closeout，并有 affected graph receipt。
5. AetherForge/omlxc 作为算力面边界清楚且当前健康。
6. Orca 已能承担终端、观察和 supervised human workflow。
7. 数字分身、Agent 控制与 Instruction Pack 文档的原则大体一致：Outcome 是完成事实，Agent 只能提交 Candidate。
8. SQLite Ledger 有 append-only 与 integrity 基础。

### 2.2 已出现的结构性偏差

1. 台账在审计前 119 个 BET 全部 done，但 NorthStar 为 0。
2. MOS 有大量 calibration，但 decision outcome 为 0。
3. 通用 workflow 没有默认编译和绑定 WorkPacket。
4. Spec Binding 在 ECOS 与根仓 lint 中使用不同编码，且门禁延迟到未来日期。
5. capability 有两个 writer 写同一路径、不同 Schema。
6. Codex registry 与 ACP 完成声明不一致；自动 transport 仍可能是 `cli_prompt`。
7. Agora/A2A 当前不可达，历史 smoke 不能代替当前 conformance。
8. Instruction Pack 很完整，但没有成为每次 dispatch 的强制 hash/ack 合同。
9. clone lifecycle 默认不初始化子模块，scope 违规可假绿，retire 缺 hard gate。
10. 硬编码 attribution 报告以常量生成“节省成本/复利”等价值数字。
11. 协调库 97 个 claims 中有 91 个仍标 active 但已超过 expires_at；状态 active 与时间有效分叉。
12. BDSK 实际直连 Ollama，却把结果标记为 AetherForge/omlxc；简化 sandbox 还声明未实际扫描的风险类别为零。

### 2.3 本轮已完成的控制面恢复

本轮不是纯文档评估，已经完成以下可重复恢复：

- 核对共享运行态 5 个 active run 无匹配活进程；
- 使用现有 broker CLI 逐个以 `blocked` 关闭，不直接改运行文件；
- `prune-locks` 后 active runs 与 locks 均为 0；
- `agent-workflow compliance` 恢复 `decision=continue`；
- 新建 independent clone `/Users/xiamingxing/agents/blueprint-value-rebaseline/ws`；
- clone identity guard 返回 `verified_clone`；
- Orca 注册 exact repo/worktree；
- 初始化必要子模块后，workflow lint 和 required integration health 全绿；
- 登记 `BET-Y1Q3-T4-01`，新增本 Spec 与复盘报告；
- ledger lint 和文档 SSOT lint 已通过。

初始化还复现了一个机制问题：自动 health 生成物会抢占尚未初始化的子模块目录，clone lifecycle 又默认不初始化依赖，导致 bootstrap 失败。该问题已纳入主 BET，而不是留作人工经验。

## 3. 蓝图要求—当前证据矩阵

### 3.1 数字分身蓝图

| 要求 | 当前证据 | 状态 | 下一门 |
|---|---|---|---|
| 本人接受的真实委托结果是北极星 | NorthStar 0 journeys / 0% | `NOT_PROVEN` | 一条真实 Human Outcome |
| 只证明一个人的闭环 | 工程面继续增长、价值面空 | `CONTRADICTED` | 冻结扩张，做 Golden Slice |
| 一个瘦 OMO＋一个因果 Ledger | Ledger 存在、无 Outcome/anchor/recovery proof | `PARTIAL` | 唯一 broker、anchor、restore |
| Responsibility→Episode→Mandate→Outcome | 前段事件存在，Outcome 缺失 | `PARTIAL` | 非测试完整 replay |
| 两个持续真实信号源 | 有零散/历史信号，无持续双源证明 | `PARTIAL` | freshness+dedup+privacy |
| Cockpit Decision Inbox | 能力与历史实现分散，当前旅程未复验 | `NOT_PROVEN` | 一张真实卡片裁决 |
| 连续四周每周 ≥3 接受结果 | 观察窗未开始 | `NOT_PROVEN` | Outcome projector 后启动 |
| 能力晋升与无价值资产退役 | 未由真实 Outcome 驱动 | `CONTRADICTED` | 先退役一个零价值资产 |

### 3.2 多 Agent 控制蓝图

| 要求 | 当前证据 | 状态 | 下一门 |
|---|---|---|---|
| Workflow/lock/evidence 健康 | 本轮已恢复 0 active/0 locks/compliance continue | `PROVEN` | 保持 broker-only |
| Active Wave/BET 唯一 | 审计前无 claimable BET | `CONTRADICTED` | 新主 BET 已登记 |
| G-1 SR-01～06 当前全绿 | 历史证据不等于当前；Agora down、human gate 未证 | `PARTIAL` | 当前 SHA 重演并签名 |
| WorkPacket 是唯一执行契约 | ECOS 有，通用入口未强制 | `PARTIAL` | start 前编译和 revalidate |
| Agent 只交 Candidate | Schema/文档已有，非所有入口强制 | `PARTIAL` | dispatch/collect 全接线 |
| 独立 verifier | contract 有，生产覆盖不全 | `PARTIAL` | 真实 candidate direct measure |
| 独立 clone 与 claim | guard 和 claim 已可用 | `PROVEN` | 修 changeset/retire 假绿 |
| 唯一 Cockpit blueprint 入口 | 蓝图仍标 planned/not implemented | `NOT_PROVEN` | 只建薄 facade，不建平台 |

### 3.3 Spec、Instruction 与协作

| 要求 | 当前证据 | 状态 | 下一门 |
|---|---|---|---|
| canonical accepted Spec | ECOS 正确，根 lint 编码/启用时点错误 | `CONTRADICTED` | 一种编码、立即 fail-closed |
| 每次派工注入 instruction pack | 文档有模板，无强制 pack hash/ack | `NOT_PROVEN` | compile + packet_ack gate |
| escalation/handoff 是运行契约 | 主要是 Markdown 模板 | `PARTIAL` | 严格 Schema/receipt |
| OpenSpec/BMAD/GSD 可协作 | adapters 存在 | `PARTIAL` | 只作 ingress/discipline |
| 不建第二任务真相 | 原则正确 | `PROVEN` | 外部工具只产规范/证据 |

### 3.4 协议边界

| 协议/工具 | 正确角色 | 当前状态 | 战略裁决 |
|---|---|---|---|
| ACP | 本地 Agent session/permission/lifecycle | `PARTIAL/CONTRADICTED` | 修 exact scope + live canary 后才 cutover |
| MCP | 工具与上下文 | `PARTIAL` | receipt 回链 packet，不拥有 task truth |
| A2A | 跨 Agent/节点 transport | `DEFERRED/NOT_PROVEN` | 价值门后做 HTTP+JSON shadow/TCK |
| Orca | terminal/supervisor/人工 break-glass | `PARTIAL` | 不做自动 fallback/Controller |
| AetherForge | 模型与算力路由 | `PROVEN` | 保持，不拥有任务/价值真相 |
| BOS | capability address/resolve | `PARTIAL` | exact resolve + admission，禁模糊执行 |
| BDSK | 多视角决策方法 | `CONTRADICTED` | 所有本地推理走 BOS/AetherForge；rule fallback 必须标 unverified |

## 4. 最重要的架构判断

### 4.1 架构不是从零开始

当前系统并不缺 WorkPacket、Workflow、clone、ACP 设计、Capability registry 或 Ledger。继续“再造一个统一平台”会扩大问题。

### 4.2 真正缺的是默认身份链

```text
BET
  → accepted spec
  → workflow run
  → WorkPacket hash
  → claim/admission/dispatch
  → multi-repo changeset
  → PR/reachability
  → independent receipt
  → real human outcome
```

只要其中一段仍是可选、fixture-only、不同编码或 first-match，整体就不能称为 proven。

### 4.3 完成语义必须拆轴

过去最大的问题是把工程绿推导成价值绿。今后必须分开：

- Engineering：代码、测试、PR、rollback；
- Operational：live、replay、cleanup、fresh receipt；
- Value：real signal、human verdict、revision、burden/saved time。

三个轴不能互相替代。

## 5. 战略优化

### 5.1 原战略保留部分

- 一个人的业务操作系统；
- 把真实信号变成愿意署名的产出；
- 记录每次人类修订；
- Y1 是净减法年；
- Outcome 而非工程代理量是北极星；
- 未通过价值门不扩场景、不提高自治。

### 5.2 调整后的执行主轴

原蓝图按 W0–W6 大规模铺开，容易再次先造中段。调整为：

```text
Phase 0 事实重基线
  → Phase 1 首条真实价值样本
    → Phase 2 14–45 日习惯门
      → Phase 3 90 日稳定门
        → 才允许 Evolution/A2A/多场景
```

控制面只修到足以保护价值脊柱，不作为独立扩张主线。

### 5.3 当前唯一 Active BET

`BET-Y1Q3-T4-01 — 真实个人价值证据脊柱与战略事实重基线`

该 BET 同时承担：

1. 三轴完成语义；
2. canonical Spec/WorkPacket identity；
3. 多仓 fail-closed 集成；
4. capability 单一 writer 和 exact load；
5. ACP 默认事实校准；
6. NorthStar/Outcome 真相修复；
7. 首条真实低敏样本；
8. 重复/假权威资产减法。

它不承担 A2A、家庭蜂群、多场景、远程 Agent、自治升级或新 Dashboard。

## 6. P0 / P1 / P2 执行优先级

### P0：不完成不得继续扩张

1. 修 completion truth：done 不再由工程状态单独推导。
2. 修 Spec 编码与未来日期旁路。
3. WorkPacket 接入通用 start/claim/dispatch。
4. 修 changeset root scope、claim fail-open、reachability 和 unsafe retire。
5. capability registry 裁定唯一 writer；暂停竞争写入。
6. 修 NorthStar 的 self-record、negative outcome 与 provenance。
7. ACP registry/默认 transport 与真实实现一致；无 live 证据则标 not proven。
8. 产出首条真实低敏 human-adjudicated outcome。
9. BDSK 禁止绕开 BOS/AetherForge，且不得为未运行的检查生成“0 风险”声明。

### P1：P0 后立即收敛

1. Instruction Pack hash/ack 进入 WorkPacket。
2. Cockpit 提供唯一薄 Decision/Outcome 入口。
3. Ledger anchor、backup、restore 和 projector rebuild。
4. 退役硬编码 attribution 报告与平面 workflow 权威。
5. 更新蓝图、战略、SYSTEM-INDEX 和 Documents handoff。
6. 协调 claim 展示与回收分开 `state_active/expired_by_time/live_by_time`，修复 91 个过期 active claim 的假活跃。

### P2：价值门后再做

1. A2A 1.0 HTTP+JSON shadow/TCK；
2. Dynamic Agent Cell；
3. Evolution 自动晋升；
4. 第二/第三场景；
5. 家庭/组织扩展；
6. 远程、多节点、streaming/push。

## 7. 冻结清单

在第一条真实 Outcome 和 14 日可重复读取证据之前，冻结：

- 新顶级项目；
- 新长期 daemon/service；
- 新协议权威；
- 新 Agent 类型；
- 新 Scene；
- 新 Dashboard；
- 新 capability registry；
- 新 workflow engine；
- A2A 生产接线；
- 自动外发和自治升级；
- 用合成数据回填 NorthStar。

## 8. 净减法清单

本 BET 至少完成四项中的两项，并且保护测试不下降：

1. 两个 capability registry writer 收敛为一个；
2. 硬编码 compound attribution 报告退役/降级；
3. 平面 `agent-workflows.yaml` 降为 generated compatibility view 或退役；
4. ACP 成立后移除 Codex 自动 `cli_prompt`；若不成立，移除提前完成声明。

删除前必须证明无活调用者；不能靠删测试、历史 ADR 或 advisory 规则优化指标。

## 9. 两周执行计划

| 日 | 工作包 | 主要文件面 | 验收 |
|---|---|---|---|
| D1 | 事实基线、BET、Spec、冻结 | ledger/spec/report | lint + accepted decision |
| D2 | Spec Binding 统一 | bet-ledger/ECOS tests | 全编码负例 |
| D3 | start/claim → WorkPacket | workflow/OMO | hash/scope binding |
| D4 | multi-repo changeset | clone lifecycle/tests | root/subrepo fail-closed |
| D5 | capability 单一 writer | generators/registry/tests | check/find/load receipt |
| D6 | NorthStar/Outcome truth | BCOS/OMO/tests | reject/modify/provenance |
| D7 | ACP 默认事实 | workers/adapter/tests | live or not_proven |
| D8 | 真实低敏 signal | Cockpit/OMO runtime | SignalReceipt |
| D9 | 人类裁决与修订 | Outcome broker | RevisionReceipt |
| D10 | verify、docs、PR | all claimed surfaces | independent receipt/CI |

## 10. 多 Agent 与多仓安排

### 10.1 角色

| 角色 | 职责 | 禁止 |
|---|---|---|
| Director | 分解 packet、依赖、预算、Gate | 写执行候选 |
| Builder | 最小实现和本地证据 | 自报 done |
| Devil | 负例、假绿、越权审计 | 修候选 |
| Verifier | 只读直接测量 | 信任 builder 摘要 |
| Release | child merge、gitlink、root PR | 使用不可达 SHA |

### 10.2 仓库顺序

```text
child spec/claim
  → child code/tests
  → child PR green+merge
  → reachability receipt
  → root gitlink transaction
  → root PR
  → independent verify
  → safe retire
```

共享 Workspace 继续只读；writer 使用 verified independent clone。

## 11. PR、合并与清理策略

1. 每个子仓先独立 PR，禁止根仓引用未合并 SHA。
2. 根仓按 lane 拆 commit，D0 用 tag 或远端分支持久化。
3. CI 全绿不自动等于价值完成；只表示工程轴通过。
4. 合并后验证 origin/main 的 gitlink 与目标 SHA 完全一致。
5. 清理前要求 clean、pushed、merged/reachable、无 active workflow/lease/Orca worker。
6. dirty、legacy ambiguous 或 external-owned 资源只报告，不猜测删除。

## 12. Documents 同步策略

最终交接文档应放到 canonical Documents 架构域，而不是把 Workspace Markdown 当个人知识真相。

同步前置：

- 读取 Documents 域级 `CLAUDE.md`；
- Documents context/guard 可用；
- 不写脚本、cache、runtime；
- 只同步决策、状态、下一步和证据引用；
- 不复制敏感正文、绝对路径和运行凭证；
- Workspace 保留工程规范，Documents 保留人类可读交接。

若 Documents gateway 仍不可用，本轮先提交 Workspace 报告，明确同步为 blocked，不能绕过域门直接写。

## 13. 风险与停止规则

| 风险 | 触发 | 动作 |
|---|---|---|
| 再造平台 | 需要新 DB/engine/protocol truth | 停止，扩展现有权威 |
| 假价值 | 只能用 fixture/自报/proxy | 标 NOT_PROVEN |
| 双执行 | transport uncertain 后自动 fallback | fence/cancel/reap 后新 assignment |
| 多仓假绿 | child SHA 不可达 | 阻断 root pointer |
| 隐私 | receipt 含正文/绝对路径/secret | fail closed，销毁候选 |
| 用户负担过高 | review time ≥ saved time | scene 降级/关停 |
| 表面积继续扩大 | P0 期间新增顶级面 | 停止该变更，要求配对减法 |
| 路由标签失真 | 实际模型端点与 receipt 声明不同 | 拒绝证据，标 route_unverified |

## 14. 给后续 Agent 的最小接手协议

1. 进入 `/Users/xiamingxing/agents/blueprint-value-rebaseline/ws`。
2. 设置 `AGENT_ID=blueprint-value-rebaseline` 并运行 clone guard。
3. 读取本报告、同名 Spec、BET-Y1Q3-T4-01。
4. 先执行 `agent-workflow status/compliance`，不要重开第二 BET。
5. 每个 Task 从 Spec AC 派生 WorkPacket；先 affected graph 再 claim。
6. 不修改共享 `/Users/xiamingxing/Workspace`。
7. 不把审计前 119 个 done 当作价值基线。
8. 不启动 A2A 或业务蜂群。
9. 遇到需要用户真实输入/裁决时，工程继续但价值轴保持 NOT_PROVEN。
10. 合并、清理和 Documents 同步按本报告 §11–12 执行。

## 15. 结论

近期工作没有白做：控制、契约、隔离和算力基础已经形成。真正的偏离是把这些基础本身当成了用户价值，并让多个“已完成”声明领先于默认调用链和真实 Outcome。

修正后的方向不是收缩愿景，而是提高证据门槛：

> 先让一个真实事项进入系统，形成一个本人愿意接受或明确拒绝的 never-send 候选，并准确记录他改了什么；然后连续观察，再谈 Agent 蜂群、A2A 和自我进化。

这条路径同时满足个人价值、架构收敛、协议清晰、多 Agent 可控、多仓可集成和长期可持有性。

## 16. 2026-08-21 closeout delta

> 本节是对本报告的追加收口，不改写页首 `evidence_cutoff`，也不把本节证据倒灌为
> 2026-08-20 的历史结论。会漂移的运行事实继续以对应 SSOT、broker 回执和实时命令为准。

### 16.1 三轴终局判定

| 轴 | 收口状态 | 直接判定 |
|---|---|---|
| Engineering | `PROVEN` | accepted Spec、WorkPacket 身份链、verified independent clone、canonical changeset/claim coverage、BDSK 路由约束与 Coordination 控制面已经形成可执行机制；工程绿只证明交付链，不替代价值证明。 |
| Operational | `PARTIAL` | tick 调度已切至受管 LaunchAgent，启动目录、进程参数、协调库完整性、agent heartbeat、attestation 与备份轮转的只读 shadow 证据通过；但 backup cron 仍错误指向共享 Workspace，未完成所有权切换，因此整体运行轴不得标 `PROVEN`。 |
| Value | `NOT_PROVEN` | `engineering-delivery` 的真实 Human Outcome 仍为 0；测试、合成、`user_provided` 或无法绑定 `human_verdict` 的记录不计入价值门。工程资产、PR、review 与历史 harvest 都不能替代真实 `decision_outcome`。 |

### 16.2 机制收敛结果

本轮已把此前分散的控制能力收敛到同一条身份和证据链：

```text
accepted Spec
  -> bound WorkPacket
  -> verified independent clone
  -> affected graph + claimed paths
  -> canonical cross-repo changeset
  -> BDSK-governed decision
  -> Coordination collect/verify
  -> independent receipt
  -> Human Outcome
```

- Spec/WorkPacket：执行输入不再只是一段 prompt；规范身份、范围、验收与回执必须绑定。
- clone/changeset：writer 使用身份匹配的独立 clone；根仓与子仓变更以可校验 changeset 和
  claim coverage 进入集成面，不能以本地 dirty 或不可达提交冒充交付。
- BDSK：多视角裁决是决策方法，不是第二任务真相；本地推理必须经 BOS/AetherForge 边界，
  无真实执行的 fallback 必须标记为未验证。
- Coordination：tick、collect、verify 与 attestation 已有受管运行面；调度健康与任务完成、
  价值完成保持分轴，任何 agent 都不能自行把 BET 标为 done。

### 16.3 未完成事实与协议裁决

1. LaunchAgent tick 迁移为 `PASS`，但 backup cron 仍为 `BLOCKED`。在备份命令不再引用共享
   Workspace、且新的 scheduler owner 有直接回执前，不得宣称调度切换完整完成。
2. `BET-Y1Q2-T1-19` 的权威复盘结论是 `blocked / NOT_PROVEN`：ACP stdio 尚未成为可重复证明的
   默认 transport，`cli_prompt` 仍是现实默认或安全兼容路径；不得沿用“已切割/已退役”的旧声明。
3. ACP 可以继续做受监督 canary 与权限代理验证，但只有默认链、权限、取消/回收和 live receipt
   同时成立后才允许 cutover。
4. A2A 保持 `DEFERRED`。它可作为未来跨 agent/节点的 HTTP+JSON transport，但当前不接入生产
   Golden Slice，也不拥有任务、证据或价值真相。

### 16.4 下一轮唯一 Golden Slice 准入

下一轮不得继续横向铺平台；只允许一条低敏、可由本人裁决的 `engineering-delivery`
Golden Slice：

1. 一个真实外部信号进入 accepted Spec，并编译为绑定 WorkPacket；
2. writer 在 verified independent clone 内交付，changeset、claim、PR 与独立验证可重复读取；
3. Cockpit/Outcome broker 呈现单个候选，用户可 `accept`、`modify` 或 `reject`；
4. revision 与 `human_verdict` 绑定为真实 `decision_outcome`，MOS 只消费该权威结果；
5. 完成一次 replay/restore，并证明证据不含正文、凭证或不必要的个人信息。

准入证据缺任一项，三轴不得升级；尤其没有真实 Human Outcome 时，Value 必须保持
`NOT_PROVEN`。

### 16.5 停线与交接状态

本批次到此进入停线：不启动 A2A 生产接线，不新增 Scene、Dashboard、顶级项目、长期 daemon、
protocol truth 或自治升级；不以测试样本补价值基线；不自行修改 BET 完成状态。下一轮只有在用户
明确下令后启动，并先从本报告、`BET-Y1Q3-T4-01` SSOT 与
`.omo/_knowledge/retros/BET-Y1Q2-T1-19.md` 重新读取当前事实。

## 17. 2026-08-21 全量交接与优化后的持续推进方案

> 本节面向临时接手本工作的 Agent、维护者与 Human Principal。它把 2026-08-20 复盘之后的
> 实际交付、纠偏、验证、未决边界和下一轮顺序固化为一个可执行交接面。这里记录的是证据快照，
> 不替代会漂移的运行 SSOT，也不授权任何 Agent 代替人类做价值裁决。

### 17.1 本轮最终判断

系统的主要矛盾已经从“缺少控制构件”转为“构件是否默认串成一条不可伪造的责任链”。近期大量
更新并没有推翻原愿景，反而证明以下判断应成为后续规划的中心：

1. **愿景保持不变**：继续建设一个以本人真实结果为北极星、可授权但不可冒名裁决的个人业务
   操作系统。
2. **工程策略从扩面改为收敛**：不再按组件数量、PR、测试数或 Agent 数衡量推进；只修复 Golden
   Slice 所需的默认身份链、完成语义和可重放证据。
3. **WorkPacket 是唯一执行契约**：Spec、Instruction Pack、claim、dispatch、candidate、verify、
   human outcome 必须共享同一不可变身份，任何转换都必须可校验。
4. **Agent 只能提交候选与证据**：Agent 不得替本人生成 `human_verdict`，不得把工程授权解释为
   内容接受，也不得自行把 BET 标为 done。
5. **协议按价值顺序启用**：ACP 继续受监督验证，A2A 保持后置；只有一个人的闭环形成稳定 E4
   证据后，才扩展第二场景、远程节点或自治等级。

按三轴重新判断：

| 轴 | 2026-08-21 状态 | 判断依据 | 升级条件 |
|---|---|---|---|
| Engineering | `PROVEN`（本轮作用域） | instruction binding、worker-origin ACK、四类 adapter、OMO dispatch、跨仓 PR/CI、独立复核与 `origin/main` 落地复核均有直接证据 | 保持默认链 fail closed，并补齐尚未支持该协议的 worker |
| Operational | `PARTIAL` | 实际子进程能在 provider 启动前 ACK；但跨 CLI 进程恢复故意 fail closed，且运行/备份 shadow 仍有窗口与 owner 问题 | 完整 shadow 窗、scheduler owner 修正、replay/restore 证据 |
| Value | `NOT_PROVEN` | Golden Slice 候选存在，但尚无本人显式 `accept/edit/reject/defer/ignore`；T7-01 真实 outcome 证据仍未证明 | Human verdict 与 revision/outcome 可重复读取 |

### 17.2 已落地交付与不可变证据

| 交付面 | PR / 合并证据 | 当前裁决 |
|---|---|---|
| Phase A：授权 Instruction Pack 与五类执行入口接线 | 根仓 PR #1796，merge `e621dfa1c030b5fc828a70e16c8ccedee1dad148` | `PROVEN`；文档身份成为可解析输入 |
| ECOS：WorkPacket instruction binding | ECOS PR #33，merge `fa986f0212db79d908667119fa2ae4ad448532a7` | `PROVEN`；ref/version/digest/profile 进入 canonical packet/hash |
| OMO：初版 ACK gate | OMO PR #63，merge `d0071679cb209509107c83b394112cba43bc0359` | `SUPERSEDED`；保留历史，但初版由 controller 代 ACK，不满足职责分离 |
| OMO：worker-origin ACK 修复 | OMO PR #66，merge `b479a7ab5254521f2b1c8f80f0e2d2aa4ad5f37c` | `PROVEN`；真实 worker 子进程消费一次性证明并写入 durable ACK |
| 根仓：resolver、registry、四类 adapter、OMO gitlink 与本交接 | 根仓 PR #1805，merge `3b251217f11a2e9dc722fc63c39620f114e548e9` | `PROVEN`；全量 CI 绿，`origin/main` 保留 ECOS/OMO 已合并修复指针 |

标签为 ECOS、OMO 与根仓各阶段提供 D0 恢复点；标签只证明工程产物可恢复，不证明价值完成。

### 17.3 最关键的安全纠偏：ACK 必须来自实际 worker

独立审查发现初版实现存在两个高风险问题：workflow YAML 与 Workflow Mesh 同时存在时被误判为
歧义；controller 又在启动 worker 前自己生成 proof 并 ACK，破坏了职责分离。

修复后的确定性状态机为：

```text
controller resolve workflow YAML + Mesh
  -> 分别验证 schema / spec / instruction / packet identity
  -> immutable identity 一致才 reconcile
  -> Requested -> Admitted -> StepDispatched
  -> 仅把 ACK context + one-time proof 注入实际 worker 子进程环境
  -> worker adapter 在 provider 解析/启动前完成 exact-match ACK
  -> OMO broker 持久化 WorkerAcknowledged
  -> controller 重读 durable state
  -> ACK=proceed 才允许继续，缺失/错配/重复/过期全部 fail closed
```

必须保留的边界：

- proof 不写入 packet、事件、日志或 provider 环境；消费后从进程环境删除；
- admission-only 只能写到 `StepDispatched`，不能伪造 `WorkerAcknowledged`；
- fake worker 即使退出码为 0，只要没有 durable ACK，仍视为失败；
- controller 内存中的 proof 不跨 CLI 进程持久化，跨进程 resume 因此会拒绝。这是当前安全选择；
  未来若需要恢复，必须设计可吊销 capability handoff，不能把 proof 落盘；
- CodeBuddy 与 Reasonix 尚未实现 `omo-worker-origin-ack/v1`，绑定 instruction 的任务对它们必须
  fail closed，不能静默回退到无 ACK 执行。

### 17.4 验证账本

| 层 | 结果 | 解释 |
|---|---|---|
| ECOS focused | 97/97 passed | WorkPacket、schema、compiler、negative cases |
| ECOS full | 1261 passed, 4 skipped | strict schema/state/compiler clean |
| OMO focused | 89 passed；最终三条 worker-origin 关键用例 3 passed | fake worker 拒绝、真实 child ACK、supervised start |
| OMO CI-equivalent | 1624 passed, 202 skipped, 1 deselected | 两个本机 sandbox 环境失败来自 `bus_foundation` DLQ SQLite；GitHub PR #66 CI 全绿 |
| 根仓 workflow | 61 passed | 双投影 reconcile、packet/instruction identity、durable ACK |
| 根仓 adapter | Codex 54；Pi 36；OMP 60；Orca start 8；Orca supervisor 55 passed | deselect 是既有 cwd/process-reaper 环境敏感用例 |
| 根仓真实组合 | 3 passed | dual-plane identity、真实 OMO broker ACK、provider 启动前 ACK |
| 静态质量 | changed Python Ruff check/format clean | 不代表全仓无历史债务 |
| 独立复核 | 初审 `BLOCKED` 两项 HIGH；修复后 `CLEAR` | 报告位于 `.omo/evidence/root_final_binding_review-code-review.md` |

不得把以下环境或机制缺口误报为本轮产品回归：

- 本机 GAC 访问 `~/Library/LaunchAgents/com.l4.governance.watch.plist` 受 sandbox 限制，同时检测到
  该 plist 的既有 service-config drift；
- `projects/omo-debt` 在部分环境缺失；
- Pi 组合测试受 process-group/reaper 与临时 cwd 用例影响收到 exit 143，本轮采用精确文件级结果；
- `projects/agora/uv.lock` 是并发/既有脏项，本轮未修改、未暂存、未清理。

### 17.5 优化后的目标树

```text
North Star: 本人持续接受、修订或明确拒绝的真实结果
|
+-- G0 价值真相
|   +-- 首条低敏 Golden Slice human verdict
|   +-- revision / outcome / provenance / privacy receipt
|   `-- 14d -> 45d -> 90d 可重复观察窗
|
+-- G1 执行责任链
|   +-- accepted Spec -> WorkPacket -> instruction identity
|   +-- claim/admission -> worker-origin ACK -> candidate
|   `-- independent verify -> Human Outcome
|
+-- G2 运行可靠性
|   +-- LaunchAgent/backup owner 收敛
|   +-- replay/restore/anchor
|   `-- stale claim、timeout、cancel、reap、compensation
|
+-- G3 净减法
|   +-- capability 单 writer/exact load
|   +-- 假价值报告降级或退役
|   +-- 平面/重复 workflow 权威退役
|   `-- 未产生真实 Outcome 的资产进入 hold/retire
|
`-- G4 条件式扩展（G0-G3 未过不得启动）
    +-- ACP default cutover
    +-- A2A shadow/TCK
    +-- 第二 Scene / 家庭与组织
    `-- 更高自治与多节点
```

战略优先级调整为 `G0 > G1 > G2 > G3 > G4`。G1/G2 是保护 G0 的手段，不能因工程复杂度
高就反客为主；G4 是期权，不是当前承诺。

### 17.6 接手后的执行序列

#### Wave A：本轮工程集成（已完成）

1. 根仓 PR #1805 的级联拓扑、集成、GAC、Governance、接口、证据、文档与其余 required checks
   已全部通过；
2. 已 squash merge 为 `3b251217f11a2e9dc722fc63c39620f114e548e9`；`origin/main` 中
   `projects/ecos` 指向 `fa986f0`，`projects/omo` 指向含 PR #66 的 `b479a7a`；
3. merged root SHA 已由
   `bet/BET-Y1Q3-T4-01-root-worker-origin-ack-pr1805-merged-20260821` 固定；
4. `BET-Y1Q3-T4-01` 与 workflow run 仍保持 active，**不要 close/complete**。

#### Wave B：完成唯一的人类价值门

1. 向 Human Principal 呈现 episode `episode_dfed37d14182f59457e1064d` 的 never-send 候选；
2. 只接受五种显式 verdict：`accept`、`edit`、`reject`、`defer`、`ignore`；
3. “全权委托工程决策”“继续”“按最优解”不等于候选内容 verdict；
4. 记录 verdict、必要 revision diff 与 OutcomeFeedback，但不持久化敏感正文或无关绝对路径；
5. 重放 NorthStar/MOS projector，确认只有 human-adjudicated outcome 计入价值轴。

#### Wave C：补齐运行轴而不触碰 shadow 红线

1. `T1-05A` 一周窗口到 `2026-08-22T00:06:13Z` 才结束；之后仅在 LaunchAgent、SQLite
   integrity、6 agent heartbeat/monotonic last_seen、attestation、clone cleanliness、backup N=3
   等直接证据齐全时报告 `human_gate ready`；
2. backup cron 仍指向共享 Workspace 时只报告 `FAIL/BLOCKED` 与最小修复建议，不在 shadow 巡检
   中直接改 plist/crontab/service；
3. `T7-01` 只有真实、非测试、可绑定 `human_verdict` 的 `decision_outcome` 才计入 >=20 gate；
   GitHub PR、issue comment、reviewDecision、旧 harvest 只能做供给侧诊断；
4. `T1-18` 若仍 awaiting human approval，只提醒，不发送 Orca/Codex 输入、不代点审批；settled 后
   才继续 collect/verify。

#### Wave D：完成 P0/P1 的净减法

1. capability 单一 writer + exact ID load；
2. NorthStar 拒绝 self-assert、代理量和无法绑定 principal/provenance 的结果；
3. hard-coded attribution 报告降为非权威诊断或退役；
4. clone changeset/reachability/retire 全部 fail closed；
5. replay/restore 与 evidence privacy 验收；
6. 仅当 AC-01～12 均有直接证据、retro 完整、Human Gate 通过时，才由正式 broker 推进 BET
   closeout；任何 Agent 不得自行改 done。

### 17.7 接手 Agent 的启动清单

接手者不要从聊天摘要推断当前状态，按以下顺序直接测量：

```bash
cd /Users/xiamingxing/Workspace
git status --short
git fetch origin main
git rev-parse origin/main

uv run --with pyyaml python bin/plan/bet-ledger.py show BET-Y1Q3-T4-01
uv run --with pyyaml python bin/agent-workflow.py show-run \
  20260821T020328Z-bet-execution-fa86eef6 --json
uv run --with pyyaml python bin/agent-workflow.py compliance --json

git show origin/main:docs/operations/blueprint-agent-instruction-pack-v1.md >/dev/null
git ls-tree origin/main projects/ecos projects/omo
gh pr view 1805 --json state,mergedAt,mergeCommit,statusCheckRollup
```

若继续写入：使用身份匹配的独立 clone；读取 `CLAUDE.md`、本报告、accepted Spec、Instruction
Pack 和现有 run；复用当前 BET/run 并 claim 精确路径；子仓先 PR/merge/reachability，根仓再更新
gitlink；每阶段 `add -> commit -> tag/push`；ACK 缺失、SHA 不可达或 identity 不一致时立即 fail
closed；最终分别报告 Engineering / Operational / Value。

### 17.8 可授权与不可代签的决策边界

Human Principal 已授权本轮按最优解处理工程、治理、PR、合并、恢复和文档收敛。因此接手 Agent
无需再次询问常规可逆工程步骤，应基于最小表面积、fail-closed、可回滚和直接证据自行选择。

以下事项仍必须由本人显式给出：Golden Slice 候选 verdict；高风险外发、资金、法律承诺、不可逆
删除或提高自治等级；将 shadow gate 判为 human-approved；将尚未满足全量 AC 的 BET 标记为 done。

### 17.9 当前未决与最小修复建议

| 未决 | 状态 | 最小下一步 |
|---|---|---|
| Golden Slice human verdict | `AWAITING_HUMAN` | 呈现候选，收集五选一显式 verdict |
| 根仓 PR #1805 | `MERGED/PROVEN` | 后续只做防回退验证，不重复实现或重开同类 PR |
| CodeBuddy/Reasonix worker ACK | `NOT_IMPLEMENTED` | 实现同一 `omo-worker-origin-ack/v1`，此前保持 fail closed |
| cross-process resume capability | `DEFERRED` | 设计可吊销、短时、不可重放 handoff；禁止持久化当前 proof |
| T1-05A 完整周 | `WINDOW_OPEN` | 2026-08-22T00:06:13Z 后只读复核 |
| backup cron owner | `FAIL/BLOCKED` | 在非 shadow 变更窗口切到受管 clone，并留 rollback |
| T7-01 周产 gate | `NOT_PROVEN` | 只统计真实 human-adjudicated decision_outcome |
| LaunchAgent GAC 本机检查 | `ENVIRONMENT_BLOCKED/PREEXISTING_DRIFT` | 有权限的受管运维窗口核对 plist |
| OMO DLQ SQLite 两用例 | `ENVIRONMENT_BLOCKED` | 给 `bus_foundation` 可写测试 DB 或隔离 fixture 后复跑 |
| Documents canonical 同步 | `BLOCKED_BY_GATEWAY` | Workspace 报告作工程 SSOT；gateway 可用后同步脱敏人类交接 |

### 17.10 完成定义

本计划真正完成，不是“所有 PR merged”，而是同时满足：

1. Engineering：身份链在根仓与子仓默认入口均 fail closed，CI、独立 reviewer、reachability 与
   rollback 证据可重复；
2. Operational：真实 signal/dispatch/ACK/candidate/verify/replay 在受管运行面可重复，shadow 窗口
   和 scheduler owner 没有未说明缺口；
3. Value：至少一条低敏真实候选获得本人明确 verdict，revision/outcome/provenance 被权威记录；
4. Governance：BET AC、retro、surface accounting 与文档事实一致，无 Agent 自报 done；
5. Simplification：至少两项重复/假权威资产完成退役或降级，且保护测试不下降。

在此之前，最准确的总体状态仍是：**工程脊柱已显著收敛，运行闭环部分成立，个人真实价值尚待本人
裁决证明。**

## 18. 2026-08-21 AC-05 capability 收敛增量

> 证据截止：2026-08-21T11:53:20Z。本节记录 D5/AC-05 的新工程事实，并纠正 §17 中已经漂移的
> 台账状态；它不改变 Value 轴，也不授权绕过 Golden Slice 人类裁决。

### 18.1 状态纠正

`origin/main` 上的 `BET-Y1Q3-T4-01` 已从 `blocked` 经 `candidate` 推进为 `in_progress`；根仓 PR #1827
合并为 `3caf67080c7da8cf09c72bd29f37c6eb5ab3b5a9`，权威 run_ref 为
`20260821T111433Z-bet-execution-967f03e6`。T1-19 live canary 与 `acp_stdio` 默认 transport 切换已解除
AC-06 的前置依赖，但 ledger 仍明确保留 AC-06 最终验证与 AC-11 收尾。后续 Agent 必须以实时 ledger
为准：不得沿用 §17.6 或本节早期快照，不得重新打开第二个同目标 BET，也不得因为 AC-05/T1-19
工程绿自行把原 BET 改成 `done`。Value 仍为 `NOT_PROVEN`。

### 18.2 AC-05 的最小正确边界

近期审计确认，`capability-sync find` 已能精确解析并拒绝歧义，但 Cockpit 仍存在三项高风险旧行为：

1. 用短名/子串和 first-match 选择服务；
2. 从 BOS YAML 读取 `command` 后直接 `subprocess.run`，并接受任意尾随 argv；
3. 无 invocation-time admission、lifecycle route gate、bounded health probe 或隐私安全 receipt。

本轮没有再建第二个 registry 或通用 executor，而是把调用面收敛为：

```text
canonical capability registry
  -> exact `bos-service:<bos://...>`
  -> generated registry row 与 Agora runtime service 双重一致性
  -> internal-only native adapter
  -> capability/admission lifecycle catalogs
  -> invocation-time admission
  -> exact route + bounded readiness probe
  -> explicit load 或 structured JSON invoke
  -> fixed allowlist privacy receipt
```

硬边界如下：

- `load/invoke` 只接受 exact canonical ID；`find --query` 永远不能升级为执行授权；
- 只有 generated registry 与 Agora runtime 同时声明 `active/internal` 的 BOS 服务可进入 gateway；
- caller 不能提供 command、argv、module、function、URL、adapter 或 target；
- Cockpit 只接受完整 BOS URI/canonical ID 与有界 JSON 文件，不再展示或执行 provider command；
- lifecycle catalog 缺失、admission 非 `admitted`、route 不一致、health 非 healthy 或 receipt 非法时
  全部 fail closed；
- Cockpit 把子进程回执当作不可信输入，校验 schema/operation/capability identity 后再按固定字段
  allowlist 投影，未知 payload/path/error 字段不输出。

### 18.3 已合并证据与验证

| 交付面 | 证据 | 判定 |
|---|---|---|
| CodeBuddy/Reasonix truth correction | 根仓 PR #1809，merge `1a0ce173ccfa32816623c730221270807e944164` | `PROVEN`；从 admitted 降为 declared，绑定 instruction 时在 provider parsing 前 fail closed |
| Agora native gateway | Agora PR #34，merge `cf137b1efade1da2d22d5639f38ec75cceb5373e` | `PROVEN`；exact reconcile、admission、route、probe、native invoke、privacy receipt |
| Cockpit governed invocation | Cockpit PR #70，merge `bc3e31efd541beb9c3d1b307d7f8d70e21e889f2` | `PROVEN`；移除 substring/raw command/argv，固定治理 CLI 与 receipt allowlist |
| 根仓公共 `load/invoke` 与 gitlink 集成 | 根仓 PR #1816，merge `c83ca926be1e6365403fa21854232e4c77c6d42e` | `PROVEN`；完整 CI 通过并落入 `origin/main` |

直接验证：

- 根仓 capability 契约 32 项通过；另 1 项全量 registry generator 检查因本独立 clone 未初始化全部
  项目而隔离，不是产品 RED，交由完整 GitHub checkout 复核；
- Cockpit capability + CLI 路由回归 92 项通过；changed Python Ruff 全绿；
- 完整 Agora Python 环境真实执行 `load` 时，当前 admission 返回 `ADMISSION_REQUIRED`，receipt 为
  `status=rejected`、`invocation_attempted=false`，证明它没有因本地 observe/warning 状态降级直调；
- 独立 reviewer 初审发现 plain router lifecycle 绕过与 child receipt 附加字段泄露两项 HIGH；修复后
  复审 `PASS`，并补入缺 catalog、gate-before-seed 和恶意 schema-valid receipt 负例。

早期本地 `make gac-local-gate` 的失败来自不完整独立 clone：缺 `cockpit-ui` 构建输入，以及未初始化
`scripts` 子模块导致 compatibility shim 扫描大量假缺失。补齐根仓锁定的本地子模块对象后，门禁
已复跑为 46 checks ALL GREEN；这证明早期结果属于 `ENVIRONMENT_BLOCKED`，而非 AC-05 产品失败。

### 18.4 优化后的后续顺序

1. 根仓公共 `load/invoke`、Agora/Cockpit gitlink、完整 CI 与 `origin/main` reachability 已完成；
   后续只保留回归保护，不再扩展第二调用入口。
2. AC-05 工程轴落地后停止继续扩 capability transport；HTTP/MCP/stdio 通用执行器、跨进程 proof
   持久化与更多 adapter 全部后置。
3. 下一主线仍是唯一 Golden Slice：只收集 Human Principal 对
   `episode_dfed37d14182f59457e1064d` 的显式 `accept|edit|reject|defer|ignore`；广义工程授权不计 verdict。
4. T1-05A 在 2026-08-22T00:06:13Z 后才可做完整周只读复核；backup cron owner 错误只报告并在
   非 shadow 变更窗口修复。
5. T7-01 继续只统计真实、非测试、可绑定 `human_verdict` 的 `decision_outcome`；PR、review、issue
   comment 仍只是供给侧证据。
6. T1-18 继续遵守 human approval 边界，不向既有 Orca/Codex canary 发送输入或代点审批。

因此，AC-05 的正确结论是：**capability 工程调用面已经从可模糊直执行收敛为 exact、native、
admitted、health-gated、receipt-safe 的窄入口；它提高了 G3 的完成度，但不增加任何个人价值计数。**

### 18.5 WorkPacket v2 回归与最小恢复

T1-19 residual cleanup 的根仓提交 `88dc6d651` 删除了 BET 编译侧的 instruction binding，但保留了
worker ACK validator 与四类 adapter 对该绑定的强制校验，造成默认 BET start 在 WorkPacket v2
编译阶段 fail closed。该问题不是新协议设计，而是 producer/consumer 原子性被拆开的回归。

producer 恢复已由并发根仓 PR #1825 合并为 `2099fe5ea73b9f523524bf57c28f9a3a4ac1b1bb`：重新测量唯一
instruction pack 的 ref/version/profile/content digest，并将其纳入 packet hash、read surfaces 与
start 投影。根仓 PR #1823 经直接比对后不再重复提交 producer 代码，只保留 identity、missing pack、
digest drift、direct OMO projection 等保护测试与本报告更新；状态为 `IN_REVIEW`。原始修复提交的
D0 标签 `delivery/codex-ac05-instruction-binding-20260821` 仍保留，可用于证明并发吸收前的恢复内容。

直接验证：

- `tests/test_agent_workflow.py`：61 passed；
- 真实持久化 worker identity/rehash/reconcile 定向用例：3 passed；
- `make gac-local-gate`：47 checks ALL GREEN；
- run `20260821T095209Z-bet-execution-c17c20ff` 的 workflow verify：2/2 PASS；
- Ruff、`git diff --check` 与独立只读 reviewer：PASS。

这次回归的机制教训是：WorkPacket producer、worker ACK validator、adapter consumer 与 instruction
pack fixture 必须作为一个 compatibility set 变更；后续 cleanup 若只删除其中一端，契约门禁必须
立即阻断。该修复只恢复 Engineering 身份链，不增加任何 Operational 或 Value 证明。

### 18.6 深度复核后的缺口排序与路线优化

最近迭代已经证明“能力入口收敛”和“身份 fail closed”可以落地，但也暴露出下一阶段不应继续按
组件横向扩张。按对端依赖、失败半径和 Golden Slice 贡献度重排后，唯一推荐顺序如下：

| 优先级 | 缺口 | 当前判断 | 下一验收物 |
|---|---|---|---|
| P0 | G-1 证据矩阵 | `PARTIAL`；工程证据丰富，但三轴与 AC 的直接映射仍不完整 | 每个 AC 固定 Engineering/Operational/Value 来源、命令、receipt、反证与 owner |
| P0 | `SpecLifecycle/v1` | `PARTIAL`；accepted binding 已存在，draft/review/accept/supersede/rollback 生命周期未统一 | 单一状态机、accepted decision、不可变 digest、supersede/rollback 负例 |
| P0 | 外部 Agent lifecycle adapter | `PARTIAL`；Codex/OMP/Pi/Orca 已接入，CodeBuddy/Reasonix 仅 declared 且必须 fail closed | 统一 attach/start/ack/heartbeat/result/cancel/timeout 适配契约，不允许伪 admitted |
| P1 | `ContextEnvelope/v1` | `NOT_PROVEN`；packet、spec、instruction、principal/provenance 尚未形成单一上下文载体 | 脱敏 envelope、hash identity、预算/权限边界与 consumer rehash |
| P1 | `CrossRepoDeliveryManifest/v1` | `PARTIAL`；changeset 与 claim coverage 已有，跨根仓文件/子仓 gitlink/PR/reachability 尚未单据化 | 一份可重放 manifest 覆盖 commit、gitlink、PR、CI、reachability、rollback |
| P1 | `ComputePlan/v1` | `PARTIAL`；BDSK/AetherForge 路由约束存在，任务级资源预算与运行 receipt 尚未统一 | route、预算、thermal/VRAM、fallback、actual runtime receipt 对账 |
| P0-H | 唯一 Golden Slice | `AWAITING_HUMAN`；候选已存在，human verdict 缺失 | 本人五选一 verdict 后生成 revision/outcome/provenance；任何 Agent 不得代裁决 |

执行上采用“三段单链”，避免再制造平行权威：

1. **先补证明面**：完成 G-1 矩阵与当前契约 compatibility set 门禁，让删除、替换和 cleanup 都能
   在 producer/consumer 不一致时立即失败；
2. **再补生命周期面**：优先 `SpecLifecycle/v1` 和 external-agent adapter contract，随后再把
   ContextEnvelope、CrossRepoDeliveryManifest、ComputePlan 作为同一 WorkPacket 身份链的扩展；
3. **最后只跑一个真实价值切片**：不新增 Dashboard、BET、registry 或 transport；只把现有低敏
   candidate 交给本人裁决，并用可重复读取的 revision/outcome receipt 判断是否真正产生价值。

继续推进的硬停止条件不变：没有显式 human verdict、完整 shadow 窗、真实 decision_outcome 或可重复
运行证据时，必须报告 `NOT_PROVEN`/`UNPROVABLE`，不得用 merged PR、issue comment、reviewDecision、
测试、mtime、Agent 自报或历史 harvest 替代。
