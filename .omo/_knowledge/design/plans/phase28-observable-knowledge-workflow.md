---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# Phase 28 — 可观测的知识工作流 (Observable Knowledge Workflow)

> 入口门控: phase27_completed
> 主题: 从"架构完善度"切换到"每天解决一个真实问题"

---

## 背景

Phase 27 完成了 OMO 蜂群网络纪元的四大目标（Agora MCP 隔离、算力调度统一、图谱记忆共享、OMO MCP 化），架构治理能力已充分验证。Phase 28 的核心命题是：**系统能否为用户产生每天可感知的价值？**

SystemsThinking 审计（2026-06-05）识别出两个核心系统原型：
- **成长上限**：认知负担（25 包 + 4 平面治理）制约增强回路
- **舍本逐末**：治理质量成了目标本身，缺乏真实用户场景验证

---

## 目标

| ID | 描述 | KPI | Wave |
|----|------|-----|------|
| G28.0 | 北极星定义 + 工具热力图 | 写出 2-3 个具体日常场景；输出零调用工具清单 | W0 |
| G28.1 | E2E 可演示知识工作流 | 1 个研究场景从输入到带来源报告全链路，30 秒可演示 | W1 |
| G28.2 | 包瘦身 | kairon 包数量从 25+ → 20 以内，归档低使用率包 | W2 |
| G28.3 | ADR 制度化 | `.omo/_knowledge/decisions/` 建立，写入前 3 条 ADR | W3 |

---

## Wave 规划

### Wave 0 — 北极星定义 & 热力图（入门门控）

**核心原则**：没有北极星场景，不开 Phase 28 正式执行。

任务：
- `P28-W0-NORTH-STAR`（**人类完成**）：写下 2-3 个"我每天会用 omostation 做的具体事情"，记录到 `.omo/_control/north-star.md`
- `P28-W0-TOOL-HEATMAP`（Agent 执行）：分析 Agora trace log + agora-routes.json，输出工具调用热力图，标注零调用候选

### Wave 1 — E2E 可演示场景

选定 1 个来自北极星清单的研究场景，打通：
```
用户输入 → KOS 搜索 → kairon 推理/研究 → gbrain 知识持久化 → 带来源的知识报告输出
```

验收标准：**30 秒可演示**（非仅测试通过）。

任务：`P28-W1-E2E-DEMO`

### Wave 2 — 包瘦身

目标：25+ 包 → 20 包以内。

归档候选（基于热力图结果）：
- `wksp`（零测试，疑似遗留）
- `kairon-assistant`（状态待评估）
- `kairon-voice`（状态待评估）

任务：`P28-W2-PKG-SLIM`

### Wave 3 — ADR 制度化

建立 `.omo/_knowledge/decisions/` 目录，首批 ADR：
- ADR-001: Agora 作为唯一 MCP 网关（Phase 27 决策）
- ADR-002: gbrain Postgres 作为知识持久层（Phase 27 决策）
- ADR-003: OMO MCP Server 防越权机制（Phase 27 决策）

任务：`P28-W3-ADR-SETUP`

---

## 验收标准

Phase 28 完成条件：
1. ✅ 北极星场景文档存在（人类签署）
2. ✅ 工具热力图已生成，零调用工具已处理（归档或保留说明）
3. ✅ E2E 场景可在 30 秒内演示
4. ✅ kairon 包数量 ≤ 20
5. ✅ ADR 目录建立，至少 3 条 ADR 写入

---

## 风险

| 风险 | 缓解 |
|------|------|
| 北极星场景定义困难（用户没有具体用例）| W0 阻塞整个 Phase，必须人类完成再开展 W1 |
| 包归档引入回归 | 每次归档前必须跑 `make kairon-test` 确认无破坏性影响 |
| ADR 写完无人维护 | 每个 Phase 关闭前检查 decisions/ 是否有新决策未记录 |

---

*创建: 2026-06-05 · 来源: SystemsThinking 审计建议*
