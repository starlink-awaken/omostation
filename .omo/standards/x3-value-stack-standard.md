---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-29
---

# X3 Standard: Value Stack & Cost Attribution

> Status: PARTIAL (Vault domain gap remaining)
> Authority: protocols/x-axis-registry.yaml (rules), .omo/_truth/x3-value-stack.yaml (domain mapping)

## 1. 核心目标

系统内所有功能域支柱必须能回答: **资源消耗是否可归因?** (Can resource consumption be attributed to value?)

X3 与 X1 (审计)、X2 (新鲜度)、X4 (HITL 变更) 共同构成 X 轴四维治理。X 平台总分取短板: `min(X1, X2, X3, X4)`, 不可用平均值稀释。

## 2. 值栈维度

每个功能域支柱必须声明以下维度:

| 维度 | 含义 | 示例 |
|------|------|------|
| `compute` | 计算资源消耗 | LLM token 调用、API 请求次数 |
| `storage` | 存储占用 | SQLite 行数、文件体积 |
| `maintenance` | 维护成本 | 审计、清理、迁移工时 |
| `network` | 网络开销 | 跨节点消息、外部 API 调用 |

部分域有专属维度 (如 Kairon 的 `type_check`、`test_execution`)。

## 3. 归因机制

| 功能域 | 机制 | 工具 / 不变量 ID | 状态 |
|---------|------|-----------------|------|
| CARDS | card_history SQLite 聚合 (count by status, 平均 age, 月活) | `CARDS-X3-METRICS-v1` | ✅ |
| OMO | omo_cost.py + cost-tracking.jsonl | — | ✅ |
| OMO_State | 按 state/control/knowledge/delivery 分层归因 | — | partial |
| OMO_Kernel | kernel-side governance execution cost | — | ✅ |
| C2G_Ingress | 战略入口到执行任务的转化收益归因 | — | ✅ |
| AetherForge | unified cost tracking (gateway/mesh/swarm) | — | ✅ |
| Kairon | mof-analyze cost + mypy strict + test execution | — | ✅ |
| Vault | 未实现 | — | ❌ |
| Domain_Systems | 复用 cards_x3_metrics 模式 (P44 R0) | `DOMAIN-X3-METRICS-v1` | design |

## 4. 强制约束

1. 任何新增功能域支柱必须在 `.omo/_truth/x3-value-stack.yaml` 中声明 X3 value 归因机制。
2. 声明 `implemented: false` 时, 必须同时声明 `mechanism: 未实现` 和计划实现路径。
3. X3 规则 (K1/K2/K3) 定义在 `protocols/x-axis-registry.yaml`; X3 score < 80 触发告警。
4. 禁止用其他维度的满分稀释 X3 的零分 (木桶效应)。

## 5. 关联文件

| 文件 | 角色 |
|------|------|
| `protocols/x-axis-registry.yaml` | X3 规则定义 (K1-K3) |
| `.omo/_truth/x3-value-stack.yaml` | 功能域 X3 归因映射 (权威 SSOT) |
| `scripts/omo/cards_x3_metrics.py` | CARDS X3 指标采集工具 |
| `scripts/omo/vault_x1_audit.py` | Vault X1 审计工具 (X3 待补) |

## 6. 当前缺口

- **Vault X3**: 未实现成本归因。计划复用 `vault_x1_audit.py` 的文件扫描能力, 聚合存储/维护维度。
