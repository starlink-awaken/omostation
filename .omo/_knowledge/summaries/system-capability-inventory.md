---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: summaries/ 根目录历史快照批量归档, 当前状态以 .omo/state/system.yaml + .omo/tasks/active/ 为准"
---
# Phase 11 Wave 1 — System capability inventory (T1.5)

> Scope: `projects/kairon/`
> Method: workspace package scan + rough code metrics (`*.py` count/LOC excluding caches; test modules via `test_*.py` / `*_test.py`; `ruff check --statistics --exit-zero .`)
> Notes:
> - `Py files`/`LOC` include tests.
> - `Tests` is a test-module count (not pytest-collected cases).
> - `Owner` is read from `pyproject.toml` (`project.authors[0].name`) when present.
> - `Health` is a **derived** bucket from `Ruff findings` using explicit thresholds (see below).
> - The **L1-L4 layer** column is an inventory label inferred from current package role/name so Wave 1 can group capability surfaces consistently.

## Inventory rubric

- **L1 Foundation** — shared model/schema/kernel surfaces
- **L2 Core capability** — reasoning, extraction, knowledge, and analysis engines
- **L3 Orchestration/service** — runtime, schedulers, pipelines, multi-tool orchestration
- **L4 Interface/product edge** — user-facing bridges, vertical products, workspace interfaces

## Health rubric (derived)

- `green`: Ruff findings < 20
- `yellow`: 20–99
- `orange`: 100–499
- `red`: >= 500
- add `testless` if `Tests == 0`

## Package inventory (plan scope: 17 packages)

| Package | Layer | Owner | Py files | LOC | Tests | Ruff findings | Health | Snapshot |
|---|---:|---|---:|---:|---:|---:|---|---|
| `core-models` | L1 | Workspace Team | 6 | 267 | 0 | 1 | green + testless | Minimal shared types/models |
| `shared-lib` | L1 | — | 1 | 146 | 0 | 2 | green + testless | Tiny common helper surface |
| `ssot` | L1 | 运营生态组 | 64 | 17,616 | 10 | 1,905 | red | Largest governance/schema debt hotspot |
| `codeanalyze` | L2 | Workspace Team | 72 | 7,560 | 9 | 17 | green | Static/code intelligence utility surface |
| `eidos` | L2 | Workspace Team | 45 | 5,954 | 16 | 9 | green | Strongest interactive modeling/test posture in core tools |
| `iris` | L2 | xiamingxing | 56 | 10,513 | 10 | 52 | yellow | Knowledge/search adjacent capability surface |
| `kos` | L2 | Kos Contributors | 85 | 14,485 | 16 | 80 | yellow | Large knowledge substrate; lint debt still meaningful |
| `minerva` | L2 | Minerva Contributors | 100 | 17,046 | 30 | 17 | green | Research/retrieval heavy package with moderate debt |
| `ontoderive` | L2 | Summer | 127 | 18,839 | 47 | 3 | green | Best-tested core reasoning package in the workspace |
| `sophia` | L2 | Minerva Contributors | 16 | 2,304 | 6 | 16 | green | Smaller reasoning/knowledge companion |
| `agora` | L3 | Minerva Contributors | 98 | 18,774 | 30 | 39 | yellow | Major orchestration hub / service registry |
| `cron-service` | L3 | — | 12 | 1,849 | 1 | 88 | yellow | Small surface, disproportionate lint debt |
| `kronos` | L3 | Workspace Team | 24 | 3,817 | 9 | 15 | green | Scheduling/runtime support |
| `metaos` | L3 | — | 32 | 7,548 | 11 | 72 | yellow | Runtime/meta orchestration surface |
| `forge` | L4 | — | 35 | 10,142 | 11 | 110 | orange | Product/CLI surface with high lint debt |
| `sharedbrain-bridge` | L4 | — | 5 | 140 | 0 | 14 | green + testless | Thin bridge package |
| `wksp` | L4 | 夏铭星 | 53 | 11,996 | 38 | 144 | orange | Workspace-facing interface with good test depth, high lint debt |

## Additional packages detected (out of plan scope)

The live `projects/kairon/packages/*` directory currently contains three additional packages beyond the Phase 11 “17-package” shorthand:

| Package | Layer | Py files | LOC | Tests | Ruff findings | Health |
|---|---:|---:|---:|---:|---:|---|
| `agent-runtime` | L3 | 16 | 2,600 | 5 | 69 | yellow |
| `ecos` | L3 | 31 | 5,901 | 8 | 102 | orange |
| `eu-pricing` | L4 | 2 | 147 | 0 | 5 | green + testless |

## High-signal findings

1. **Wave 2 debt pressure is dominated by `ssot`**: `ssot` is an outlier at **1,905 ruff findings** (next tier: `wksp` 144, `forge` 110, `ecos` 102, `cron-service` 88, `kos` 80).
2. **Test posture is uneven** (by test-module count): `ontoderive` (47), `wksp` (38), `agora` (30), and `minerva` (30) lead; 3 packages in the plan-scope inventory show **0 discovered tests** (`core-models`, `shared-lib`, `sharedbrain-bridge`).
3. **Plan shorthand vs live inventory**: Wave 1 includes a 17-package baseline table for alignment with the Phase 11 plan, but the live workspace inventory is **20 packages** (the 3 additional packages are listed above).
4. **Small packages are not necessarily low debt**: `cron-service` is tiny but still has 88 ruff findings; `eu-pricing` remains testless.

## Suggested Wave 1 / Wave 2 usage

- Treat this file as the **baseline snapshot** for T1.5.
- Promote the top lint/test debt surfaces into Wave 2 ownership explicitly:
  - `ssot`
  - `wksp`
  - `forge`
  - `ecos`
  - `cron-service`
  - `kos`
- Keep `ontoderive`, `wksp`, and `eidos` as the strongest early sources for “known-good” package patterns when normalizing weaker packages.
