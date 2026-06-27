# Phase 4 GaC M1 化 — Feasibility Analysis

> **Task**: Feasibility analysis for materializing GaC rules to M1 `GAC-RULE-*.yaml` nodes + integrating with mof-schema-validate / mof-bridge-sync.
> **Date**: 2026-06-28 | **Analyst**: worker subagent | **Status**: COMPLETE

---

## 1. Current M1 Structure

### File Counts

| Metric | Value |
|--------|-------|
| **Total M1 YAML nodes** | **1196** (across 43 domain directories) |
| M2 schema files | 48 (`projects/ecos/src/ecos/ssot/mof/m2/*.yaml`) |
| Governance M1 nodes | 25 (`GOV-*.yaml` in `m1/governance/`) |
| Existing GAC-RULE M1 nodes | **0** (none exist yet) |

### M1 Directory Layout

Path: `projects/ecos/src/ecos/ssot/mof/m1/<domain>/<NAME>.yaml`

Top 10 directories by node count:
1. `lesson/` — 138
2. `entity/` — 136
3. `specification/` — 122
4. `omo_layer/` — 101
5. `component/` — 88
6. `bosroute/` — 77
7. `mechanism/` — 66
8. `mcptool/` — 62
9. `skill/` — 61
10. `artifact/` — 61

Full list: 43 domain directories.

### Naming Convention

- M1 files use `{DOMAIN}-{DESCRIPTOR}.yaml` (e.g., `GOV-CHECK-X1-AUDIT-CHAIN.yaml`)
- Each M1 YAML has top-level fields: `id`, `type`, `name`, `description`, `status`, `domain`, `layer`, `created`, `version`, `properties`, `source`, `model_driven_refs`, `state_history`
- The `type` field references the M2 `m2_type` (e.g., `type: GovernanceCheck` maps to `m2/governance_check.yaml`)

### Sample M1 Node (GOV-CHECK-X1-AUDIT-CHAIN.yaml)

```yaml
id: "GOV-CHECK-X1-AUDIT-CHAIN"
type: GovernanceCheck
name: "X1 审计链检查器"
description: "..."
status: running
domain: "meta"
layer: "X1"
created: "2026-06-14"
version: "1.0.0"
properties:
  m3_parent: "GovernanceElement.Check"
  check_id: "x1-audit-chain"
  dimension: "X1"
  ...
source: "ecos/l0/governance/checkers.py"
model_driven_refs:
  source_file: projects/ecos/src/ecos/ssot/mof/m1/
state_history:
  - state: running
    timestamp: '2026-06-19T00:00:00Z'
    reason: initial_modeling
```

---

## 2. GaC Rule Structure

### Source File

`.omo/_truth/registry/governance-checks.yaml` (multi-document YAML with frontmatter)

### Rule Counts

| Category | Count |
|----------|-------|
| **Total GaC rules** | **115** |
| Native rules (no `source_type`) | 18 |
| Indexed rules (`source_type: indexed`) | 97 |

### By Dimension

| Dimension | Count |
|-----------|-------|
| X1 (Audit) | 29 |
| X2 (Freshness) | 26 |
| X3 (Value) | 5 |
| X4 (Consistency) | 55 |

### By Layer

| Layer | Count |
|-------|-------|
| L0 | 74 |
| L1 | 1 |
| L2 | 6 |
| L3 | 1 |
| M0 | 1 |
| meta | 32 |

### By check_type

| check_type | Count |
|------------|-------|
| legacy_index | 97 (all indexed rules) |
| ssot_pointer | 5 |
| drift_audit | 3 |
| audit_chain | 2 |
| mof_stage_gate | 1 |
| bos_resolve | 1 |
| task_field | 1 |
| value_roi | 1 |
| freshness | 1 |
| direct_io_gate | 1 |
| hygiene_zero_byte | 1 |
| hygiene_case | 1 |

**Total unique check_type values used: 12** — all match the M2 schema enum exactly.

### Native Rule Fields (18 rules)

All 18 native rules have these fields (100% coverage):
`id`, `dimension`, `layer`, `name`, `description`, `check_type`, `target`, `executor`, `lifecycle`, `version`, `created_at`, `adr`

Optional field: `forbid_copy_in` (3/18 rules)

### Indexed Rule Fields (97 rules)

All 97 indexed rules have:
`id`, `source_type`, `source_ref`, `dimension`, `layer`, `check_type`, `executor`, `enforcement`, `lifecycle`, `version`, `created_at`, `adr`

Optional field: `relates_to` (6/97 rules)

**Key difference**: Native rules have `name`, `description`, `target`; indexed rules have `source_type`, `source_ref`, `enforcement`. The M2 schema does NOT cover `source_type`, `source_ref`, `enforcement`, `relates_to`, `name`, `description`, `forbid_copy_in` — these are GaC-registry-specific fields not modeled in M2.

---

## 3. M2 Schema for Governance Rules

### Existing M2 Schemas (governance-related)

| M2 File | m2_type | Size | Description |
|---------|---------|------|-------------|
| `gac_rule.yaml` | `GacRule` | 4544 bytes | **GaC rule metamodel (mechanism 7)** — created 2026-06-26 |
| `governance_check.yaml` | `GovernanceCheck` | 1985 bytes | Governance check instances |
| `governance_decision.yaml` | `GovernanceDecision` | 2904 bytes | Governance decisions |
| `governance_event.yaml` | `GovernanceEvent` | 1535 bytes | Governance events |
| `governance_policy.yaml` | `GovernancePolicy` | 2288 bytes | Governance policies |

### GacRule M2 Schema Details

Path: `projects/ecos/src/ecos/ssot/mof/m2/gac_rule.yaml`

**Fields defined**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string (pattern `^[A-Z][A-Z0-9_-]+$`) | ✅ | Rule unique ID |
| `dimension` | enum [X1,X2,X3,X4] | ✅ | Governance dimension |
| `layer` | enum [M0,L0,L1,L2,L3,meta] | ✅ | Architecture layer |
| `check_type` | enum (12 values) | ✅ | Check type |
| `executor` | list of enum (10 values) | ✅ | Execution channels |
| `lifecycle` | enum [draft,active,deprecated,removed] | ✅ | Lifecycle state |
| `version` | semver | ✅ | Semantic version |
| `created_at` | date | ✅ | Creation date |
| `target` | string | ❌ | Check target |
| `forbid_copy_in` | list of glob | ❌ | SSOT copy prohibition |
| `adr` | string | ❌ | ADR reference |

**State machine**: `draft → active → deprecated → removed` (terminal)

**M2 schema check_type enum**: 12 values — matches all 115 GaC rules exactly.

**Gap**: The GaC registry's own `gac.schema.check_type_enum` declares 28 values, but the M2 schema only has 12. However, **no actual rule uses the extra 16 values** (e.g., `schema_integrity`, `yaml_bypass`, `sensitive_write`, etc.). This is a latent schema drift, not a Phase 4 blocker.

---

## 4. mof-schema-validate.py Analysis

### How It Works

Path: `projects/ecos/src/ecos/ssot/tools/mof-schema-validate.py` (23,639 bytes)

**Validation logic**:
1. Loads all M2 schemas from `m2/*.yaml` (48 files)
2. Iterates all M1 nodes in `m1/<domain>/*.yaml` (1196 nodes)
3. For each M1 node:
   - Checks `type` field exists in M2 schemas (with alias matching: PascalCase + snake_case + lowercase)
   - Checks `requiredProperties` are present (in `properties` dict or top-level)
   - Checks `status` is in M2 `stateMachine` valid values
   - Optional Phase 3 checks: field types, state transitions, ref paths

**Key code snippet** — the core validation function:

```python
def check_m1_node(data, schema, m2_type, *, check_types=False, check_transitions=False, check_refs=False):
    issues = []
    props = data.get("properties") or {}
    status = data.get("status")
    
    # Check 1: requiredProperties
    req = list((schema.get("requiredProperties") or {}).keys())
    for k in req:
        if k not in props and k not in data:
            issues.append(f"  - missing required: {k}")
    
    # Check 2: state machine valid values
    sm = list((schema.get("stateMachine") or {}).keys())
    if sm and status and status not in sm:
        issues.append(f"  - status={status!r} 不在 stateMachine {sm}")
    ...
```

### What Would Need to Change for GAC-RULE-*.yaml?

**Answer: NOTHING in mof-schema-validate.py itself.**

The validator is **generic** — it auto-discovers M1 files in any `m1/<domain>/` subdirectory and matches them against M2 schemas by the `type` field. If you create `m1/governance/GAC-RULE-CR-X4-HEALTH-SSOT.yaml` with `type: GacRule`, the validator will:

1. Find the M2 schema `gac_rule.yaml` (m2_type=`GacRule`)
2. Match `type: GacRule` via alias resolution
3. Validate required fields (`id`, `dimension`, `layer`, `check_type`, `executor`, `lifecycle`, `version`, `created_at`)
4. Validate `status` against the stateMachine (draft/active/deprecated/removed)

**One caveat**: The M2 `gac_rule.yaml` uses `fields` (not `requiredProperties`/`optionalProperties`). The validator checks `requiredProperties` — so either:
- (a) The `fields` dict in GacRule M2 needs fields with `required: true` to be recognized, OR
- (b) The M2 schema needs restructuring to use `requiredProperties`/`optionalProperties` format (like other M2 schemas)

Looking at the validator code, it reads `schema.get("requiredProperties")` — the GacRule M2 schema uses `fields` with per-field `required: true`. This is a **schema format mismatch** that needs resolution.

---

## 5. mof-bridge-sync.py Analysis

### How It Works

Path: `projects/ecos/src/ecos/ssot/tools/mof-bridge-sync.py` (17,019 bytes)

**Current scope**: Syncs ONLY `lifecycle/` M1 nodes (Stage/Gate) against `model-driven/m3_extended.py:STANDARD_STAGES/STANDARD_GATES`.

**Sync logic**:
1. Loads model-driven `STANDARD_STAGES` (7 stages) and `STANDARD_GATES` (4 gates)
2. Loads M1 lifecycle nodes from `m1/lifecycle/*.yaml`
3. Diffs by stage key (planning/design/...) and gate transition (from_stage→to_stage)
4. Can write missing M1 nodes with `--sync` flag

**Key limitation**: This tool is **lifecycle-specific** — it only syncs Stage/Gate M1 nodes. It does NOT handle GaC rules or any other M1 domain.

### What Would Need to Change for GaC?

**Option A (minimal)**: Leave mof-bridge-sync.py as-is. GaC rules don't have a model-driven M3 source (they're defined in `governance-checks.yaml`, not in `model-driven/m3_extended.py`). The bridge sync concept doesn't apply to GaC rules directly.

**Option B (full integration)**: Create a new sync tool `gac-m1-sync.py` that:
1. Reads `governance-checks.yaml::gac.rules` (115 rules)
2. Reads `m1/governance/GAC-RULE-*.yaml` M1 nodes
3. Diffs by rule `id`
4. Writes missing M1 nodes with `--sync`

**Recommendation**: Option B. The existing `gac-mof-validate.py` already validates rules against the M2 schema. A new `gac-m1-sync.py` would handle the M1 materialization.

---

## 6. Existing GaC Tooling (Already in Place)

### 12 GaC Tools at `bin/gac-*.py`

| Tool | Size | Purpose |
|------|------|---------|
| `gac-validate.py` | 9738B | Schema validation (mechanism 2) + conflict detection (mechanism 5) |
| `gac-drift.py` | 8804B | Drift detection (mechanism 4) — registry vs actual execution |
| `gac-mof-validate.py` | 5050B | **M2 metamodel validation (mechanism 7)** — validates rules against `gac_rule.yaml` M2 schema |
| `gac-healthcheck.py` | 14237B | 12-point healthcheck (files/validate/drift/M2/doc-ssot/hygiene/...) |
| `gac-bootstrap.py` | 6640B | GaC self-bootstrapping (GaC governs itself) |
| `gac-executor.py` | 8250B | Executor registration drift (declared vs actual) |
| `gac-gc.py` | 4263B | Garbage collection (lifecycle: deprecated → removed after 28 days) |
| `gac-hook-pre-edit.py` | 4663B | Pre-edit hook (mechanism 3) |
| `gac-hygiene-check.py` | 6536B | Hygiene checks (0-byte files, case sensitivity) |
| `gac-ingest-legacy.py` | 12823B | Legacy rule ingestion (X1-X4 → indexed) |
| `gac-dashboard.py` | 6845B | Dashboard data aggregation |
| `gac-daemon.py` | 4341B | Daemon mode |

### Key Existing Validation: `gac-mof-validate.py`

This tool **already validates GaC rules against the M2 `gac_rule.yaml` schema** (mechanism 7). It:
- Reads M2 fields from `m2/gac_rule.yaml`
- Reads rules from `governance-checks.yaml::gac.rules`
- Validates each rule's required fields, enum values, patterns

**This means the M2 validation layer is already done.** What's missing is the **M1 materialization** — creating actual M1 YAML instance nodes.

---

## 7. Risk Assessment

### Blast Radius Analysis

| Category | Files to Create | Files to Modify | Risk Level |
|----------|:---:|:---:|:---:|
| M1 GAC-RULE-*.yaml nodes (115 rules) | **115 new files** | 0 | **Medium** |
| M2 `gac_rule.yaml` schema fix (fields format) | 0 | 1 | **Low** |
| New `gac-m1-sync.py` tool | 1 new file | 0 | **Low** |
| mof-schema-validate.py (no change needed) | 0 | 0 | **None** |
| mof-bridge-sync.py (no change needed) | 0 | 0 | **None** |
| Pre-commit hook integration | 0 | 1-2 | **Low** |
| L0-constraints.yaml registration | 0 | 1 | **Low** |

### Risk Breakdown

**Overall Risk: MEDIUM**

| Risk Factor | Level | Justification |
|-------------|:---:|---------------|
| Volume of new files | Medium | 115 new M1 YAML files — large batch, but each is small (~20-30 lines) and follows a template |
| Existing tool disruption | Low | mof-schema-validate.py and mof-bridge-sync.py need NO changes — they're generic |
| M2 schema format mismatch | Low | `gac_rule.yaml` uses `fields` not `requiredProperties`; needs format alignment or validator enhancement |
| SSOT duplication | Medium | GaC rules live in `governance-checks.yaml` (SSOT). M1 nodes would be **derived instances**, not a new SSOT — must establish clear derivation direction |
| CI gate impact | Low | New M1 files would be validated by existing `mof-schema-validate.py --staged` pre-commit hook automatically |
| Concurrent agent conflict | Medium | ecos submodule — must check `pgrep -fl governance` before batch write; use AdvisoryLock if needed |
| Naming collision | Low | `GAC-RULE-*.yaml` prefix is new; no collision with existing `GOV-*.yaml` governance nodes |
| Lifecycle management | Medium | 115 M1 nodes need lifecycle tracking; `gac-gc.py` already handles deprecated→removed but M1 nodes add maintenance surface |

### Key Risks Explained

**1. SSOT Direction Confusion (Medium)**

The GaC NORTH-STAR states: "governance-checks.yaml is the唯一 rule源 (SSOT)". If we create 115 M1 YAML files, there's a risk of **SSOT duplication** — the same rule data exists in two places. The design docs (stage3-4-design.md) clarify: M1 nodes are the **metamodel** (RuleDefinition), M2 is the **instance** (governance-checks.yaml::gac.rules), M3 is the **execution binding**. So the M1 node should be the **schema definition**, not a copy of each rule.

However, the task description says "materialize GaC rules to M1 GAC-RULE-*.yaml nodes" — this implies creating one M1 node PER RULE (115 nodes), which would be M1 instances, not a single M1 metamodel.

**This is the critical design decision**: 
- **Option A**: Create 1 M1 `RuleDefinition` metamodel node (as stage3-4-design.md suggests) + keep rules in governance-checks.yaml as M2 instances. Low risk, aligns with design docs.
- **Option B**: Create 115 M1 `GAC-RULE-*.yaml` instance nodes (one per rule). Higher risk, large batch, potential SSOT confusion.

**2. M2 Schema Format Mismatch (Low)**

The `gac_rule.yaml` M2 schema uses a `fields` dict with per-field `required: true`, while `mof-schema-validate.py` checks `schema.get("requiredProperties")`. The GacRule M2 schema section structure is:

```yaml
GacRule:
  fields:
    id:
      required: true
      ...
```

But the validator expects:
```yaml
GacRule:
  requiredProperties:
    id: {...}
```

This means `mof-schema-validate.py` won't validate GacRule M1 nodes correctly unless the M2 schema is restructured or the validator is enhanced to read `fields` as an alternative to `requiredProperties`.

---

## 8. Recommended Approach

### Recommendation: PARTIAL — Do Option A now, defer Option B

**Rationale**: The GaC design docs (stage3-4-design.md) already specify the correct M1→M2→M3 derivation chain. The existing `gac-mof-validate.py` already validates rules against the M2 schema. What's truly missing is minimal.

### Phase 4A: Do Now (Low Risk, High Value)

1. **Fix M2 `gac_rule.yaml` schema format** — align `fields` to `requiredProperties`/`optionalProperties` format so `mof-schema-validate.py` can validate GacRule M1 nodes automatically. (~1 hour)

2. **Create 1 M1 metamodel node**: `m1/governance/RULE-DEFINITION.yaml` with `type: GacRule` — this is the M1 metamodel instance that the design docs specify. It defines the rule structure, not individual rules. (~30 min)

3. **Verify `mof-schema-validate.py` picks it up** — run `python3 src/ecos/ssot/tools/mof-schema-validate.py --focus governance` to confirm the new M1 node validates against the M2 schema. (~10 min)

4. **Register in L0-constraints.yaml** — add a constraint entry for GaC M1 metamodel integrity. (~15 min)

5. **Commit in ecos submodule** — immediate commit + root pointer bump. (~10 min)

**Total estimated effort**: ~2-3 hours, 2-3 files changed.

### Phase 4B: Defer (High Effort, Marginal Value)

Creating 115 individual `GAC-RULE-*.yaml` M1 instance nodes:

**Why defer**:
- The rules already have a SSOT (`governance-checks.yaml`) — M1 instances would be derived copies
- `gac-mof-validate.py` already validates rules against M2 schema without needing M1 instances
- 115 files is a large batch with maintenance overhead (lifecycle, drift, gc)
- The design docs specify M1 = metamodel (RuleDefinition), not M1 = per-rule instances
- No existing tool requires M1 instance nodes to function

**If needed later**: Write a `gac-m1-sync.py` tool that auto-generates M1 instance nodes from `governance-checks.yaml::gac.rules` with `--sync` flag, similar to how `mof-bridge-sync.py` generates Stage/Gate M1 nodes from model-driven.

---

## 9. Summary

| Question | Answer |
|----------|--------|
| How many M1 nodes exist? | 1196 across 43 directories |
| How many GaC rules? | 115 (18 native + 97 indexed) |
| Is there an M2 schema for GaC? | **Yes** — `gac_rule.yaml` (GacRule type, created 2026-06-26) |
| Does mof-schema-validate.py need changes? | **No** — it's generic, auto-discovers M1 files by `type` field |
| Does mof-bridge-sync.py need changes? | **No** — it's lifecycle-specific (Stage/Gate only); GaC has no model-driven M3 source |
| Is there existing GaC MOF validation? | **Yes** — `bin/gac-mof-validate.py` already validates rules against M2 schema |
| Risk level | **Medium** (if 115 M1 nodes) / **Low** (if 1 metamodel node) |
| Recommended approach | **Partial**: Do Phase 4A (1 metamodel node + M2 fix) now, defer Phase 4B (115 instances) |

### Files Referenced

| File | Path |
|------|------|
| GaC registry (SSOT) | `.omo/_truth/registry/governance-checks.yaml` |
| GaC M2 schema | `projects/ecos/src/ecos/ssot/mof/m2/gac_rule.yaml` |
| M1 governance dir | `projects/ecos/src/ecos/ssot/mof/m1/governance/` (25 GOV-*.yaml) |
| Schema validator | `projects/ecos/src/ecos/ssot/tools/mof-schema-validate.py` |
| Bridge sync | `projects/ecos/src/ecos/ssot/tools/mof-bridge-sync.py` |
| GaC MOF validator | `bin/gac-mof-validate.py` |
| GaC validate | `bin/gac-validate.py` |
| GaC NORTH-STAR | `.omo/_knowledge/gac/NORTH-STAR.md` |
| GaC stage3-4 design | `.omo/_knowledge/gac/stage3-4-design.md` |
| GaC roadmap | `.omo/_knowledge/gac/roadmap-v1.md` |

---

*Analysis complete · 2026-06-28 · worker subagent*
