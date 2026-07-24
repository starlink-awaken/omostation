# Physical recovery package (Batch2 C1)

One-command rehearsal after LAN hosts return.

## Entry

```bash
bash bin/delivery/physical-recovery.sh
# optional:
PHYSICAL_RECOVERY_HOSTS=host1,host2 bash bin/delivery/physical-recovery.sh
```

Python twin: `bin/delivery/physical_recovery.py`.

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
