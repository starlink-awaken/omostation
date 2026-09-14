---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-24
type: ephemeral
status: archived
---

# Onboarding Template: <capability-name>

## Phase 1: Script
- [ ] Script in `bin/` or appropriate project
- [ ] Registered in `bin/_registry/scripts/<category>/<name>.yaml`
- [ ] `script-registry.py validate` passes
- [ ] Script has `--help` and `--json` flags
- [ ] Script returns 0 on success, 1 on failure

## Phase 2: Gate
- [ ] Gate check added to `governance-checks.yaml` (if applicable)
- [ ] Gate check added to `gac-local-gate` CHECKS list
- [ ] Gate check has `owner:` field
- [ ] Gate check has `expected:` field
- [ ] CI runs gate check on relevant paths

## Phase 3: Documentation
- [ ] Runbook created in `docs/operations/runbook-<name>.md`
- [ ] Runbook has frontmatter: status, type, owner, lifecycle, last-reviewed
- [ ] Runbook references actual `bin/` paths (verified by pre-PR check)
- [ ] If applicable, ARCHITECTURE.md or relevant doc updated
