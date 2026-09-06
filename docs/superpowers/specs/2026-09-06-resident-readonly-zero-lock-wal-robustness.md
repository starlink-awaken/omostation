---
schema_version: specification/v1
spec_version: 1.0.0
title: Resident 只读观测零锁加固与 WAL 并发防腐
bet_id: BET-Y1Q4-T10-126
status: accepted
lifecycle: contract
owner: omo
created: 2026-09-06
last-reviewed: 2026-09-06
risk_level: L1
human_gate: false
type: ssot
last_updated: 2026-09-06
---

# Resident 只读观测零锁加固与 WAL 并发防腐

## Problem

`projects/omo/src/omo/resident/status.py` 和 `ledger_check.py` 在执行健康探测时，
可能触发 SQLite 写锁或 journal_mode 降级 PRAGMA，在后台 Daemon 持续写入时导致
锁争用，使 `make resident-status` 不稳定。

## Solution

1. 所有健康探测使用真正的无锁只读 URI (`file:...?mode=ro`)
2. 消除低版本 Python SQLite 环境因安全模式校验误尝试降级 journal_mode 的路径
3. 确保 `make resident-status` 在任意环境 100% 幂等瞬时返回

## Criteria

- status.py 探测过程完全杜绝写锁申请与模式变更 PRAGMA，使用只读 URI 连接
- 并发执行 100 次 status.py 零报错、零锁死
- `make resident-status` 在各开发环境与 CI 环境均稳定返回 recovered/healthy
- `uv run pytest projects/omo/tests/unit/test_resident_status.py -q` exit 0
- `make gac-local-gate` exit 0

## Scope

- `projects/omo/src/omo/resident/status.py`
- `projects/omo/src/omo/resident/ledger_check.py` (if needed)
- `projects/omo/tests/unit/test_resident_status.py`
- 不修改后台 Daemon 写入 SQLite WAL 账本的核心事务协议
