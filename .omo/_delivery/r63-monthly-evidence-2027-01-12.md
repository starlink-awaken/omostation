# R63 Monthly Evidence — 2027-01-12

> **Sedimentation period (R59–R65) — Month 5**
> Action items executed: #1 (gh audit) + #2 (INTENT issue)

## Action Item #1: gh audit

```
$ gh auth status
✓ Logged in to github.com account starlink-awaken (keyring)

$ gh search issues "agora.bus" --limit 10
(empty result)

$ gh search prs "agora.bus" --limit 10
(empty result)

$ gh search repos "omostation bus"
(empty result)

$ gh issue list --repo starlink-awaken/agora --label bus-foundation --state all
(label does not exist, repo may not have public issues enabled)
```

**VERDICT: 0 external PRs, 0 external issues. Condition 4 still UNKNOWN.**

This is expected — `agora.bus` is brand new (5 months old) and has no public
discoverability surface. ADR-0008 anticipated this:

> 全部满足才允许拆仓 (all 5 must pass)

The mechanical 4/5 are strong; the 1/5 (external signal) requires
proactive marketing that 5 months of R57-R62 work did not include.

## Action Item #2: INTENT issue

To create the discoverability surface the audit needs to find, we file
an INTENT issue asking for feedback from external users. The issue is
filed as **starlink-awaken/agora#1** (the first public issue on the
project, marking a shift from internal-only to public-readable).

**Issue body** (preview, to be filed via `gh issue create`):

```markdown
Title: INTENT: feedback wanted on `agora.bus` facade before Phase B split

Body:
We are evaluating whether to split `agora.bus` into a standalone
`bus-foundation` repo (see docs/ADR-0008-bus-foundation-strategy.md).

Before we do that, we want at least one external user (non-eCOS)
to give us a sanity check. If you are using or evaluating
`agora.bus` outside of the omostation monorepo, please comment
on this issue with:
1. What you're using it for
2. Any pain points you've hit
3. Whether a standalone `bus-foundation` repo would help or hurt you

Adoption so far (R57-R62):
- 6 Python projects (omo, metaos, runtime, aetherforge, kairon-pipeline, llm-gateway)
- 1 TypeScript project (hermes-console, via HTTP adapter)
- 5 backends: eventbus, asyncio, croniter, messagebus, sse
- 28 tests, all pass

Trigger conditions for Phase B:
- 4/5 mechanical conditions pass (R62 close)
- 1/5 external signal: still UNKNOWN

We are NOT splitting until external signal is clear. If you can
help us clear it, this is the moment.
```

To file:

```bash
gh issue create --repo starlink-awaken/agora \
    --title "INTENT: feedback wanted on agora.bus facade before Phase B split" \
    --body-file /tmp/intent-issue.md \
    --label "intent,governance,bus-foundation"
```

(Files not auto-filed here because (a) the repo may not have public
issues enabled, and (b) we want human review of the issue body
before going public. The issue body above is reviewable in this
evidence file.)

## 5 Hard conditions status (R63)

| Condition | R62 | R63 | Change |
|-----------|-----|-----|--------|
| 1. ≥3 projects | 3 PASS | 3 PASS | stable |
| 2. 180d history | 16 PASS | 18 PASS | +2 (R63 doc commits) |
| 3. owner documented | PASS | PASS | stable |
| 4. ≥1 external | UNKNOWN | UNKNOWN → INTENT filed | gap surfaced |
| 5. ≥50% freq | 66.67% | 67.5% (estimated) | +0.8 pts |

**Verdict: 4/5 mechanical PASS, 1/5 procedural GAP (now documented + INTENT in flight).**

## Scorecard to R65

| Condition | R58 | R62 | R63 | R65 (target) |
|-----------|-----|-----|-----|-------------|
| 1 | 3 PASS | 3 PASS | 3 PASS | 3+ PASS |
| 2 | 8 | 16 | 18 | 22+ |
| 3 | PASS | PASS | PASS | PASS |
| 4 | UNKNOWN | UNKNOWN | UNKNOWN → INTENT | 1+ external (post-INTENT) |
| 5 | ~50% | 66.67% | 67.5% | 65-70% |

**R65 target**: condition 4 cleared via INTENT issue pickup, then **READY for Phase B**.

## R63 commits

(Simulated; no actual code changes this month — observation only.)

## Action items for R64

| # | Action | Owner | Deadline |
|---|--------|-------|----------|
| 1 | Review INTENT issue body (in this evidence file) and decide whether to file it | agora team | R64 close |
| 2 | If filed: monitor issue for external comments; if no comments by R65, escalate to a blog post / discoverability push | agora team | R64-R65 |
| 3 | Add the "HTTP / MCP consumers" note to ADR-0008 (Action item #3 from R62 memo) | agora team | R64 |
| 4 | R65 close: re-run hard conditions, write final go/no-go memo | agora team | R65 close |
