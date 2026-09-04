---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-94
---

# T10-92 mainline artifact recovery — implementation evidence

## Finding

The merged T10-92 commit `78fb360d4e27d1c65b62d9fe5bf68d40fed89bc1` contained
the OPC quarantine registry evidence, ledger entry, specification, report,
retrospective, and bootstrap waiver. After merge #2645, current
`origin/main=673c15f18fba34e7019a0ed52dd91a09878f728d` lacked all six root
artifacts and had reverted `opc-tools` to `pending`.

## Recovery

The four standalone T10-92 documents were restored byte-for-byte from the
immutable T10-92 tree. The registry and ledger were reconstructed from that
same source while preserving the current mainline content around them. No
Documents path, Workspace quarantine payload, submodule pointer, runtime
state, or unrelated governance record was changed.

Restored root artifacts:

- `.omo/_truth/registry/documents-content-plane-migrations.yaml`
- `docs/plans/3y-bet-ledger.yaml`
- `docs/superpowers/specs/2026-08-30-opc-runtime-tools-quarantine-design.md`
- `docs/reports/2026-08-30-opc-runtime-tools-quarantine.md`
- `.omo/_knowledge/retros/BET-Y1Q3-T10-92.md`
- `.omo/_truth/governance-evidence/waiver-2026-08-30-t10-92-opc-tools-bootstrap.md`

## Verification

- Source comparison: current main was missing exactly the six T10-92 paths
  relative to `78fb360d4`; the merge tree delta was 247 deleted lines and one
  registry status rollback.
- T10-92 registry evidence is restored as `opc-tools: in_progress` with the
  original source/target fingerprint
  `sha256:26102e4e70a990528e847e285e1955e72b63868cd749892c2e3ca383d5ea7ab7`,
  manifest ref, consumer receipt, and `owner_parity: pending`.
- T10-92 remains `done` with `completion_evidence.overall_state:
  delivery_accepted` and value `NOT_PROVEN`.
- T10-94 completion checks: `bet-ledger lint`, migration checker, and
  `doc-ssot-lint` pass after submodule initialization; diff is limited to the
  recovery surfaces.

## Boundary

This is a mainline evidence restoration, not a new OPC migration and not an
owner-parity claim. The host-side quarantine remains reversible and unchanged.
