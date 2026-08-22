---
schema: value-evidence/engineering-diff/v1
bet: BET-Y1Q3-T4-01
axis: engineering
evidence_key: diff
primary_diff: 9c4978c4bb680a214df4c2d4d2212454adba0a7d
diff_scope:
  - bin/bc-os/north_star_meter_v2.py      # NorthStar v2 三轴实现
  - bin/gac/compound-attribution-report.py # 三轴报告
  - bin/plan/bet-ledger.py                 # completion-evidence + attestation verifier (#1849)
  - docs/plans/3y-bet-ledger.yaml          # T4-01 条目 + completion_evidence
merged: true
verified_at: 2026-08-22
---

实现变更 diff:
- #1831: 台账 T4-01 done + done_evidence + retro
- #1845: north_star_meter_v2 恢复(rename from _archive, 100% 相似)
- #1849: bet-ledger.py +165 行(validate_human_attestation + value.ACCEPTED 接入)
- 全部已合并到 origin/main(git log 可验证)
