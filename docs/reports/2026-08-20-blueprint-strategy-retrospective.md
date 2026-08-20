---
title: 织星近期架构、战略与执行体系深度复盘
date: 2026-08-20
status: active-baseline
bet_id: BET-Y1Q3-T4-01
evidence_cutoff: 2026-08-20T04:10:00Z
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
