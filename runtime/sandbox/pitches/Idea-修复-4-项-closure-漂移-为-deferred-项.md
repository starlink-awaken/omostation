# 修复 4 项 closure 漂移 + 为 deferred 项打 Next-Action

> **Upstream**: P42-W0-W1-COMBO (omo 治理面 SSOT 同步纪元)
> **Appetite:** 2 hours

## 背景与上下文
2026-06-20 `omo governance` 巡检出 4 项 P1 closure 漂移:
- DEBT-CROSSPROJECT-SYSPATH (high) — closed 但无 `resolution_evidence`
- DEBT-EMPTY-INIT-PY (low) — closed 但无 `resolution_evidence`
- DEBT-GBRAIN-55-TODOS (low) — closed 但无 `resolution_evidence`
- DEBT-KAIRON-ONTODERIVE-PHANTOM (critical) — closed 但无 `resolution_evidence`

同时 DEBT-GBRAIN-OPERATIONS-TS (deferred) 缺 `next_review_at` + `gate_level`,
在 owner-routing/review-queue 全空背景下可能永久搁置。

## 目标
1. 用 omo CLI 给 4 项补齐 ≥ 20 字符 `resolution_evidence`
2. DEBT-GBRAIN-OPERATIONS-TS 补 `next_review_at: 2026-07-01` + `gate_level: P3`
3. `omo governance` 重跑验证 score ≥ 90
4. mof-validate 通过

## NoGos (YAGNI)
- 不改 SSOT 注册表结构 (deferred 项就是 deferred, 不强行推进)
- 不动其他 closed 债务 (避免无谓 audit 噪音)
- 不改 omo governance 巡检阈值 (debt_health 已 87.9, 漂移 4 项 closure 是真实信号)