# OPC P7-H1 release train 节奏 — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P7 / Gate H / Sub-gate H1

## 1. 1 release cycle 实证

```text
$ OPC_RELEASE_CUTOFF="3 days ago" python3 scripts/opc_p7_release_cycle.py
returncode: 0
version: v2026-06-12-r1
```

| 产物 | 路径 |
|------|------|
| release notes | `.omo/_delivery/release/CHANGELOG.md` |
| cycle json | `.omo/_delivery/release/v2026-06-12-r1.json` |
| retrospective | `.omo/tasks/registry/done/OPC-P7-H1/retrospective-v2026-06-12-r1.md` |

## 2. release notes 三件套 (红线)

CHANGELOG.md `v2026-06-12-r1` 段含:

### Summary
- 217 commits since 3 days ago
- Drift kinds scanned: 4, drift_count: 0
- Debt: total=4, open=1, resolved=3

### Validation
- omo tests: rc=0 | 12 passed in 0.18s
- drift detector: kinds=4 drift_count=0

### Debt
- total: 4
- open: 1
- resolved: 3

## 3. retrospective 落盘

`.omo/tasks/registry/done/OPC-P7-H1/retrospective-v2026-06-12-r1.md` 含
cycle state + 3 字段 (summary/validation/debt) + next-action.

## 4. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | ≥1 个 1-2 周周期跑通 (cut → review → ship) | ✅ | v2026-06-12-r1 cycle json |
| 2 | retrospective 落盘 | ✅ | retrospective-v2026-06-12-r1.md |
| 3 | release notes 含 summary/validation/debt 三件套 | ✅ | CHANGELOG.md v2026-06-12-r1 |

## 5. 红线遵守

- ✅ release notes 不缺三件套
- ✅ retrospective 不缺 next-action
- ✅ 实施、测试、task、doc 同步
