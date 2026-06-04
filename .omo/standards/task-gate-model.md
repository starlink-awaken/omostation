# Task gate model

> Wave 2 standard for separating canonical task status from derived lifecycle gate facts.

## Canonical status vs gate facts

- `task.status` is the canonical truth-plane field.
- Gate facts are derived from task/run evidence.
- `dispatched` is not a task.status enum.
- `reclaimed` is not a task.status enum.
- `review_ready` is not a task.status enum.
- `accepted` is not a task.status enum.

## Derived gate facts

Wave 2 keeps the canonical status flow stable:

`candidate -> pending -> in_progress -> review -> done`

Gate facts are derived from evidence that already exists around the task:

- `dispatched` -> `dispatch_id`, `run_ref`, and worker assignment exist.
- `reclaimed` -> reclaim artifact and successor linkage exist.
- `review_ready` -> review artifact is linked.
- `accepted` -> required evidence is satisfied and no blocking divergence remains.

## Promotion rule

Promotion to `done` requires review evidence, satisfied evidence requirements, no blocking divergence, and a completion summary before the task leaves `active/`.

## Plane ownership

- **Truth** owns canonical task fields and the gate model definition.
- **Control** owns the current gate summary and divergence snapshot.
- **Delivery** owns dispatch/reclaim/review artifacts referenced by the gate facts.
- **Knowledge** explains the model by linking back to truth/control/delivery sources.
