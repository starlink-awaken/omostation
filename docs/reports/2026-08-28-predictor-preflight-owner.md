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

## Candidate schedule

```cron
30 8 1 * * cd "$HOME/.local/share/omostation/accepted-20260905" && /opt/homebrew/opt/python@3.14/bin/python3.14 lib/documents_predictor_preflight.py --documents-root "$HOME/Documents" --workspace-root "$HOME/Workspace" --evidence "$HOME/Workspace/runtime/predictor-preflight.json" --json >> "$HOME/Workspace/runtime/cron/predictor.stdout.log" 2> "$HOME/Workspace/runtime/cron/predictor.stderr.log"
```

The candidate is not installed by the implementation PR. A separate governed
cutover must record accepted-release identity, crontab backup/hash, exact
old/new counts, unrelated-line byte identity, and post-cutover smoke.
