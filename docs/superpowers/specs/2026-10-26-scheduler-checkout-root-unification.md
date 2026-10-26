---
schema_version: specification/v1
spec_version: 1.0.0
title: 统一 scheduler 检查的检出 —— A4 与 cockpit 采集器读同一棵 registry
bet_id: BET-Y2Q4-T10-269
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-26
---

# 统一 scheduler 检查的检出 —— A4 与 cockpit 采集器读同一棵 registry

> 范围：cockpit `scheduler` 采集器的 registry 根解析 + A4 的 scheduler 读数来源收敛；
> 加一条判据钉住两者恒等。不改 A9 判据、不改主工作区只读策略、不新增 bin/ 脚本。

## 1. 缺陷证据（实测，2026-10-26T01:0x–02:4xZ）

同一个 `bin/scheduler-compile.py --check`，被两个消费面**以两个不同的根**各跑一次：

| 消费面 | 代码位置 | cwd | 根 |
|---|---|---|---|
| A4 门禁 | `bin/panorama/panorama-collect.py` 的 `collect_runtime()` | publisher 检出 | `~/.local/opt/omostation-publisher`（每 180s 同步 origin/main） |
| cockpit `scheduler` 采集器 | `collectors/scheduler.py` 的 `workspace_root()` | 主工作区 | `/Users/xiamingxing/Workspace`（共享、可变、常落后） |

`collect_runtime()` 的 `run(["python3", "bin/scheduler-compile.py", "--check"])` 不带 `cwd=`，
因此继承 publisher 进程的 cwd（= publisher 检出）；`collectors/scheduler.py:33` 的
`DEFAULT_WORKSPACE_ROOT = Path("/Users/xiamingxing/Workspace")` 则是硬编码的另一个根。

### 实测读数（同一时刻，同一台机器）

| 时刻 | 主工作区落后 | A4 | cockpit `scheduler` | A9 |
|---|---|---|---|---|
| 2026-10-26T01:2xZ | 4 commits | PASS `{"ok": true, "drift_count": 0, "orphan_count": 0}` | `DEGRADED` `last_success_at=2026-10-23T14:04:39Z` | PARTIAL `scheduler=DEGRADED` |
| 2026-10-26T02:4xZ（推进主工作区后） | 0 | PASS 同上 | `OK` `last_success_at=2026-10-26T02:4xZ` | PASS |

**两条读数同时为真**：A4 说调度器检查通过，cockpit 说它降级 —— 因为它们读的是两棵不同的
registry。A9 于是一半看 A4 的根、一半看主工作区的根，主工作区一落后就转 PARTIAL。

### 触发它的具体条目

`2026-10-26T08:1x` 登记的 `test-all`（`known_orphans`，PR #4893）只进了 origin/main；
主工作区尚未前进时，publisher 检出认得它（A4 PASS），主工作区不认得（cockpit DEGRADED）。
这正是本缺陷的一次真实发作 —— 不是构造出来的场景。

## 2. 设计约束：不得把「观测根陈旧」读成「源降级」

A9 的语义是「ASD 与 Cockpit 可观测」，不是「主工作区是否新鲜」。主工作区陈旧是**另一个**
信号（本 BET 的 P5 面：把陈旧度显式化），不该由 A9 以「源降级」的形式二次表达 ——
那会让同一个根因在两处报成两种病。

因此本轮**不改 A9 判据**：A9 继续按 `source_states` 判，但 `source_states` 里的 `scheduler`
必须与 A4 同源，两条读数恒等，假阳性从根上消失。

## 3. 方案

### 3.1 单一 registry 根解析

`collectors/scheduler.py` 的 `workspace_root()` 增加 registry 根的解析，顺序为：

1. `PANORAMA_CODE_ROOT`（publisher 检出；orchestrator 的 launchd env 已带
   `/Users/xiamingxing/.local/opt/omostation-publisher`）—— 最鲜，与 A4 同源；
2. 缺省回退 `DEFAULT_WORKSPACE_ROOT`。

只影响 **registry 的读取位置**；`_run_cmd` 的 `cwd` 仍用 `workspace_root()`（调度器检查
本身要跑主工作区的 `bin/gac/managed-python`，那部分是工作区级事实，不属本缺陷）。

### 3.2 判据：两条读数恒等

新增用例：对同一台机器，`collect_runtime()` 的 `rt["scheduler"]` 与 cockpit `scheduler`
采集器的 `ok` 必须一致；不一致即失败。

### 3.3 陈旧度可见（observe-only）

`scheduler` 源状态补 `registry_root` / `registry_root_oid` / `registry_root_stale` 三键
（缺省不参与任何判定），使「读的是陈旧根」在 cockpit 上直接可见 —— 与 P5 的主工作区
陈旧度观测面汇合。

## 4. 验收（done_when）

- `scheduler` 采集器与 A4 的 `rt["scheduler"]` 对同一台机器给出**相同 verdict**；测试钉住，
  且用例自带「注入分歧 → 判据必须报出」的自证（AGENTS.md §7③ 不接受空绿）。
- registry 根解析三条断言：`PANORAMA_CODE_ROOT` 覆盖即赢；未声明 env 走 `DEFAULT_WORKSPACE_ROOT`；
  解析顺序由测试点名（不手抄第二份名单）。
- 缺省 observe-only：A9 判据逐字节未改；主工作区策略未改。

## 5. 非目标（non_goals）

- 不改 A9 的源判据（`collect_a9_gate` 的 `bounded` 逻辑本轮不动）
- 不改主工作区只读策略，不引入任何「自动推进主工作区」的机制
- 不给 `known_orphans` 增减条目（那是 PR #4893 的事，已交付）
- 不新增 `bin/` 脚本（受 `check-bin-quota-diff.py` 净增配额约束）
- 不改 `scheduler-compile.py` 的比对语义（归一化解释器那部分已在 PR #4867 交付）
