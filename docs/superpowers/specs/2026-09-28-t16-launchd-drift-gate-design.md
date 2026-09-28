---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-28
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: launchd 平面漂移门 — 三段式落地与存量清单
bet_id: BET-Y2Q4-T16-01
created: 2026-09-28
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
related: ADR-0457, ADR-A, ADR-0435
---

# launchd 平面漂移门 — 三段式落地与存量清单

## 背景

见 ADR-0457。`bin/scheduler-compile.py::check_drift()` 只比对 crontab 平面
（`if "crontab" not in j.get("planes", []): continue`），launchd 平面既无生成也无校验。
2026-09-28 实测 57 个已装 plist 中仅 6 条在 registry 登记，约 86% 未声明。

同日发现三个互不相关、长期未被发现���缺陷全部落在该盲区：未排程的 `omo state refresh`、
crontab + launchd 双重驱动的 6 个 resident 角色、plist 已装但从未 load 的
`com.l4.resident.orchestrator`。

## 目标

1. 让 launchd 平面进入漂移校验视野
2. 修复 `--generate launchd` 静默无操作仍返回 `rc=0` 的死代码路径
3. 使 plist 解析失败可被观测，而非被 `except: continue` 静默吞掉

## 非目标

- 不自动 `unload` / `bootout` / 改写任何 launchd 作业（本门为只读观测）
- 不在本 spec 决定 resident 双驱动的收敛方向
- 不把存量一次性登记充数
- 不改 crontab 平面既有语义与 `known_orphans` 机制

## 阶段门（不可跳过）

| 阶段 | 行为 | 转段条件 |
|---|---|---|
| shadow | 只报告不阻断 | 跑满 1 周且 27 条 W 组存量完成 owner 分类 |
| warning | 报警 + 清理期限，仍不阻断 | 存量清零且异常项均有 owner |
| fail | 硬门禁 | 需 principal 再次确认 |

依据 E5 事故（ADR-0380 上线即检出 18 个 rewind 并锁死主干）：新门禁跳过 shadow/warning
直接 fail 会复现该路径。

## 校验口径（三项，只读）

### C1 · 登记 ↔ 安装 label 双向差集

- 登记侧：`registry.yaml` 中 `planes` 含 `launchd` 且 `status == active` 的条目，
  按 `com.omostation.{name}` 合成 label
- 安装侧：`~/Library/LaunchAgents/*.plist` 的实际 `Label`
- 输出：登记有安装无（drift）、安装有登记无（undeclared）两个方向

命名口径对齐：`compile_launchd()` 既有惯例为 `com.omostation.{name}`，
8 条 launchd 登记中 6 条严格符合。例外为带后缀的历史条目
（如 `zhixing-host-drift-hourly-active` → `com.omostation.zhixing-host-drift`），
需以显式 `label` 覆盖字段消歧，不得靠猜测后缀。

### C2 · plist 可解析性

以 `plistlib.loads` 为准，**不以 `plutil -lint` 为准**。

原因：`bin/gac/meta-doctor.py:364-367` 的 plistlib 读取包在 `except Exception: continue`
中，解析失败的 plist 被静默跳过出 M2 引用/活性校验 —— 即「登记了但治理看不见」。
而 Apple 的 plutil 与 launchd 解析器更宽容，`plutil -lint` 会通过、作业照常运行。

XML 规范禁止注释内出现 `--`。已知 3 例：

| 文件 | 行 | 内容 | 状态 |
|---|---|---|---|
| `com.omostation.expiry-radar` | 11 | `--strict` | 存量，未修 |
| `com.omostation.zhixing-host-drift` | 7 | `drwx------` | 存量，未修 |
| `com.omostation.omo-health-refresh` | 15 | `--dry-run` | 已修（同批 commit `3002d878f`） |

### C3 · 目标可执行性

由 C1 解析出的脚本路径是否存在。不存在者计入 `dead_target`，
与 crontab 侧的 `dead` 语义对齐（不单独作为 fail 条件）。

## 存量清单基线（2026-09-28 实测）

| 分组 | 数 | 已加载 | 说明 |
|---|---:|---:|---|
| R 已登记 | 6 | 5 | 唯一受治理覆盖 |
| W 仓内脚本·未登记 | 27 | 21 | shadow 阶段的主要处置对象 |
| H 宿主部署副本 | 3 | 3 | zhixing-dashboard，由 `zhixing-host-sync` 管 |
| E 用户本机外部工具 | 6 | 5 | aictl / omlyxd / opencode 等 |
| ? 待判 | 12 | 7 | 含 3 个 plistlib 解析失败 |
| D 目标缺失 | 2 | 0 | `gac-worktree-cleanup.sh` 等 |

## 实现约束

- 报告落到既有 `scheduler-compile.py --check --json` 输出，**新增字段不改既有字段语义**
- shadow 阶段 `ok` 的判定不因 launchd 段而变 false（否则等于提前 fail）
- 不引入新依赖；plist 解析用标准库 `plistlib`
- 与 `panorama-collect.py:1563-1567` 的既有约定一致：Panorama 与本门均为只读观测

## 验收

1. `python3 bin/scheduler-compile.py --check --json` 输出含 launchd 段，
   可复算出上述存量数字
2. `python3 bin/scheduler-compile.py --generate launchd` 产出非空 JSON，
   且 `rc=0` 时必有内容（消除静默无操作）
3. 3 个 plistlib 解析失败的 plist 在报告中可见
4. 27 条 W 组存量完成 owner 分类并有处置结论，方可申请转 warning
