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

## Cutover evidence

- Run: `20260827T185253Z-governance-state-mutation-96427aa2`
- Accepted root: `32b78ee65431f12f390e9458f53bd81af6693dab`
- Before crontab SHA-256: `6a0d008c922eda8ed0410b8e91ea93fa2dabc04044d25ee13d0e125d55f68083`
- After crontab SHA-256: `c3e8c84e499400f074429928a6d267b8346153dadbede10e4871abe7631ef334`
- Target replacement: old `controller.py` count `1 -> 0`; new
  `controller-preflight` count `0 -> 1`.
- Unrelated crontab lines: `108`, byte-identical before/after.
- Post-cutover result: `documents.controller-preflight.v1`, status `findings`,
  exit `1`, `rules=11`, `rule_findings=5`, `findings=5`.
- Documents `_runtime/巡检报告` tree fingerprint was identical before/after
  the live owner invocation (`15` files); no legacy report was written.
