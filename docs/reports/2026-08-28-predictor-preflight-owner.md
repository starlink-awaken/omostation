---
type: ephemeral
created: 2026-09-03
---

# Predictor preflight owner evidence — 2026-08-28

The legacy Weijian predictor writes a dated forecast Markdown file below
Documents. This owner preserves its four forecast categories and date-driven
rules while emitting a Workspace-only structured evidence envelope.

## Live smoke

- Schema: `documents.predictor-preflight.v1`.
- Forecast categories: `sanyi`, `assessment`, `quality`, `contracts`.
- Three assessment months and five renewal contracts were emitted.
- Status: `findings`, exit `1`, because the forecast contains unresolved/high
  pressure attention items.
- Documents report tree was not written; evidence target is Workspace runtime.

## Accepted-release cutover

- Accepted release: `accepted-20260905`, root SHA `1b7c11314`.
- Crontab backup: `.omo/evidence/20260827T210911Z-governance-state-mutation-cd18022f/crontab-before.txt`; before SHA-256
  `07b9b8de9c8ef06aa35912d92787fa657f70ca7c4eefd8b1c6212fb76e1c3701`.
- After SHA-256: `f3c7584e7221dfe806e9e57c7582a897ab3124d04d201796d77a275de9c82113`.
- Exact old Documents executor count: `1 → 0`.
- Exact new Workspace owner count: `0 → 1`.
- Unrelated crontab lines: byte-identical.
- Post-cutover smoke: `documents.predictor-preflight.v1`, status `findings`,
  expected exit `1`; summary is three assessment months, five renewals, and
  one new project.
- Documents report tree: 15 files before and after; inventory SHA-256
  `5e4636ae67441b5628b37341e1ff3bce5bc5bbf7300265a092f411c4996b5bdd` on both
  sides. No Documents report write occurred.
- Workspace evidence: `$HOME/Workspace/runtime/predictor-preflight.json`.
- Local cutover evidence directory:
  `.omo/evidence/20260827T210911Z-governance-state-mutation-cd18022f/`.

## Candidate schedule

```cron
30 8 1 * * cd "$HOME/.local/share/omostation/accepted-20260905" && /opt/homebrew/opt/python@3.14/bin/python3.14 lib/documents_predictor_preflight.py --documents-root "$HOME/Documents" --workspace-root "$HOME/Workspace" --evidence "$HOME/Workspace/runtime/predictor-preflight.json" --json >> "$HOME/Workspace/runtime/cron/predictor.stdout.log" 2> "$HOME/Workspace/runtime/cron/predictor.stderr.log"
```

The implementation and live cutover are separate governed steps; the cutover
above records the accepted-release identity, crontab backup/hash, exact
old/new counts, unrelated-line byte identity, and post-cutover smoke.

## Current release verification — 2026-08-29

The active 08:30 day-1 line now runs exactly once from clean
`accepted-20260908`. A fresh no-evidence smoke returned
`documents.predictor-preflight.v1`, status `findings`, exit `1`, with four
forecast categories (`sanyi`, `assessment`, `quality`, `contracts`), three
assessment months, five renewal contracts, one new project, and no errors. The
focused regression suite passes `3/3`, help exits `0`, and no legacy
`predictor.py` process was observed. Documents report content remains
rollback/source material; the owner writes no Documents file.
