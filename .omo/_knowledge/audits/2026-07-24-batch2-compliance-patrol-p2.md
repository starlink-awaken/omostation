---
title: Batch2 D3 governance patrol P2
date: 2026-07-24
type: audit
batch: 2
period: P2
---

# Governance weekly patrol — P2

| Check | Result |
|-------|--------|
| compliance.ok | True |
| compliance.decision | continue |
| P74 warn_count | 0 |
| physical-hosts reaffirmation | needs-human-p80-physical-hosts still open (ADR-0228 D3) |
| health snapshot | see `.omo/state/health.yaml` (excerpt below) |

## Health excerpt

```
# governance health — 治理健康分 SSOT
# generated_at: 2026-07-24T02:49:16Z
# source: c2g.strategy (real audit, no mock)
# range: 0-100, higher = healthier
# health_score: composite (ISC-3) = {'governance': 0.3, 'freshness': 0.2, 'runtime': 0.5}

generated_at: "2026-07-24T02:49:16Z"
source: "c2g.strategy (real audit, no mock)"
health_score: 98
governance_anomaly_score: 92
anomaly_count: 0
service_online
```

## Notes

P2: Batch2 in-progress patrol. Fuse: health must stay ≥95 for continue.
