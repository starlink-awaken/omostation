# Post-2408 Main Recovery — R1/H1/R2a evidence

## Immutable mainline evidence

- Current verified main: `6bcf17b4e7f2d0de6f444bd5e5da10dd7ad7c3c8`.
- R1 recovery merged in PR `#2438`.
- H1a strict gate promotion merged in PR `#2441`.
- H1c branch-protection writer and baseline fixes merged in PRs `#2451`, `#2452`,
  and `#2455`.
- R2a immutable runtime policy merged in PR `#2457`.

## R1 and H1 disposition

- ADR-0432 remains `candidate` with evidence status `UNPROVABLE`.
- The existing `gac-gate` strict step is blocking and passed on main canary
  runs `33165584374` and `33165797084`.
- Live branch protection was changed only through the canonical status-check
  subresource writer. The cache-busted before/after receipt proves that
  `gac-gate` was added while review, admin, force-push, deletion, linear-history
  and strictness settings were preserved.
- The final protection check reports the desired three-context set aligned.

## R2a repository hygiene

- `omo-runtime-stamp-policy.py --treeish` now audits an immutable git tree and
  does not treat tracked files or `.gitignore` matches as automatically allowed.
- The PR tree, merged main tree and fresh clone each report zero forbidden
  runtime paths.
- Approved output/cache/snapshot artifacts were removed from the repository
  final tree and given precise ignored landing rules. Runtime contracts,
  fixtures and stable runtime code remain tracked.
- Ledger lint, script registry validation, focused tests, document governance,
  conflict scan and mainline strict GaC are green on the verified revision.

## R2b host boundary

R2b remains `UNPROVABLE` and was not executed. Read-only evidence confirms that
the candidate host files are owned by `xiamingxing:staff`, have stable recorded
digests, and both candidate SQLite databases pass `PRAGMA integrity_check`.

The host also has active launchd jobs and crontab entries that can write
Workspace/runtime or related evidence. The shared `/Users/xiamingxing/Workspace`
checkout currently contains unrelated dirty files, `.omo` state changes and
submodule changes. No backup, producer stop/start, checkout update, ignored
restore or cleanup was performed, so no host-data preservation claim is made.

## Final disposition

- BET `BET-Y1Q3-T6-15` remains `candidate` until R2b evidence exists.
- Product P0 Wave A remains locked by the explicit R2b prerequisite.
- Engineering and operational evidence remain value-exempt; personal value is
  `NOT_PROVEN`.
