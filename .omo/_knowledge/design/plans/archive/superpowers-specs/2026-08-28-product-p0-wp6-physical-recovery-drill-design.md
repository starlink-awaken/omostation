---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last-reviewed: 2026-08-28
bet_id: BET-Y1Q3-T4-08
risk_level: L3
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Product P0 WP6 — Physical Backup, Restore and Integrity Drill

## 1. 目标

把当前只生成计划的 physical recovery 入口升级为一条可实际执行、不覆盖源数据、可重放且有人工确认的 backup -> isolated restore -> integrity -> replay 链。

本 WorkPacket 依赖 WP3，因为恢复后必须对 durable event/outbox 数据做完整性和重放验证。

## 2. 不可突破的安全边界

- `--dry-run` 永远保持 `executed=false`、`meets_physical_gate=false`、`meets_gate=false`。
- live drill 必须显式提供 source、backup dir、空的 isolated restore dir 和 human confirmation reference。
- restore dir 必须为空，不能是 source、source 父目录或任何 production/runtime root。
- 任一 digest 不等立即停止，不自动修复、不自动确认。
- 人工确认是外部回执 reference，不得由脚本自报。

## 3. 回执合同

```python
@dataclass(frozen=True)
class RecoveryReceipt:
    drill_id: str
    source_digest: str
    backup_digest: str
    restored_digest: str
    replay_digest: str
    isolated_target: str
    executed: bool
    integrity_ok: bool
    human_confirmed: bool
    started_at: str
    completed_at: str
```

`meets_physical_gate` 只在以下条件同时成立时为 true：

- `executed is True`；
- `integrity_ok is True`；
- `human_confirmed is True`；
- source/backup/restored/replay digest 满足 Spec 声明的等价规则；
- restore target 是已记录的隔离目录；
- replay 真实执行并有回执，而不是仅生成 command string。

## 4. 执行流程

1. 验证 source 是用户明确批准的非生产源，计算 source tree digest。
2. 将源复制到显式 backup dir，计算 backup digest。
3. 验证 restore dir 为空且与 source/production roots 不重叠。
4. 从 backup 恢复到 isolated target，计算 restored digest。
5. 执行注册的 integrity/replay check，计算 replay digest。
6. 不可变地写入一份 RecoveryReceipt，然后由人类确认结果。
7. 保存证据后只清理显式 isolated target，不删除 source 或唯一 backup。

## 5. 写面

- `bin/delivery/physical_recovery.py`
- `docs/operations/physical-recovery-package.md`
- `tests/test_batch2_physical_recovery.py`
- `tests/test_physical_recovery_live_drill.py`

证据使用已注册 audit/evidence 落点，不新增 registry、database 或 runtime truth root。

## 6. 负例和验收

- dry-run 永远不通过 physical gate。
- 恢复到 source 或非空 target：在任何写入前拒绝。
- 任意篡改 restored byte：integrity/replay halt。
- human confirmation 缺失：即使 digests 相等，physical gate 仍为 false。
- replay command 未真实执行：`executed` 和 gate 为 false。
- 真实 isolated drill：记录 command、开始/结束时间、四个 digest、target、replay 回执、人工确认和清理结果。

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_batch2_physical_recovery.py tests/test_physical_recovery_live_drill.py -q
```

测试 fixture 只证明工程合同；完成还必须有一次真实非生产源的 isolated drill 回执。

## 7. 回滚与停机

回滚时保留当前 dry-run 安全入口和已生成 receipt，关闭 live adapter。只有在已捕获证据且用户明确批准后才可清理 isolated target。任一 root overlap、digest mismatch、replay 失败或人工确认不明时立即停机。

## 8. 价值政策

`value_indicator_policy=false`。物理恢复是运行可靠性证据，不计个人价值。
