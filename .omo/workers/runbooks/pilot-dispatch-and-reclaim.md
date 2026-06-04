# Pilot Runbook: Dispatch, Monitor, Reclaim

This runbook operationalizes the worker framework for the first real tasks.

## 1. Pilot Scope

Use this runbook for:

- one active task at a time
- one worker lease at a time
- L1 execution only
- `codebuddy` or `reasonix` as worker

Do not use this runbook to release L2/L3 actions.

## 2. Preconditions

Before dispatch:

1. task exists in `.omo/tasks/active/`
2. task scope is narrow enough for one worker
3. relevant standards/docs are identified
4. output paths are explicitly declared
5. worker exists in `.omo/workers/registry.yaml`
6. blocked domains are not in scope

## 3. Dispatch Packet

For each run, prepare four artifacts under `.omo/workers/runs/`:

1. copied task envelope
2. copied worker prompt
3. dispatch record
4. optional scratch review note

Recommended naming:

- `<dispatch-id>-envelope.yaml`
- `<dispatch-id>-prompt.md`
- `<dispatch-id>-dispatch.yaml`
- `<dispatch-id>-review.md`

## 4. Dispatch Flow

1. Set task to `in_progress`.
2. Assign `assigned_to` to the worker ID.
3. Set `dispatch_id` and `run_ref` on the task YAML.
4. Create run artifacts under `.omo/workers/runs/`.
5. Launch the worker with the prompt artifact.
6. Record launch command, session ref, and launch time in the dispatch record.
7. Move dispatch state from `dispatched` -> `acknowledged` -> `running`.

## 5. Launch Patterns

### 5.1 codebuddy

CLI prompt mode:

```bash
PROMPT_FILE=.omo/workers/runs/<dispatch-id>-prompt.md
codebuddy -p "$(cat \"$PROMPT_FILE\")"
```

ACP mode:

```bash
codebuddy --acp --acp-transport stdio
```

### 5.2 reasonix

CLI prompt mode:

```bash
PROMPT_FILE=.omo/workers/runs/<dispatch-id>-prompt.md
reasonix run "$(cat \"$PROMPT_FILE\")"
```

ACP mode:

```bash
reasonix acp
```

## 6. Monitor Flow

During execution, coordinator checks:

1. has the worker acknowledged the task?
2. has a checkpoint or material write happened within 5 minutes?
3. has the worker produced evidence after the read budget?
4. has the worker attempted an L2/L3 action without approval?

Update the dispatch record on each meaningful event.

## 7. Reclaim Flow

If no progress appears:

- at 15 minutes: warn and inspect
- at 20 minutes: mark dispatch `warning`
- at 20+ minutes with no recovery: mark dispatch `lease_expired`
- at 30 minutes: reclaim the lease

Reclaim procedure:

1. preserve current logs/stdout/session refs
2. preserve partial files and evidence
3. create a reclaim note
4. mark dispatch `reclaimed`
5. either reassign or move task to `blocked`/`review`

## 8. Reassignment Rule

When reassigning:

1. new worker reads the old dispatch record first
2. then reads the reclaim note
3. then reads the task envelope
4. only then resumes implementation

This avoids knowledge loss and duplicate investigation.

## 9. Pilot Success Criteria

Pilot is successful when:

- worker completes or yields a reusable partial result
- dispatch record shows the execution history
- reclaim can happen without losing the task state
- reviewer can decide from artifacts alone
- a second worker can continue without hidden context
