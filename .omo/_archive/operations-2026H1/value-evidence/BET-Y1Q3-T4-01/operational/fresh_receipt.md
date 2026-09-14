---
schema: value-evidence/operational-fresh-receipt/v1
bet: BET-Y1Q3-T4-01
axis: operational
evidence_key: fresh_receipt
receipt_source: runtime/omo/_delivery/ingress/ingress-audit.jsonl
latest_receipt_ts: 2026-08-21T06:51:01Z
receipt_kind: ingress_sync_state_projection
receipt_actor: omo state sync
source_ref: omo-state:sync
artifact: runtime/omo/_delivery/ingress/state/system-projection-2026-08-21T06-51-01Z.yaml
freshness: < 24h
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
新鲜运行 receipt(operational 证据):
- 最新 ingress 审计 receipt: 2026-08-21T06:51:01Z(state projection 写入)
- 运行面持续产生新鲜 receipt(ingress-audit.jsonl 实时追加)
- freshness < 24h, 证明运行系统活跃
