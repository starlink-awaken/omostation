---
name: deepwork-tracker
description: Track deep work sessions.
triggers:
  - "deep work"
  - "focus session"
  - "pomodoro"
---

# Deep Work Tracker

## Contract
- On each deep work session, record start time, task, and expected outcome.
- On session end, log duration, achieved outcome, and any interruptions.
- Keep one entry per session; do not merge or overwrite earlier entries.
- Report totals when asked: sessions, hours, and completion rate.

## Anti-Patterns
- Do not log shallow or interrupt-driven work as deep work.
- Do not fabricate durations or outcomes.
- Do not store personal reflections outside the session log.

## Output Format
- A session log entry: `YYYY-MM-DD | task | duration_min | outcome`.
- A summary response: `N sessions, H hours, completion P%` plus optional notes.
