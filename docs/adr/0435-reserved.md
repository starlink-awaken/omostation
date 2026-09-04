---
adr_id: ADR-0435
status: accepted
title: Machine-level launchd plists are generator output; broken invocations are repaired via services.yaml + wrapper scripts
type: doc
created: 2026-08-30
last_updated: 2026-08-30
---

# ADR-0435 — launchd plist 修复必须走生成器 + 注册表，不允许手改 plist

## 决策

`com.l4.resident.event-ingest` 的 plist 自创建起从未生效（生成器组合出
`uv <dir> resident ingest --once`——无 `resident` console script 且缺 `run`
动词）。修复不采用手改 plist，而是：

1. 新增 tracked wrapper `bin/ssot/resident-event-ingest.sh`
   （`exec uv run --project <omo> python -m omo.resident.cli ingest`）；
2. services.yaml 登记项改为 `interpreter: /bin/bash, entrypoint: 该 wrapper`；
3. 由 `gen-service-configs.py --write` 从**规范检出**（canonical anchor，
   ADR 对 2026-08-08 事故的加固）重新生成 plist。

## 上下文

R2b host retention（BET-Y1Q3-T6-15）的 producer restart 揭示该 defect。
手改 plist 会在下一次 `--write` 时被注册表内容覆盖回坏状态——修复必须落在
registry + tracked wrapper 这一层。

## 后果

- event-ingest 恢复为可运行 producer（exit 0）。
- wrapper 属 bin/ 新脚本：subtraction_quota.script_baseline 同步 536→537，
  并登记 script-registry。
- 后续任何 uv-run 形态的 launchd 服务一律用 wrapper 模式表达。
