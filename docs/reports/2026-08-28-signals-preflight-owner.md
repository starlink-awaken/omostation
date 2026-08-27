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
10 6 * * 1 cd "$HOME/.local/share/omostation/accepted-20260831" && uv run --with pyyaml python bin/gac/documents-domain-owner-job.py signals-preflight --json --documents-root "$HOME/Documents" --workspace-root "$HOME/.local/share/omostation/accepted-20260831" --evidence .omo/_delivery/documents-plane/signals-preflight.json >> runtime/cron/documents-plane.log 2>&1
```

The candidate is not installed by the implementation PR. A separate governed
cutover must record accepted-release identity, crontab backup/hash, exact
old/new counts, unrelated-line byte identity, and post-cutover smoke.
