---
type: operations
status: active
owner: governance-team
created: 2026-09-20
last-reviewed: 2026-09-20
scope: business-value-evidence
---

# Value operator runbook

This runbook is for the human operator to record **real, post-baseline use** of
the system.  It does not create value by itself.  Agents must never fabricate,
backfill, proxy, or replay evidence.

## Qualifying sample

A sample counts only when all of the following are true:

1. A real human performed and reviewed the task.
2. It is bound to a real `run_id`, `scene_id`, and persisted `decision_id`.
3. It is covered by a fresh principal authority receipt.
4. It is post-baseline and bound to the frozen baseline digest.
5. Net saved time is at least 60 seconds (`saved - review >= 60`).
6. The final verdict is `accepted` or `modified`.
7. It is explicitly confirmed with
   `--confirm-real-human-post-baseline`.

Never add a sample for a test, replay, speculative estimate, or another person.

## 1. Check current readiness

Read the machine-readable readiness projection:

```bash
curl -fsS http://127.0.0.1:43191/api/v1/agent/value-proof-readiness | jq .
```

Confirm:

- `state` may be `NOT_PROVEN`, but `validation.ok` must be `true`;
- the frozen baseline path exists;
- no validation issues are reported.

## 2. Complete one real task first

Run a real task through the normal workflow.  The task must persist a decision
and produce authoritative decision evidence containing at least:

```json
{
  "decision_persisted": true,
  "decision_id": "decision:<real-id>",
  "principal_id": "principal:xiamingxing",
  "source_class": "real_human"
}
```

Do not hand-write this file unless the authoritative workflow itself exported
it.  The file must be the persisted decision evidence, not a prompt or notes
file.

## 3. Issue a fresh authority receipt

From the repository root:

```bash
/opt/homebrew/bin/python3 -B bin/ssot/value-operator-doctor.py \
  --issue-authority-receipt \
  --principal-id principal:xiamingxing \
  > /tmp/value-authority-receipt.json
```

The receipt is short-lived.  Run doctor and recording in the same session.

## 4. Run the read-only doctor

```bash
/opt/homebrew/bin/python3 -B bin/ssot/value-operator-doctor.py \
  --decision-id <REAL_DECISION_ID> \
  --authority-receipt /tmp/value-authority-receipt.json \
  --decision-evidence <PERSISTED_DECISION_EVIDENCE.json> \
  > /tmp/value-doctor-report.json
```

Continue only when `ready_to_record` is `true`.

## 5. Record the real-use sample

Use the local operator helper with the real values from the completed task:

```bash
/Users/xiamingxing/.local/share/zhixing-dashboard/bin/value-operator.py \
  --review <ACTUAL_HUMAN_REVIEW_SECONDS> \
  --saved <ACTUAL_ESTIMATED_SAVED_SECONDS> \
  --verdict accepted \
  --run-id <REAL_RUN_ID> \
  --scene-id <REAL_SCENE_ID> \
  --decision-id <REAL_DECISION_ID> \
  --authority-receipt /tmp/value-authority-receipt.json \
  --decision-evidence <PERSISTED_DECISION_EVIDENCE.json> \
  --confirm-real-human-post-baseline
```

Use `modified` instead of `accepted` only when you actually modified the output.
If net saving is below 60 seconds, the sample is non-qualifying and must not be
adjusted, split, or retried just to pass.

## 6. Revalidate

```bash
python3 bin/ssot/value-recorder.py validate --json
curl -fsS http://127.0.0.1:43191/api/v1/agent/value-proof-readiness | jq .
```

The target remains 30 qualifying v2 samples.  Current progress is visible from
the readiness endpoint; delivery, CI, or dashboard success never substitutes for
business value.
