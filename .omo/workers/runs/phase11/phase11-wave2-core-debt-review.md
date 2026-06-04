# Phase 11 Wave 2 review

Wave 2 is now the only active Phase 11 packet. Use this review surface to summarize debt-burn progress and exit-gate evidence.

## Current baseline evidence

### T2.1 — CI/test baseline truth

- `projects/kairon/Makefile` no longer uses `python`; it now calls `python3 -m pytest` and returns non-zero when any package test run fails.
- `make kairon-test` is now a truthful baseline signal. Current observed result is **failing**, not green:
  - failing/erroring packages include `agent-runtime`, `agora`, `ecos`, `eidos`, `forge`, `iris`, `kos`, `kronos`, `minerva`, and `sophia`
  - no-tests packages currently include `core-models`, `eu-pricing`, `shared-lib`, `sharedbrain-bridge`, and `wksp`
- `.github/workflows/phase11-ci.yml` now provides the first dedicated Phase 11 CI runner path:
  1. checkout
  2. Python 3.13
  3. `astral-sh/setup-uv@v3`
  4. `uv sync --all-packages`
  5. `make kairon-test`

### T2.2 — eu-pricing test baseline

- `projects/kairon/packages/eu-pricing/tests/` now exists with a first executable suite.
- Current covered behaviors:
  1. consume succeeds and charges the configured operation cost
  2. blocked / insufficient balance rejects without pushing consumption
  3. unknown operations fall back to the default unit cost
- Root cause fixed while adding tests:
  - `EUBalance.sufficient` was incorrectly implemented as a `@property` but called like a method from `consume()`
  - it is now a normal method again
- verification:
  - `cd projects/kairon/packages/eu-pricing && python3 -m pytest tests/ -q` → `3 passed`

### T2.3 — orphan debt audit

- live orphaned task count is now effectively **zero**
- stale orphan debt residue is cleaned automatically by `sync_omo_state.py`
- supporting audit report:
  - `.omo/summaries/phase11-wave2-orphan-audit.md`

### T2.4 — SharedBrain decision

- decision document landed at:
  - `.omo/summaries/SB-DECISION.md`
- chosen posture:
  - **selective extraction + layered contraction**
- operational meaning:
  1. preserve the proven runtime/governance core
  2. keep compatibility seams explicit and shrinking
  3. demote archive/demo residue out of live ownership
  4. do any future rewrites behind stable contracts instead of repo reset

### T2.5 — SharedBrain first test slice

- verified SharedBrain Phase 11 test asset:
  - `projects/SharedBrain/tests/unit/test_m11_harvest_scheduler_scheduling.py`
- current result:
  - `41 passed`
- this exceeds the Wave 2 threshold of **≥10 passing SharedBrain tests**
- coverage focus aligns with the retained core:
  - `organs.D_Governance.organs.harvest_scheduler`

### T2.6 — interactive eidos define CLI

- `eidos define` now exposes an explicit `--interactive` flag in argparse/help output
- implementation status:
  1. `define_command()` now treats `--interactive` as an explicit interactive branch
  2. file-based mode remains supported for backward compatibility
  3. `main()` now returns success for `define` dispatch instead of falling through to `1`
- verification:
  - `uv run pytest packages/eidos/tests/test_cli.py -q` → `4 passed`
  - `uv run --package eidos eidos define --help` shows `--interactive`

### T2.7 — KOS ruff threshold

- local verification baseline:
  - `ruff check packages/kos --statistics --exit-zero`
- current visible result:
  - **80 findings**
- exit judgment:
  - this is already below the Wave 2 target of **≤500**
  - no functional edit was required to satisfy the Phase 11 threshold

### T2.8 — hardcoded path replacement

- highest-impact user-machine absolute paths were removed from:
  1. `scripts/daily-backup.sh`
  2. `scripts/restore-from-backup.sh`
  3. `kos-infra/kos`
  4. `bin/scan_hardcoded.sh`
  5. `tests/integration/test-08-knowledge-pipeline.sh`
  6. `tests/integration/test-09-agora-degrade.sh`
- replacement pattern:
  - prefer `OMOSTATION_ROOT` / `KOS_ROOT`
  - otherwise derive workspace/base paths from script location
- verification:
  - `.omo/tests/test_phase11_wave2_path_debt.py` → `1 passed`

### T2.9 / T2.10 — OntoDerive model unification

- `Inference` now carries `meta_type="inference"`
- `Scheme` now carries `meta_type="document"`
- local normalization now lowercases valid type inputs instead of preserving uppercase variants
- ADRs:
  1. `.omo/summaries/phase11-wave2-adr-ontoderive-inference-metatype.md`
  2. `.omo/summaries/phase11-wave2-adr-ontoderive-scheme-metatype.md`
- verification:
  - `uv run pytest packages/ontoderive/tests/test_models.py -q` → `15 passed`

### T2.11 — Minerva relation unification

- `Relation` now carries additive `meta_relation`, defaulting to `struct`
- existing `predicate` behavior remains unchanged
- ADR:
  - `.omo/summaries/phase11-wave2-adr-minerva-relation-metarelation.md`
- verification:
  - `uv run pytest packages/minerva/tests/unit/test_knowledge.py -q` → `5 passed, 1 skipped`
