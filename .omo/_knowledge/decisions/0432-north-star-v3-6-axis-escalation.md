---
id: ADR-0432
status: candidate
lifecycle: spec
owner: xiamingxing
last_updated: 2026-08-28
---

# ADR-0432: North Star v3 6-Axis Escalation

## Status: candidate

## Evidence Status: UNPROVABLE

The six-axis proposal remains a candidate. Direct evidence currently contains
mutually inconsistent axis values (including A2 values of `0.0` and `0.15`);
this recovery does not select a value, accept the model, or produce completion
or value evidence.

## Date: 2026-08-28

## Context

The north_star v3 metric has evolved from 3-axis to 6-axis to provide
deeper visibility into value proof:

- **3-axis (A70+B30)**: Original backward-compatible composite (94/100)
- **4-axis (A60+B20+D20)**: Added knowledge consumption dimension (96/100)
- **5-axis (A50+B10+D20+E15)**: Added decision quality dimension (93/100)
- **6-axis (A45+B8+D18+E14+A215)**: Added KV cache efficiency dimension (83/100)

The escalation provides increasing granularity:
- A-axis (0.70): Time saved via automated governance events
- A2-axis (0.0→0.15): KV cache hit rate from omlxc persistence
- B-axis (0.30→0.10→0.08): Decision throughput and cadence
- C-axis (0.00): BET completion rate (佐证 only)
- D-axis (0.20): Knowledge consumption events
- E-axis (0.15): Decision quality (P0/P1 adoption rate)

## Candidate proposal (not an accepted decision)

1. **E-axis (Decision Quality)**: Added as 5th axis measuring P0/P1 decision
   count and adoption ratio. Score = 20 × p0_p1_count × adoption_ratio.
   Currently: 7 P0/P1 decisions, 100% adoption → score 100.

2. **A2-axis (KV Cache Hit Rate)**: Added as 6th axis reading from persisted
   cache stats (~/.omlxc/cache_stats.json). Score = hit_rate × 100.
   Currently: 0 (cache cold, no inference queries).

3. **6-axis composite weights**: A45+B8+D18+E14+A215 (total 100%)
   - A2 weight (0.15) represents real-time inference acceleration
   - When A2=0 (cache cold), composite drops to 83/100 (honest signal)

4. **Signposting**: Each composite includes axis_contributions and
   explanation of weight redistribution for dashboard readers.

## Consequences

- Provides actionable visibility: A2=0 is a real gap in value proof
- E-axis shows decision quality, not just quantity
- 6-axis composite is more conservative than 3-axis (83 vs 94)
- Dashboard users can see which dimensions need improvement
