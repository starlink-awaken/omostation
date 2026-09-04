---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
type: ssot
---
# ADR-0196: Shadow Challenger & Red-Team Deliberation Loop

## Status
Accepted

## Context
Generative proposals and draft specifications frequently harbor hidden regulatory, financial, or cyber-security compliance flaws (e.g. unverified large budgets, missing MLPS Level 3 specifications, or non-compliant reward splits). Humans often lack the time to manually audit every angle before submission.

## Decision
1. Implement `ShadowChallenger` in `ecos.ssot.compiler.shadow_challenger`.
2. Construct three dedicated adversarial attack angles:
   - `AUDIT_FINANCE`: Audit Bureau inspection for >500w un-reviewed budgets.
   - `CYBER_SECURITY`: Network security inspection for clinical data MLPS Level 3 and SMx cryptography.
   - `TECH_TRANSFER`: Legal inspection for team reward ratio (≥70%) and TRL readiness.
3. Provide automated patch synthesis (`--auto-patch`) to append certified compliance declarations.
4. Expose via CLI `ecos-constraint challenge "<target>" [--auto-patch]` and FastMCP `runtime_shadow_challenge`.

## Consequences
- Guarantees zero ungrounded or vulnerable drafts are presented to humans without automated red-teaming.
- Robustness score provides quantified assurance before delivery.
