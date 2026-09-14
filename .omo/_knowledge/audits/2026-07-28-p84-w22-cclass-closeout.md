---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-07-28
type: ephemeral
status: archived
---
# P84 W2.2 C/S 类检测器 closeout

> ADR-0254 · run `20260728T121910Z-project-code-change-08ac1747`

## 结果
- C 类 15 + S 类 12 检测落地于 `scenario_lib.py`
- 新对抗 ADV13/15/17 保持 ≥3 失败
- `pytest tests/test_collab_scenario_runner.py` **9 passed**

## 回归
- `test_cclass_detectors_pass` 锁 ADV07/09/11 常绿
