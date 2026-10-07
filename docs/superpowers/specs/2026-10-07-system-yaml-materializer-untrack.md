---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B5 Phase 2b — 给 system.yaml 一个创建者，然后把它摘出库
bet_id: BET-Y2Q4-T10-235
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-07
---

# B5 的最后一件生成态 — 缺的不是摘库动作，是创建者

## 1 判据现状（2026-10-07 实测，非引用）

方案 `nimble-bay-asp.md` 给 B5 的交付是「走 ADR-0129 canonical 路径 + untrack」，判据两条：

> 一次 dev 运行后 `git status --short .omo/state` 为空；`git diff --name-only origin/main..HEAD` 不含生成态

决策 4 点名的四件生成态里，`health.yaml` / `brief.md` / `governance-data.json` 已由 BET-Y2Q4-T10-212
摘库，`resident retros` 由 T10-230 摘库，只剩 `.omo/state/system.yaml`。实测：

| 量 | 读数 | 判据 |
|---|---|---|
| `git ls-files .omo/state` | `collab-dualtrack.yaml` + `system.yaml` | 未摘 |
| 跑一次 `make gac-local-gate` 后 | `M .omo/state/system.yaml`（单键 `health_score_evidence_generated_at` 时间戳） | B5 判据 1 当场不成立 |
| `git log --oneline -3 -- .omo/state/system.yaml` | 该文件被反复改写（47 commits/30d） | 决策 4 说的「生成态随文档 PR 漂移」仍在发生 |

`.gitignore` 的 `!.omo/state/system.yaml`（本轮实测在其上游**没有**任何 `.omo/state/*.yaml` 否定式，
`*.json` / `*.jsonl` 才是）⇒ 这条反选是**空操作**。所以「它仍被跟踪」不是反选救回来的，是
`git add` 的历史遗留；而摘库时**只删这行没有用**，必须补一条正向忽略，否则摘库后每个 fresh clone
都会多出 `?? .omo/state/system.yaml`，判据 1 从「M」变成「??」而已。

## 2 为什么不能直接 `git rm --cached`

BET-Y2Q4-T10-212 已把这条列为「先决条件不存在，另立 Phase 2b」。本轮把先决条件测实：

**(a) 没有任何脚本会创建这个文件。** 8 个写者全部是「存在才改、缺席即跳」：
`bin/compass_radar.py:1415`(`if not system_yaml.is_file(): … 跳过同步`)、
`bin/gac/evidence-smoke.py:244`、`bin/gac/harness-omo-bridge.py:193`、
`bin/gac/self-evolution-loop.py:246`、`bin/gac/unified-health-score.py:397`、
`projects/omo/src/omo/omo_state.py:322`(`⚠️ state/system.yaml not found`)、
`projects/omo/src/omo/omo_ingress.py:127`(`raise FileNotFoundError`)、
`projects/omo/src/omo/omo_audit_sync.py:585`(`ERROR: … not found`)。
全仓 `open(…, "w")` 命中该文件的只有 `evidence-smoke.py:250`（被 `:244` 守卫）与一个测试。
⇒ 摘库不是「移到 state 根」，是**把整块面板关黑**。

**(b) profile state 根今天就没有这块面板。** 实测
`~/.local/state/omostation/{prod,dev}/.omo/state/` **两个目录都不存在**。所以「声明 profile 后写面
落到 state 根」这件事对 system.yaml 是空的：`state_file_read()` 兜回检出那份，八个写者继续改
**检出**的跟踪文件（未声明 profile 时 `state_root()==code_root()`，逐字节写进检出）。

**(c) 摘库会让 CI 从绿变红 —— 而今天它是绿的。** 本轮用 `git archive origin/main | tar -x`
造了个 fresh 复刻（纯跟踪文件，无 symlink，与 CI checkout 同形）实测：

| 状态 | `current-state-coherence.py --root <复刻>` 读数 | rc |
|---|---|---|
| 复刻含跟踪的 `system.yaml`（= 今天的 CI） | `active phase=29 wave=W1 active=1 planned=0 blocked=0` | **0** |
| 复刻删掉该文件（= `git rm --cached` 之后） | `missing input: …/.omo/state/system.yaml` | **2** |
| 删除后先跑物化器再检 | `active phase=29 wave=W1 active=1 planned=0 blocked=0` | **0** |

`:35-36` 对缺失输入抛 `CoherenceInputError`、`:281-283` 返回 rc 2；`.github/workflows/state-goals-enforce.yml:28`
（该行就是整个文件的最后一步）直接调用它，且该 workflow 刻意 `submodules: false`（`:23`，注释 `:21-22`：递归检出会撞
private 子模块）。它**没有 `on.paths` 过滤**（`on:` 段只有 `push.branches: [main]` 与裸 `pull_request:`，`:7-10`）
⇒ 任何 PR 都会跑这条检查，摘库的影响面是全量 PR 而不是个别路径。
⇒ 危险不是「CI 已经红着」，而是**摘库这一刀会自己把绿的 CI 砍红**，所以 §5 第 2 条（在该步骤之前物化一次）
不是锦上添花，是摘库的前置。第 3 行就是它的全部补偿动作：物化后 rc 逐字节回到今天的水位。

**唯一消费它的硬 CI 步骤就是这一条**（全量扫 `.github/workflows/` 所得）：
`c2g-radar-daily.yml:39` 与 `gac-gate.yml:272` 是**写方**且非阻塞；`projects/omo/tests/` 里提到该路径的
用例全部用 `tmp_path` 或只断言文档字符串（`projects/omo/tests/test_worker_mechanism_consistency.py:148`、
`projects/omo/tests/test_omo_governance.py:72`），**不读主仓真文件**。

## 3 契约：创建者必须只靠已提交真源、且值可复算

创建者的输入面与判据都取自仓库里已存在的真源，实测逐键对拍（判据是**同一棵树上派生值 == 该树读数**，
不是「== 本机看到的值」—— 理由见 §3.1）：

| 键 | 真源 | 实测对拍 |
|---|---|---|
| `current_phase` / `current_wave` | `.omo/goals/current.yaml` 的 `phase` / `current_wave` | `29` / `W1` == 该树 `system.yaml` 值 |
| `active_tasks` / `planned_tasks` / `blocked_tasks` / `completed_tasks` / `total_tasks` | `.omo/tasks/{active,planned,blocked}/` + `tasks/done` + `tasks/archived/done` 的 `*.yaml` 计数 | 与 `current-state-coherence.py:_task_counts` **同一棵树同组数**（复刻实测 `1 / 0 / 0 / 303 / 304`） |
| `next_active_tasks` / `next_planned_tasks` | 同目录文件（`stem (title)` 行） | — |
| `updated_at` | 物化时刻（UTC，`…Z`） | — |
| 其余 13 键（`health_score*` / `runtime_health_summary` / `workflow_mesh_health` / `governance_*` / `harness` / `self_evolution` / `service_online_ratio` / `governance_feedback_last_run`） | 各生成者所有；物化器给**该键的空形** | — |

### 3.1 派生是**树相对**的，不是本机对拍（本轮原型阶段纠正的两条）

**(i) 上游任务面本身部分被 gitignore。** 实测 `git check-ignore -v`：
`.gitignore:391` 忽略 `.omo/tasks/done/`、`:392` 忽略 `.omo/tasks/planned/`（这两行原为 `:388/:389`，本轮
§5 第 3 条在 `.gitignore` 新增 3 行注释后下移 —— 路径字面量才是锚，行号只作辅助）。于是同一份代码在三棵树上数出三组数：

| 树 | active | planned | blocked | done + archived/done | total |
|---|---|---|---|---|---|
| `origin/main` 的 fresh 复刻（= CI） | 1 | 0（目录不存在） | 0 | 13 + 290 = 303 | 304 |
| 本机主工作区 `/Users/xiamingxing/Workspace`（活运行态） | 3 | 6 | 0 | 41 + 290 = 331 | 340 |
| 本轮 worktree 检出 | 1 | 0（目录不存在） | 0 | 13 + 290 = 303 | 304 |

⇒ **判据只能写成「物化值 == 同一棵树 `_task_counts` 的值」，不能写成「== 某组绝对数字」**。
把 `3 / 6 / 331 / 340` 抄进契约或用例，就是 AGENTS.md §7② 那类「fixture 写绝对值 × 断言用相对量」的
时钟炸弹换皮（此处换成 host 炸弹）：它在别的机器上必红，且形状与真回归无法用眼景区分。
已提交的那份 `system.yaml` 与 fresh 复刻逐键一致（`1/0/0/303/304`）⇒ 今天 CI 的自洽**不是巧合**，
是「跟踪的投影恰好跟踪了它对应的跟踪真源子集」，摘库后由物化器把这层自洽变成构造保证。

**(ii) `.omo/goals/current.yaml` 是双文档 YAML**（frontmatter doc + `---` body doc；`phase`/`current_wave`
在**第二个**文档里）。原型第一版用 `yaml.safe_load` 直接 `ComposerError: expected a single document`，
被这条绊倒。物化器必须沿用仓内既有约定 —— `current-state-coherence.py:_merged_yaml`（`:44-48`，
`safe_load_all` + 逐文档 `update`）。同理 `runtime-projections.yaml` / `write-owners.yaml` 的读取口径。

四条硬约束：

- **I1 键集合 == 声明集合（钉成集合相等）。** `bin/gac/omo-state-write-guard.py:check_field_ownership()`
  对 `present` vs `write-owners.yaml` 声明做**双向**检查（`:181` undeclared-key、`:200-206`
  **ghost-declaration**，两者都进 `findings` ⇒ 非 0 退出）。所以物化器不得少写声明过的键，也不得多写；
  判据 = 物化器输出的 top-level 键集合与 `.omo/_truth/registry/write-owners.yaml` 里
  `fields['.omo/state/system.yaml']` 的键集合**相等**。
- **I2 落点在调用时刻的 state 根。** 写路径一律 `repo_root.state_root()` 现取（AGENTS.md §7
  「写路径要在调用时刻解析」），且**只在物化时**创建目录；未声明 profile 时 `state_root()==code_root()`，
  与历史布局逐字节一致。**并且该落点必须与 omo 内核的写目标逐字节相等** —— 本轮实测：
  `repo_root.state_root()/.omo/state/system.yaml` == `omo.omo_paths.STATE_SYSTEM_YAML`
  （`STATE_DIR` 即由 `STATE_ROOT` 派生，`projects/omo/src/omo/omo_paths.py:97` + `:102`），
  未声明 profile 与 `OMOSTATION_STATE_ROOT=/tmp/profileroot` 两种模式下均相等。
  这条等式是 §8「不动 omo 侧写者」得以成立的**唯一依据**：摘库后 `omo_workspace.py:44`、
  `omo_audit_sync.py:584`、`omo state sync-tasks` 全在 state 根那份上增量维护，
  物化器若落在别处，就是造第二个身份而不是补缺失。
- **I3 幂等且不覆盖。** 目标已存在 ⇒ 退出码 0 + `skipped`，绝不改写现有字节（生产机上那份是活的运行态，
  8 个写者正在增量维护它）。要重算必须显式 `--force`。
- **I4 原子。** 临时文件 + `os.replace`，读者不可能读到半份（与 `state_dir_write()` 那条「不许写半份镜像」
  同族纪律）。

## 4 为什么走 `state_file_read`，不在本轮注册 canonical 改名

`repo_root.py:204-220` 的 `state_file_read()` 文档串**自己点名**这一类：「它是同一个文件的
『最后提交快照 + 运行态镜像』（.omo/state/system.yaml 这一类）」，且明确它与 `projection_read()` 的
区别是「没有 canonical/legacy 两个名字」。`runtime-projections.yaml:87-93` 那段注释掉的
`system_projection` 占位（canonical `.omo/state/runtime/system.yaml`）是**未采纳的将来项**，理由本轮实测：

1. `bin/gac/omo-state-projection-guard.py:87-110` 要求**注册为 `state: active` 的 canonical 路径必须存在且可解析**，
   fresh CI 检出上 `.omo/state/runtime/*` 被 `.gitignore:281` 忽略 ⇒ 注册即造红（T10-230 的
   `circuit_breaker` 已因此拒绝过注册）。
2. 改名要同时动 omo 侧 `omo_paths.STATE_SYSTEM_YAML` / `find_omo_dir()` 系与
   `omo-state-write-guard.py:33`（现读 `state_root()/.omo/state/system.yaml`）⇒ 写面出现两个身份。

本轮因此**沿用**已落地的 ADR-0456 接缝（`state_file_read` / `runtime_state_root`），把「创建者 + 摘库」
做实；canonical 改名若要发生，须先解掉上面两条，属另一条 BET，不在这里偷偷做也不假装完成。

## 5 摘库面（与创建者同批，缺一即回归）

1. `bin/gac/materialize-system-state.py`（新，仅 stdlib + pyyaml，无子模块无网络依赖）。
2. `state-goals-enforce.yml` 在 `:28` 之前物化一次 ⇒ 「缺失」重新变成真错误而不是新检出的常态。
3. `git rm --cached .omo/state/system.yaml` + `.gitignore` 加正向忽略、删该行死反选。
4. 把仍钉检出根的读者/写者接进 `state_file_read`（消费面实测见 §6）。
5. `tests/unit/test_system_yaml_materializer.py`：I1–I4 各一条 + **正向落点断言**（AGENTS.md §7：
   每条「移走某个写目标」的契约都要配一条正向落点断言，且先跑一次再写进契约）。
6. **把该用例接进 CI，否则第 5 条只是本地证据**：`.github/workflows/governance-check.yml` 的
   `governance-verify` job 用**显式文件白名单**跑 pytest（`:118-127` 那组在 `projects/omo` 下，
   `:189` 与 `:193` 是 root 侧两条），`tests/unit/**` 默认**永不被 CI 执行** —— 该文件 `:191-192`
   自己写明了这条边界，并给出先例（T10-232 为此新增了 `:193` 那一步）。本轮按同一形状加一步
   `python3 -m pytest tests/unit/test_system_yaml_materializer.py -q`（命名沿用 `ADR-0456 B5 …` 前缀）。
   判据：验收-5 的「pytest 全绿」必须同时有 CI 步骤号可指认，否则不成立。

## 6 消费面（实测清单，非估计）

全仓 `state/system.yaml` 命中 177 处 / ~40 文件。**已经是接缝**（不动）：
`bin/compass_radar.py:1145`、`bin/mof/generate-brief.py:26`、`bin/gac/evidence-smoke.py:224`、
`bin/gac/harness-omo-bridge.py:46`、`bin/gac/self-evolution-loop.py:42`、
`bin/gac/unified-health-score.py:396`（`runtime_state_root()`）、
`bin/gac/{governance-convergence-lint:133,governance-alert-dispatch:54,check-project-health-freshness:21,
harness-omo-bridge:94,state-freshness-check,omo-state-write-guard:33}`（`state_file_read`/`state_root`）、
`bin/ssot/current-state-coherence.py:173`。

**仍钉检出根**（本轮接入）：`bin/meta/compass_radar.py:1079`（注意它是 `bin/compass_radar.py` 的
第二份拷贝 —— T10-220 把接缝装到了前者，这份漏了）、`bin/arch-health-meter.py:142`、
`bin/check_health_ssot.py:83`、`bin/panorama/panorama-collect.py:4511`（`state_path = CODE_ROOT / ".omo" / "state" / "system.yaml"`）、
`bin/ssot/ssot-guardian.py:44`、`bin/gac/architecture-check.py:47`、`bin/gac/session-recovery.py:40`、`bin/ssot-watcher.py:59`、
`bin/gac/m1-closeout-report.py:137`、`bin/gac/{check-silent-loss:28,check-dual-track-purity:32,
check-adversarial-effectiveness:29}`（这三件读的是 `collab-dualtrack.yaml`，见 §8 非目标）。

清点方法（本轮踩到后修正）：行号一律用 `git show origin/main:<path>` 取该行内容复核；
**子模块内路径不适用此法** —— `git show origin/main:projects/omo/src/omo/omo_paths.py` 返回空串
而非报错（父仓无法穿进 gitlink），会伪装成「该行不存在」。子模块侧改用
`git -C projects/omo rev-parse HEAD` 与 `git ls-tree origin/main projects/omo` 比对 gitlink
（本轮实测二者同为 `8f5c0524`，故直接读工作树即等于读在案提交）。

**指针审计的复跑结果**（基线已从 `d8135e8c8` 前进到 `94a76ce0d`，本文全部 40 个 `path:line` 重跑一遍）：
根侧 31 个逐行命中、子模块侧 8 个在 gitlink `8f5c0524` 上命中，其中 2 个此前**写法不完整**
（`test_worker_mechanism_consistency.py` / `test_omo_governance.py` 实际在 `projects/omo/tests/` 而非 `tests/unit/`），
另有 1 处行号写错（`submodules: false` 在 `:23` 而非 `:24`，注释在 `:21-22`）—— 三处均已就地订正。
⚠️ 审计装置自己也会造假阴性：我的解析器初版把 `.yml` 排除在「按整路径直查」之外，于是把**确实存在**的
`state-goals-enforce.yml` 报成 MISSING。**纪律**：任何「路径不存在 / 行不存在」的结论，先怀疑解析器的
匹配规则，再怀疑仓库 —— 与 §7 里「检测器须自证」「判据不得与被验对象共享失效模式」同族。

## 7 验收（逐条可跑）

1. `python3 bin/gac/materialize-system-state.py --dry-run --json` 的 `key_set_equals_declared == true`
   （23 == 23，实测集合相等），且 `derived` 的五个计数等于**同一棵树**上
   `current-state-coherence.py:_task_counts` 的读数 —— **断言是树相对的**，不得写死 §3.1 表里任何一组数字。
2. `OMOSTATION_STATE_ROOT=<tmp> python3 bin/gac/materialize-system-state.py --json` 后
   `<tmp>/.omo/state/system.yaml` 存在，且 `<checkout>/.omo/state/system.yaml` 逐字节未变。
   判据要分两段：**摘库前**用 `git diff` 证明未变，**摘库后**该文件不再被跟踪、`git diff` 对它恒为空
   （否定式判据就此失效），必须改跑 `shasum -a 256` 前后比对。
3. 二次运行同一命令 ⇒ `status == skipped` 且文件 mtime/字节不变（I3，本轮原型已实测：
   `status: skipped` + sha256 与 mtime 双不变）。
4. **fresh 复刻三段式**（本 BET 的核心可复算判据）：复刻必须用 `git archive origin/main | tar -x` 造，
   **不许用 symlink 拼树** —— symlink 复刻会让 `bin/ssot/scene-card-candidates.py:_relative_ref`
   抛 `ValueError: '…' is not in the subpath of '…'`（本轮实测踩到），那是装置噪声不是产品行为。
   ① 复刻原样：`current-state-coherence.py --root <复刻>` rc **0**；② 删掉复刻里的该文件：rc **2** +
   `missing input`；③ 物化后再检：rc **0** 且读数与 ① 逐字段相同。
5. `python3 bin/gac/omo-state-write-guard.py --json` 对着复刻（`OMOSTATION_STATE_ROOT=<复刻>`）报
   `declared: 23 / present: 23` 且 `undeclared-key / ghost-declaration / unresolvable-owner` **三项全 0**
   （本轮原型已实测该三条）。
6. `git ls-files .omo/state/system.yaml` 为空，且 `git status --short .omo/state` 为空；
   在摘库后的检出里跑一次 `make gac-local-gate` 仍为空（B5 判据 1 的字面成立）。
7. `python3 -m pytest tests/unit/test_system_yaml_materializer.py tests/unit/test_projection_reader_resolution.py
   tests/unit/test_system_yaml_write_plane.py -q` 全绿，**且** `tests/unit/test_system_yaml_materializer.py`
   被 `.github/workflows/governance-check.yml` 显式点名（§5 第 6 条）。指认命令：
   `git grep -n test_system_yaml_materializer -- .github/workflows/` 必须命中该文件的一行 pytest 调用。
   理由：`tests/unit/**` 不在任何 CI 白名单里（该文件 `:191-192` 自证），本地全绿不构成交付证据。

### 7.1 空形取值的实测依据（13 个生成者所有的键）

物化器给这 13 键的是**空形而非测量值**：标量给 `null`，`runtime_health_summary` /
`workflow_mesh_health` / `harness` / `self_evolution` 给 `{}`。依据两条：

- `null` 而不是 `0`：AGENTS.md/`bin/gac/unified-health-score.py:259` 记着同一个病 ——
  「一个从未测量被记成了一个分数」。写 `0` 会让 `check-project-health-freshness` /
  `governance-convergence-lint` 的 R-GOV 系把「没人测过」读成「测了，是零分」。
- 空形不额外破任何在接线上的消费者：实测 `bin/check_health_ssot.py` 对着物化产物报
  `system.yaml 缺 health_score_ref 字段`，而它对着**今天的活文件与跟踪文件逐字相同地报同一条**
  （该键既不在 `write-owners.yaml` 声明集合里、也不在文件里），且 `check_health_ssot`
  在 `.github/workflows/`、`Makefile`、`gac-local-gate.py`、`governance-checks.yaml` **零命中**
  ⇒ 它是孤儿检查器的预存债，不是本轮引入的回归。
  **纪律**：不得为了让它变绿而往物化器里加 `health_score_ref` 键 —— 那会当场造 ghost/undeclared
  并破 I1。该检查器另立 BET（要么改判据、要么正式声明该键并补写者）。

## 8 非目标

- **不修 `bin/check_health_ssot.py` 的 `health_score_ref` 期望**，也不为它加键（理由与纪律见 §7.1）。
  顺带登记两条同源事实：该检查器在全仓门禁/CI **零接线**；`.omo/tasks/done/`、`.omo/tasks/planned/`
  被 `.gitignore:391/:392` 忽略 ⇒ 「任务面是 SSOT」这句话只在活运行态成立，在 CI 检出上是**残缺面**
  （fresh 复刻数出 planned=0，活机器是 6）。本轮只保证物化与同树自洽，不假装修好这个口径分裂。

- 不改任何键的**语义与取值口径**，不碰 `health_score` 三口径判定（T10-220 已定），不改 R-GOV-2 分级。
- 不引入 `OMO_ALLOW_GIT_WRITE`（决策 3 属 B4b 批次 2，逐批授权）；不改 plist/cron 指向（B4b 批次 2+）。
- 不摘 `.omo/state/collab-dualtrack.yaml`。它本轮实测**自相矛盾**：
  `bin/gac/check-dual-track-purity.py:40` 自称「是 tracked 治理 SSOT，不是投影 —— 仍按固定路径读」，
  而 `bin/mof/generate-brief.py:342` 写明「数据源 …（`bin/collab/export-dualtrack.py` 产出）」——
  有产出者就不是 SSOT。该切分另立判据，不在本轮顺手摘（三个 `check-*` 门禁会当场报 not found）。
- 不做 canonical `.omo/state/runtime/system.yaml` 改名（理由见 §4，另立 BET）。
- 不动 `projects/omo` 侧写者（其 `system_yaml_for(omo_dir)` 已参数化；omo 侧 bump 仅在验收 5 实跑
  发现 omo 写者打不开 state 根时才作为同 BET 的第二条 PR，且需 re-pin 指针）。

## 9 交付实况（2026-10-07 实跑读数，非计划）

§5 六项同批落地，逐项可指认：

| §5 项 | 落点 | 实测 |
|---|---|---|
| 1 创建者 | `bin/gac/materialize-system-state.py`（stdlib + pyyaml） | `--dry-run --json` ⇒ `key_set_equals_declared: true`、`declared/present 23`、`undeclared/ghost` 空 |
| 2 CI 先物化 | `state-goals-enforce.yml:30`（物化）早于 `:31`（coherence） | 由 `test_enforce_workflow_materializes_before_the_check` 钉住「行必须是 `run:` 步骤行」—— 按首次命中会撞上 `:2/:4` 的注释 |
| 3 摘库 | `git rm --cached` + `.gitignore:297` 正向忽略，死反选 `!.omo/state/system.yaml` 删除 | `git ls-files` 空；`git check-ignore -v` 命中 `:297` |
| 4 读者接线 | 8 处改 `state_file_read` / `state_root` | `bin/meta/compass_radar.py`（新增 `_system_yaml()`）、`bin/arch-health-meter.py`、`bin/check_health_ssot.py`、`bin/gac/session-recovery.py`、`bin/ssot-watcher.py`、`bin/gac/m1-closeout-report.py`（2 站点）、`bin/ssot/ssot-guardian.py`（常量 → `system_yaml_path()`）、`bin/panorama/panorama-collect.py` |
| 5 用例 | `tests/unit/test_system_yaml_materializer.py` 26 条 | I1–I4 + 8 条读者落点，全绿 |
| 6 CI 点名 | `governance-check.yml:196` | `test_unit_suite_is_named_by_ci` 反向钉住该命名 |

**§6 的检测器盲区已就地补掉。** 旧判据只匹配尾段 `.omo/state/system.yaml`，看不见
`OMO_DIR / "state" / "system.yaml`（根变量已含 `.omo`）—— `bin/ssot/ssot-guardian.py:44` 正是这一形，
所以 §6 列 9 处而允许清单只有 6 处非归档项。本轮把尾段放宽到 `state/system.yaml`，同时豁免
`Path(".omo") / "state" / "system.yaml"` 这类**不带根的相对路径常量**（创建者自己就是这一形），
并按 §7「检测器须自证」补两条用例：`test_checkout_pinned_detector_fires_on_both_pinned_shapes`
（两种钉死写法都要命中）与 `test_checkout_pinned_detector_does_not_fire_on_seam_or_relative_constant`
（接缝、`state_root()`、相对常量三种都不许命中）。允许清单随之从 8 条收敛到 3 条
（两份归档 + `architecture-check.py`）。

**`bin/gac/architecture-check.py:47` 不接线，是裁决不是遗漏。** `CORE_DOCS` 这个 dict 全仓零消费者
（`CORE_DOCS` 只在自身文件出现），而 T10-220 的在案 spec 已写明「⛔ 该 dict 本身零消费者 → 留着,
不为其造判据」。为死码造落点断言会把「判据数量」变成装饰。允许清单里那条的理由已补上此出处。

**I2 的复测必须用 fresh 子进程。** 本轮第一次实测得到 `equal=False`，原因是我在**同一进程**里先
`import omo.omo_paths`（import 时刻求值）再设 `OMOSTATION_STATE_ROOT` —— 那份常量冻结在旧根上，
量到的是探针的错，不是产品的错。改成一模式一个子进程后两种模式都 `equal=True`
（未声明 profile 落到检出、声明后落到 `<state root>/.omo/state/system.yaml`，且该目录不存在时
创建者 `mkdir(parents=True)` 补上）。这正是 AGENTS.md §7「写路径要在调用时刻解析」那条的同源复发,
**测量装置也会犯它被测量对象的错** —— 判据类实测一律 subprocess 隔离。

**§7 三段式（`git archive HEAD | tar -x` 复刻, 非 symlink 拼树）实测**：① 原样 rc **0**，
跟踪快照派生 `29 / W1 / 1 / 0 / 0 / 303 / 304`；② 删文件 rc **2** +
`missing input: …/.omo/state/system.yaml`；③ 物化后 rc **0**，派生读数与 ① **逐字段相同**、
`write-guard` 报 `declared: 23 / present: 23` 且 `undeclared-key / ghost-declaration / unresolvable-owner`
三项 0。二次运行同一命令 ⇒ `status: skipped`、sha256 与 mtime 双不变。
隔离 profile（`OMOSTATION_STATE_ROOT=<tmp>`）⇒ 落点在 `<tmp>/.omo/state/system.yaml`，
检出那份 sha 逐字节未变。

**顺带登记一条与本轮无关的陈旧文档**：`spaces/AGENTS.md:59` 与
`.omo/standards/agent-mutation-protocol.md:53` 都称 pre-commit 跑 `ssot-guardian`，实测
`.githooks/` 与 `.github/` 对它**零接线** —— 它是 crontab（`crontab.new:134`）与手工 `make ssot-guardian`
的通道。据此本轮给它的缺失分支补了可执行措辞（打印落点路径 + 物化器命令）而不是让它静默 rc 2，
因为摘库后「文件不在」第一次成为合法状态。接线面收敛属另一条 BET。

**摘库这一刀自己也让行号指针变陈旧 —— 复算记录（AGENTS.md §7⑥）**：本轮 §5 第 3 条给 `.gitignore` 加了
3 行注释，`tasks/done` 与 `tasks/planned` 从 `:388/:389` 下移到 **`:391/:392`**（已订正本文 §3.1 与 §8
两处）。但订正时发现漂移有**两个独立来源**：AGENTS.md 那条 bullet 引的 `!.omo/state/system.yaml`
写作 `:294`，基线实为 **`:295`**；`health.yaml` 写作 `:411`，基线实为 **`:412`** —— 两处**在本轮之前就已经
off-by-one**，与本轮的 +3 无关。判据：订正行号要 `git show origin/main:<path>` 与当前树**各取一次**，
否则会把「上一轮遗留的陈旧读数」误记成「本轮交付造成的漂移」，下轮又照着错基线推。同一条 bullet 里
`test_system_yaml_write_plane.py:254/:293/:296` 三个指针也确实被本轮改掉了（允许清单 8→3、抽出
`_is_checkout_pinned_source`），已换成**符号名优先 + 现行号**：`_path_segments`（`:252`）、
`test_checkout_pinned_system_yaml_sites_are_the_reviewed_list`（`:322`，断言 `:324`）、
`test_allowlist_reasons_point_at_real_files`（`:327`）。

**AGENTS.md §7「扫源码的门禁」新增第 ⑧ 类形状**：「实测集合 ⊋ 允许清单」时**先怀疑检测器的匹配规则，
而不是给多出来的项造豁免** —— 记下本轮漏认的两种字面量形状（`OMO_DIR / "state" / "system.yaml"` 尾段不含
`.omo`、`ROOT / var` 尾段是变量名），以及「检测器少认 ⇒ 实测集合恰好等于按旧读数写下的清单 ⇒『清单相等』
这条绿是同一个 bug 的自证」。

**台账 `write_surfaces` 与交付面不同步，必须在 claim 之前补定**：条目原列 **18** 项，交付面实测也是 **18** 项
（`git status --short` 逐条数，摘掉自造的 scratch `runtime/affected/` 之后）—— **总数相等而集合不等**，
按总数对拍会直接放过它。双向差集：交付面有 **4** 项没登记 —— `AGENTS.md`、`bin/panorama/panorama-collect.py`、
`tests/unit/test_system_yaml_write_plane.py`、`.omo/state/system.yaml`（本轮 staged 删除）；补齐后 **22** 项。⚠️ 补列时**按记忆下手会造出重复项**：本轮把已在清单里的
`bin/gac/m1-closeout-report.py` 又加了一次，`yaml.safe_load` 对**列表重复项**与对重复键一样静默
（AGENTS.md §7「六类静默失效」①的列表面），于是总数从 22 变 23 而**没有任何检查会红**，我自己还把它当真值写进了本段。
**判据**：改完打三次读数 —— `len(ws)`、`collections.Counter(ws)` 里 value>1 的项、与交付面的**双向差集**各一次；
只看总数会把 23 读成「补好了」，实际是「补错了」。反向多列而未动的有 4 项（`bin/lib/repo_root.py`、`Makefile`、
`bin/gac/architecture-check.py`、`bin/gac/state-freshness-check.py`）。判据出处
`projects/omo/src/omo/workflow/claims_authority.py:842-845`：`set(requested_paths) ⊆ set(write_surfaces)`
是**逐字面**比较，无 glob、无目录前缀匹配 ⇒ 少列一项则该路径 claim 不进来；多列没有任何检查会红
（所以漏列是唯一会咬人的方向）。`write_surfaces` 进 packet 投影而 `refresh-packet`
要求台账**已在 `origin/main`**（新建 BET 首轮用不上），故顺序按 AGENTS.md 纪律走
**台账定稿 scope → `start` → `claim`**，不在 start 之后改投影字段。

**撞号：本 BET 由 `BET-Y2Q4-T10-234` 改铸为 `BET-Y2Q4-T10-235`。** `git fetch` 后实测 `origin/main` 已有
`0cdcf4a4a`（PR **#4670**，标题正是「BET-Y2Q4-T10-234 closeout」）—— 干的是**另一件事**：MOS 观测缝门禁
（代码在 #4668 / kairon #98），它的 spec frontmatter 把 `bet_id` 由 233 改成 234，并落了
`.omo/_knowledge/retros/BET-Y2Q4-T10-234.md`，其**台账条目因同一把 ledger 路径锁尚未插入**。于是 234 在 main 上已被
**纸面占用**，而我这条从未提交过。处置按 #4670 自己立下的先例（233 被占 → 顺延 234）顺延到下一个空号 **235**，
判据是两侧都数：`git grep` 在 main 上 234 命中 spec/retro，235 在 main 的台账、路径名、spec/retro 里**零命中**。
改铸**实测落点 12 处 / 8 个文件**（台账 `- id:` 与 `decision_ref` 2 处、spec `bet_id` 与正文 2 处、
`.gitignore` 注释、`state-goals-enforce.yml:28` 注释、`tests/unit/test_system_yaml_materializer.py:5` 头注释、
AGENTS.md 3 处、`tests/unit/test_system_yaml_write_plane.py`、`.github/workflows/governance-check.yml`），
每处先断言**该文件在 main 上 234 命中数为 0** 再替换 —— 否则会把别人那条线的引用一起改掉。
**首轮只改了 6 处 / 4 个文件，两处测量装置各自漏了一半**：① `git grep -n T10-235` 报 9 处 / 6 文件，
**结构上看不见新建未跟踪件**（spec 与本体的 2 处、`test_system_yaml_materializer.py` 的 1 处），
补数只能用 `git ls-files` + `--others --exclude-standard` 并集逐文件 `read_text().count()`；
② 另有 3 处引用是**在改铸之后写进去的**（AGENTS.md 第 ⑧ 类、governance-check.yml 的 pytest 点名注释、
写面用例的 docstring）—— 新写判据时抄的是当时的旧号。**判据**：改号后必以 filesystem-scan 复算，
且残留的 234 要**逐条确认每一处都是「叙述历史」而非「引用本 BET」**（本轮 3 处全在 spec 撞号段内，合法）。**连带代价**：
`start` 把 packet 快照（`bet_id` / `decision_ref` / `packet_id` / 台账 goal 全文）写进 run 记录，改号后那份快照
指向的是**别人的 BET**，而 closeout 的 `missing_bet_binding` 校验读的就是它 ⇒ 只能 `close` 旧 run
（实测其记录为 `locks` 19 条 = 17 条 path 锁 + `project` / `root-gate` 两条 lane 锁，`claims` 17 条）
以 235 重新 `start` + 重新 claim（锁须由新 run 自己持有，手改 run yaml 蒙混会留下锁主与 run 不一致的状态）。
**旧 run 从没 claim 到 `docs/plans/3y-bet-ledger.yaml`**（那把锁当时在并发 run 手里），新 run 补 claim 后才凑齐
**18 条 path 锁** —— 与交付面逐条相等，判据：枚举 `locks/*.yaml` 里 `run_id` 等于新 run 的 path 锁，
与 `git status --short` 的交付路径（摘掉 scratch）做双向差集，两侧都应为空。
**纪律**：`start --bet` 之前先 `git fetch origin main` 并 `git grep` 该号占用面 —— **台账条目未插入 ≠ 号码空闲**，
spec/retro 里的 `bet_id` 同样是占用。
**hermetic 复跑的装置本身有一面会让人误读成回归（2026-10-07, 本轮实测）**：AGENTS.md §7「门禁的探测代码
自己也读 host」要求源码扫描类用例除最小依赖 venv 外还要在 `HOME=<空目录>` + `env -u OMOSTATION_ROOT` 下再跑一次。
本机照做时 `HOME=$tmp python3 -m pytest …` 直接 `No module named pytest` —— 因为 **`HOME=<空目录>` 会连带摘掉
装在 user-site（`~/Library/Python/3.14/...`）里的 pytest**，宿主解释器因此没有依赖面。换绝对路径二进制
`/opt/homebrew/bin/python3` 同样失败（同一个 user-site）。**判据**：hermetic 复跑必须把**依赖面与 host 面分开供给**
—— 依赖由 venv 给、host 面清空：`env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB
HOME=<空> UV_CACHE_DIR=<空> uv run --no-project --with pytest --with pyyaml python -m pytest
tests/unit/test_system_yaml_materializer.py tests/unit/test_projection_reader_resolution.py
tests/unit/test_system_yaml_write_plane.py tests/unit/test_repo_root_profile.py -q -p no:randomly`
⇒ **933 passed**（与正常 HOME 下同一读数）。**纪律**：跑出 `No module named pytest` 时先疑装置，
不要把它记成「用例在干净 host 面上红」—— 那是测量工具缺依赖，不是写面回归。

## 10 第二次交付实况：五处红指向同一件事 —— 读者比创建者先跑（2026-10-07 实跑读数）

第一次交付（`1a27f4e45`）把文件摘出库并放上创建者，PR **#4671** 的 CI 当场 5 处红。逐条复现后，
它们**没有一条**指向「摘库这个动作错了」，全部指向同一件事：**读者先于创建者执行，或创建者没被登记**。

| # | 红 | 实测报错（干净复刻里逐字复现） | 本轮处置（只允许「补创建者」这一侧） |
|---|---|---|---|
| 1 | `architecture-check --gate` | `核心文档缺失: .omo/state/system.yaml (声明于 core_documents.STATE.md)` | 在 gate 步骤之前插创建者 |
| 2 | `doc-link-check` | `README.md:51/:144: broken link .omo/state/system.yaml` | 同上（strict `gac-gate.yml` 面也补一步） |
| 3 | `current-state-coherence` | `missing input: …/.omo/state/system.yaml` ⇒ **rc 2** | 第一次交付已接步骤，本轮补**登记面** |
| 4 | `script-registry validate` | `Missing registrations: 1` | 新增 `bin/_registry/scripts/governance/materialize-system-state.yaml` |
| 5 | `check-bin-quota-diff` | `新增 1 > 删除 0 + baseline_delta 0` | `script_baseline 715 → 716`（§7 计数链保持） |

**circuit_breaker 的边界是实测出来的，不是声明的**：判据只允许补创建者侧，因此本轮**没有**动任何读者的
判定语义 —— `architecture-check` 的 `core_documents` 存在性断言、`doc-link-check` 的链接目标解析、
`current-state-coherence` 的 `missing input ⇒ rc 2` 全部逐字保留，上面三条报错正是它们在干净复刻里
**仍然会报**的证据。反形状要说清代价：把 `system.yaml` 从 `core_documents` 删掉、或让 coherence
缺输入时返回 0，同样能让这 5 处「消」，但那删掉的恰好是 §2 论证「这份文件不能被直接摘库」的全部理由 ——
**红消失而判据同时失明，不是修复**。

**接线顺序判据**（新建 `tests/unit/test_system_yaml_consumer_inputs.py`，12 用例）：只吃 YAML 解析后的
`run:` 内容，按 **(步骤号, 步骤内字符偏移)** 比较 —— 同一步里 `python3 创建者 && python3 读者` 的链式写法
也是顺序，只比步骤号会把它误判成违规（本轮真实踩过并修）。实测三条 workflow 的落点（0-based，仅 `run:` 步）：
`gac-gate.yml` 创建者 `(19,8)` / `gac-local-gate.py` `(20,8)`；`architecture-check.yml` `(2,8)` / `(3,8)`；
`state-goals-enforce.yml` `(1,8)` / `(2,8)`。检测器按 §7「自证」纪律配正反两面：注入「缺创建者」与
「创建者排在读者之后」必须报违规，「顺序正确」「链式两侧各方向」「读者根本不在该 workflow」必须不报。

**登记六层里本轮补的两层，加一条最贵的静默形状**：
① `bin/_registry/scripts/governance/materialize-system-state.yaml` 新建后 `script-registry.py validate`
⇒ `VALIDATION PASSED: 716 scripts registered`（注意 `validate` **不接受 `--json`**；仓库里也**没有**
`bin/validate-script-registry.py`，按记忆找它只会撞上 §7⑤ 的 `fd` 别名）。
② `script_baseline 715 → 716`。⚠️ `check-bin-quota-diff.py::_get_baseline_delta` 读的是
`git show HEAD:` 与 `git show <base>:`，即**已提交的两棵树** ⇒ 工作树里的 bump 在 commit 之前对该检查
**不可见**（实测：commit 前 `baseline_delta=0` FAIL，commit 后 `added 1 / deleted 0 / delta 1 / ok true`）。
③ `ci-surfaces.yaml` 登记为 `workflow: architecture-check.yml` + `also_in: [gac-gate.yml, state-goals-enforce.yml]`
—— 只登记一条会造 `overlap` 违规，判据是 `{workflow} ∪ also_in ⊇ 实际执行它的全部 workflow`（第一次交付已在三条里都接了步骤）。
④ **本轮最贵的一处**：`note:` 写成裸多行标量且行内含 `: ` ⇒ `ScannerError`，而 `check-ci-surfaces.py` 的
`_load_yaml` **吞异常返回 `{}`**，整个登记面凭空消失，输出形态是 **129 条 `unregistered-check` error** ——
与「真漏登记 129 个检查」逐字同形。修法与固化见 AGENTS.md §7「扫源码的门禁」⑨；修好后的稳定读数
`ok true / errors 0 / warns 5 / surfaces 148 / registered 148 / wired 144`，并钉成
`test_registry_yaml_parses`（ci-surfaces 与 governance-checks 各解析一次）+ 登记用例里的 surfaces 非空断言。

**第 5 类读者是 Makefile，而它的失效形态是「打印四个空 grep」**：`make debt-check` 对
`.omo/state/system.yaml` 做 4 次 `grep`（`debt_weight` / `debt_health` / `resolved_count` / `unresolved_count`），
而 `write-owners.yaml` 为这份文件声明的 **23** 个键里**没有**这四项，`origin/main` 那份跟踪快照的 24 个顶层键里也没有 ⇒
该目标**永远「检查完成」而不给任何读数**（门禁成功 ≠ 门禁有用）。本轮改为经 `bin/lib/repo_root.py --json`
取**调用时刻**的 state 根，缺失时显式指路 `make state-materialize`，键不在声明面时明说「不是空 grep，去看
`.omo/debt/` 与 `make debt-audit`」。实跑读数：`读数根: <checkout>/.omo/state/system.yaml` + 四行如实说明。
入口新增 `make state-materialize` 而**不是**再加一个 bin 脚本 —— `bin/` 受净增配额约束（本表第 5 行），Makefile 不受限。

**判据-6 的干净复刻实跑**（`git archive HEAD | tar -x`：无 `.git`、无子模块内容、`.omo/state/system.yaml` 按摘库后形状不存在）：

| 阶段 | 读数 |
|---|---|
| 创建者**之前** | `doc-link-check` rc=1 / 15 broken（其中 3 行点名 `system.yaml`）；`architecture-check --gate` rc=1 / 1 错「核心文档缺失」；`current-state-coherence` **rc=2** `missing input` |
| 创建者 | `python3 bin/gac/materialize-system-state.py --json` rc=0，`status: materialized`、`key_count 23 == declared 23`、`key_set_equals_declared true`、落点即复刻的检出路径（CI 未声明 profile ⇒ §4 的 D1 不变量） |
| 创建者**之后** | 三份读者对 `system.yaml` 的抱怨 **0 行**；`architecture-check` 错误 0；`current-state-coherence` **rc=0**（`phase=29 wave=W1 active=1 …`） |

复刻里剩下 **12 条 broken link + 2 条 registry 警告全部指向未初始化的子模块内容**（`projects/{agora,ecos,omo}/…`，
逐条 `worktree=True / archive-replica=False`；`.gitmodules` 的 17 条 gitlink 被 `git archive` 结构性排除）⇒
那是**复刻装置的缺口，不是交付的缺口**。因此「0 broken links」这格判据必须在**子模块齐备**的树上取，本轮也取了
（同一棵 worktree，先把那份 1446 字节的现值备份并按 sha 还原）：

| 阶段 | 子模块齐备树上的读数 |
|---|---|
| 文件不在 | `doc-link-check` rc=1 / **17 broken，其中 16 行点名 `system.yaml`**（`ARCHITECTURE.md:21`、`LAYER-INDEX.md:15` …）；`architecture-check --gate` rc=1 / `❌ 核心文档缺失`；`current-state-coherence` **rc=2** `missing input` |
| 创建者 | rc=0，`status: materialized` |
| 创建者之后 | 三者 **rc=0** 且 `doc-link-check: PASS` **0 broken links**；`✅ Architecture Check 通过 (0 error, 0 warning)`；coherence `phase=29 wave=W1` |

**判据**：一条写「0 broken links」的判据，其装置必须**包含被链接的对象**；`git archive` 复刻能证明
「抱怨被创建者消掉」这一类，但**证不了**「总数为 0」⇒ 两种树各跑一次，缺一格就是空绿。

**B5 的两条判据本轮第一次同时成立**：跑完 `make gac-local-gate`（PASS，68 checks / 1 SOFT WARN = 本机无 KOS 库
runtime 产物）之后 `git status --short .omo/state` **为空**；`git check-ignore -v` 命中 `.gitignore:297`；
`git ls-files --error-unmatch` rc=1。分支自身改动面 `git diff --name-status d25b0dcee..HEAD` = **25 个文件**，
其中 `.omo/` 下只有一条**故意的 `D .omo/state/system.yaml`（摘库本体）**，无生成态夹带。⚠️ 用
`git diff --name-only origin/main..HEAD` 数会得到 34 并夹带 `D` 行 —— `origin/main` 已前进到 `5dbe543a6`，
两点式 diff 把上游新增显示为反向删除（AGENTS.md §7「生成态会被交付动作扫进 commit」那条同源的读数陷阱）。

**全量 `tests/unit` 与「预存红必须用基线复刻证明」**：`2033 passed / 11 failed`（575s）。这 11 条本轮不写成
「不是我引入的」，而是复现了基线：① 涉及的 5 个用例文件对本分支 diff 的 9 个关键词（`materialize-system-state` /
`ci-surfaces` / `governance-checks.yaml` / `gac-gate.yml` / `architecture-check.yml` / `governance-check.yml` /
`Makefile` / `T10-235` / `system.yaml`）命中 **0**；② 把**分支基线** `git archive d25b0dcee | tar -x` 到临时目录
跑同 5 个文件 ⇒ **FAILED 列表逐条 test id 与分支完全相同（11 failed）**，故为预存；③ 这些文件也不在
`governance-check.yml:118` 起的显式 pytest 白名单里（`tests/unit/**` 不被 CI 采集）⇒ 它们既不会让 CI 红，
**CI 绿也不构成它们的证据**，本轮因此把新建的两个用例文件都点名进步骤。
**纪律**：「预存」这一格只能用基线复刻复跑来填，叙述不算证据（AGENTS.md §7 ci-red-triage 的预存判定）。
