---
title: Batch2 B1 C2 schedule harness wall-clock days (honest)
date: 2026-07-24
type: audit
batch: 2
---

# C2 schedule harness — wall-clock day coverage

- distinct calendar days in reports: **1** → ['2026-07-24']
- required: **3** continuous wall-clock days
- status: **partial**

## Honesty

Session span cannot invent dates. Only real report files under
`.omo/_delivery/schedule-harness/` count. Same-day multiple runs do **not**
count as multiple days.

## Mechanism readiness

- entry: `bin/delivery/schedule_harness.py`
- config switch: `SCHEDULE_HARNESS_MODE=sim|physical`
- daily artifact: `sim-report-YYYY-MM-DD.json` + `.jsonl` history

When cron/natural runs accumulate 3 distinct dates, flip C2 to done without
code change.

## Gap

Need 2 more distinct calendar day(s).
