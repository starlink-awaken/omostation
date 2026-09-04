---
type: ssot
---

# 真实场景 — Y1Q4 B2 可观测自愈最小闭环

> 链路：`runtime Matrix 重启 <30s` + `aetherforge 熔断 0 误杀`

## 场景
1. `runtime Matrix` 模拟崩溃 → 自愈重启计时
2. `aetherforge` 预算熔断探针 → 0 误杀验证
3. 두 链路均 <30s 可观测

## 验证
- `uv run pytest scenarios/Y1Q4-B2/test_e2e.py -q` 2 passed
