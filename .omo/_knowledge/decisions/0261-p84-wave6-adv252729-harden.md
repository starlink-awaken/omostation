---
id: ADR-0261
status: ACCEPTED
lifecycle: spec
owner: governance-team
last_updated: 2026-07-29
related:
  - 0260-p84-wave5-adv-bos-m2.md
  - 0254-p84-w22-cclass-collab-detectors.md
---

# ADR-0261: wave6 — ADV25/27/29 检测闭环 + ADV31/33/35 加硬

## Decision

1. **闭环**: `split_brain_detected` / `identity_spoof_detected` /
   `supply_chain_tamper_detected`（ADV25/27/29）。
2. **加硬**: ADV31 sybil-flood / ADV33 time-travel-write /
   ADV35 quorum-eclipse — 管线未实现 → 诚实 FAIL（≥3 失败，P84）。
3. **测试**: `tests/test_collab_scenario_runner.py` 增 wave6 闭环与加硬断言。

## Status

**ACCEPTED** 2026-07-29.
