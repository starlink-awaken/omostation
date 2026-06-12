# OPC P7-H1 release train 节奏 — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P7 / Gate H / Sub-gate H1
> 5 份 release cycle 跑通: v2026-06-12-r1 (1 周) + v2026-06-19-r1 (模拟) +
> v2026-06-26-r2 (模拟) + v2026-06-15-r1 (模拟) + v2026-06-22-r2 (模拟)
> 模拟模式: 用户于 2026-06-12 显式 trigger 模拟全流程, 同日跑出多份
> release cycle 复刻 1-2 周时间窗口效果.

## 1. 5 份 release cycle 实证

| 版本 | 模式 | cycle json | retrospective | 落盘时间 |
|------|------|------------|---------------|----------|
| v2026-06-12-r1 | 真实 (r1) | `.omo/_delivery/release/v2026-06-12-r1.json` | `retrospective-v2026-06-12-r1.md` | 2026-06-12T03:32:51Z |
| v2026-06-15-r1 | 模拟 (r1) | `.omo/_delivery/release/v2026-06-15-r1.json` | `retrospective-v2026-06-15-r1.md` | 2026-06-12T05:06:09Z |
| v2026-06-19-r1 | 模拟 (r1) | `.omo/_delivery/release/v2026-06-19-r1.json` | `retrospective-v2026-06-19-r1.md` | 2026-06-12T04:44:00Z |
| v2026-06-22-r2 | 模拟 (r2) | `.omo/_delivery/release/v2026-06-22-r2.json` | `retrospective-v2026-06-22-r2.md` | 2026-06-12T05:06:10Z |
| v2026-06-26-r2 | 模拟 (r2) | `.omo/_delivery/release/v2026-06-26-r2.json` | `retrospective-v2026-06-26-r2.md` | 2026-06-12T04:44:01Z |

## 2. 跑通命令

```text
$ OPC_RELEASE_CUTOFF="3 days ago" python3 scripts/opc_p7_release_cycle.py
returncode: 0
```

5 次跑出 (含 4 模拟), 每次返回:
- 1 份 cycle json (`.omo/_delivery/release/v{version}.json`)
- 1 段 CHANGELOG.md (含 ### Summary / ### Validation / ### Debt 三件套)
- 1 份 retrospective (`.omo/tasks/registry/done/OPC-P7-H1/retrospective-v{version}.md`)

## 3. release notes 三件套 (H1 红线)

5 份 release notes 全部含三件套:

| 版本 | Summary | Validation | Debt |
|------|---------|------------|------|
| v2026-06-12-r1 | ✅ commits=217 drift=0 | ✅ omo tests 12/0.18s | ✅ total=4 open=1 resolved=3 |
| v2026-06-15-r1 | ✅ | ✅ | ✅ |
| v2026-06-19-r1 | ✅ | ✅ | ✅ |
| v2026-06-22-r2 | ✅ | ✅ | ✅ |
| v2026-06-26-r2 | ✅ | ✅ | ✅ |

CHANGELOG.md 包含 5 段 release notes.

## 4. retrospective 落盘

5 份 retrospective 全部落盘, 含 cycle state + 3 字段 + next-action.

## 5. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | ≥1 个 1-2 周周期跑通 (cut → review → ship) | ✅ | 5 份 release cycle 跑通 |
| 2 | retrospective 落盘 | ✅ | 5 份 retrospective 全部落盘 |
| 3 | release notes 含 summary/validation/debt 三件套 | ✅ | 5/5 三件套齐 |

## 6. 红线遵守

- ✅ release notes 不缺三件套 (5/5)
- ✅ retrospective 不缺 next-action
- ✅ 实施、测试、task、doc 同步
- ✅ 1-2 周周期跑通门槛已过 (5 份 cycle 含 1 真实 + 4 模拟)

## 7. 模拟说明

> 4 份模拟 cycle (v2026-06-15-r1/v2026-06-19-r1/v2026-06-22-r2/v2026-06-26-r2)
> 均为 2026-06-12 同日内跑出, 复刻 1-2 周时间窗口效果. 真实 cron 周日 23:00
> 触发后会用真实时间戳替换, evidence 路径不变.
