---
schema_version: specification/v1
spec_version: 1.1.0
title: Runtime Projection Plane Phase 2 — Stop Legacy Dual-Write and Untrack Generated State (ADR-0456 B5)
bet_id: BET-Y2Q4-T10-212
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-28
adr: ADR-0129
---

# ADR-0129 Phase 2 — 生成态摘库（停止 legacy 双写 + 消费端接 projection_path）

> 正文只写不变量。所有数字为撰写时点（2026-09-28T10:25Z）在工作副本
> `/Users/xiamingxing/ws-b5-genstate-untrack-20260928` 上的实测，用于说明前提，不构成判据。
> 上游契约：`.omo/_knowledge/decisions/0129-state-projection-plane-phase3.md`、
> `ADR-0456`（code_root / state_root 双根）、`.omo/_truth/registry/runtime-projections.yaml`。

## 0. 这一轮解决什么

ADR-0129 Phase 1 把投影写成 **canonical + legacy 两份**
（`projects/omo/src/omo/omo_ingress_state.py:234-298`，注释自陈
"Legacy paths kept during ADR-0129 migration (Phase 1 dual-write)"）。
后果是 legacy 那一份**既是 git 跟踪文件又被 cron 改写**，于是每次 commit / claim 都会把
纯时间戳漂移扫进无关 PR（AGENTS.md §7 实证 #4346 / #4359 / #4419 / #4420）。

Phase 2 = **停止 legacy 双写 + 把 legacy 从跟踪中摘除**，不是新发明一个机制。

### 前一轮为什么失败（必须避免重复）

PR **#4334**（2026-09-25 合并）是一次**整片清扫**：把 `.omo/debt|_control|_log` 与 `BRIEF.md`
一次性 `git rm --cached`，连带删掉了真正属于权限面的 SSOT
（`.omo/_control/INDEX.md`、`north-star.md`、`evolution/config.yaml`、
`governance-overlay/*.yaml`、`obsidian-vault/*.md`）。PR **#4358** 随即
"Re-track `.omo/state/health.yaml`（gitignore `!` exception）" 回滚了其中一部分。

⇒ 本契约的硬约束：**逐文件判定 + 消费端接线与摘库同批落地 + 撤销豁免只针对被摘的那些行**。
判据不是"看起来像状态"，而是下面 §1 的两个测试。

## 1. 入册判据（每个文件独立过闸）

一个 legacy 路径 `L` 可以在本轮被摘除，**当且仅当**同时满足：

- **P1 已入册**：`runtime-projections.yaml` 里存在一条 `legacy: L` 的 projection，
  且 `omo_paths.projection_path(name)` 可解析它（未入册的名字会 `KeyError`，
  见 `projects/omo/src/omo/omo_paths.py:146`）。
- **P2 摘除后不新增红**：在 canonical 也不存在的最坏形态（= fresh clone，
  `.omo/state/runtime/` 目录缺失）下，所有读 `L` 的门禁/工具的**退出码不高于基线**。
  测量方法见 §4；判据是退出码，不是报告行数。

本轮判定结果（实测，非推断）：

| legacy 路径 | 入册 | 缺失时最差退出码变化 | 判定 |
|---|---|---|---|
| `.omo/state/health.yaml` | ✅ `health` | 门禁全为 SOFT，CI 侧 `meta-doctor --refs-only` 跳过心跳 → 无新增硬红 | **摘** |
| `.omo/_control/governance-data.json` | ✅ `governance_data` | 同上 | **摘** |
| `BRIEF.md` | ✅ `brief` | 同上（`panorama-collect` 需先修，见 §2.3） | **摘** |
| `.omo/state/system.yaml` | ❌ registry `:87-93` 明写 "Future" | `current-state-coherence.py` **0 → 2**，且被 `state-goals-enforce.yml:28` 直接调用 → CI 红 | **不摘** |
| `.omo/state/collab-dualtrack.yaml` | ❌ 无条目 | `check-dual-track-purity.py` **0 → 1** | **不摘** |

`system.yaml` 不摘的理由不是"它是配置"这么笼统：它是**配置与投影的混合体**，
`write_system_projection_fields()` 在文件缺失时**直接 `raise FileNotFoundError`**
（`projects/omo/src/omo/omo_ingress.py:126`）——先决条件（bootstrap）不存在，
所以必须另立一轮（Phase 2b）。

## 2. 不变量

### 2.1 单一写入面

`sync_state_projection()` 对 health / brief / governance_data **只写 canonical**。
Phase 1 的三次 `_mirror_projection()` 调用（`omo_ingress_state.py:291-298`）移除；
`legacy_*_path` 三个局部变量随之消失。canonical 仍由 `omo_paths` 解析到
`state_root`，不得由 `workspace_root` 反推（ADR-0456 §7）。

### 2.2 读取面一律经解析器

任何读这三个投影的工具不得硬编码 legacy 字面量，必须走
`omo_paths.projection_path(name)`（canonical 存在则用，否则回退）。
**缺失不是错误状态**：新生成的检出里 canonical 尚未产出，工具必须区分
"absent（生成器还没跑）" 与 "stale（跑过但老化）"，前者不得计为 expired。
这条同时治掉一个既有假红：已摘库的 `system_health.yaml` 今天让
`state-freshness-check` / `meta-doctor` / `probe-heartbeat-monitor` 在任何 fresh clone 上
恒报过期。判据必须原地 A/B（`git checkout origin/main -- <file>` 跑完再 checkout 回来）——
这些工具用 `__file__` 反推根，把 baseline 落盘到别处会凭空变绿。
`#4515` 实测：`meta-doctor` 在同一检出上 `stale_beats` 1→0（新增 `absent_beats` 1），
rc 保持 1（`ritual_lapsed` 预存）；`probe-heartbeat-monitor` 在 state root = `~/Workspace`
时逐条等于 baseline（总计 8 / 正常 7 / 异常 1 / 未生成 0，即生产路径行为零变化），
在从未生成运行态的检出里 `异常 1 → 0`（原先那条是 `系统健康巡检: 9999h / 48h` 的永久红）。
**只有"文件不存在"才降级为 absent**；存在但字段缺失/不可解析仍算异常。

### 2.3 摘库与忽略同批

`git rm --cached` 之后文件变成 untracked，而 `gac-gate.yml:204,233` 断言
`test -z "$(git status --porcelain)"`（porcelain **含** untracked）。
⇒ `.gitignore` 新增规则必须与摘库在同一个 commit。

实测（`git check-ignore --stdin -v`）三件在**撤销 `!` 之后仍然不被任何规则覆盖**：
`.omo/state/` 的 ADR-0404 块只忽略 `*.jsonl` / `*.json` / 若干目录，**没有 `*.yaml` 通配**，
根级也没有任何命中 `BRIEF.md` 的规则。所以必须**逐条新增精确忽略**，光删 `!` 会留下
untracked-unignored 文件、直接撞 porcelain 断言：

- 新增 `.omo/state/health.yaml`、`.omo/_control/governance-data.json`、`/BRIEF.md`
  （根锚定，避免波及嵌套的同名文件）
- 删除 `:296` `!.omo/state/health.yaml`（本轮回该轮摘掉的那行）
- 删除 `:295` `!.omo/state/system_health.yaml`：它被 `:395` 的精确忽略
  覆盖，是死规则（实测 `git check-ignore -v` 归因到 `:395`）。

反向豁免的撤销只允许针对**本轮摘掉的那几行**，其余 `!` 行一律不动 —— 这正是 #4334 越界的地方。

### 2.4 历史面不得随投影路径漂移

`_append_health_history()` 用 `health_yaml_path.parent.parent / "state" / "history"` 推导
历史目录（`bin/compass_radar.py:942`，副本 `bin/meta/compass_radar.py:702`）。
一旦 `health_yaml_path` 上移到 `state/runtime/`，该推导静默变成
`.omo/state/state/history/health.jsonl`，而 `tests/test_compass_radar_history.py:125`
钉的是 `.omo/state/history/health.jsonl`。⇒ 历史目录必须**锚定到根**，不得由投影文件位置反推。

### 2.5 已跟踪事实不得成为门禁前提

`write-owner-audit.py:35` 只看 `git diff --cached --name-only`，untracked 文件对它不可见；
本轮不新增任何"某路径必须 tracked"的断言，也不保留此类断言。

### 2.6 P2 消费端逐工具实测裁决（2026-09-28）

先定一条被 §1 表格隐含、但没写出来的结构事实：**`git rm --cached` 不删磁盘文件**。
摘库后已存在的检出（生产机、历史 worktree）里三件照旧生成、照旧存在，
所以 P2 的差异**只发生在新建检出**（fresh clone / 新 claim / CI checkout）。
把这条摊开，"摘库会不会打红在跑的东西"与"新建检出会不会一上来就红"是两个问题，答案不同。

一轮委托审计给出 26 个消费端、把 5 个列为 P2 失败。逐条用直接测量仲裁（只报测到的）：

| 消费端 | 接线 | 实测 | 裁决 |
|---|---|---|---|
| `panorama-collect.py:4836,4846`<br>`git checkout -- .omo/ BRIEF.md` | launchd `com.omostation.panorama-dashboard-refresh` + `Makefile:541` | 临时仓复现：BRIEF.md untracked 后该命令 **rc=1 且 `.omo/` 一个都不恢复**；`run()` 只返回 `(rc,out)` 不抛 → 脏 `.omo` 留给 `:407` `--untracked-files=all` → `projection_code_root_dirty` | **确认，PR-2 必修**（拆成两条 pathspec） |
| `governance-readiness.py:152` | 无 CI/cron（仅 `bin/_registry/scripts/**`） | `score_governance()`：present `(0, 73.0)` / absent `(0, 0.0)` —— 维度分**同为 0**（health_score 73 < 90 早已 forfeit） | **驳回**：`:365` 的 rc 无变化 |
| `c2g-radar-daily.yml:44-50`<br>`upload-artifact: .omo/state/health.yaml` | CI（每日） | `compass_radar.py:1252` 自己写 legacy（`args.output or omo_dir/"state"/"health.yaml"`），与 `_mirror_projection` 无关 | **驳回**：移除双写不影响 artifact 步骤 |
| `check-dual-track-purity.py:105` | `redlines.yaml:53` + `ci-surfaces.yaml:51`，但该条目 `workflow: "(none)"`、`triggers: []` | BRIEF.md 缺失 → `return []` → rc 0（红线静默不检） | **降级**：不在 CI 跑，本地检出 BRIEF.md 恒在 ⇒ 不瞎；新建检出的空转归 PR-3 |
| `unified-health-score.py:250` | cron `.omo/cron/registry.yaml:634`（带 `--sync`）、`install-maturity-cron.sh:14` | `score_runtime()` 实测：present `100.0` / **absent `0.0`** / `service_online_ratio: unavailable` `100.0` / 不可解析 `100.0`；权重 `runtime: 0.10` ⇒ UHS −10.0，`--sync` 把 `health_score` 写进**仍被跟踪的** `system.yaml` | **确认**：缺陷是"存在但坏 ⇒ 满分，不存在 ⇒ 零分"，方向反了；新建检出红，生产机不变 |
| `omo_doctor.py:48`（`_check_key_files` 含 `state/health.yaml`） | 手动 CLI（`governance-check.yml` 跑的是 `meta-doctor.py`，不是它） | `:194` `fail_count > 0 → return 1` ⇒ 新建检出 0→1 | **确认**，非门禁，PR-3 |
| `health-predict.py:34`（`if not current: return 1`） | 仅 `bin/_registry/scripts/state/` | 新建检出 0→1 | **确认**，非门禁，PR-3 |
| `maturity-align.py:205-221` | 仅 `bin/_registry/scripts/governance/` | health 缺失 ⇒ `c_norm=None` ⇒ `state_values` 只剩一个 ⇒ `spread=0` ⇒ `reconciliation_score=100.0` 且 `drift_detected=False`（分歧再也测不出） | **确认**：不新增红，但把"缺席"算成"完全一致"，PR-3 |
| `observability-events.py:328` / `auto-remediate.py:94` | cron `:603-605` | 均为 `if not path.exists(): return 0/False`；生产机上文件仍随 cron 生成 | **不构成 PR-2 阻塞**（新建检出没有别的运行态，本就不该有事件） |

⇒ PR-2 的**准入增量只有一处**：`panorama-collect.py` 的 pathspec 拆分。
其余"新建检出"侧的读法修正统一归 **PR-3**，判据是 §4 第 8 条。

## 3. 明确不做

- 不动 `system.yaml` / `collab-dualtrack.yaml` 的跟踪状态（§1 判定）。
- PR-2 不为 §2.6 的"新建检出"侧缺陷扩车道 —— 那会让摘库 commit 混入
  `code` 与 `governance_code` 两条 lane，`change-lane-check` 直接 hard fail。
- 不做 #4334 式整片清扫；`_control/` 下的真 SSOT 一个都不碰。
- 不改 `.omo/_truth/registry/**` 的跟踪状态（那是权限面，不是状态面）。
- 不引入新的 projection 条目 —— `collab_dualtrack` 若要入册需先定 generator 归属，另立 BET。

## 4. 完成判据（全部为可复跑命令）

在 canonical 目录不存在的形态下（fresh clone，或把 legacy 三件临时移走）：

1. `python3 bin/gac/state-freshness-check.py` 退出码 **等于**基线，且报告里不再出现
   `health.yaml / governance-data.json / system_health.yaml — file missing` 被计为 expired。
2. `python3 bin/gac/meta-doctor.py --workspace .` 的 `heartbeat` 段对三件投影报
   `exists: false` 但**不计入 `stale_beats`**。
3. `python3 bin/panorama/panorama-collect.py --check-side-effects` 可跑；
   `git checkout --` 的 pathspec 不再包含 `BRIEF.md`。
4. `git ls-files` 不再含三件 legacy 路径；`git status --short` 在摘库后为空
   （证明 `.gitignore` 与摘库同批，`gac-gate.yml` porcelain 断言成立）。
5. `git show origin/main:BRIEF.md` 之类不再被任何**门禁**用作测量来源；文档引用改指 canonical。
6. `uv run --project projects/omo pytest projects/omo/tests/test_omo_ingress_state.py` 绿，
   且断言改为"legacy 不再被写"（`_mirror_projection` 消失）。
7. `make gac-local-gate` 相对基线**无新增 hard fail**（SOFT_CHECKS 内的变化须逐条解释）。
8. （PR-3）在把三件临时移走的检出里：`unified-health-score.py` 不再把缺失记成 `0.0`
   而是"不参评"（且不写 `system.yaml::health_score`）；`omo_doctor.py` /
   `health-predict.py` 对未生成投影报 absent 而非 fail；`maturity-align.py` 在
   `c_norm is None` 时给出 `reconciliation_score = None` 而不是 `100.0`。
   三条都得给出**原地 A/B**（§2.2）的前后退出码。

## 5. 回滚

本轮全部改动在单 PR 内，回滚 = revert 该 merge commit。摘库与 gitignore 同批，
故 revert 即恢复跟踪；`_mirror_projection` 的移除即恢复双写。无数据迁移，无外部效应。
