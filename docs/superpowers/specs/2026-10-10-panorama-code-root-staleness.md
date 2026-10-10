---
schema_version: specification/v1
spec_version: 1.0.0
title: Panorama CODE_ROOT 指向陈旧检出导致门禁与台账读数失真
bet_id: BET-Y2Q4-T16-03
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-10
---

## 症状
`runtime/dashboard/data.json` 内同一文件自相矛盾：门禁 A4 与台账 bet 条数取自陈旧代码副本，而 `runtime.*` 取自当前工作区。

## 根因（已实测）
- 唯一写 `Workspace/runtime/dashboard/data.json` 的 launchd 作业是 `com.omostation.panorama-dashboard-refresh`（`StartInterval=240s`）
- 其 `EnvironmentVariables.PANORAMA_CODE_ROOT = /Users/xiamingxing/.local/share/zhixing-dashboard/code-main`
- `code-main` 是 2026-09-26 的一次性手工克隆（`remote.origin.url` 为本地路径 `/Users/xiamingxing/Workspace`），此后从未 fetch
- 实测落后：**fetch 前因 remote-tracking ref 是克隆快照，`behind` 恒为 0**；执行一次 `git fetch origin`（仅更新 remote-tracking ref，HEAD/工作树/索引均未变）后，`behind_origin_main=279` 变为可见
- `code_root_health` 的自比逻辑（`bin/panorama/panorama-collect.py:2131` `collect_code_root_health()`，判据约 `:2184`）是拿 `CODE_ROOT` 的 HEAD 与**它自己克隆时的 `refs/remotes/origin/main`** 比，因此在从未 fetch 的前提下**结构上不可能发现自身陈旧**，恒报 `verdict=PASS`

## 影响面（实测）
走 `CODE_ROOT`（陈旧）的字段：`gates`(A1–A7/RF0/reference_cell) · `bets` · `objective_coverage` · `code_root_health` · `debt` · `debt_registry` · `alerts` · `tasks` · `claims_task16` · `value_evidence_validation` · `service_lifecycle` · `scene_calibration_fallback`
走 `ROOT`（当前）的字段：`runtime.*` · `launchd_health` · `documents` · `workspace` · `submodules` · `remote_hygiene` · `ci` · `cron` · `services`

关键复现证据：
- `git -C code-main show HEAD:docs/plans/3y-bet-ledger.yaml` 的 `bets` 长度 = **482**（与 dashboard 读数逐字一致）
- Workspace `origin/main` 同一文件 `bets` = **535**；Workspace `HEAD` = **529**
- `bin/scheduler-compile.py` 在 `3b55e3ca..HEAD` 区间 `+84/−1`，`code-main` 副本缺整个 `check_launchd_plane()` 段，故其 `--check` 输出**不含 `launchd` 键**

## 当前真值（以 Workspace 只读复算）
```
python3 bin/scheduler-compile.py --check
{"ok": false, "drift_count": 0, "orphan_count": 6, "known_orphan_count": 13,
 "launchd": {"mode":"shadow","blocks_gate":false,
             "registered_count":13,"installed_count":40,"undeclared_installed_count":27,
             "label_match":{"matched":17,"registered":17,"rate":1.0},
             "unparseable_plists":[], "dead_targets":[]}}
```
注：`orphan_count(6) + known_orphan_count(13) = |raw_orphan|(19)`，两者**互斥互补、非子集关系**。dashboard 上曾显示的 `drift=3 / orphan=8` 是陈旧副本对 2026-09-26 的 `registry.yaml` 做的比较，其中 3 条 drift 已在当前 registry 降级为 `proposed`、另 2 条 orphan 已补登记，**均早已修复**。

## 决策矩阵（待 principal 裁定，本单不代决）
| 方案 | 动作 | 影响 | 已知代价 |
|---|---|---|---|
| A | `PANORAMA_CODE_ROOT` → `/Users/xiamingxing/Workspace` | 仅 dashboard-refresh | `CODE_ROOT == ROOT` 触发 `collect_code_root_health` 的 `available=False/verdict=UNMANAGED` 分支；且 Workspace 常驻功能分支、可能脏 |
| B | `PANORAMA_CODE_ROOT` → `~/.local/opt/omostation-publisher` | 同上 | publisher HEAD `240d4da`，落后 17；**保留自比缺陷**（拿自身快照比）；其更新脚本 `projection-full-refresh.py` 未在 launchd/crontab 中登记 |
| C | 删除 `PANORAMA_CODE_ROOT`，走代码内 fallback | 同上 | 解析结果与 A 完全相同 |
| D | 把 `code-main` 快进到其 origin/main | **同时**修好 dashboard 与 `bin/ssot/reference-cell-direct-local-smoke.py:89`（亦硬编码 `code-main`） | 改变多个读点的取数；`code-main` 的 origin 指向**本地 Workspace 仓**，跟的是 Workspace 本地 `main` 分支，而该分支又落后 Workspace 自己的 `origin/main`——「对齐到哪」需先定义 |

## 本单不做
- 不自动改任何 plist，不执行任何 `launchctl` 子命令（需 principal 单独授权）
- 不对任何克隆执行 `reset --hard` / `merge` / `pull`
- 不把 crontab 平面的 6 条 orphan 纳入本单——它们属 crontab 平面，而 `BET-Y2Q4-T16-01` 的 `non_goals[4]` 明写「不改 crontab 平面既有语义与 known_orphans 机制」
- 不把本单内容塞进 T16-01（其范围是 launchd 平面 shadow 校验）

## 验证口径
- 「陈旧是否可见」：`collect_code_root_health()` 的 `verdict` 从假 `PASS` 变为 `STALE` 且 `behind_origin_main` 反映真实差距（已达成，fetch 后实测 `behind=279`）
- 「读数是否同源」：`data.json` 内 `gates[*]` 与 `runtime.scheduler` 不再出现来自不同代码副本的互斥数值
