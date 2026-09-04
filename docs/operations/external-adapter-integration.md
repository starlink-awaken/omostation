---
status: active
lifecycle: entry
owner: governance-team
last-reviewed: 2026-08-18
type: ssot
last_updated: 2026-09-03
---
# External Adapter Integration Pattern

> SSOT: AGT × eCOS v6 Integration (ADR-0366)  
> Date: 2026-08-04

## 1. Overview

This document describes the canonical pattern for integrating external adapters (如 AGT、KEMS 等) into eCOS v6 via BOS URI + M1 registration + GaC hook.

## 2. Registration Checklist

| Step | Surface | File | Action |
|------|---------|------|--------|
| 1 | M1 Component | `projects/ecos/src/ecos/ssot/mof/m1/component/COMP-EXT-{ADAPTER}-*.yaml` | 8 components |
| 2 | M1 BOSRoute | `projects/ecos/src/ecos/ssot/mof/m1/bosroute/BOSROUTE-{ADAPTER}-*.yaml` | 8 routes |
| 3 | I0 Service | `projects/agora/etc/bos-services.yaml` | stdio transport entries |
| 4 | L0 Constraint | `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml::agt_constraints` | CR-{ADAPTER}-* |
| 5 | X1 Policy | `.omo/_truth/x1-governance-policies.yaml` | block-write / audit policies |
| 6 | X3 Domain | `.omo/_truth/x3-value-stack.yaml` | trust / value attribution |
| 7 | L1 Hook | `bin/gac/gac-local-gate.py` | --{adapter}-backend flag |
| 8 | Test | `tests/test_{adapter}_integration.py` | 11 integration tests |

## 3. Key Decisions

### 3.1 Namespace Isolation
All AGT components use `agt` namespace to avoid collision with existing `agentmesh` concept.

### 3.2 M1 Status Machine Compliance
M1 Component `status` must be one of: `active`, `degraded`, `stopped`, `archived`.  
`proposal_only` is rejected by `mof-validate.py`.

### 3.3 L0 Constraint Structure
Constraints must be under a top-level key (e.g. `agt_constraints`), not bare list items.

### 3.4 Agora CLI Fallback
`run_agt_policy_engine()` catches `FileNotFoundError` and returns `FAIL` with clear stderr, ensuring gate works without Agora installed.

### 3.5 Finding Topic Registration
New backend checks must be added to `FINDING_TOPIC_CHECKS` in `gac-local-gate.py` for dashboard observability.

## 4. File Templates

### M1 Component
```yaml
type: Component
status: active
m3_parent: StructuralElement.Component
state_history:
  - timestamp: "2026-08-04T00:00:00Z"
    from_status: proposal_only
    to_status: active
    actor: agent-workflow
```

### M1 BOSRoute
```yaml
name: bos://{domain}/{adapter}/{action}
subtype: BOSRoute
properties:
  protocol: BOS_URI
cross_references:
  - component: COMP-EXT-AGT-{name}
```

### L0 Constraint
```yaml
agt_constraints:
  - id: CR-AGT-ASI-01
    applies_to: [L0, L1, I0]
    dimension: X1
    rule: agent.identity.verified == true
    type: required
    severity: high
    enforcement: block-write
```

## 5. Commands

```bash
# Validate M1 nodes
python3 projects/ecos/src/ecos/ssot/tools/mof-validate.py

# Validate drift
python3 bin/mof/mof-drift

# Run AGT integration tests
pytest tests/test_agt_integration.py -v

# Sync bos-registry mirror
python3 bin/ssot/sync-bos-registry.py

# Run gate with AGT backend
python3 bin/gac/gac-local-gate.py --agt-backend
```

## 6. Anti-patterns

- **Don't** modify `.omo/` directly without broker
- **Don't** use `proposal_only` status in M1 (fails mof-validate.py)
- **Don't** add bare list items to L0-constraints.yaml
- **Don't** forget to add new checks to `FINDING_TOPIC_CHECKS`
- **Don't** edit `projects/agora/` files from superproject worktree without submodule init

## 7. Verification

```bash
pytest tests/test_agt_integration.py -v
# Expected: 11 passed
```
