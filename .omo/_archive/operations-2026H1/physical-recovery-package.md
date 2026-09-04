---
lifecycle: contract
owner: runtime-team
last_updated: 2026-07-31
review-state: metadata-only
metadata-migrated-at: 2026-07-31
title: Physical recovery package (Batch2 C1)
type: doc
---
# Physical recovery package (Batch2 C1)

One-command rehearsal after LAN hosts return.

## Entry

```bash
bash bin/delivery/physical-recovery.sh
# optional:
PHYSICAL_RECOVERY_HOSTS=host1,host2 bash bin/delivery/physical-recovery.sh
```

Python twin: `bin/delivery/physical_recovery.py`.

Live drill (仅限明确批准的非生产源、空隔离目标，并必须提供外部人工确认)：

```bash
python3 bin/delivery/physical_recovery.py --live \
  --source /path/to/approved-source \
  --backup-dir /path/to/new-backup \
  --restore-dir /path/to/empty-isolated-target \
  --human-confirmation-ref human://operator/recovery-YYYYMMDD \
  --replay-command <command> [args...]
```

成功回执包含 source/backup/restored/replay 四个 digest、隔离目标、时间戳、
人工确认引用和清理结果；`--live` 不接受 shell 字符串，replay 以 argv 方式
执行。缺人工确认、目标重叠/非空、digest 不一致或 replay 非零退出时 fail-closed。

## What it does (dry-run default)

1. **Probe** listed hosts (TCP connect, short timeout)
2. **Registry plan** — which nodes *would* register (not auto-applied)
3. **G-DEL.3 plan** — ready iff reachable ≥2; measure **not** executed in dry-run
4. **G-DEL.1 precheck** — ready iff reachable ≥4; measure **not** executed

Evidence JSON lands under `.omo/_knowledge/audits/*-physical-recovery-dry-run.json`.

## Hard rules

- Dry-run / sim must keep `meets_physical_gate=false` and `meets_gate=false`
- Official G-DEL.1/3 requires real `measure_physical` + human confirm (workorder §F)
- Config-only host list via `PHYSICAL_RECOVERY_HOSTS`

## Recovery-day checklist card

`.omo/tasks/planned/needs-human-batch2-physical-recovery-checklist.yaml`
