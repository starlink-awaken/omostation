---
title: "runbook-ci-red"
type: runbook
owner: governance-team
lifecycle: history
last_updated: 2026-08-23
---
# Runbook: CI 红了怎么办

## 定位
```bash
gh pr checks <PR_NUMBER>
```

## 本地复现
```bash
cd projects/ecos
uv run pytest tests/ -q
uv run python3 src/ecos/ssot/tools/ecos-constraint-compiler.py --enforce
uv run python3 src/ecos/ssot/tools/mof-scan.py --check-status
uv run python3 src/ecos/ssot/tools/mof-reason.py impact ACTION-ACP-IMPLEMENT
```

## 验证
```bash
uv run python3 src/ecos/observability/dashboard.py --check
```
