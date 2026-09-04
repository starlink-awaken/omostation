---
title: "runbook-reasoning-engine"
type: runbook
owner: governance-team
lifecycle: history
last_updated: 2026-08-23
---
# Runbook: 推理引擎异常排查

## 症状
- `mof-reason impact` 返回 0 依赖
- `mof-derive` 覆盖率 <100%
- `mof-gate` 报告违规 >0

## 排查

### 1. 检查 M1 关系图谱
```bash
cd projects/ecos
uv run python3 src/ecos/ssot/tools/mof-relation-builder.py
```
- 如果 `有边节点 = 0`: 运行 `mof-relation-builder.py --apply`

### 2. 检查 M1 status
```bash
uv run python3 src/ecos/ssot/tools/mof-scan.py --check-status
```

### 3. 检查约束编译器
```bash
uv run python3 src/ecos/ssot/tools/ecos-constraint-compiler.py --enforce
```

### 4. 验证
```bash
uv run python3 src/ecos/observability/dashboard.py --check
```

## 预防
- CI 每次 commit 自动运行 reasoning checks
- M1 节点变更后重建关系图谱
