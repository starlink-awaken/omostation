---
type: ephemeral
created: 2026-09-03
---

# Signals preflight owner evidence — 2026-08-28

The legacy `@公共/_runtime/signals-rotate.py` rewrites Documents
`@驾驶舱/_control/SIGNALS.md` and appends machine records under `_generated`.
The replacement is a Workspace-only observation owner; it leaves the source
content unchanged and does not replace canonical OMO/resident signal ingress.

## Owner contract

- Entry: `bin/gac/documents-domain-owner-job.py signals-preflight`.
- Schema: `documents.signals-preflight.v1`.
- Exit `0`: readable signal ledger with no machine signals; exit `1`: readable
  ledger with findings; exit `2`: missing/invalid source or evidence boundary.
- Documents is read-only; evidence is written only below Workspace runtime
  state.

## Live preflight

- Source: `$HOME/Documents/@驾驶舱/_control/SIGNALS.md`.
- Result: 3 signals, all human/user sources, machine `0`, status `ok`, exit `0`.
- The source file was not rewritten and no Documents `_generated` output was
  created by the owner.

## Candidate schedule

The canonical candidate replaces only Monday 06:10:

```cron
10 6 * * 1 cd "$HOME/.local/share/omostation/accepted-20260908" && uv run --with pyyaml python bin/gac/documents-domain-owner-job.py signals-preflight --json --documents-root "$HOME/Documents" --workspace-root "$HOME/.local/share/omostation/accepted-20260908" --evidence .omo/_delivery/documents-plane/signals-preflight.json >> runtime/cron/documents-plane.log 2>&1
```

## Cutover evidence

- Run: `20260827T175111Z-governance-state-mutation-702337a3`
- Accepted root: `c5187900d4ae77e16631c512571cdb82a35dcafb`
- Before crontab SHA-256: `705894d0cf34e8a61fa01dfd8dd3452b15cfc34ce735384cb5a8a7bf730d2cdd`
- After crontab SHA-256: `ef7e25fc16346b6792cbdb918d1e971a61f6dd6a17b270615b9dc5c9932f6d7b`
- Target replacement: old `signals-rotate.py` count `1 -> 0`; new
  `signals-preflight` count `0 -> 1`.
- Unrelated crontab lines: `108`, byte-identical before/after.
- Post-cutover result: `documents.signals-preflight.v1`, status `ok`, exit `0`,
  `human=3`, `machine=0`, `total=3`, errors `[]`.
- The accepted release ran from its own directory; `SIGNALS.md` was not
  rewritten and no Documents `_generated` output was created by the new owner.

## Current verification

The active 06:10 line now uses clean `accepted-20260908` and appears exactly
once. A fresh live smoke returned `documents.signals-preflight.v1`, status
`ok`, exit `0`, human `3`, machine `0`, total `3`, errors `[]`. The source
SIGNALS.md remained unchanged, no `_generated` output was created, and no legacy
signals-rotate process was observed. Focused tests pass `4/4`.
