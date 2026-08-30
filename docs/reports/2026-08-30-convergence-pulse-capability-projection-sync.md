---
schema_version: report/v1
status: active
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
bet_id: BET-Y1Q3-T10-107
---

# Convergence pulse capability projection sync

PR #2744 registered `convergence-pulse-weekly` in the canonical workflow
registry but did not regenerate `docs/generated/capability-registry.yaml`.
Required capability-registry CI therefore blocked downstream PR #2750.

The full-profile generator changed exactly two semantic facts: workflow total
18 to 19, and one `convergence-pulse-weekly` projection entry. No native MCP,
BOS, CLI, skill, workflow source, script, baseline, or runtime state changed.

`gen-capability-registry.py --check --quiet`, doc SSOT, GaC, and the generated
diff check pass locally. The repair remains projection-only.
