---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-219 — system.yaml 字段写者归属实测并接成可校验门禁
bet_id: BET-Y2Q4-T10-219
status: accepted
lifecycle: contract
last-reviewed: 2026-10-01
owner: governance-team
---

# system.yaml 字段写者归属实测并接成可校验门禁

> ADR-0456 决策 4 / plan B5 的残留。本轮**不动任何一个键的位置**，只把"谁写这个字段"
> 从一句没人校验的注释变成门禁。这是键摘库（T10-220）的前置：没有机器可校验的写者图，
> 搬字段等于赌读者清单没漏。

## 1 问题（全部为本轮实测，非推断）

`.omo/state/system.yaml` 是**既是跟踪文件又被运行时改写**的那一类（决策 4）。30 天窗口内它
被 54 个 commit 改动（对照同 cohort 的两份跟踪 jsonl：`governance-history.jsonl` 4 次、
`omo-events.jsonl` 2 次）。要摘掉波动字段，先得知道每个字段的写者。现有声明面是
`.omo/_truth/registry/write-owners.yaml`，它自称被 GaC #38 `bin/gac/omo-state-write-guard.py`
强制（文件头第 4 行："非授权写入被 … 检测为违规"）。实测三件事与该声明不符：

1. **字段归属覆盖率 6/23。** `fields[".omo/state/system.yaml"]` 声明 14 个键，文件实有 23 个顶层键。
   其中 17 个键无任何声明：`current_wave`、`health_score_evidence`、`health_score_evidence_source`、
   `health_score_evidence_generated_at`、`completed_tasks`、`planned_tasks`、`active_tasks`、
   `blocked_tasks`、`total_tasks`、`next_active_tasks`、`next_planned_tasks`、`updated_at`、
   `harness`、`self_evolution`、`health_score_source`、`governance_feedback_last_run`、
   `workflow_mesh_health`。
2. **8 个声明是幽灵。** `phase41_status`…`phase44_status`、`next_milestone`、
   `debt_adjusted_health_score`、`debt_items_total`、`debt_items_resolved` 在
   `.omo/state/*.yaml` 与 `.omo/state/runtime/*.yaml` 全域**不存在**（逐个 `grep -l '^<key>:'` 零命中）。
   `registry` 的 `last_updated` 停在 `"2026-07-17"`。
3. **声明没有任何消费者。** `write-owners.yaml` 有两个下游，都只读 `write_owners`（路径段）：
   `bin/ssot/write-owner-audit.py:54` `return data.get("write_owners") or []`（pre-commit G-CONV.5），
   而 `omo-state-write-guard.py` 的 check 2 名叫 `check_unauthorized_writes`，实际只做
   `git status --short -- .omo/debt/` 找未暂存删除（`:76-95`），**一次都没读过 `fields:`**。
   check 1 只查重键。结论：字段级归属是装饰性的 —— 声明错了也不会红。

顺带两条同批实测（写进本 spec 是为了让下一轮有读数，不在本轮修）：

- `bin/mof/generate-brief.py:15-17` 的注释断言 system.yaml 有"三个写者"。实测写者是 **10 个入口**：
  6 个 root 侧 + 4 个 `projects/omo` 侧。少算的那个是 `bin/compass_radar.py:1394-1430`
  （`_sync_system_yaml_health_fields`，它还会把 `health_score_evidence` 覆写成自己的 `health_score`
  并把 source 改成 `"compass_radar (synced)"` —— 这就是 R-GOV-2 要比对的两个数为何同源）。
- 3 个 root 侧写者仍是 `__file__` 反推的检出根，与 ADR-0456 写侧契约相悖：
  `bin/gac/harness-omo-bridge.py:181`（`WORKSPACE = Path(__file__).resolve().parents[2]`，`:28`）、
  `bin/gac/self-evolution-loop.py:28`（`REPO` 同法）、`bin/compass_radar.py` /
  `bin/meta/compass_radar.py`（`ws_root` 由参数传入）。改根属 T10-220/后续，见 §3 非目标。

## 2 契约（本轮交付，四条都可执行）

**C1 字段归属全覆盖。** `fields[".omo/state/system.yaml"]` 必须为系统当前键集里**每个**顶层键声明 owner。
owner 词法：`script:<repo 相对路径>` | `daemon:<name>` | `human:<name>` | `broker:<name>` | `anyone`。
`script:` 的路径必须在 `code_root()` 下存在。声明按 §4 的实测写者图填写。

**C2 无幽灵声明。** 声明了但文件里没有的键 → 违规。理由与 C1 对称：一份会漏报的清单，
在"这个字段没人写了吗"这个问题上和没有清单等价。

**C3 门禁真校验。** `omo-state-write-guard.py` 新增 `check_field_ownership()`，输出三类违规
（`undeclared-key` / `ghost-declaration` / `unresolvable-owner`），非零退出。
该脚本已在 `gac-local-gate.py:219` 与 `harness-omo-bridge` 所在的 CI 面上作为 gate step 存在，
因此接线成本为零 —— 只要它开始真的失败。

**C4 判据用对根。** guard 读的 `system.yaml` 是**写面**（profile 声明）→ `state_root()`；
读的 `write-owners.yaml` 是**读面**（治理 SSOT）→ `code_root()`。当前两者都由
`Path(__file__).resolve().parents[2]` 得出（`:19-22`），即两个都钉在脚本自己的检出上 ——
这正是 AGENTS.md §7 记的那类"写者已改挂 state_root、读者还跟着检出，于是永远看最后一次提交的快照"。
本轮把 guard 自己纠正，并把 `--json` 作为可核对的输出面（打印两个目标路径）。

## 3 非目标（带读数）

- **不搬任何字段**，不 `git rm --cached`，不改 `.gitignore`。键摘库是 T10-220；
  波动读数（30 天出现次数）：`health_score_evidence_generated_at` 21、`updated_at` 20、
  `planned_tasks` 15、`health_score_generated_at` 15、`health_score` 14、
  `governance_feedback_last_run` 14、`next_planned_tasks` 13、`workflow_mesh_health` 13、
  `runtime_health_summary` 12、`completed_tasks`/`total_tasks`/`governance_anomaly_score` 8。
  骨架 `current_phase`/`current_wave` 必须留在跟踪文件里：CI 唯一消费面是
  `.github/workflows/state-goals-enforce.yml:28` → `bin/ssot/current-state-coherence.py:169-183`，
  而它对**缺文件**硬失败（`:32`），对缺这两个键才回退。
- **不动 `projects/omo/**`**（含 gitlink）。`updated_at` 与 5 个 task 计数键的写者在
  `omo_state.py:352-364`、`omo_audit_sync.py:319-335`，且 `omo_state.py:33` 无视
  `omo_paths.STATE_SYSTEM_YAML` —— 那是子模块 commit + 指针 bump 的批次。
- **不改 3 个检出根写者的根**（§1 末条）。本轮只把它们登记为 owner。
- **不碰 `write_owners` 路径段** —— 它有独立消费者（`write-owner-audit.py` → pre-commit G-CONV.5），
  改 owner 字符串会改变 pre-commit 行为，与本轮目标无关。

## 4 实测写者图（`fields:` 据此填写）

| 键 | 写者 file:line | 根 |
|---|---|---|
| `health_score_evidence`, `_source`, `_generated_at` | `bin/gac/evidence-smoke.py:225-245` | state_root |
| `health_score`（第二写者） | `bin/gac/unified-health-score.py:396-401`（`--sync`） | state_root |
| `health_score`, `governance_anomaly_score`, `service_online_ratio`, `health_score_source`, `health_score_generated_at`, `runtime_health_summary`, `workflow_mesh_health`, 并覆写 `health_score_evidence`/`_source` | `bin/compass_radar.py:1154-1178` + `:1394-1430`（`bin/meta/compass_radar.py` 为副本） | 检出根（参数传入） |
| `self_evolution` | `bin/gac/self-evolution-loop.py:228-241`（`--sync-omo`） | 检出根 `REPO:28` |
| `harness` | `bin/gac/harness-omo-bridge.py:181-195` | 检出根 `WORKSPACE:18` |
| `current_phase`, `current_wave`, `total_tasks`, `active_tasks`, `blocked_tasks`, `planned_tasks`, `updated_at` | `projects/omo/src/omo/omo_audit_sync.py:319-335` | 子模块 |
| `planned_tasks`, `active_tasks`, `blocked_tasks`, `total_tasks`, `next_active_tasks` | `projects/omo/src/omo/omo_state.py:352-364` | 子模块 |
| `governance_feedback_last_run` | `projects/omo/src/omo/omo_ingress_state.py:263` | 子模块 |
| `current_wave`（第二写者） | `projects/omo/src/omo/omo_ingress_goal.py:395` | 子模块 |
| `completed_tasks`, `next_planned_tasks` | 同上 omo 侧聚合（`omo_state.py` / `omo_audit_sync.py`） | 子模块 |

一个键允许有多个写者（`health_score` 有三个），但 owner 字段只能表达一个 —— 因此 C1 声明的是
**权威写者**，其余写者在本表与本 spec 里留名；`health_score_evidence` 的 owner 记
`evidence-smoke.py`，而 `compass_radar` 对它的覆写是本表里唯一一处"两个写者写同一个键且值不同口径"，
这条留给 T10-220 处理（摘库前先解决口径，否则投影里会留下互相覆盖的两个数）。

## 5 回归面与检测

| 风险 | 检测 |
|---|---|
| 新校验把别人的交付变红（有人刚加了键） | 这是**期望行为**；报错文本必须直接给出该补哪一行（`undeclared-key` 消息带键名与 registry 路径） |
| CI 检出（HEAD 版 system.yaml）与本声明键集不符 | 实测：`git show HEAD:.omo/state/system.yaml` 与工作副本键集**逐键相等**（23 = 23，差集两侧皆空）→ CI 首跑即绿 |
| 未声明 profile 时 guard 解析换根导致行为漂移 | `--json` 在无 env 时打印的 `system_yaml` 必须等于 `$(git rev-parse --show-toplevel)/.omo/state/system.yaml`；由测试钉住 |
| 幽灵声明被"顺手补个假 owner"糊过 | C2 与 C1 由同一函数双向断言，测试含 ghost 与 unresolvable-owner 两条负例 |
