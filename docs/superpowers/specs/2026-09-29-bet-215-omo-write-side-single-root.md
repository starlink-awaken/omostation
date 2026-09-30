---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 F1 — omo 写入侧统一挂 state_root（投影与 runtime 镜像根）
bet_id: BET-Y2Q4-T10-215
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-29
---

# ADR-0456 F1 — omo 写入侧统一挂 `state_root`

## 1. 问题：写侧仍按调用方给的根落位，profile 到 omo 边界就断

ADR-0456 把根分成两个：**读**跟随当前检出（`code_root`，治理 SSOT），**写**跟随 profile
（`state_root`，运行态与生成态）。根侧 `bin/lib/repo_root.py` 已实现两个根并由
`tests/unit/test_repo_root_profile.py` 钉住；omo 侧 `projects/omo/src/omo/omo_paths.py:31`
也已有 `STATE_ROOT`（同一 env `OMOSTATION_STATE_ROOT`），且 `STATE_DIR` /
`STATE_SYSTEM_YAML` 的读者（`omo_audit_sync.py`、`omo_sync.py`、`omo_workspace.py`）已挂上去。

断点在唯一的**写入者**：`projects/omo/src/omo/omo_ingress_state.py:208 sync_state_projection()`
自己从入参重建根 —— `:221` `omo_dir = workspace_root / ".omo"`、`:226`
`runtime_state_dir = omo_dir / "state" / "runtime"`、`:234` `system_path = omo_dir / "state" / "system.yaml"`。
调用方 `omo_state.py:439` 传的是 `omo_dir.parent`（检出根）。于是声明 dev profile 后，
omo 仍把四件高 churn 投影写进**开发检出**：

| 写出 | 当前位置（入参根） | 应落位置（profile 根） |
|---|---|---|
| `.omo/state/runtime/health.yaml` | 检出 | `state_root()` |
| `.omo/state/runtime/brief.md` | 检出 | `state_root()` |
| `.omo/state/runtime/governance-data.json` | 检出 | `state_root()` |
| `.omo/state/system.yaml` | 检出 | `state_root()` |
| `runtime/omo/_delivery/ingress/*`（artifact / audit / trail / lock / mutation 日志） | 检出 | `state_root()` |

最后这组同样必须翻根：`repo_root` 的契约把镜像根定义为 `state_root()/runtime/omo`
（实测断言 `runtime_omo == state_root / "runtime" / "omo"`，
`tests/unit/test_repo_root_profile.py`），而 omo 侧
`omo_ingress_paths.py:39 _runtime_omo_root()` 从 `omo_dir.parent` 反推 —— 两根在 dev profile
下会分叉成两处 delivery 日志，「谁在写」的审计链因此断裂。

这正是 plan 开头「开发打击运行」的机制形态之一：dev 检出里跑一次 sync 就改写跟踪文件，
G9 实测到的 `system.yaml` 被动写回即此路径。

**实现期实测（2026-09-29）把这条路径查到底了**：把四件投影翻到 state 根之后，
`OMOSTATION_STATE_ROOT=<tmp> omo state sync --dry-run --json` 跑完仍让
`git status --short` 报出 `M .omo/state/system.yaml`（只动
`health_score_evidence_generated_at` 一个时间戳）。残留作者不是投影写入者，而是调用图里
的**子进程**：`_build_health_projection` → `bin/compass_radar.py:485` 起
`bin/gac/evidence-smoke.py` → `_write_health_score_evidence()` 写
`SYSTEM_YAML = WORKSPACE / ".omo" / "state" / "system.yaml"`（`__file__` 反推检出根；
两个行号均为**修改前**读数）。它和投影写的是**同一个逻辑文件**，因此必须同根，否则本 BET
的判据 2「检出零新增」不成立 —— 这属 plan 决策 4 点名的连带面
（`evidence-smoke.py:227` 换成 profile 感知解析），不是新发明。
该子进程在 `--dry-run` 下照样落盘，也是「dry-run 不写」这句措辞的真实边界。
链节能闭合还有一个**不被复述的前提**：`bin/compass_radar.py:482` 的 `subprocess.run` 不传
`env=`，所以 `OMOSTATION_STATE_ROOT` 靠继承进入子进程；若那里改成显式 env 白名单，
C6 会静默断掉（判据 7 的实测读数即探针）。

## 2. 契约

**C1 参数语义**：`sync_state_projection(code_root, *, state_root=None, …)`。第一参更名为
`code_root`（读侧：`_build_health_projection` / `_build_brief_content` /
`build_governance_data` 与 `.omo` 存在性检查），它**不再**决定任何写出路径。

**C2 写侧解析**：优先级 **显式 `state_root` 入参 > env `OMOSTATION_STATE_ROOT` > `code_root`**。
env 在**调用时**读（与 `omo/workflow/delivery_anchor.py:47` 同惯例），因为
`omo_paths.STATE_ROOT` 是 import 期常量，测试无法用 monkeypatch 改变它。第三条回落的是
`code_root` 而非 `omo_paths.WORKSPACE_ROOT`，理由有两层：① 生产调用方 `omo_state.py:439` 传的
`omo_dir.parent` 恒等于 `WORKSPACE_ROOT`（`find_omo_dir()` 优先返回 `OMO_ROOT`，实测），
所以未声明 profile 时它与 `STATE_ROOT` 逐字节相同；② 若第三条取 `WORKSPACE_ROOT`，
一个 `tmp_path` 根的测试会在 env 未声明时把投影写进**宿主检出** —— 那正是 AGENTS.md
「hermetic 测试泄漏 host 状态」点名的形态。写出路径一律
`state_root / ".omo" / "state" / …`，delivery/audit/trail/lock/mutation 一律经
`_runtime_omo_root(state_root)`。不新增第二个开关 —— profile 只有 env
`OMOSTATION_STATE_ROOT` 这一个入口（ADR-0456 §env 面），CLI 也不加 `--state-root`。

**C6 写面在调用图内闭合**：`omo state sync` 的整条调用图（含它经 `compass_radar`
subprocess 起来的根侧脚本）在声明 profile 时不得留下第二个写**投影面**的作者。
`bin/gac/evidence-smoke.py` `_write_health_score_evidence()` 与投影写的是同一个逻辑文件，
其写目标须与投影同根：本轮实现为 `bin/gac/evidence-smoke.py:210 _system_yaml()`
→ `bin/lib/repo_root.state_root()`，未声明 profile 时路径逐字节同旧常量。
解析发生在**写的那一刻**而非模块 import 时
（`workflow/delivery_anchor.py:34,47` 已是这个约定；模块常量会在测试里冻住 env）。
它的读侧（`GOV_LOG` / `EVENTS_LOG`）本轮不动。C6 须有正向用例钉住（判据 8），
不能只靠判据 7 的「没有 diff」这种否定式证据。
闭合的边界是**投影面**（`health.yaml` / `brief.md` / `governance-data.json` /
`system.yaml` 的 health 与 evidence 字段）；`system.yaml` 的 task 计数字段仍由 tasks 面
写检出，见 §3 第一条与判据 7 的实测读数。

**C3 无 profile 不变量**：`OMOSTATION_STATE_ROOT` 未设时 `STATE_ROOT == WORKSPACE_ROOT`，
四件投影与镜像根的路径字符串与本轮之前**逐字节相同**。该不变量由测试钉住，与根侧
`test_kernel_read_plane_stays_on_checkout` 同形。

**C4 receipt 路径口径**：`_workspace_relative()` 的既有回退（写出不在 code_root 下时返回
绝对路径字符串）即为本契约的显示口径 —— dev profile 的 `_record_state_sync` artifact 里
`changed_paths` 是绝对路径。不为此再造相对化规则；把「不在检出下」伪装成相对路径会让
审计读者误判写落点。此行为须由测试钉住。

**C5 读侧不动**：`projection_path(name)`（`omo_paths.py:142`）的 canonical→legacy 回退顺序、
`OMO_ROOT` 下的权限面（`.omo/_truth/**`、`.omo/standards/**`）本轮一律不变。

## 3. 非目标

- 不搬 `.omo/tasks/`（709 个跟踪文件）、`.omo/debt/`（73）、`.omo/workers/`：
  这些是跟踪的治理状态面，翻根等于把它们从 git 历史里摘走，属 B5 残留（G9/#98）的判断，
  不属 F1。本轮只登记实测计数。
  **本轮实测把这条非目标的真实形态钉住了**：真实（非 `--dry-run`）sync 之后检出仍剩两个
  脏文件，作者是 tasks 面而非投影面 —— `omo_state.py:449` 在主 sync 内跑 `sync-tasks`，
  后者重写 `system.yaml` 的 task 计数字段（`total_tasks` / `next_*_tasks` / `updated_at`）
  与 `tasks/registry/INDEX.md`（`omo_state.py:232`、`:283`），两处都由检出的 `omo_dir` 派生。
  实测脏量是纯时间戳（`updated_at: 2026-09-27T08:22:42Z → 2026-09-29T16:54:29Z`、
  `INDEX.md` 的 `Updated:` 日期），计数逐字未变。翻这一面的根 = 把 `.omo/tasks/` 从 git
  历史里摘走，是 §3 第一条排除的动作。
- 不改 `system.yaml` 的**跟踪状态**（仍 tracked）；本轮只改它**写到哪**。
- 不新增 `runtime-projections.yaml` 条目，不改 `.gitignore`。
- 不碰 `bin/lib/repo_root.py`、不启停任何 launchd/cron 服务、不改 plist。
- 不给 CLI 加 `--state-root` 旗标（C2：单一 env 入口）。
- 不动 `system.yaml` 的**读者**：`governance-convergence-lint.py:32`、
  `check-project-health-freshness.py:12`、`omo-state-write-guard.py:20`、
  `bin/mof/generate-brief.py:11`、`doc-ssot-lint.py:36`、`governance-alert-dispatch.py:43`
  六处仍从检出读 `system.yaml`。声明 profile 后它们读到的是**最后一次提交的快照** ——
  这正是决策 4 要的 dev 侧语义（比较的两端 `health_score` 与 `health_score_evidence`
  同在这份快照里，不会自造分歧），摘库（#98）时随读侧解析一起收口。
- 不搬 `evidence-smoke` 自己的 JSON 报告根 `OUTPUT_DIR`（`:103`
  → `.omo/_delivery/evidence-smoke/`）：它落在 `.gitignore:12` 的 `_delivery/*` 里，
  脏不了 `git status`，且它的读者（`check-evidence-freshness.py`、
  `governance-dashboard.py`）也在检出侧 —— 单翻写侧会让读数断链，与上一条同属读/写配对
  未闭合的面，登记不解。

## 4. 完成判据

1. `omo_ingress_state.py` 内不再出现由入参根派生的写出路径；四件投影 + 镜像根经 `state_root` 解析。
2. `projects/omo/tests/test_omo_ingress_state.py` 新增 dev-profile 用例：声明外置 `state_root`
   后写出全部落在 state 根，检出的 `.omo/state/**` 与 `runtime/omo/**` 零新增文件。
3. 同文件新增 C3 用例：未声明 profile 时写出路径字符串与历史一致。
4. C4 用例：dev profile 下 artifact 的 `changed_paths` 是绝对路径字符串。
5. omo 全量测试绿；根侧 `tests/unit/test_repo_root_profile.py` 与
   `tests/unit/test_projection_reader_resolution.py` 读数不因本轮改变。
6. 真实 CLI 读数：`OMOSTATION_STATE_ROOT=<tmp> … omo state sync --dry-run --json` 报告的
   `writes[].path` 指向 `<tmp>`，且不写出任何文件（dry-run 语义不变）。
7. **端到端**（C6 的判据，不是 6 的复述）：`OMOSTATION_STATE_ROOT=<tmp> … omo state sync
   --dry-run --json` 跑完，检出的 `git status --short` 与运行前逐行相同 —— 本轮实测这条
   在只翻投影写侧时**不成立**（evidence-smoke 子进程写时间戳），翻完 C6 后成立。
   真实（非 `--dry-run`）sync 的判据不同，且必须分开写：它仍让检出脏两个文件，
   两者都是 §3 第一条点名的 tasks 面时间戳（`system.yaml` 的 `updated_at` 与
   `tasks/registry/INDEX.md` 的 `Updated:`），**不是**投影面字段；「dev 跑一次就脏检出」
   这句话里属于投影面的那一半由本判据关掉，属于 `.omo/tasks/` 的那一半是登记在案的非目标。
8. C6 的正向用例（`tests/test_evidence_smoke_paths.py`）：声明 profile 后
   `_write_health_score_evidence()` 把 `health_score_evidence` / `_source` 三行写进
   `<state_root>/.omo/state/system.yaml`，且 `_system_yaml()` 的解析路径**不在** `WORKSPACE`
   的 parents 之下；未声明时写目标字符串与旧值逐字节相同。
   本判据钉的是「写目标的解析」，检出副本的字节由判据 9 的 diff 钉。
   负向证据（判据 7 的「无 diff」）不能替代它。
9. 真实 sync 的正向落点读数：`<tmp>/.omo/state/system.yaml` 同时含
   `health_score_evidence` / `health_score_evidence_source: bin/gac/evidence-smoke.py` /
   `health_score_evidence_generated_at`（evidence 面），以及四件投影与 `runtime/omo/**`
   镜像根（`_delivery/ingress/{ingress-audit.jsonl,ingress-trail.jsonl,ingress.lock,state/*.yaml}`、
   `change-log/mutations.jsonl`）。检出的 `system.yaml` **本来就有**这三行（它们是跟踪态里
   上一次生产运行的读数），所以正确的判据不是「检出里没有」，而是**检出的这三行逐字未变**
   —— `git diff -U0` 只出现 `updated_at` 一处在滚（tasks 面，见 §3 与判据 7），
   `_generated_at` 的新时刻只落在 state 根。写落点由「同一字段的值只在 state 根滚动」正面证明，
   而非仅由「检出没脏」反证。
   （2026-09-30 串行复跑实测：state 根 `health_score_evidence: 100.0` +
   `_generated_at: '2026-09-30T01:43:58.014449+00:00'`；检出副本 evidence 三行仍是
   `2026-09-27T08:42:13.059879+00:00`，diff 仅 `updated_at` 一行。）
