---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-07-31
review-state: metadata-only
metadata-migrated-at: 2026-07-31
type: ssot
---
# Workorder Authoring Standard (STRAT-P85 G2.2)

Every workflow-supporting task under `.omo/tasks/` must use this
frontmatter. The set of keys is the schema enforced by
`check-workorder-schema` (built in G2.2 of STRAT-P85) and consumed by
`check-governance-ratio` (G1.2) and `check-redline-coverage` (G2.1).

## Required fields

| Field | Type | Description |
|---|---|---|
| `id` | string | Run-stable identifier. Convention: `<scope>-<short>`. |
| `title` | string | ≤ 80 chars. Action-oriented. |
| `description` | string | What the work moves forward and why. |
| `track` | enum | One of `governance`, `collaboration`, `flex`. Required by G1.2 ratio accounting. Default `flex` if absent (and a G2.1 GATE warns). |
| `task_type` | enum | One of `governance`, `collaboration`, `product`, `research`, `operational`. |
| `appetite` | string | The time box the work is committed to (e.g. `2d`, `1w`). |
| `授权范围` | string | What the agent is allowed to commit without human review. Anything outside this scope requires a human approval card. |
| `需人类拍板项` | list[str] | Explicit list of decisions that need a human before this work can be considered done. |
| `熔断条件` | list[str] | Conditions that turn this work into a halt + human review (e.g. `为让 G1.2 达标而给工单错标 track`). |
| `验收标准` | list[str] | Binary, verifiable outcomes. Each item should be one of: (a) a real file/SSOT that now exists, (b) a real CI run that now passes, (c) a real metric now in range. |
| `evidence_required` | list[str] | Required proof items, in the form of `(file path, commit, PR, CI run id)`. |
| `risk_level` | enum | `L0`..`L3` per the `operation-levels.md` standard. |
| `allowed_operation_level` | enum | Same scale. Must be ≥ `risk_level`. |
| `human_approval_required` | bool | When `true`, the work must wait for an explicit human ack in `approval_ref`. |
| `status` | enum | `pending` | `active` | `closed` | `archived`. |
| `priority` | enum | `low` | `medium` | `high` | `urgent`. |
| `source_docs` | list[str] | Provenance pointers (paths or capability URIs). |

## Optional but recommended

- `acceptance_criteria` (alias of `验收标准` for systems that choke on
  non-ASCII keys)
- `tags` (free-form taxonomy)
- `deliverables`, `test_plan`, `knowledge_refs`, `handoff_refs`,
  `review_ref`, `run_ref` (existing keys retained for compatibility)

## Compatibility

- Existing `.omo/tasks/planned/*.yaml` files do **not** need to be
  rewritten retroactively. `check-workorder-schema` skips files
  with `status: archived` or `status: closed` so we do not penalise
  historical work.
- New tasks created after 2026-07-28 must conform.

## Track semantics

- `governance` — work that maintains the system itself (gates,
  redlines, registry, audit, ADRs). Counted against the ADR-0249
  40% governance cap.
- `collaboration` — work that delivers the P84 dual-track
  collaboration capability (scenarios, agent mesh, executor).
- `flex` — work that does not fit the two above (product surface,
  operational hygiene, R&D, anything the two tracks cannot
  categorise). Tracked separately for the 20% flex budget.
