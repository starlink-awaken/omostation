# Worker Prompt Contract

WORKER_ID: `codebuddy`
TASK_ID: `P2-FIX-HARDCODED-PATHS`
TRANSPORT: `cli_prompt`
READ_BUDGET: `5`

## Mission

Fix remaining 21 hardcoded /Users/xiamingxing paths

## Task SSOT

- Task YAML: `.omo/tasks/active/P2-fix-hardcoded-paths.yaml`
- Source doc: `.omo/standards/hardcoded-paths-inventory.md`

## Constraints

- You may write to `projects/kairon/packages/eidos/`
- You may write to `projects/kairon/packages/ecos/`
- You may write to `projects/kairon/packages/ssot/`
- You may write to `projects/kairon/packages/agent-runtime/`
- You may write to `projects/kairon/packages/metaos/`
- You may write to `.omo/standards/hardcoded-paths-inventory.md`
- You may write to `.omo/tasks/active/P2-fix-hardcoded-paths.yaml`
- You may write to `.omo/workers/runs/p2-fix-hardcoded-paths-codebuddy-20260530-145751-review.md`
- Do not modify global state files.
- Do not mark the task `done`.
