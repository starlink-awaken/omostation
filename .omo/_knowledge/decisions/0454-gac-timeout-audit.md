---
schema: md/v1
status: accepted
lifecycle: active
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
id: ADR-0454
title: 治理脚本无界网络调用审计
date: 2026-09-18
---


# ADR-0454: 治理脚本无界网络调用审计

## 背景

`bin/gac` + `bin/ssot` + `.githooks` 中的 `git fetch/ls-remote/clone/submodule-update` 与 `curl/wget` 网络调用必须设置有界超时，防止 CI 挂起或网络不稳定导致的长时间阻塞。

#3934/#3937 修复了 `claim` 和 `agent-clone` 两处无界调用，本 ADR 收口全仓审计策略。

## 决策

1. **审计工具**: `bin/gac/timeout-audit.py` 扫描全仓无界网络调用
2. **首 landing advisory**: 现有 17 处无界调用先 warn 不阻断，90 天内收敛
3. **升级策略**: 90 天后评估升级为 blocking gate

## 约束

- 所有网络调用必须包裹在 `gac_run_with_timeout` 或设置 `GAC_*_TIMEOUT` 环境变量
- Python `subprocess` 调用必须传 `timeout=` 参数或路由到 bounded helper
- `curl/wget` 必须加 `--max-time`/`--timeout` 参数

## 关联

- CR-GAC-TIMEOUT-AUDIT (X4 维度)
- #3934, #3937
