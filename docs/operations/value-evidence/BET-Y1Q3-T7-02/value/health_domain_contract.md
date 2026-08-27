# T7-02 Value Evidence: P1 健康域契约落定

## Health domain contract: real_signal ready

**Symptom/metric/onset/severity** 健康事件 → **needs_doctor_visit 判定** → 就诊准备包
**（symptom_timeline/history_summary/question_list）** → 就诊结果归档
**(diagnosis/prescription/followup_required)** → 复查追踪
**(followup_checklist: 复查日期/用药周期)**.

5-file supply chain delivers P1 contract:
- health-medical-workflow (4-state branched journey, recorded → {prepared→visited→archived, archived})
- 4 scene cards, each declaring L0 contract + (where applicable) L2 boundary

## Risk tier alignment (risk_engine DOMAIN_OVERRIDES.health)

| Action | Tier | Source |
|---|---|---|
| generate:report (4 cards' record/archive/prep actions) | L0 auto | risk_engine health domain |
| send_email:doctor (any outbound) | L2 strong HITL | risk_engine health domain + agent-cli-worker standard |

Each of the 4 health scene cards' notes field explicitly names the tier
boundary in this vocabulary, making future runtime implementation a
direct mapping to risk_engine.guard checks.

## Time burden (proxy: north_star v3 axis A1)

Health is a sensitive domain — value here is **avoiding wrong-action time
cost**, not raw automation. The 4 contract scenes replace the implicit
"manual 30-min per event" workflow with explicit local-storage-only
contracts, capping the runtime implementation effort at the P2
"wire up llm:local-classify + storage:local-health-ledger" task.

## Source

- spec: docs/superpowers/specs/2026-08-26-health-domain-p1-design.md
- retro: .omo/_knowledge/retros/BET-Y1Q3-T7-02.md
- attestation: P1 health domain was user-授权 2026-08-26 (face-to-face)
