---
description: "Scan all git repos in the workspace for health metrics: dirty files, unpushed commits, test status, and produce a health report."
---

# Workspace Health Scan

Scan git repositories in the workspace and produce a health metrics report.

## Steps

1. **Discover repos**: Find all git repos under the workspace root (and `projects/` subdirectory)
2. **For each repo, collect**:
   - Dirty files count (`git status --porcelain | wc -l`)
   - Unpushed commits (`git log @{upstream}..HEAD --oneline 2>/dev/null | wc -l`)
   - Branch name (`git branch --show-current`)
   - Last commit date (`git log -1 --format='%ai'`)
3. **Classify health**:
   - 🟢 Clean: 0 dirty, 0 unpushed
   - 🟡 Minor: 1-5 dirty or 1-3 unpushed
   - 🔴 Problem: >5 dirty or >3 unpushed
4. **Produce report**

## Output Format

```markdown
## Workspace Health Scan — [Date]

### Summary
- Total repos scanned: N
- 🟢 Clean: X | 🟡 Minor: Y | 🔴 Problem: Z

### Per-Repo Status

| Repo | Branch | Dirty | Unpushed | Last Commit | Health |
|------|--------|-------|----------|-------------|--------|
| repo-name | main | 0 | 0 | 2026-06-10 | 🟢 |

### Issues Requiring Attention
1. [Repo]: [Problem description]

### Recommendations
- [Action items]
```

## Arguments

$ARGUMENTS — optional scope (e.g., "kairon-only", "projects-only", "full"). Default: full workspace scan.
