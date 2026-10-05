---
schema_version: specification/v1
spec_version: 1.0.0
title: policy-radar Artifacts Resolve Their Write Plane at Call Time and Leave Git Tracking
bet_id: BET-Y2Q4-T10-230
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-05
adr: ADR-0456
---

# ADR-0456 B5 — policy-radar 生成态落 state 根并摘出跟踪

> 契约正文只写不变量。所有数字为撰写时点（2026-10-05T11:06Z）在隔离 worktree
> `~/ws-b5-policy-radar` 上的一次**真实生成**实测，用于说明前提，不构成判据。
> 引用所在 ADR 必须写文件名 `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md`
> （`ADR-0456` 标识冲突：同 id 另有 `ADR-0456-governance-downshift-closeout-grading.md`）。

## 1. 缺陷形状（比 T10-229 更靠前一层）

`bin/bc-os/policy_radar.py:24-25` 从未询问根解析器，直接用源码位置反推写面：

```python
ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / ".omo/state/policy-radar"
```

这不是"import 时求值 env 被冻结"（T10-229 的形状），而是**连 env 都不读**：profile 声明与否
都写进检出。实测（同一 worktree、真实跑 `--generate-morning-brief --force`，4 源网络降级）：

```
OMOSTATION_STATE_ROOT=/tmp/t10230-baseline → RC=0, "brief-20261005 | 3 items"
  /tmp/t10230-baseline/.omo/state/policy-radar/  → 0 个文件
  .omo/state/policy-radar/                        → 新增 brief-20261005.json / brief-20261005.md
```

后果有两条，方向相反，所以必须一起改：

1. **写面错**：产物落在检出里，且 `brief-<日期>` 每天新增一份，于是
   `git status --short .omo/state` 永远不可能为空 —— B5 的完成判据被这一面单独卡住。
   当前 `origin/main` 跟踪着这目录的 3 个文件（`brief-20261003.json`、`brief-20261003.md`、
   `cache.json`），即运行时的每日产物本来就在污染版本面。
2. **读者同根**：`bin/gac/convergence-pulse.py:179` 同样用 `ROOT` 拼 `.omo/state/policy-radar/brief-*.json`，
   且该文件没有任何 `repo_root` import。只改写侧不改读侧，晨报探针在新根上看不见产物，
   `:182` 会当场把 `state["morning_brief"]` 判成 `stale` 并告"晨报断更"——
   **把写面收敛做成了一个假的运行中断更**。

## 2. 不变量

- **I1 调用时解析**：`policy_radar` 的读面（`collect()` 取 cache）与写面（`generate()` 落
  brief、`main()` 判当日是否已生成）必须经 `state_dir()` 在**调用时刻**取值；模块级不得再出现
  由 `__file__` 或 env 派生的路径常量。`state_dir()` 依次取①显式覆盖（模块属性 `STATE_DIR`，
  仅当被赋值为 `Path | None` 的覆盖位）②`OMO_POLICY_RADAR_STATE_DIR` ③
  `repo_root.state_root() / ".omo" / "state" / "policy-radar"`。保留①是为了让既有
  `tests/unit/test_policy_radar_internal.py:20` 的 `monkeypatch.setattr(pr, "STATE_DIR", tmp_path)`
  不 reload 也照常生效——覆盖恰恰是该属性过去承担不了的职责。
- **I2 未声明 profile 时逐字节沿用历史布局**：`state_root()` 在未声明 `OMOSTATION_STATE_ROOT`
  时等于 `code_root()`，故写面仍是 `<检出>/.omo/state/policy-radar`。本轮**不引入新的路径形状**，
  只换锚点。
- **I3 摘出跟踪**：`git rm --cached` 那 3 个已跟踪产物，`.gitignore` 增 `.omo/state/policy-radar/`。
  跟踪的是权限与代码，不是每日生成的快照；`.omo/_truth/registry/**` 保持跟踪不变。
- **I4 不进 canonical/legacy 登记表**：不得为本面新增 `runtime-projections.yaml` 条目。
  两条机制约束：`repo_root.projection_read()` 的语义是**单文件**（`bin/lib/repo_root.py:199` 判
  `is_file()`），`brief-<日期>` 这种变名目录套不进 canonical/legacy 一对一；且
  `bin/gac/omo-state-projection-guard.py` 要求"登记的 canonical 路径必须存在且可 YAML/JSON 解析"，
  而生成态在 fresh clone / CI 干净检出里两面皆无（AGENTS.md §7「已提交的 legacy 兜底不是仓库性质」）
  —— 登记会让那条门禁在 CI 上**按构造必红**。摘库边界改由测试钉住：
  `git ls-files` 不含 `.omo/state/policy-radar/` 与 `.omo/state/runtime/policy-radar/` 下任何路径。
- **I5 读者同缝**：`bin/gac/convergence-pulse.py` 的晨报探针必须经 `repo_root.state_dir_read()`
  取目录（state 根目录存在则优先，否则退回当前检出），不得自行拼 `ROOT`。该 helper 与既有
  `state_file_read()`（`bin/lib/repo_root.py:204`）同族，区别是它按**目录**是否存在定优先级、
  且文件名在调用时才拼——这是 I2 的读取侧对偶：未声明 profile 时结果与历史逐字节相同。
- **I6 正向落点判据**：验收不得只靠"检出不变脏"这一个否定式。必须实测一次声明 tmp state 根
  的真实生成，断言三个产物（`cache.json`、`brief-<当日>.json`、`brief-<当日>.md`）**只出现在
  tmp 根**，且检出的 `.omo/state/policy-radar/` 目录在跑后仍不含当日文件。判据先跑一次再写进用例。

## 3. 非目标（本轮不做，理由随条写）

- **子模块侧的两个读者**：`projects/omo/src/omo/pipeline_supervisor.py:129` 与
  `projects/cockpit/src/cockpit/commands/brief.py:73` 仍按 `ws/.omo/state/policy-radar/` 拼路径。
  改它们要同时动两个子模块 gitlink，且 `pipeline_supervisor` 自己就是写侧的调用方（`:121`）；
  把它们塞进本轮会把一个 bin 级接缝扩成三仓交付。另立 BET。
- **`OMO_ALLOW_GIT_WRITE=0`**：属计划决策 3 / B4b 批次 2，需逐批授权。
- **launchd/cron 改道**：属 B4b 批次 2+，需逐批授权。前置事实见 §4——本轮对本机运行时效应为零，
  正是因为改道尚未发生。
- **`system.yaml` 摘库**：另见任务 #98 / G9，其前置是 `current-state-coherence.py` 缺输入时
  如何诚实降级，不能与本轮混做。

## 4. 前置事实（决定本轮风险半径）

实测 `~/Library/LaunchAgents` 的 24 个 plist 与 crontab 的 39 行**零条声明 profile env**
（`OMOSTATION_STATE_ROOT` / `OMOSTATION_PROFILE`），因此本机 `state_root() == code_root()`：
I1 的改道在现网**不改变任何实际落点**，只改变"若某天声明了 profile 会落到哪"。
另两条：无任何 cron 项运行 `policy_radar.py`；无任何 CI workflow 引用 `policy-radar` 或
`convergence-pulse`。故本面的落点**不可能靠 CI 验证**，I6 的本地实跑是唯一证据来源。
