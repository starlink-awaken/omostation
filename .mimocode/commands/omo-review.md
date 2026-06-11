---
description: "Read OMO governance files and produce a structured overview of system state, goals, active tasks, and governance health."
---

# OMO Governance Review

Read the OMO governance files from the workspace and produce a structured overview.

## Steps

1. **Read system state**: `Read .omo/state/system.yaml`
2. **Read goals**: `Read .omo/goals/current.yaml`
3. **Read active tasks**: List all `.omo/tasks/active/*.yaml` files, read each
4. **Read summaries**: Check `.omo/summaries/` for latest phase closeout
5. **Read standards**: Scan `.omo/standards/` for governance rules
6. **Read PROJECTS.yaml**: `Read .omo/PROJECTS.yaml` for project registry

## Output Format

```markdown
## OMO Governance Review — [Date]

### System State
- Current Phase: ...
- Health: ...

### Goals
| Goal | Status | Progress |
|------|--------|----------|

### Active Tasks
| Task | Priority | Status | Owner |
|------|----------|--------|-------|

### Governance Health
- Standards compliance: ...
- Debt items: ...
- Recent audit findings: ...

### Recommendations
1. ...
```

## Arguments

$ARGUMENTS — optional scope filter (e.g., "tasks-only", "goals-only", "full"). Default: full review.
