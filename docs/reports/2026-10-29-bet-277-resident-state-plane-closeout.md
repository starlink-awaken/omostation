---
type: ephemeral
status: completed
owner: governance-team
last-reviewed: 2026-10-29
lifecycle: history
---

# BET-Y2Q4-T10-277 Closeout Report — omo.resident 状态面写者的第四种形状：调用方给的根绕过缝

> **BET ID**: `BET-Y2Q4-T10-277`
> **所属规划**: 3Y-BET-LEDGER (Y2Q4) / ADR-0456 决策 2「写路径改挂 state_root」的 B1 verify 残面
> **责任团队**: governance-agent
> **交付日期**: 2026-10-29
> **规格**: `docs/superpowers/specs/2026-10-28-bet-277-resident-writer-anchor-convergence.md`
> **交付链**: 登记腿 [#4941] → 代码腿第一半 omo [#224] → `a8709b9` → 代码腿第二半 omo [#225] → squash `be1a900b18918ef3b0cae5bdc508332902103389`（mergedAt `2026-10-29T03:11:46Z`）→ 本收口腿（根 gitlink + receipt + retro + 台账指针订正）
> **闭环状态**: **工程轴 VERIFIED**（四条 `done_when` 逐条见 §1，其中 V4 由指针订正支撑）；运行轴 **PROVEN 局部**（见 §3，未做机器侧改道）；价值轴 NOT_PROVEN
> **不做的宣布**: 本轮**不**宣布 ADR-0456 B1/B2/B3/B4/B4b/B5 或整个 plan 完成

---

## 1. 四条 done_when 与实际交付形状

| # | 台账判据 | 实测读数 | 判定 |
|---|----------|----------|------|
| V1 | 8 处写者的锚点在声明 `OMOSTATION_STATE_ROOT=<tmp>` 后全部落在 `<tmp>` 下；未声明时与历史路径逐字节一致（C5） | 落点判据在 `projects/omo/tests/unit/resident/test_resident_writer_anchor.py` 里逐写者断言：`test_declared_profile_writers_land_in_state_root`（正向落点）、`test_sema_default_root_writes_land_in_declared_state_root`、`test_pipeline_supervisor_state_subdirs_follow_the_state_root`；未声明侧 `test_undeclared_profile_lands_on_workspace_root_not_the_code_tree`（按写者参数化）+ `test_sema_state_paths_identity_without_profile` | **MET** |
| V2 | 从与检出无关的 cwd 实例化 `RefinementStore`/`SnapshotManager` 与 sema 默认路径，产物不落 cwd | 同一轮补的两条默认根用例：`OMOSTATION_STATE_ROOT=<tmp>` + `cwd=<无关目录>`，sema 规则库读入 2 条、manifest 落盘、`im-triage` 卡片三者都在 `<tmp>` 下；代码树与 CWD 目录一份不多 | **MET** |
| V3 | 修后一次运行 `git -C projects/omo status --porcelain --untracked-files=all .omo/state` 不新增行 | 交付 worktree 内该命令**修前修后读数均为空**（该树按构造没有 `projects/omo/.omo/state/`：fresh claim 浅 init）。台账写的「改前 15 行 ??」来自 2026-10-28T07:12Z 在 **canonical** 检出（四面齐全、写者曾在此跑过）的登记腿读数，本轮**未在 canonical 复现**（复现要在共享主区跑写者，与「主工作区只读」冲突）。因此 V3 成立的是「声明 profile 后写者不再落代码树」这一条，不是「把 15 行清零」 | **MET（带读数来源披露）** |
| V4 | `tests/unit/test_omo_resident_writer_anchor.py` 含变异对照：改窄任一侧落点断言当场红，绿不得来自检测器没命中 | 台账点名的这个路径**在 origin/main 与 omo main 上都不存在**（`git ls-tree -r origin/main` 计数 0），尺实际落在 omo 侧 `projects/omo/tests/unit/resident/test_resident_writer_anchor.py`。变异对照三条都在那份文件里：① `test_the_ruler_fires_on_the_real_module_once_the_seam_is_removed` 在**真实模块源码**上摘缝 → 尺当场命中 1（两个模块各一条）；② 摘掉产品（把缝退回旧锚）→ 落点断言 7 红 / 检测断言 15 绿；③ 改窄任一侧断言 → 2 红。本 PR 同时**订正**台账里这个陈旧指针（§4.2） | **MET（指针订正后）** |

## 2. 尺（第四种形状）与其反基线

`state_plane_from_arbitrary_root`：状态面路径由**调用方给的根**（`self.ws` / `ws`）拼出来、绕过缝。判据只看最长 `/` 链的最外层，且最左操作数是缝调用（`write_path`/`state_root`/`code_root`/`event_ledger_path`/`canonical_root`）或 `WORKSPACE` 锚、或整条链都在缝实参里 → 不算命中。前两版候选设计分别读过 **0（空绿）** 和 **18（假命中）**，第三版才与被检对象同源。

反基线与改后读数由**同一次扫描**产出（AGENTS.md §7⑤）：

```
omo.resident.memory_pipeline     pre=0 post=0
omo.resident.replay              pre=0 post=0
omo.resident.refine_rollback     pre=0 post=0
omo.pipeline_supervisor          pre=3 post=0
omo.resident.sema_crystallizer   pre=2 post=0
TOTAL  pre(a8709b9 src/omo) = 5   post(be1a900 src/omo) = 0
```

（`git archive a8709b9 src/omo` 造反基线树，与交付树逐模块跑同一把尺。）

## 3. 真实改动：spec 的 8 站表之外还有 4 处

第一半（#224）把 8 处写者的**锚**从 `parents[3]`/`Path.cwd()` 收到 `WORKSPACE` + `write_path()`。第二半（#225）修的是同一根因的**另两种形状**，spec 的 8 站表没覆盖：

- `sema_crystallizer`：状态面由调用方根 `self.ws` 直拼（`hard-negative-rules.jsonl` 读、`sema-skills-manifest.json` sentinel）→ 收进 `_state_path()`，`workspace_root` 改可选默认 `WORKSPACE`，**显式注入根仍优先**（契约 C2：注入根 > profile）。
- `pipeline_supervisor`：4 处站点用代码面 `ws` 拼状态面 —— `policy-radar/brief-*.{json,md}` 两处读、`im-triage` 一处真实写、`card_file.relative_to(ws)` 一处。**最后一处不在尺的射程**（它不是路径拼接，是声明 profile 后当场 `ValueError` 的锚错位），统一收进 `_state_dir()` 后一并消除。所以「尺命中 3 处」与「修 4 处」同时为真，不是读数矛盾。
- 代码面用法**刻意留在 `ws`**：`bin/bc-os/policy_radar.py`、`projects/{omlxc,cockpit,agora}` 这些 subprocess 引用的 checkout 路径，以及 `skills_root()`/`index_path()`（SKILL.md 是进版本库的资产，不是运行态）。
- 删的是死码不是搬家：`DEFAULT_RULES_REL`/`SKILLS_DIR_REL`/`INDEX_REL` 三个相对量常量全仓检索零引用（ecos 的 `DEFAULT_RULES_REL` 是同名独立定义，不受影响）。

**运行轴只做到「写面归位」**：没有碰 plist / launchd / crontab / 权威 ledger，也没有把既有文件从版本库里摘出去 —— 改道与摘库是 B4b/B5 的 principal 决定面。`projects/omo/.omo/state/` 下 `cell_states.json`（2B）与检出根面同名文件（906816B）的**合并方向仍是数据决定**，本轮未替代人做。

## 4. 已知、未进本 PR

### 4.1 根测试回归（独立 lane）
`tests/test_pipeline_supervisor.py` 三条用例把 `_ws` patch 到 `tmp_path`；第一半之后状态面不再跟随 `_ws()`，于是 `test_state_roundtrip` 与 `test_inbound_degrade_on_missing_file` 在 main 上**红**，并把 `.omo/state/pipeline-supervisor-state.json` 漏进检出根（hermetic 泄漏）。该路径**不在本 run 的 WorkPacket scope** 内（claim 报 `WORK_PACKET_SCOPE_MISMATCH`），按「独立 lane 单独 PR」处理，不在本 PR 顺手改窄。已定修法：用例内声明 `OMOSTATION_STATE_ROOT=tmp_path`（保意图、变封闭），不删用例（omo 侧无等价覆盖，根文件是唯一证据）。

### 4.2 台账陈旧指针（本 PR 订正）
`write_surfaces` / `done_when[3]` / `verify[0]` 三处引用 `tests/unit/test_omo_resident_writer_anchor.py`，该路径按构造不存在（尺在 omo 侧，因为写者与 CI 都在 omo 侧：omo `ci.yml` 跑整份 `pytest tests/`，根 `governance-check.yml` 的显式白名单不含 `tests/**`）。订正为实际交付路径，`accepted_specifications[0].content_digest` **逐字未改**（写回后回读对拍 `sha256(spec 文件字节)` 相等）。

### 4.3 交付 worktree 的无关漂移与浅历史读数
- 收口 worktree 里 `projects/agora` 有**不是我做的** gitlink 漂移：index 里是 `4ae1a58a…`（本地 gitdir 无此对象），而 `origin/main` 的树是 `e3bd2445…`，子模块工作树 HEAD 又在第三处 `4832369…`。**三读数互不相同 ⇒ 这不是「我 bump 了 agora」，是 claim/守卫留下的 index 与检出不对齐。**
- 因此**没走** `submodule-pointer-transaction.sh`（它按 base 差集会 `git add` 全部漂移，并 push 别人子仓）。第一次尝试用 `git commit -- projects/omo`，判据 `git diff --cached --stat` 当时确实只有一行 —— 但 commit 后 `git diff --name-status origin/main..HEAD` 里**多了一条 `M projects/agora`**。原因：`git commit <pathspec>` 是在**当前 index 之上**构造提交，只把工作树里那些路径盖上去，**其它已 staged 的内容照旧入 commit**；我核的是「暂存了什么」，实际要核的是「commit 后树上多了什么」。处置：`git reset --mixed origin/main`（三个本地未推的 commit 退回、工作树文件逐字保留）→ 每步 `git add` 显式列路径 → **不带 pathspec** 的 `git commit` → 每次提交后立刻跑 `git diff --name-status origin/main..HEAD` 复核。判据以最后那条为准，`git diff --cached` 不足以支撑「没带别人的东西进来」这个结论。
- omo 侧 clone 是浅的（`rev-parse --is-shallow-repository` = true），`git show --stat be1a900` 因此把整棵树列为 1253 files / 239109 insertions —— 那是 graft 产物，**不是 PR 内容**。PR 内容在深 worktree 里复核为 3 个文件：`src/omo/pipeline_supervisor.py`、`src/omo/resident/sema_crystallizer.py`、`tests/unit/resident/test_resident_writer_anchor.py`。（附带事实：omo 仓自己跟踪了一份 `.claude/skills/omo-srp-refactor/SKILL.md`，早于本轮，非本次引入。）
- 本地门禁/测试曾在 worktree 状态面留下 gitignored  fixture 产物（`pipeline-supervisor-state.json`、`compute/dynamic_nodes.json`），确认为测试写入且 canonical 无同名，已删。

### 4.4 顺手记录但不本轮修的兄弟面
- `tests/unit/test_resident_write_plane_split.py`：6 条既有红 + 声明 18 / 实扫 42 的口径缺口 + `.omo/state/*` 通配标签需按新键集重签。
- `tests/unit/test_swarm_mesh.py`：非封闭（读 host 状态）。
- cockpit / omlxc / ecos 侧的同类写者兄弟（读者与写者成对出现，本轮只覆盖 omo）。
- 门禁的「登记面假设」本身在更早轮次已被否证（`runtime-projections.yaml` 17 条只 1 条被跟踪），V3 那类「旧值还在」不能当仓库保证。

## 5. 验证台账

| 命令 | 读数 |
|------|------|
| `pytest tests/unit/resident/test_resident_writer_anchor.py -q -p no:randomly` | 22 passed（交付 worktree 复跑） |
| `pytest tests/unit/resident -q` | 27 passed |
| `pytest tests/unit -q` | 624 passed / 2 skipped |
| omo CI `ci.yml`（lint / test / test-cov） | 全绿 —— CI 干净检出跑整份 `pytest tests/`，构成本轮 hermetic 的外部佐证 |
| L3 deep security review（提交集 `f62d521`） | 0 findings |
| `git -C projects/omo status --porcelain --untracked-files=all .omo/state` | 空（修前修后同读数） |
| 尺反基线/改后同扫 | pre=5 / post=0 |

## 6. 一次运行一条记录（AGENTS.md §13.2）

| 字段 | 值 |
|------|-----|
| `inputs` | `projects/omo/src/omo/resident/{sema_crystallizer,__init__}.py`、`projects/omo/src/omo/pipeline_supervisor.py`、`projects/omo/tests/unit/resident/test_resident_writer_anchor.py`、`docs/plans/3y-bet-ledger.yaml`、`docs/superpowers/specs/2026-10-28-bet-277-resident-writer-anchor-convergence.md`、`git archive a8709b9 src/omo`（反基线树，用完即删） |
| `basis` | ADR-0456 决策 1–2（`0456-dev-runtime-profile-root.md`，按文件名引用）；契约 C2（注入根优先于 profile）；AGENTS.md §7⑤「改后为 0 与改前为 N 同扫产出」、§7③「按构造就绿须配变异对照」、§7⑧「先怀疑检测器匹配规则」、§7「主工作区只读」「子仓合并后同轮 bump 根 gitlink」 |
| `approver` | 夏明星（预推 gate 答复「Run L3 deep security review」+「继续」；独立 lane、不翻 done、不 force/伪造绑定 三条约束沿用同一串答复） |
| `result` | omo `be1a900` 合并；根 gitlink `a8709b9 → be1a900` 单路径暂存；receipt + retro + 台账指针订正落本 PR；V3 的「改前 15 行」未复现并如实标注来源 |
| `duration_ms` | `null` —— 本轮未做逐步骤计时，两腿加收口腿跨 2026-10-28T07:12Z 起断续执行、含两次 CI 等待，写一个粗估时长就是 D1（代理量顶替） |
| `model_usage` | QoderCN 会话模型，token 计数未在本轮落面（缺项如实记 `null`） |
