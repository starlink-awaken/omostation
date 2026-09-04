---
lifecycle: history
owner: governance-team
last_updated: 2026-08-25
type: ephemeral
---

# resident 常驻体系与治理接线深度复盘

> BET-Y1Q3-T6-14 · 项目粒度复盘 · 基于 2026-08-24T22:28Z 实测数据
> 范围：resident 五类角色运行时 + 治理接线（MOF/SGF/BOS、agent-workflow 契约、gac-local-gate、PR 工作流、MCP 工具）
> 本文只沉淀分析结论，不改动 resident 运行时行为或治理接线代码。

## 0. 实测基线（2026-08-24T22:28Z, `omo resident status`）

| 组件 | 实测值 | 判定 |
|------|--------|------|
| health | `recovered`，degraded_components=[] | ✅ |
| daemon | 最后一次 tick 10s 前；byte_offset=1,554,794（水位新鲜 ≤30min） | ✅ |
| events | 2,159 行 / 1,554,794 bytes；输入流 idle 33,320s（≈9.25h） | ⚠️ |
| sediment | 290 runs + 115 failures = 405 total（失败率 **28.4%**） | ⚠️ |
| alert | watermark 120,686 bytes，watermark_set=true | ✅ |
| ledger | chain ok，sequence=39 | ✅ |

水位文件：`resident-decision/execute/heartbeat/monitor/sediment/sub` 六件齐备。
治理检查：`CR-RESIDENT-STATUS-01` PASS（daemon 水位活性 ≤1800s 阈值）。

## 1. 目标与愿景

resident 体系（ADR-0396 DigitalAgent，tier=resident）的目标是打破"一次性会话"模式：
以**事件驱动常驻节点**替代"按需拉起 agent"，让五类角色（记忆沉淀/大脑决策/手执行/眼睛监控/心脏心跳）订阅 workflow-mesh 事件流，以独立 projector + topic_filter 并行推进各自水位，最终把运行经验持续沉淀为可复用知识。

愿景达成度评估：**架构接线已闭环，知识价值尚未兑现**。运行时（五类角色、路由表、水位、ledger）全部就位且健康（recovered），但沉淀产出的 405 条 sediment 全部是模板占位（见 §4），事件流 idle 9.25h 说明"持续进化"的数据源近期近乎停摆。即：**管道建好了，但没有东西在流**。

## 2. 场景与功能

实测存在的功能面（对照 `omo resident roles` + `resident-routes.yaml`）：

| 角色 | 订阅事件子集 | handler | 实测功能状态 |
|------|-------------|---------|-------------|
| sediment 记忆沉淀 | WorkflowClosed / WorkflowSucceeded / PersonalSignal | knowledge_sediment | ✅ 事件→草稿模板生成 |
| decision 大脑决策 | WorkflowFailed / StepFailed / StepTimeout | decision_agent | ✅ 失败→决策提案（水位文件在） |
| execute 手执行 | ExecutionRequested / WorkPacketDispatched | execution_agent | ✅ 执行请求→pi-worker（safe=false 需批准门）|
| monitor 眼睛监控 | system.health / governance:gate_failed / alert | alert | ✅ 可观测→告警（watermark 120,686B）|
| heartbeat 心脏心跳 | heartbeat / system.alive | heartbeat | ⚠️ 预留占位，无实际心跳消费者 |

事件类型实测分布（2,159 事件）：WorkflowRequested 716 / WorkflowAdmitted 288 / StepDispatched 288 / StepStarted 288 / WorkflowClosed 268 / WorkflowSucceeded 169 / **StepFailed 119** / EvidenceRecorded 20 / PersonalSignal 2 / ExecutionRequested 1。

关键功能发现：
- **execute 角色近乎空转**：ExecutionRequested 全流仅 1 条，WorkPacketDispatched 0 条——"手执行"管道存在但无真实工作包流过。
- **decision 角色消费失败事件**：119 条 StepFailed + 1 条 ExecutionRequested 是 decision 的真实输入；但决策提案的实际产出未见沉淀到可检索位置（仅水位文件）。
- **monitor 角色正常**：告警水位持续前进（120,686B），是五类角色中唯一持续消费的。

## 3. 用户旅程 (User Journey)

实测支持的用户旅程三段式：

1. **注入**：人类通过 `cockpit decide`（或 CodeBuddy personal-signals 文件，WP-D，已注册 signal-sources `scene_binding: personal-steward`）把意图注入事件流 → PersonalSignal 事件（全流仅 2 条）。
2. **自治处理**：事件经 `resident-routes.yaml` 规则路由 → 五类角色并行消费。失败走 decision_agent（提案），成功走 knowledge_sediment（沉淀草稿）。
3. **监督回收**：人类通过 `cockpit resident status` / `make resident-status` 查看运行状态，通过 `SWARM_ESCAPE_ID` 逃生口处理异常，最终人类仅需监督不需微操。

旅程堵点（实测）：**注入端几乎无流量**（PersonalSignal 2/2159、ExecutionRequested 1/2159）→ 中间管道空转（daemon 每次 tick processed=0）→ 沉淀端产出模板。用户旅程实际停在"注入即完成"，自治闭环未产生真实业务价值。

## 4. 体验评估

正向：**治理体验**上，`make resident-status`（0.2s 快照）、Agora MCP `resident_status/roles`、BOS URI 三入口一致（同一 `omo resident` SSOT 委派），五类角色状态一屏可见。水位 + ledger 哈希链（sequence=39, chain ok）提供了可审计的运行轨迹。

负向（核心体验缺陷）：
- **sediment 产出 100% 是模板占位**。抽查 405 条 sediment（runs + failures）均为"待补充：计划 vs 实际 / 结果与证据 / 关键发现 / 净增减 / 交接建议"的空复选框——事件只是生成带元数据的草稿外壳，**没有任何一篇完成真正的五问知识提炼**。这使"知识沉淀"名存实亡。
- **daemon 每次 tick 处理 0 事件**（`events_in_file: 2159, processed: 0`），因为 byte_offset 已到文件尾——不是 bug，但暴露"水位判活性"的盲区：**系统 health=recovered 但实质空闲 9.25h**，"活性"度量的是一根停摆的管道。
- sediment 失败率 28.4%（115/405）：failure 文件同样是模板，**没有失败根因分类**，失败沉淀没有变成可检索的避坑知识。

## 5. 长期运营与运维

现状（实测）：cron 驱动（每 2min 五类 daemon --once --role + 每 5min signals/alert），**无常驻进程**，以 byte_offset 水位判活性（stale >1800s → degraded，CR-RESIDENT-STATUS-01 兜底）。daemon.log 显示每次 tick 正常注册 handlers。

运维画像：
- 好：幂等、无状态、进程即弃（cron 一次 tick 即退出），崩溃自愈成本低；水位文件 6 件持久化在 `.omo/_delivery/resident-orchestrator/watermarks/`。
- 隐患 1：**活性度量与价值度量脱钩**——水位"新鲜"只证明 daemon 在 tick，不证明事件在流、知识在沉淀。§0 中 health=recovered 与 idle 9.25h + 模板产出并存即为证据。
- 隐患 2：**信号输入通道单一且弱**——personal-signals 仅 2 条，说明依赖手工投喂而非自动接入 workflow 生命周期。
- 隐患 3：sediment 模板无自动升级路径——事件生成的 draft 草稿没有任何后续 agent/机制把它补成完整 retro/pattern（模板里留了 checkbox 但无人勾）。

演进方向（与现有规划一致）：全托管 Agent 虚拟机（omlxc）转移运行时，彻底脱离人类主机；同时需补一条"草稿→完整知识"的晋升管线（resident promote 场景升迁已列 CLI，但未见实际消费）。

## 6. 防腐与约束接线

实测接线状态（全部落点已确认）：

| 接线面 | 落点 | 状态 |
|--------|------|------|
| MOF 元模型 | `.omo/_truth/registry/mof-m2-extensions/digital_agent.yaml`：extends Agent, tier=[resident, on_demand, emergent]（ADR-0396） | ✅ |
| L0 约束 | CR-RESIDENT-STATUS-01（水位活性 ≤30min）、CR-RESIDENT-MOF-SYNC-01（五类角色双份对齐 roles.py↔文档） | ✅ |
| Agora MCP | `tools_resident.py` → `resident_status` / `resident_roles`（委派 `omo resident status/roles`） | ✅ |
| cron | `install-resident-cron.sh`：每 2min 角色化 daemon + 每 5min signals/alert | ✅ |
| Makefile | `resident-status` / `resident-roles` / `resident-daemon` 等 12 目标 | ✅ |
| GAC Gate | `bin/gac/check-resident-status.py`（CR-RESIDENT-STATUS-01 实测 PASS） | ✅ |
| signal-sources | `scene_binding: personal-steward`, path `~/.codebuddy/personal-signals/`（WP-D） | ✅ |

防腐设计评估：
- **批准门**：execute 角色 `safe: false`（ExecutionRequested/WorkPacketDispatched 需人工批准门）——对"手执行"类自治动作保留人类否决权，设计正确。
- **领域隔离**：五类角色独立 projector + topic_filter（M4.2/M4.3），事件分片互不干扰，实测水位文件六件独立推进，符合设计。
- **防失控**：事件→handler 全部走路由表（schema resident-routes/v1），无事件类型可绕过路由直呼 handler；GAC Gate 用 yaml schema + AST 拦截危险动作。

防腐缺口：**decision 提案缺少可观测出口**。decision_agent 的产出（决策提案）只有水位文件计数，没有沉淀到可检索的 `.omo/_knowledge/` 或提案收件箱，导致"大脑决策"既无输入追踪（输入是 StepFailed）也无输出审计。

## 7. 约束 (Constraints)

- **运行时不可改**：本 BET 仅沉淀分析结论（non_goals），所有实测均只读。
- **无常驻进程**：架构刻意选 cron+水位而非常驻 daemon——运维需接受"活性=水位新鲜度"的代理度量及其盲区（§5 隐患 1）。
- **事件流依赖上游**：resident 是消费端，事件源（workflow-mesh）不产生事件则体系空转——idle 9.25h 是上游供给问题，不是 resident 自身故障。
- **spec 契约**：canonical spec binding 强制 status=accepted；`accepted-specifications` surface 已原生存在（document-governance.yaml，valid_statuses 含 accepted），25 份 spec 全部通过校验，无需 legacy exception（E4 已闭环）。

## 8. 结论与下一步

**总体结论**：resident 体系是**接线完整、价值未兑现**的系统。运行时五类角色、路由表、水位、ledger、治理接线（MOF/L0/MCP/cron/GAC）全部实测就位且健康；但知识沉淀产出 100% 为模板占位、事件流 idle 9.25h、execute/decision 角色近乎空转——"事件驱动持续进化"的愿景尚未转化为实际知识资产。

**已闭环项**：
- E4 accepted-specifications surface 原生建立，25 份 spec 全过校验（无需扩大 legacy exception）。
- E3 platform-rebase 退役 provenance spec 已入库（accepted），绑定 BET-Y1Q3-T1-11 follow-up。

**下一步（建议另开 bet，不在本 BET 实施）**：
1. **T1-11（已登记）**：platform-rebase clone 退役 provenance 收敛实施。
2. **新 follow-up 候选**：sediment 模板→完整知识晋升管线（promote 场景升迁落地）；decision 提案可观测出口；事件源接入自动 workflow 生命周期（解决 idle 空转）。
