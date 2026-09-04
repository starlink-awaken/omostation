---
status: planned
lifecycle: plan
owner: governance-team
last_updated: 2026-07-31
review-state: metadata-only
metadata-migrated-at: 2026-07-31
type: ephemeral
---
# MetaOS 深度架构治理优化方案（战略 + 战术 + 落地规划）

> 日期: 2026-07-25
> 状态: 提案（待 D1–D4 决策签核后进入 Round 执行）
> 范围: `projects/metaos/` 本体 + workspace 侧 metaos 注册/引用面（registry、layer-contract、CI、能力地图）
> 依据: 2026-07-25 metaos 双路深度架构分析（本文件 §2 诊断）
> 姊妹方案: [`2026-07-25-mof-m4-governance-optimization-plan.md`](2026-07-25-mof-m4-governance-optimization-plan.md)（跨项目系统性模式并轨，见 §8）

## 1. 摘要

metaos 处于"**入口收敛完成、能力纵深待填**"的巩固期。ADR-0181 三平面契约（Policy=ecos / Decision=metaos / Execution=runtime）方向健康：独立 MCP 入口已封停、能力重叠已降级为 ecos backend、`contract_gatekeeper.py` 的 AST 级 `.omo` 禁写优于 workspace 平均水平。

当前核心问题不是架构方向，而是**三层失真**：

1. **测试失真** —— 文档宣称 100% 通过，实测 260 tests / 5 failed（bus e2e 测试与源码重构漂移）
2. **CI 失真** —— ignore 清单与代码现状双向漂移，CI 绿是假绿
3. **宣称失真** —— PID 控制/免疫三层/日课仪式等能力宣称超前于实现与消费实证

外加与 model-driven 同构的系统性模式：CLI 弃用未拆、注册面漂移、声明/执行鸿沟。

本方案给出 3 个 Phase、12 个 deliverable、4 个决策点，全部映射 Round playbook 与现有门禁。

## 2. 诊断（证据摘要）

| # | 问题 | 证据 | 性质 |
|---|------|------|------|
| Q1 | 测试宣称全绿实际 5 红 | AGENTS.md/CLAUDE.md 写"100% 通过 188 tests"、INTERFACE.yaml 写 189；实测 260 tests / 5 failed（`tests/test_workflow_bus_publish_e2e.py`，测试 patch 已不存在的 `metaos.core.workflow.requests.post` / `bus_foundation.facade`，源码已走 `integrations.bus_adapter`） | P71 类 A 声明/执行鸿沟（最刺眼） |
| Q2 | CI 与本地双向漂移 | `metaos-ci.yml` --ignore 3 文件（chaos_workflow/workflow_engine/workflow_mvp，标 P41-W1 债）本地实际能过；CI 未排除的 bus e2e 本地红 | 假绿门禁 |
| Q3 | 双入口债 | `metaos.py` / `metaos_main.py` 功能等价需同步改（AGENTS.md 自承）；均打印 deprecated 但都被 cockpit shell 调用 | 双入口冗余 |
| Q4 | 能力虚标 | `l2_controller.py` PID 自标 READONLY prototype 不生效；免疫三层/日课无跨仓消费实证；M1 `SPEC-OMO-DESIGN-metaos-gap-analysis` 自认 Shell vs. Target 鸿沟 | 宣称超前实现 |
| Q5 | 版本残留 | `mcp_server.py:398` serverInfo 硬编码 `"7.1.0"`（版本已归一 1.0.0） | 遗留痕迹 |
| Q6 | workspace 注册面漂移 | `projects-capabilities.yaml:201-216` 残留 `kairon.metaos` 死条目（路径已不存在）；`phase-scope.yaml:56` 引用不存在的 `src/metaos/leap/**`；submodule_policy 分支名与实际 `reconcile/p45-20260717` 不符 | P71 类 A（跨项目同构） |
| Q7 | 代码瑕疵 | `cli/__init__.py:157` 包外相对导入（非包布局 ImportError）；`status()` 重复定义（noqa F811） | 技术债 |
| Q8 | agentkit 未收敛 | `tools/metaos-agentkit` CONVERGENCE.md 自承"v0.2 才接 bridge"，provider 端不强制会话门控 | 半建 |
| Q9 | admit 检查非阻塞 | governance-check.yml 中 `metaos admit` 为 informational non-blocking | 门禁无牙 |

## 3. 战略目标与北极星

**北极星（12 周）**：metaos 达到"**绿是真的绿、宣称=实现、入口单轨**"，且能力纵深按消费驱动补齐，不回退任何现有门禁。

三条战略主线：

- **S1 诚实优先（Honesty First）**：先修"宣称/门禁/实现"三层失真。假绿比红更危险——它让后续所有变更失去安全网。这是全部工作的第一优先级，也是战术上的 P0。
- **S2 消费驱动纵深（Demand-driven Depth）**：能力纵深不为宣称补实现，而为真实消费者补实现。omo self-healing 已在调 `metaos run`（真实消费实证），能力补齐围绕这类已存在的消费链展开；无消费者的宣称一律降级。
- **S3 守住收敛成果（Guard the Convergence）**：ADR-0181 的三平面收敛是本项目最正确的决策，所有优化不得回退它——不加回独立 MCP 入口、不让 metaos 越界写 `.omo`、不绕过 cockpit 新增人类入口。

**战术原则**：
- 每 Phase 内部按"先实证、再修声明、后补实现"排序——先让测量说真话。
- 所有修复以测试先行：Q1 的 5 红修好后必须进 CI 且不可 ignore。
- 与 MOF/M4 方案并轨的项（注册面漂移门）不重复建设，直接扩展其覆盖面（见 §8）。

## 4. 治理原则（不可违反）

- **ADR-0181 三平面不回退**：Policy=ecos / Decision=metaos / Execution=runtime。
- **ADR-0217 跨层桥接白名单**：ecos→metaos、metaos→agora 的既有登记不滥用，新增跨层依赖必须登记 ADR。
- **`.omo` 写入红线**：保持 `contract_gatekeeper.py` AST 级禁写，任何新写面必须走 broker。
- **P74 / ADR-0203**：每 deliverable 走 workflow run 留 evidence；新检查注册 `diff_checks`。
- **Round 纪律**：每 Phase 走完 7 步闭环，相关测试套件不回退。

## 5. 分阶段落地规划

### Phase 0 — 让绿是真的绿（Week 0–2，R-patch 型，1 ADR）

目标：消灭测试/CI/文档三层失真，恢复安全网可信度。

| Deliverable | 内容 | 验证 |
|---|---|---|
| P0-1 修复 5 红测试 | `test_workflow_bus_publish_e2e.py` 的 patch 目标改为 `integrations.bus_adapter` 实际路径，与源码对齐 | 本地 `uv run pytest tests/ -q` 260/260 全绿 |
| P0-2 CI ignore 清单对账 | 移除已过期的 3 个 ignore（chaos_workflow/workflow_engine/workflow_mvp，本地实证能过）；修复后 bus e2e 纳入 CI；原则：**CI 跑的东西必须等于本地跑的东西** | metaos-ci.yml 全量绿；ignore 清单归零或仅剩带 ADR 锚的豁免 |
| P0-3 文档数字收口 | AGENTS.md/CLAUDE.md/INTERFACE.yaml 的测试数与通过率改为指针或 `as_of` 快照 | diff review；后续由 P0-4 防复发 |
| P0-4 版本与残留清理 | `mcp_server.py` serverInfo `7.1.0` → 读取 pyproject 版本；顺手修 `cli/__init__.py:157` 包外导入与 `status()` 重复定义 | ruff 无 noqa F811 压制；非包布局导入测试 |
| P0-5 失真防复发门 | metaos-ci.yml 增加"宣称对账"步骤：文档中的测试计数/通过率声明与 pytest 实跑输出比对（或彻底指针化后此门退化删除） | CI 注入失真可检出 |

退出标准：本地与 CI 全量绿且一致；宣称=实测。

### Phase 1 — 入口单轨与注册面守自（Week 2–6，R-feature 型，2–3 ADR）

目标：消灭双入口，注册面零漂移，能力宣称对齐实现。

| Deliverable | 内容 | 验证 |
|---|---|---|
| P1-1 双入口合并 | `metaos.py` / `metaos_main.py` 合并为单一入口（保留一个薄 shim 防外部引用断裂，标 deprecated 指向主入口） | cockpit `workflow plan/run/history/approve` 全链路回归 |
| P1-2 CLI 定位正名（依赖 D1） | 推荐：承认 CLI 是 cockpit 的稳定 subprocess 契约，**移除弃用警告**，改为定位说明（"人类入口请用 cockpit，本 CLI 是 cockpit 的后端契约"）；同时推动 cockpit 侧从 shell 逐步切 import adapter（cockpit adapters/metaos.py 已存在，长期方向） | 警告消除；adapter 路径与 shell 路径行为快照一致 |
| P1-3 workspace 注册面修复 | 清 `projects-capabilities.yaml` 的 `kairon.metaos` 死条目、`phase-scope.yaml` 的 `leap/**` 死路径、submodule_policy 分支名 | 对应 registry 校验通过 |
| P1-4 注册面漂移门扩展 | 把 MOF/M4 方案 P0-2 的漂移门覆盖面扩展到 metaos 相关 registry（path 存在性 + 分支名 + entrypoint 可达性）——**不新建门，扩展现有门** | 注入漂移可检出 |
| P1-5 能力宣称对账 | `docs/FUNCTIONAL-CAPABILITY-MAP.md` 的 metaos 条目逐项标注：已实现且有消费实证 / 已实现无消费 / prototype / 宣称超前；超前项降级 | 能力地图与实证一致 |

退出标准：单入口；注册面漂移门覆盖 metaos 且全绿；能力宣称=实证。

### Phase 2 — 能力纵深与门禁长牙（Week 6–12，R-meta 型，3–4 ADR）

目标：围绕真实消费链补能力纵深，门禁从 informational 变 blocking。

| Deliverable | 内容 | 验证 |
|---|---|---|
| P2-1 免疫闭环接通 | omo `self_healing` 已调 `metaos run`（真实消费实证）——把 ImmuneMonitor 的 WARNING→FREEZE→MELTDOWN 状态经 bus-foundation 事件回传 omo，形成"检测→熔断→自愈触发→evidence"闭环 | 端到端场景测试（注入熔断→观察 omo 自愈触发）；evidence 落 `.omo` 经 broker |
| P2-2 PID 控制器处置（依赖 D2） | 推荐：**正式标记 experimental**（模块级状态声明 + 能力地图降级），不接执行面；待有真实调参需求再激活。激活路径需另立 ADR | 能力地图与代码声明一致 |
| P2-3 agentkit 收敛（依赖 D3） | 推荐：按 CONVERGENCE.md 兑现 v0.2——provider 端强制会话门控（prepare/finalize 经 AgentRuntimeService），或显式降级为 reference implementation 声明 | 会话门控强制路径测试；或声明降级文档化 |
| P2-4 admit 门禁长牙（依赖 D4） | `metaos admit --domain ci` 从 informational 转 blocking（先观察期 2 周收集误拦数据，再切换） | governance-check.yml blocking 且无误拦 backlog |
| P2-5 日课仪式处置 | daily-health/quarterly-review 两个 cron job 已有 runtime 接线（l4_scheduled_jobs.yaml）——核实产出是否有人消费；无人消费则降级或下线，有消费则补 evidence 链 | job 产出消费实证或下线记录 |

退出标准：免疫闭环端到端可演示；无 prototype 冒充能力；admit 门禁 blocking。

## 6. 决策点（需签核后才进入对应 Phase）

| # | 决策 | 选项 | 推荐 | 影响 |
|---|------|------|------|------|
| D1 | CLI 定位 | A 承认 CLI 为 cockpit 稳定契约并正名 / B 彻底删除 CLI 强制 cockpit 走 import adapter | **A**——subprocess 契约隔离性更好（模块崩不拖垮 cockpit），且 cockpit 侧改动为零；B 作为长期方向记录 | Phase 1 工作量 ±3 天 |
| D2 | PID 控制器 | A 标记 experimental 降级 / B 激活接执行面 | **A**——无真实调参消费者；激活需另立 ADR 评估风险 | 仅声明变更 |
| D3 | agentkit | A 兑现 v0.2 强制门控 / B 降级为 reference implementation | **A**——agent 会话门控与 workspace agent-runtime 方向一致，有战略价值；若无排期则 B 兜底 | Phase 2 工作量 +1 周（选 A） |
| D4 | admit 门禁 | A 转 blocking（先 2 周观察期）/ B 维持 informational | **A**——informational 门禁等于没门禁；观察期控制误拦风险 | CI 行为变更 |

## 7. 度量与门禁（KPI）

| 指标 | 基线（2026-07-25） | 目标（12 周） | 测量 |
|---|---|---|---|
| 测试真实通过率 | 255/260（宣称 188 全绿） | 全量绿，宣称=实测 | pytest 实跑 |
| CI/本地一致性 | 双向漂移（3 ignore + 1 红区错位） | CI ≡ 本地 | CI 配置 diff |
| workspace 注册面漂移 | 3 处（Q6） | 0，且由漂移门机器守住 | P1-4 扩展门 |
| 能力宣称符合度 | ≥4 项超前宣称（Q4） | 宣称=实证 | 能力地图对账 |
| 入口数 | 2 等价入口 + deprecated MCP | 1 主入口 + shim | 代码结构 |
| admit 门禁 | informational | blocking | governance-check.yml |
| 免疫闭环 | 无跨仓消费 | omo 自愈端到端接通 | 场景测试 |

## 8. 与 MOF/M4 方案的并轨（跨项目系统性模式）

两个方案的诊断高度同构，执行时应并轨而非重复建设：

| 系统性模式 | MOF/M4 方案 | metaos 方案 | 并轨方式 |
|---|---|---|---|
| 注册面漂移 | P0-2 新建漂移门 | P1-4 | **同一扇门扩展覆盖**，注册清单进 SSOT |
| CLI 弃用未拆 | D1（推荐删除） | D1（推荐正名保留） | 不同结论——model-driven CLI 无消费者可删，metaos CLI 是 cockpit 活契约应正名；**按消费实证定去留，不搞一刀切** |
| 声明/执行鸿沟 | 文档数字失真 | 测试/CI/宣称三层失真 | 共用"宣称对账"检查范式（P0-5 与 MOF/M4 P0-3 同构） |
| 接口半建 | MCP 面冻结 | agentkit 收敛 | 统一原则：无消费者冻结，有消费者补齐 |

## 9. 风险与回滚

| 风险 | 等级 | 缓解 / 回滚 |
|---|---|---|
| P0-2 放开 ignore 后 CI 暴露历史红 | 中 | 先在本地全量验证再改 CI；若暴露非本次引入的红，登记 debt + ADR 锚豁免，不回滚 ignore 移除 |
| P1-1 双入口合并断裂外部引用 | 中 | 保留 shim；全 workspace grep `metaos_main` 引用点逐一核对（已知 cockpit shell 走 `python -m metaos.cli`，不受影响） |
| P2-4 admit 转 blocking 误拦 CI | 高 | 2 周观察期收集误拦率；误拦案例先修 admit 规则再切换；回滚 = revert 单行 CI 配置 |
| P2-1 免疫闭环引入跨仓耦合 | 中 | 事件走 bus-foundation 软接线（metaos 已有 bus_adapter 先例），omo 侧消费降级为可选 |
| 多 agent 并发改 metaos 子模块 | 中 | 子模块内独立仓 + 主仓 worktree+PR；ADR 先占号 |

## 10. 执行纪律与时间线

```
Week 0-2   Phase 0（R-patch）: P0-1..P0-5  → ADR-02xx（测试/CI 诚实化）
Week 2-6   Phase 1（R-feature）: P1-1..P1-5 → ADR-02xx（入口单轨）+ ADR-02xx（注册面扩展）
Week 6-12  Phase 2（R-meta）: P2-1..P2-5   → ADR-02xx（免疫闭环）+ ADR-02xx（agentkit/admit）
```

每 deliverable 一个 PR（单 lane），ADR 先占号（`bin/adr/next-adr-id.py --session <s> --claim`），子模块内先合、主仓更新 pointer。依赖决策点签核（D1–D4）。

## 11. 本方案的边界（明确不做）

- 不加回 metaos 独立 MCP 入口（ADR-0181 封顶成果不回退）
- 不为无消费者的宣称补实现（S2 消费驱动原则）
- 不动 ecos workflow fabric 的 backend 注册关系
- PID 激活、真 codegen 式能力扩张不在本方案（需另立 ADR）
- 不新建跨项目门禁框架——扩展现有门（§8 并轨）

## 12. 下一步

1. 签核 D1–D4（建议全选推荐项；D3 若排期紧张可选 B 兜底）
2. Phase 0 起 `project-code-change` run（metaos 子模块内）执行 P0-1/P0-2——这是全方案最优先项，恢复安全网
3. 与 MOF/M4 方案 Phase 0 可并行（不同子模块，无文件冲突）

---

## as_of: 2026-07-27（P0-D 附录·防脱钩锚点）

> 本子方案作为 master plan (`2026-07-27-integrated-governance-optimization-master-plan.md`) 的战术附件。
> **as_of 基线**: 2026-07-27。此后 workspace 持续演进, 本方案的"现状描述"可能已脱钩。
> **执行前必须**: 对照 master plan §P0 已落地项核实（三把锁接线 / 4 空 type / 44 dead entry 清理 / bus optional extra）, 勿凭本子方案的旧状态判断。
> **已变化项**（P0 后）: 见 master plan + gac-local-gate DEFAULT_POLICY（drift/doc-claims/layer-call-direction 已接）+ projects-capabilities.yaml（44 dead 已清）。
