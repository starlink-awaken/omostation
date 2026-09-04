---
title: "runbook-constraint-violation"
type: runbook
owner: governance-team
lifecycle: history
last_updated: 2026-08-23
---
# Runbook: 约束违规响应

## 症状
- `ecos-constraint-compiler --enforce` exit 1
- `mof-gate` 报告 L0 绕过
- Dashboard constraints.failed_required > 0

## 排查
```bash
cd projects/ecos
uv run python3 src/ecos/ssot/tools/ecos-constraint-compiler.py --json
```
查看 `constraints` 数组中 `passed: false` 的项。

## 响应
- `type: required` → 必须修复
- `type: preferred` → 可延后
- 无法立即修复 → 登记 `gate-known-debt.yaml`

## 预防
- pre-commit: `make gac-local-gate`
- CI 阻断 required 违规
