# .omo/ Cleanup Policy

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
