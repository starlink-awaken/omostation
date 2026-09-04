---
lifecycle: entry
owner: governance-team
last_updated: 2026-08-18
type: ssot
last_updated: 2026-09-03
---
# CI Plane Change Template

Use this template when creating PRs that modify CI configuration, GaC checks, hooks, or any governance/plane surface.

## PR Title

```
<type>(<scope>): <short description>
```

Examples:
- `feat(gac): add CR-SUBMODULE-REWIND check for submodule pointer rewind detection`
- `fix(hooks): prevent direct main commits without worktree claim`
- `chore(ci): update dependency baseline drift check`

## Required Commit Message Format

All commits in this PR **must** include submodule pointer changes in the commit message body when applicable:

```
Submodule pointers: projects/agora=<sha>, projects/cockpit=<sha>, projects/knowledge/gbrain=<sha>
```

If no submodule pointers were changed, include:

```
Submodule pointers: none
```

### Example Commit Message

```
feat(gac): add CR-SUBMODULE-REWIND check

- Add check-submodule-rewind.py to detect pointer rewinds
- Hook into pre-commit and gac-local-gate
- Direction validation: current pointer must be descendant of previous

Submodule pointers: projects/agora=abc1234..., projects/cockpit=def5678...
```

## Checklist

- [ ] Commit messages include `Submodule pointers:` line
- [ ] `make gac-local-gate` passes
- [ ] `make ssot-guardian` passes (if SSOT files changed)
- [ ] `make install-hooks` run if `.githooks/` changed
- [ ] CI checks pass on PR
