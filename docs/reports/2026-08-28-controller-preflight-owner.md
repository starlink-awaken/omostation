# Controller preflight owner evidence — 2026-08-28

The legacy Weijian `controller.py` writes a daily report beneath Documents and
invokes several Documents `_runtime` scripts. This owner reproduces the
controller's 11 CR observation families as a Workspace-only, read-only envelope
through the existing `documents-domain-owner-job.py` entrypoint.

## Contract

- Schema: `documents.controller-preflight.v1`.
- Rules: CR01, CR02, CR03, CR05, CR08, CR23, CR24, CR25, CR26, CR29, CR30.
- Exit `0`: no findings; exit `1`: findings were observed; exit `2`:
  unavailable or invalid inputs.
- No Documents script is executed. Evidence is written only below Workspace
  runtime state. The legacy controller remains available for rollback/parity.

## Live smoke

Against `$HOME/Documents/@工作文档/卫健委` on 2026-08-28:

- Schema: `documents.controller-preflight.v1`.
- Status: `findings`, exit `1`.
- All 11 rule IDs were present in the envelope.
- Findings: 5 rule families — CR02 has 14 warning signals; CR03 has 47 stale
  30–60 day documents; CR24 has 31 stale models; CR29 reports one project with
  missing stages; CR30 reports 29 missing material categories.
- The Documents source tree and report directory were not written by the owner.

## Candidate schedule

```cron
0 9 * * 1 cd "$HOME/.local/share/omostation/accepted-20260902" && uv run --with pyyaml python bin/gac/documents-domain-owner-job.py controller-preflight --json --documents-root "$HOME/Documents" --workspace-root "$HOME/.local/share/omostation/accepted-20260902" --evidence .omo/_delivery/documents-plane/controller-preflight.json >> "$HOME/Workspace/runtime/cron/documents-plane.log" 2>&1
```

The candidate is not installed by the implementation PR. A separate governed
cutover must record accepted-release identity, crontab backup/hash, exact
old/new counts, unrelated-line byte identity, and post-cutover smoke.
