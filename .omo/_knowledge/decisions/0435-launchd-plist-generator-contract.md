---
id: ADR-0435
status: accepted
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-30
type: ssot
---

# ADR-0435 — launchd plist 修复必须走生成器 + 注册表，不允许手改 plist

## 决策

`com.l4.resident.event-ingest` 的 plist 自创建起从未生效（生成器组合出
`uv <dir> resident ingest --once`，无 `resident` console script 且缺 `run`
动词）。修复不采用手改 plist，而是：

1. 新增 tracked wrapper `bin/ssot/resident-event-ingest.sh`，通过
   `exec uv run --project <omo> python -m omo.resident.cli ingest` 执行；
2. 在 `services.yaml` 登记 `/bin/bash` wrapper；
3. 由 `gen-service-configs.py --write` 从 canonical checkout 重新生成 plist。

## 后果

机器级 plist 是生成物；后续 uv-run 形态服务必须落在注册表和 tracked
wrapper 上，不能通过手改 plist 维持本地漂移。
