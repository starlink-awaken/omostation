---
schema_version: specification/v1
status: accepted
lifecycle: engineering
owner: governance-team
last-reviewed: 2026-10-21
type: ephemeral
bet_id: BET-Y2Q4-T10-340402
decision_id: BET-Y2Q4-T10-340402
date: 2026-10-21
spec_version: 1.0.0
---

# GOAL-04 F31/F05 共享治理能力移植合同

## 目标与写面
- 将 GoalHarness `19-CANONICAL-FIXES` 中的 F31 与 F05 生产兼容参考能力移植为主仓共享库：`lib/single_writer_lease_broker.py`、`lib/memory_tombstone_guard.py`。
- 提供定向可重放测试，覆盖 SQLite 持久化 epoch、跨任务写面互斥、stale epoch fencing、HMAC 能力校验、幂等提交、8 态记忆生命周期、WAL Tombstone 重放与快照防复活。
- 库 API 保持参考实现兼容；实现按主仓共享库约定补齐用途、持久化格式、生命周期与兼容说明。

## 非目标
- 不接管生产 Claims Authority，不迁移既有 lease 数据库，不激活生产 worker。
- 不修改真实个人或家庭记忆数据，不导入导出生产备份，不执行生产恢复。
- 不改变既有 Scene Card 业务语义、子模块 gitlink，或新增第二个 GOAL 账本。
- 不使用生产 HMAC 密钥或提交任何 secret；测试只用显式公开 fixture。

## 验证
- `python3 -m pytest tests/test_single_writer_lease_broker.py tests/test_memory_tombstone_guard.py -q -p no:randomly`
- 导入加载路径断言确认两个库从当前 worktree 加载。
- 只作工程验证；不声称生产运行或业务价值。

## 准入和交付
- BET：`BET-Y2Q4-T10-340402`，写入主台账 safe-insert 后再实施。
- canonical spec、decision、ledger、tests、reports、retro 均在获准写面内。
- 生产 operational/value 保持 NOT_PROVEN，除非另行获得生产授权。
