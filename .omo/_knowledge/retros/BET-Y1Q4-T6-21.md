---
bet_id: BET-Y1Q4-T6-21
title: "Documents 多客户端配置自愈守护与 BOS 统一事实服务网关"
status: completed
completed_at: 2026-09-06
---

# Retro: BET-Y1Q4-T6-21

## What shipped

1. **`bin/gac/documents-client-sync.py`** — CLI tool for multi-IDE config drift detection and atomic repair
   - `check` mode: scans Claude Desktop, Codex, Zed, ZCode configs against canonical `documents-domain-projects.yaml`
   - `apply` mode: atomically repairs drift with `.bak` backup
   - JSON envelope output (`--json`)
   - Verified: detected real drift in Claude Desktop config during live test

2. **`projects/agora/src/agora/tools_bos/documents.py`** — BOS Documents read-only facade
   - `bos://documents/{domain}/registry` → domain registry + client contracts
   - `bos://documents/{domain}/jobs` → runtime job definitions
   - `bos://documents/{domain}/state` → runtime state
   - All routes read-only, fail-closed on mutation
   - Schema validation on all responses

3. **Tests**: 8 CLI tests + 12 BOS facade tests (all passing)

## Lessons

1. **Spec binding is mandatory for workflow start**: Candidate bets without `accepted_specifications` block `agent-workflow start` (SPEC_BINDING_REQUIRED). Always create spec + bind before starting.

2. **Submodule init is slow in worktrees**: Full `git submodule update --init` times out at 60s. Selective init (`projects/agora`, `projects/omo`, `projects/ecos`) is sufficient for most bets.

3. **Submodule dirty state in worktrees**: `projects/bus-foundation` had all files staged as deleted. `git reset HEAD . && git checkout .` restores them. Consider adding submodule health check to worktree claim flow.

4. **Agora test isolation**: The agora package has deep dependency chains (pydantic, bus-foundation, ecos). BOS facade tests work best as standalone imports via `importlib.util.spec_from_file_location` rather than through the full agora pytest suite.

## Risk review

- L2 risk (atomic writes): Implemented via `shutil.copy2` backup + tmp-then-replace atomic write pattern.
- No unregistered new dependencies added.
