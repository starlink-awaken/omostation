# as_of principle (STRAT-P85 G2.3)

> Status: established pattern · Owner: governance-team · Source: 综合方案 P0-4
> Purpose: any time-bound number, ranking, or "now/old/new" claim
> must either carry an `as_of: <UTC ISO date>` field or point to a
> regenerable artifact. The pattern locks the rule and the regeneration
> recipe so a future reader can verify the number without trust.

## When the pattern applies

- Aggregated metrics in the BRIEF or in any `.omo/state/*.yaml`.
- "健康分 / debt 项数 / run 数" style summaries in commit messages.
- Dashboards under `docs/`.
- Recommendations that depend on the current health score, debt list,
  or agent-workflow ledger.

It does **not** apply to:

- Single-shot time-stamped events (a commit date is already its own
  as-of).
- Code contracts (a function's behaviour does not drift over weeks).

## How to apply

1. **Inline field**. When a number lives in a yaml, json, or markdown
   table, add an `as_of` field or column on the same row. Example:
   ```yaml
   ratio: 0.42
   as_of: "2026-07-28T00:00:00Z"
   ceiling: 0.40
   ```
2. **Pointer to a regenerable artifact**. When the number is large
   (a full list of debt items, an LLM trace, a 30-day event slice),
   cite the command that regenerates it. Example:
   ```
   governance_ratio_source: "uv run --with pyyaml python bin/gac/check-governance-ratio.py --json"
   as_of: "regenerated 2026-07-28T07:30:00Z"
   ```
3. **As-of in markdown tables**. Use a leading row or trailing footer:
   ```
   | metric | value | as_of |
   |---|---|---|
   | health | 96 | 2026-07-28 |
   ```

## Regeneration checklist

For any metric the BRIEF carries, the answer to "can I re-verify
this in 30 seconds?" must be yes. The regenerable artifact is the
canonical answer; the `as_of` field is the contract that the
artifact was current at the time the metric was first published.

## Anti-patterns

- "Recent" without a date.
- "We have N things to do" without a command that emits the list.
- A point-in-time number copied from a screenshot.
- A historical figure presented as a current one (this is the most
  common silent drift; an `as_of` is the cure).

## Consumers

- `brief-protect` GAC gate reads this pattern when validating that
  generated BRIEF.md carries the required `as_of` fields.
- The dashboard regeneration script should reject any panel that
  does not include `as_of` in its output schema.
- Authors of new metrics MUST link the pattern in their PR.
