# Worker Reclaim Note

DISPATCH_ID: `<dispatch-id>`
TASK_ID: `<task-id>`
PREVIOUS_WORKER: `<worker-id>`
NEXT_WORKER: `<worker-id|tbd>`
RECLAIM_REASON: `<stale|zombie|permission_denied|tool_failure|manual_reassign>`
RECLAIMED_AT: `<ISO8601>`

## Last Known Good State

- task status:
- last checkpoint time:
- last material write:
- current dispatch state:

## Partial Outputs Preserved

- changed files:
- evidence captured:
- logs/session refs:

## Why The Worker Was Reclaimed

`<short explanation>`

## Safe Restart Point

- what the next worker should read first
- what should not be retried blindly
- which gate/permission blocked progress

## Coordinator Decision

- requeue to same worker: yes/no
- reassign to new worker: yes/no
- move task to blocked: yes/no
- move task to review: yes/no
