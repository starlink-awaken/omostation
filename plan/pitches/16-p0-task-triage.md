# Pitch: P0 Task Triage & Priority Rebalancing

> **Upstream**: MS-GOVERNANCE-SSOT
> **Appetite:** 1 day

## 🎯 The Why (Problem & Opportunity)

The workspace currently has **57 P0 tasks** (threshold: 5). When everything is P0, nothing is P0. The priority system has lost its discriminating power, leading to:
- Resource diffusion across too many "urgent" items.
- Inability for agents and humans to identify the true next action.
- Governance health score distortion.

## 🚧 The What (Solution Overview)

1. **Audit all 57 P0 tasks** against current Phase 42 / Wave 3 goals.
2. **Downgrade** tasks that are not actually blocking the current wave to P1/P2/P3 or candidate.
3. **Re-link** orphaned tasks (3) and missing-goal tasks (6) to the appropriate Bet/Goal.
4. **Add missing metadata** (risk, domain) to the top 20 tasks.
5. **Update `.omo/state/health.yaml`** to reflect the corrected distribution.

## 📏 Boundaries & Appetites

- **Appetite:** 1 day.
- **No-Gos:** Do not promote any planned task to active/ without human approval.

## ⚠️ Rabbit Holes & Risks

- **Politics:** Downgrading a task may require stakeholder confirmation.
- **Scope creep:** Triage can turn into full task rewriting; stick to priority and linkage only.
