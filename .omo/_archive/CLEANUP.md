# .omo/ Cleanup Policy
> ⚠️ **LEGACY** — 历史参考文档，不再作为当前执行标准。清理策略请遵循 `.omo/state/system.yaml` 与 `state/` 目录下的实际状态。

> 历史清理策略快照；当前请优先参考 `.omo/INDEX.md`、`.omo/state/system.yaml` 与实际目录结构。

> Auto-generated cleanup guidance for stale planning artifacts.

## Current Policy

Session artifacts older than 30 days from last modified date can be cleaned.

## Cleanup Commands

```bash
# List stale plan files (older than 30 days)
find .omo/plans/ -name "*.md" -mtime +30 -ls

# List stale summary files
find .omo/summaries/ -name "*.md" -mtime +30 -ls

# Clean all stale
find .omo/plans/ .omo/summaries/ -name "*.md" -mtime +30 -delete
```

## What NOT to Clean

| File | Why |
|------|-----|
| architecture-*.md | Core architecture reference |
| full-architecture-audit-*.md | Latest audit |
| 4-plus-1-plus-3-*.md | Architecture mapping |
| boulder.json | Session state |
