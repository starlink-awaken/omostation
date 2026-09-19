---
schema_version: specification/v1
spec_version: 1.0.0
title: T10-126 Resident 只读观测零锁加固与 WAL 并发防腐
bet_id: BET-Y1Q4-T10-126
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
---

# T10-126 Resident 只读观测零锁加固

## 1. 目标

`projects/omo/src/omo/resident/status.py` 与 `ledger_check.py` 在并发场景下零锁死. 当前 `check_and_recover` 内 `wal_checkpoint(TRUNCATE)` 静默申请写锁, 与后台 daemon WAL 写入争用. 在低版本 Python SQLite 环境触发 safety mode check, 进一步尝试降级 `journal_mode`, 加重锁争用.

本 bet 把 status / lock probe 路径彻底只读化, recover/wal_checkpoint 路径独立 (不自动调用, 需 ops 显式 `make resident-recover`).

## 2. In scope

1. `status.py::_ledger_snapshot` 只调用 `lock_age_seconds` (read-only `file:...?mode=ro` URI), 不再调用 `check_and_recover`
2. `status.py` 移除 `LEDGER_RETRY_ATTEMPTS` 写锁重试逻辑 (read-only 无需)
3. `ledger_check.py` 新增 `check_lock_state_only()` 函数, 等价 `lock_age_seconds` + 返回 `journal_mode` 探测值 (不写)
4. `ledger_check.py` 保留 `check_and_recover()` (写), 但改名 `recover_ledger_with_wal_checkpoint()` 表明副作用
5. `Makefile` 新增 `resident-recover` 目标 (显式 opt-in)
6. `make resident-status` 100x 并发跑, 0 锁死, 0 OperationalError
7. 新增 `tests/unit/test_resident_status.py` 覆盖只读路径

## 3. Out of scope

- 不修改后台 daemon 写 SQLite WAL 账本的事务协议
- 不引入新 SQLite 依赖
- 不修改 `event-ledger.sqlite3` schema

## 4. 验收

1. `make resident-status` exit 0, 输出 JSON 含 `recovered/healthy`
2. `uv run pytest projects/omo/tests/unit/test_resident_status.py -q` exit 0
3. 后台 daemon 持续写入时, 并发跑 100 次 `make resident-status` 0 报错
4. `make gac-local-gate` exit 0
