---
schema: value-evidence/operational-replay/v1
bet: BET-Y1Q3-T4-01
axis: operational
evidence_key: replay
projection_source: runtime/omo/_delivery/ingress/state/
latest_projection: system-projection-2026-08-21T06-51-01Z.yaml
projection_kind: system_projection_fields_written
replayable: true
system_ref: .omo/state/system.yaml
ac12_reference: AC-12 运行投影标签可直接重放
verified_at: 2026-08-22
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-26
type: ephemeral
status: archived
---

last-reviewed: 2026-08-26
---
运行投影可重放(operational 证据):
- state-sync / system-projection 系列投影(持续生成)
- 最新投影: system-projection-2026-08-21T06-51-01Z
- 投影包含 system_ref 与 updated_fields, 可重放(AC-12 要求)
- ingress-audit 记录每次投影写入(审计可追溯)
