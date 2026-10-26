---
schema: md/v1
status: completed
lifecycle: report
type: closeout-receipt
owner: governance-team
last-reviewed: 2026-10-26
bet_id: BET-Y2Q4-T10-340401
---

# BET-Y2Q4-T10-340401 closeout receipt — scene card shared parser

Ledger: `docs/plans/3y-bet-ledger.yaml` (`BET-Y2Q4-T10-340401`)  
Specification: `docs/superpowers/specs/2026-10-20-v34-canonical-scene-parser.md`  
Retro: `.omo/_knowledge/retros/BET-Y2Q4-T10-340401.md`  
Workflow: `20261026T101604Z-bet-execution-d8fb451e`

## Delivery scope

- Added a read-only shared parser in `lib/scene_card_document.py` for single-document and explicit frontmatter-plus-body scene cards.
- Replaced ad hoc `yaml.safe_load` / `safe_load_all` document selection in review, lifecycle, and lineage entry points.
- Added strict duplicate-key detection, source-aware ambiguity failures, canonical body selection, and source SHA provenance.
- Added shared write-back helpers that update only pre-existing matching frontmatter mirrors, re-parse in memory, and preserve document order.
- Added parser and caller convergence regressions; review/lifecycle behavior and readiness authority remain unchanged.

## Validation evidence

All commands ran on 2026-10-26 in
`/Users/xiamingxing/Project/.worktrees/omostation-scene-parser` at base commit `c885c25e28cb6fdc900533d196e7abdc45ab572c`.

```text
uv run --with pyyaml pytest -q \
  tests/test_scene_card_document.py \
  tests/test_scene_card_parser_callers.py \
  tests/test_scene_card_lifecycle_check.py \
  tests/scene_v2/test_scene_card_registry_connector.py \
  tests/test_scene_card_candidates.py \
  tests/test_scene_card_intake.py
→ 45 passed in 0.40s

python3 -c "from pathlib import Path; import lib.scene_card_document as m; \
  p=Path(m.__file__).resolve(); print(p); \
  assert p.is_relative_to(Path.cwd().resolve())"
→ /Users/xiamingxing/Project/.worktrees/omostation-scene-parser/lib/scene_card_document.py

uv run --with pyyaml python bin/gac/ci-local-fast.py --ruff-gate
→ Ruff regression gate: known_debt=0 resolved=11 new=0

uv run --with pyyaml python bin/gac/gac-local-gate.py \
  --scope files --file bin/ssot/scene-card-review.py --summarize
→ PASS (68 checks executed, 0 hard fails, 1 SOFT WARN)

uv run --with pyyaml python bin/agent-workflow.py verify \
  20261026T101604Z-bet-execution-d8fb451e \
  --from-diff --include-untracked --execute --json
→ ok=true; gac-local-gate returncode=0; workflow lint returncode=0

git diff --check && git diff --cached --check
→ exit 0
```

Interpreter and dependency provenance: Python `3.14.7` via `uv`; PyYAML `6.0.3`. The isolated worktree was initialized with pinned submodules, generated `cockpit-ui/dist`, materialized `.omo/state/system.yaml`, and produced a local evidence-smoke report for the governance gate. These are validation-side runtime artifacts and are not part of the source diff.

The implementation-only frozen diff at verification time was 26,709 bytes with SHA256
`7de4a6ceda81a989c91f1064b4edbb2037adf69f202b9ac1b81cc80423ac3e64`. The final branch adds this receipt, its retro, and ledger evidence after that hash was captured.

## Boundary

- Engineering is `VERIFIED`: accepted parser contract, three entry points, write-back compatibility, and focused/governance checks pass in this worktree. Before PR merge, ledger `merged_reachable_commit` is intentionally set to the unmerged delivery head; after squash merge it is replaced by the actual `origin/main` merge commit.
- Operational is `PROVEN` only for local governance and workflow verification; no production scene card, projection, daemon, or deployment was exercised.
- Value remains `NOT_PROVEN`: there is no user-value metric or business adoption claim.
- `activate`, `transition`, and `promote` were tested only with temporary public fixtures.
- The local gate soft warning is limited to a missing KOS SQLite runtime artifact; the check reports exit 78 as an explicit skip, not a pass.

## Rollback

The rollback unit is this branch's single squash merge commit. Runtime artifacts generated in the isolated worktree do not require rollback; no production state, launchd job, submodule pointer, or real scene card was changed.
