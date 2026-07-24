---
title: GAC anomaly triage (STRAT-P80 T1.1)
date: 2026-07-24
type: audit
front: T1.1
---

# GAC anomaly 专项归因 (2026-07-24)

## Polarity / 口径

`governance_anomaly_score` 语义（`bin/compass_radar.py`）: **0–100，越高越健康**（ISC-3）。

| 来源 | 值 | 解读 |
|------|-----|------|
| brief 快照 | 45（误作低好 / 目标 ≤10） | **② 口径误报** — 与代码极性冲突 |
| `.omo/state/system.yaml` | **100** | 健康 |
| `compass_radar.py --dry-run` | **100/100, anomalies=0** | 无 governance 异常 |

## 分类清单

| ID | 现象 | 分类 | 处置 | evidence |
|----|------|------|------|----------|
| A1 | brief anomaly=45 目标≤10 | ② 新口径误报 | 以 live SSOT + compass 为准；不改评分公式 | dry-run 2026-07-24T02:29:04.787388+00:00 |
| A2 | runtime/health 曾记 35 + adr_renumber 扣分 | ③ 陈旧残留 | 现算 100/0 异常 | compass_radar --dry-run |
| A3 | system.yaml score=100 | ① 真实健康 | 保持 | system.yaml |

## 验收

- 实测 `governance_anomaly_score = 100`（健康上界；**非** brief 误写的 ≤10）
- **未**修改 GaC 评分公式（ADR-0202）

```bash
uv run --with pyyaml python bin/compass_radar.py --dry-run
# governance_anomaly_score: 100/100 (anomalies=0)
```
