---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
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

## Mainline closeout

- PR #2753 merged as `53483be5644444cb0f27b5553a8e469207016929` on
  2026-08-30. The merge is an ancestor of the closeout baseline
  `ab99a81cf7f28a11e2e644a79cc9f1fd04f97877`.
- Required CI passed, including `capability-registry drift (SSOT 同步)`,
  `gac-gate`, and `governance-verify`.
- A fresh full-profile clone reproduced
  `python3 bin/ssot/gen-capability-registry.py --check --quiet` with exit 0 and
  doc SSOT with zero conflicts.
- The blocked downstream ZCode delivery, PR #2750, subsequently merged as
  `8737b24a14e2de4ca68116a3f5b52f4e2c905c18`.

Engineering consistency is `VERIFIED` and mainline use is `PROVEN`. This repair
does not establish principal-bound user value, which remains `NOT_PROVEN`.
