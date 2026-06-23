---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Governance Phase 3 — 统一入口建立

> 周期: 2026-06-03 ~ 2026-06-07 (5天) | 负责人: sisyphus (P9)
> 目标: workspace 成为唯一用户入口

---

## Sprint 3.1: workspace CLI 完善（2 天）

### Wave 3.1.A — workspace status（P8: prometheus）

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T042 | `workspace status` 统一展示：agora health + 研究历史 + 各服务端口 | 输出格式与 USER_JOURNEYS.md 一致 | 1h |
| T043 | 服务健康状态自动聚合（agora health → 结构化数据） | `status` 中的服务状态与 `agora health` 一致 | 30min |
| T044 | 最近研究历史嵌入 status 输出 | `status` 输出包含最近 3 条研究 | 20min |

### Wave 3.1.B — workspace demo 完整版（P8: prometheus + P7: epimetheus）

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T045 | `workspace demo` 4 步完整版：health → research → list → status | 每一步有成功标记 + 关键数据展示 | 45min |
| T046 | demo 结束后输出 "接下来可以" 引导 | 输出 `workspace research "xxx"` / `workspace status` 等建议 | 15min |
| T047 | demo 首次运行前自动 setup 检查（agora 是否启动、minerva 是否安装） | 缺少组件时输出 `brew install` / `pip install` 命令 | 30min |

---

## Sprint 3.2: AgentMesh 链路验证（3 天）

### Wave 3.2.A — AgentMesh 可用性验证（P8: prometheus）

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T048 | agentmesh 编译验证：`cd agentmesh && bun run build` | 0 编译错误 | 30min |
| T049 | agentmesh CLI 基础功能测试 | `agentmesh --help` 输出有效 | 20min |
| T050 | WorkspaceMCPClient → Agora 链路测试 | toolkit 能通过 agora 发现并调用 minerva MCP | 1h |

### Wave 3.2.B — 废弃清理（P8: prometheus）

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T051 | agora monitoring/ 模块加 `@deprecated` 标注 | `agora health` 仍然可用，但 import 时有 deprecation warning | 15min |
| T052 | MetaOS 判定结果落地：归档 or 补 README | 在 AGENTS.md 和 STATE.md 中记录决策 | 30min |
| T053 | SSOT 判定结果落地：归档 or 补 README | 同上 | 30min |

---

## 依赖关系

```
T042 ──→ T043 ──→ T044
T040 ──→ T045 ──→ T046 ──→ T047
T048 ──→ T049 ──→ T050
T051/T052/T053 (可以并行)
```

## Phase 3 门禁

```
☐ `workspace status` 统一展示 agora health + 研究历史
☐ `workspace demo` 30 秒内跑通 4 步
☐ agentmesh 编译 0 错误
☐ WorkspaceMCPClient → Agora → minerva 链路验证通过
☐ MetaOS/SSOT 判定已落地
```
