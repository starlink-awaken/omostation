---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# 使用文档 — `_knowledge/usage/`

> 上手指南、CLI 规范、使用说明。回答"我怎么用它？"

---

## 使用指南

| 文件 | 用途 | 位置 |
|------|------|------|
| [ONBOARDING.md](../../ONBOARDING.md) | 新人上手指南（治理知识库入门） | 顶层 |
| [CLI-MCP-SPEC.md](CLI-MCP-SPEC.md) | CLI/MCP 实验脚本规范 | 顶层 |
| [scripts/sync-omo-state.sh](../../../scripts/sync-omo-state.sh) | 刷新 `.omo/state/system.yaml` 的统一入口 | repo `scripts/` |
| [scripts/phase3_acceptance.py](../../../scripts/phase3_acceptance.py) | 运行 Phase 3 acceptance baseline | repo `scripts/` |
| [workers/README.md](../../workers/README.md) | `scripts/omo worker dispatch/status/reclaim` 运维说明 | `.omo/workers/` |

## 任务使用说明

| 文件 | 用途 |
|------|------|
| [tasks/README.md](../../tasks/README.md) | 任务 YAML schema 规范与 Agent 使用约定 |
| [workers/README.md](../../workers/README.md) | 外部 Worker 协作与 dispatch 流程 |
| [plans/README.md](../../plans/README.md) | 计划注册表状态分类与使用规则 |
| [standards/README.md](../../standards/README.md) | 标准注册表与使用规则 |

## Worker 操作流程

| 文件 | 用途 |
|------|------|
| [workers/runbooks/pilot-dispatch-and-reclaim.md](../../workers/runbooks/pilot-dispatch-and-reclaim.md) | Worker 调度与回收 runbook |
| [workers/templates/worker-prompt.md](../../workers/templates/worker-prompt.md) | Worker 启动提示词模板 |

## 测试使用

| 文件 | 用途 |
|------|------|
| [tests/README.md](../../tests/README.md) | 测试分层标准（Spec → Integration → Failure-injection → Acceptance） |

---

## 使用文档规范

- 使用文档应包含: 前置条件 → 步骤 → 预期结果 → 故障排除
- 操作流程应提供可复现的命令和路径
- 引用事实面数据时使用指针（相对路径）

## 跨平面引用

| 引用目标 | 位置 | 用途 |
|---------|------|------|
| [控制面:状态](../../_control/INDEX.md) | `_control/` | 使用对应的系统状态要求 |
| [事实面:任务 SSOT](../../_truth/INDEX.md) | `_truth/` | 任务操作指南对应的 schema |
| [交付面:运行记录](../../_delivery/INDEX.md) | `_delivery/` | 操作流程的执行效果验证 |

---

*维护: 2026-05-31*
