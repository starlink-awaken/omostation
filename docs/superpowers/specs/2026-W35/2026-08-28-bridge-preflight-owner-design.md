---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last_updated: 2026-08-27
bet_id: BET-Y1Q3-T10-31
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Workspace bridge preflight owner

## Objective

停止 Documents `_runtime/bridge-refresh.py` 作为定时写入器，先由 Workspace
owner 做只读 bridge readiness 检查。真实 UI/投影由 Cockpit 承接；本波只保留
可审计的 source/marker 状态，不重写 Documents DASHBOARD。

## Contract

- 入口复用 `bin/gac/documents-domain-owner-job.py bridge-preflight`。
- 读取 Documents DASHBOARD 的两个 AUTOGEN marker，以及 Workspace
  `.omo/state/system.yaml`、`health.yaml` 和 cards DB 的存在性/元数据；不读出
  正文、不执行 bridge-refresh。
- 输出 schema `documents.bridge-preflight.v1`，只包含 source readiness、
  marker readiness、counts/status；evidence 只能写 Workspace。
- healthy 返回 0；source/marker 缺失或 stale 返回 1；路径/输入错误返回 2。
- 原 bridge-refresh 脚本和 Dashboard 内容保留，后续由 Cockpit projection
  parity wave 决定退役，不在本波删除。
