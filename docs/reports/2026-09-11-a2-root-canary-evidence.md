---
type: report
title: A2 Resident Status 只读 Host Canary 证据 (100/100)
created: 2026-09-11
bet: BET-Y1Q4-T10-144
---

# A2 WP-A2-ROOT Host Canary 证据

- 结果: **PASS 100 / 100**（FAIL 0）
- 判定: stdout 纯 JSON 可解析；`health ∈ {ok, degraded}`；
  `ledger.recovery_performed = false`（零恢复副作用）；
  `ledger.observation_mode = "read_only"`
- 执行: `python -m omo.cli resident status`（主 checkout，
  omo gitlink = e15bc2b09c82ba30d764e2785682d816bfbf3912，含 Spec 1.2.0
  genesis NULL probe 修复 omo#162 / 769e280a）
- 单次耗时均值: <0.2s（100 次总耗时 ~20s）
- 样本: /tmp/a2-canary-sample.json（首帧 JSON）

## 结论

done_when[5] 的 100/100 只读 host canary 达成。operational/value
按 spec 保持 NOT_PROVEN（本 canary 只证只读纯度，不证价值）。
