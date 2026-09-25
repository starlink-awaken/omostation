---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: report
bet_id: BET-Y2Q3-T10-OMLXC-01
created: 2026-09-23
---



# omlxc inventory degraded 三问归因（2026-09-23）

## 基线（写前存档）

- `docs/reports/omlxc-baseline-*.json`（status/doctor/models/nodes，2026-09-23T13:25Z）
- `~/.config/omlxc/config.toml.bak-20260923T132512Z`

## 三问结论

### Q1: mbp-omlx-app 3 placement 为何不服务？

`coding-next-local` / `ornith-9b-local` / `qwen3-8-27b-local` 的 `backend_model_id`
不在 oMLX App `/v1/models` 清单（实测 17 个模型，均不含这 3 个）。

- **归因**：模型未注册进 omlx-app inventory（权重路径/注册表缺失），非 placement 名漂移。
- **`omlxc models load` 尝试**：3 个 job 均 `failed`，`error_code=unavailable`
  （adapter `MODEL_UNAVAILABLE`：`model is not present in the oMLX App inventory`）。
- **结论**：omlxc CLI 无法凭空创建 inventory；需 omlx-app 侧重注册模型或摘除 placement。

### Q2: mbp-lm_studio 15/15 model_mismatch 根因？

LM Studio `:1234/v1/models` **仅服务 1 个模型** `qwen3.6-35b-a3b-splash`（watchdog 标记的
19.5GB 高风险模型）。config 中 15 个 lm_studio placement 的 `backend_model_id` 全部不在该清单。

- **归因**：后端 inventory 从 baseline 45 跌到 1（`inventory_drop` 警告），placement 未同步收敛。
- **`omlxc models load` 尝试**：`error_code=operation_failed`（LM Studio 单模型驻留约束）。
- **结论**：结构性失配。自愈需 (a) 重载期望模型集或 (b) R2 配置摘除失效 placement。

### Q3: conf 33 声明 vs daemon 26 可见，差 13？

| 类别 | 数量 | IDs |
|---|---|---|
| conf-only（孤儿声明） | 9 | bge-reranker-ollama, coding-qwen3-30b-a3b, gemma-4-26b-a4b-it-qat-mlx-4bit, glm-4.7-flash, qwen-3-5-9b-macmini, qwen-3.8-27b-dflash, qwen3.8-27b-ollama, qwythos-9b-1m, vision-minicpm |
| daemon-only | 2 | gemma-4-e4b, qwen3.6-35b |
| 其余 | — | placement 收敛差异（如 ollama 引擎合并展示） |

孤儿声明多为未挂 placement 的备用/ollama 变体，**不直接导致 doctor 失败**。

## doctor 复测（load 尝试后）

- status 仍 `degraded`，失败项与写前**完全一致**（未恶化）→ 未触发回滚门。
- 节点 3/3 healthy、daemon ready、四后端 HTTP 全通不变。

## 后续（开票，不在本 BET 内动手）

1. omlx-app 侧重注册 3 模型（或确认 intentionally 下线后摘 placement）。
2. LM Studio 模型集决策：恢复多模型 vs 收敛 placement（R2 config + daemon reload）。
3. conf 孤儿 9 条清理或补 placement。
4. `omlxc models reconcile` CLI 为 `_unsupported` 桩（cli.py），真 reconcile 在 daemon
   `ReconcileRuntime`（300s）；CLI 桩应实现或移除。
