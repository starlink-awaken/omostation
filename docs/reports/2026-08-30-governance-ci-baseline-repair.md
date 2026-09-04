---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-98
---

# Governance and CI baseline repair — implementation evidence

This report records the final verification of the declared root and child
surfaces. The repair did not mutate Documents content, host runtime, or any
quarantine payload.

## Scope

- Root governance and CI only.
- One missing Workspace entrypoint and one existing child Agora gitlink bump.
- No Documents host mutation and no quarantine payload mutation.

## Implementation record

- Root implementation commits: `c40aadae6617a8da834f579756242f50fb5a0639`,
  `23fa8295b3d01cb281953d07b263e36caa2853a3`,
  `4282a8b4d11e109f048abc615b478a4652ea3608`, and
  `13ca27a098e919bfb053477fe8d33c3ca6757b20`.
- Root PR #2683 merged to `origin/main` as
  `af98dbf32141501f9143266419b6a5f5adf7eb90`.
- Agora child PR `#50` merged to child `origin/main` as
  `c30c0456905b168bbb36b1593faeb5b35a823eb5`; the root gitlink was verified
  against that child main commit.
- The malformed `system.yaml` projection was repaired minimally, then
  `omo state sync-tasks` recomputed task counters and the registry index with
  no count delta (`290/7/1/1/299`).
- The generated capability projection was refreshed from the complete child
  registry: 27 MCP servers, 629 MCP tools, 282 BOS services, and 169 CLI
  commands.

## Verification record

- `uv run --with pyyaml python bin/gac/gac-mof-validate.py --json`: `ok=true`,
  80 rules, zero errors.
- `uv run --with pyyaml python bin/adr/adr-coverage.py --json`: 390 ADRs,
  zero missing/duplicate/frontmatter/index findings.
- `uv run --with pyyaml python bin/gac/check-resident-bos.py`: PASS; four
  required routes resolve and resident is allowlisted.
- Focused regression: `12 passed` across state coherence, evidence smoke
  paths, and ADR coverage tests.
- `uv run --with pyyaml python bin/ssot/ssot-guardian.py`: PASS.
- `uv run --with pyyaml python bin/ssot/current-state-coherence.py --json`:
  `ok=true`, phase/wave aligned, stored task counts aligned.
- `uv run --with pyyaml python bin/ssot/script-registry.py validate`: 542
  registered scripts, PASS; bin quota reports `新增 0 / 删除 0`.
- `uv run --with pyyaml python bin/ssot/gen-capability-registry.py --check
  --quiet`: PASS with no generated projection drift.
- `make gac-local-gate`: PASS, 57 checks executed, with only the repository's
  six pre-existing known-unavailable checks skipped.
- Compatibility owner emits JSON under both the managed interpreter and the
  macOS system-Python fallback; canonical health status remains truthful.

## Boundary

This repair restores governance observability and the canonical Workspace
health owner. It does not claim user-value completion; value remains
`NOT_PROVEN` and Documents migration families retain their own owner-parity
state.
