# 共享任务池

> 所有 agent 在此认领和更新任务。状态: backlog | ready | in_progress | review | done
> 最后更新: 2026-05-27

---

## Phase 6X: L1/L2/X1/X2 完成化 + X3 规划

> 战略目标：补齐基础设施缺口，所有层 ≥ 90%
> 总估时：~6h | 状态: **done** (2026-05-27 全部完成)

### Wave L1-1: 契约版本化 ✅

| ID | Task | 状态 | Owner |
|----|------|------|-------|
| L1-1.1 | 写契约版本化策略文档 (41-L1-契约版本化策略.md) | **done** | laowang |
| L1-1.2 | SSOT新增 version_consistency pattern + 测试 | **done** (50 passed) | laowang |
| L1-1.3 | kronos 删独立 pipeline-schemas.json, 改import eidos | **done** (+eidos-deps.json) | laowang |

### Wave L2-1: Resource Accounting ✅

| ID | Task | 状态 | Owner |
|----|------|------|-------|
| L2-1.1 | ResourceAccounting 数据模型 + DB schema | **done** | laowang |
| L2-1.2 | MCP 调用拦截中间件 + 日志写入 | **done** | laowang |
| L2-1.3 | CLI 查询命令 (cost/top/quota) | **done** | laowang |
| L2-1.4 | 单元测试 + E2E | **done** (16 passed) | laowang |

### Wave X1-1: 治理自动化 ✅

| ID | Task | 状态 | Owner |
|----|------|------|-------|
| X1-1.1 | arcnode report cron 脚本 + 微信推送 | **done** | laowang |
| X1-1.2 | arcnode drift-alert 脚本 (熵阈值检查+告警) | **done** | laowang |
| X1-1.3 | arcnode validate --all 覆盖所有24项目 | **done** | laowang |
| X1-1.4 | 覆盖率合规报告生成 | **done** | laowang |

### Wave X2-1: 抗熵管线 ✅

| ID | Task | 状态 | Owner |
|----|------|------|-------|
| X2-1.1 | arcnode-evolve 脚本 (熵检测→建议→auto-fix) | **done** | laowang |
| X2-1.2 | cron 管线串联 (freshness→health→dual-baseline→archive) | **done** (4/4 pass) | laowang |
| X2-1.3 | auto-archive 脚本实际归档逻辑 | **done** | laowang |
| X2-1.4 | 自回收规则实装 (6月未触发→暂停保鲜) | **done** | laowang |

### Wave X3-1: 价值堆栈规划 ✅

| ID | Task | 状态 | Owner |
|----|------|------|-------|
| X3-1.1 | 写42-X3-价值堆栈策略.md (7层+半衰期+保险+集成) | **done** | laowang |
| X3-1.2 | X3↔L1 schema 集成分析 | **done** | laowang |
| X3-1.3 | X3↔X2 cron 集成分析 | **done** | laowang |

---

## Phase 1-6, 8-12, W (已归档，可查看 TASK_POOL.md 完整版)

---

## 认领规则

1. 从 `plan` 中选一个 task，标记 `in_progress` + 填 Owner
2. 完成后标记 `review`
3. 验收通过 → 标记 `done`
4. 同时认领不超过 2 个 task
