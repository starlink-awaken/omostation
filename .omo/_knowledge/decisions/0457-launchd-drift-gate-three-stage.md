---
schema: md/v1
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-28
type: ssot
id: ADR-0457
related: ADR-A, ADR-0119, ADR-0121, ADR-0435, ADR-0456
tags: [launchd, scheduler, drift-gate, registry, three-stage]
---

# ADR-0457 — launchd 平面漂移门：三段式（shadow → warning → fail）

- **Status**: ACCEPTED（2026-09-28 principal 批准：立项与 shadow 阶段；warning/fail 转段须另走一次确认）
- **Date**: 2026-09-28
- **Related**: ADR-A（调度编译器）、ADR-0119/0121（crontab 登记源）、
  ADR-0435（resident launchd wrapper 形态）、ADR-0456（同机双安装位）、BET-Y2Q4-T16-01

## 背景与问题

2026-09-28 冷启动巡检发现 `meta-doctor` 报 `stale_beats=1`，连带织星驾驶舱 A2/A5 双 FAIL。
沿根因上溯时发现，当日修掉的三个互不相关的缺陷**全部落在同一个治理盲区**：

| 缺陷 | 潜伏时长 | 为何无人发现 |
|---|---|---|
| `omo state refresh`（system_health.yaml 的唯一写入者）从未排程 | 5 天（48h SLA 持续被破） | 生成器不在任何登记面，无人在看 |
| 6 个 resident 角色被 crontab + launchd 双重驱动 | 长期 | crontab 侧未登记，只体现为 A4 孤儿计数 |
| `com.l4.resident.orchestrator`（30s）plist 已装但从未 `launchctl load` | 长期 | 不在登记面，`launchctl` 状态无人比对 |

### 结构原因（已逐层验证）

`bin/scheduler-compile.py::check_drift()` 只比对 crontab 平面：

```python
if "crontab" not in j.get("planes", []):
    continue          # ← launchd 平面在此被整体跳过
```

而同一文件的 `__main__` 块覆写了 argparse 并手写分发，只认 `--generate crontab` / `--check`，
使 `main()` 与 `compile_launchd()` 成为**不可达死代码**；`--generate launchd` 静默无操作仍返回
`rc=0`。二者叠加的后果是 launchd 平面**既无生成、也无校验**。

### 实测存量（2026-09-28，57 个已装 plist）

| 分组 | 数 | 已加载 |
|---|---:|---:|
| R 已登记（registry launchd 平面） | 6 | 5 |
| W 仓内脚本·未登记 | 27 | 21 |
| H 宿主部署副本（zhixing-dashboard） | 3 | 3 |
| E 用户本机外部工具 | 6 | 5 |
| ? 待判（含 3 个 plistlib 解析失败） | 12 | 7 |
| D 目标缺失 | 2 | 0 |

即 **launchd 平面约 86% 未声明**。ADR-0456（PROPOSED）独立实测记录「指向 Workspace 的 plist
43 / 56」，与本次 28 / 57 同量级，互为佐证。

## 决策

**给 launchd 平面补漂移校验，且严格分三段落地。**

| 阶段 | 行为 | 转段条件 |
|---|---|---|
| **shadow** | 只报告不阻断，产出 27 条 W 组存量清单 | 跑满 1 周，存量清单经人工分类 |
| **warning** | 报警 + 给出清理期限，仍不阻断 | 存量清零且异常项均有 owner |
| **fail** | 转硬门 | 需 principal 再次确认 |

### 为什么不直接转 fail

E5 事故已实证：`ADR-0380 CR-SUBMODULE-REWIND` 门禁先于存量清理上线，一次性检出 18 个 rewind
并锁死主干，导致所有无关提交都无法提交。新门禁跳过 shadow/warning 直接 fail 会复现该路径。

### 校验口径（三项，均为只读）

1. **登记 ↔ 安装 label 双向比对**：registry `planes: [launchd]` 条目按
   `com.omostation.{name}` 合成 label，与 `~/Library/LaunchAgents/*.plist` 实际 Label 集合求差集。
2. **plist 可解析性**：以 `plistlib` 为准（**不以 `plutil` 为准**）。plistlib 失败者从
   `meta-doctor.py:364-367` 的 `except Exception: continue` 中被**静默跳过**出 M2 引用校验，
   即「登记了但治理看不见」。XML 规范禁止注释内出现 `--`；已知 3 例
   （`expiry-radar:11`、`zhixing-host-drift:7`、`omo-health-refresh:15`，后者已于
   BET-Y2Q4-T16-01 同批修正）。
3. **目标可执行性**：解析出的脚本路径是否存在。

### 不做的事

- 不改 crontab 平面既有语义，不动 `known_orphans` 机制
- 不自动 unload / bootout 任何作业（Panorama 与本门均为只读观测，见
  `panorama-collect.py:1563-1567` 的既有约定）
- 不在本 ADR 决定 resident 双驱动收敛方向（保留为独立决策项）
- 不把 27 条存量一次性登记充数

## 影响面

- **新增**：`check_drift()` 的 launchd 分支（shadow 阶段仅写报告）
- **修复**：`__main__` 覆写 argparse 导致的死代码（使 `--generate launchd` 可达）
- **不动**：三轴证据门禁、resident 调度、任何既有 crontab 条目

## 验收

- shadow 报告可复算：`python3 bin/scheduler-compile.py --check --json` 输出的 launchd 段
- `--generate launchd` 不再静默无操作（`rc=0` 必须伴随非空 JSON）
- 27 条 W 组存量按 owner 分类完毕并有处置结论
