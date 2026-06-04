# runtime/

`runtime/` is the workspace home for **ephemeral runtime residue**.

Use it for:

1. local logs
2. temp state
3. pid and socket files
4. generated session residue
5. non-durable execution caches
6. `run-continuation/` session heartbeat markers
7. runtime boundary contracts such as `system-runtime-boundary.yaml`

Do **not** use it for:

1. `.omo` goals/state/tasks/standards
2. long-lived user data
3. project source code
4. durable delivery evidence
