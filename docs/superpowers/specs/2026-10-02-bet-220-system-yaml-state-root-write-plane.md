---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-220 — system.yaml 写面收敛到 state_root 并拆掉 R-GOV-2 的同义反复
bet_id: BET-Y2Q4-T10-220
status: accepted
lifecycle: contract
last-reviewed: 2026-10-02
owner: governance-team
---

# system.yaml 写面收敛到 state_root 并拆掉 R-GOV-2 的同义反复

> ADR-0456 决策 4 / plan B5 的收尾。T10-219 把"谁写这个字段"变成门禁；本轮把**写者的根**
> 和**读者的根**收敛到同一处，使声明 profile 后的一次真实运行不再改写检出里那份跟踪文件。

## 1 问题（本轮实测，非推断）

在 `ws-t10-220-write-plane` 检出（干净）里声明 `OMOSTATION_STATE_ROOT=<tempdir>` 后跑
`omo state sync` 与 `sync-tasks`，两条都 rc=0。落点分两半：

**已经翻过去的** —— state 根里出现

```
.omo/state/system.yaml            # health_score_evidence: 100.0 + _source + _generated_at
.omo/state/runtime/health.yaml    # generated_at 2026-10-02T07:49:29Z
.omo/state/runtime/governance-data.json
.omo/state/runtime/brief.md
runtime/omo/_delivery/ingress/state/state-sync-2026-10-02T07-49-29Z.yaml
runtime/omo/change-log/mutations.jsonl
```

**仍钉在检出的** —— 同一次运行后 `git status --porcelain` 给出两行，且**只有一行落在
`.omo/state`**（plan B5 的判据路径）：

```
M .omo/state/system.yaml          # 唯一变化：updated_at '2026-09-27T08:22:42Z' → '2026-10-02T07:49:54Z'
M .omo/tasks/registry/INDEX.md    # 唯一变化：Updated: 那一行的日期
```

### 1.1 写者普查（`git grep` 构造式全扫，23 处命中逐条定性）

`.omo/state` 下全仓只剩 2 个跟踪文件：`system.yaml` 与 `collab-dualtrack.yaml`；后者无运行时写路径。
`system.yaml` 的写者按"根怎么取"分三类：

| 写者 | 根 | 键 | 本轮 |
|---|---|---|---|
| `projects/omo/src/omo/omo_ingress.py:124`（`write_system_projection_fields`）—— **真正落笔的那一处**，`omo_state.py:320`/`:474` 只是调用方 | `find_omo_dir()` = `OMO_ROOT`（检出派生） | 计数 + `updated_at`（sync-tasks 白名单） | ✅ 改 |
| `bin/compass_radar.py`（`sync_system_yaml`） | `ws_root = omo_dir.parent`（参数传入） | 复合分、anomaly、ratio、`runtime_health_summary`、`workflow_mesh_health` | ✅ 改 |
| `bin/gac/harness-omo-bridge.py`（`sync_harness_closeout`） | `WORKSPACE = __file__.parents[2]` | `harness` | ✅ 改 |
| `bin/gac/self-evolution-loop.py`（`sync_evolution_state`） | `REPO = __file__.parents[2]` | `self_evolution` | ✅ 改 |
| `bin/meta/compass_radar.py:1079` | 同参数传入 | 同上 | ⛔ 死副本，见 D6 |
| `projects/runtime/src/runtime/scheduler.py:518`（`OMO_STATE_FILE.parent/"system.yaml"`，根 = `__file__.parents[4]` `:22`） | 检出 | `runtime_health_summary`、`service_online_ratio`、`updated_at`、`governance_feedback_last_run` | ⛔ 见 D7 |
| `projects/omo/src/omo/omo_workspace.py:39` | **`STATE_SYSTEM_YAML`（已正确）** | `worktree_dirty_count` | 无需改 |
| `bin/gac/evidence-smoke.py:219`、`bin/gac/unified-health-score.py:396`、`bin/mof/generate-brief.py:22`、`bin/gac/omo-state-write-guard.py:30` | **`runtime_state_root()`（已正确）** | evidence 面 | 无需改 |

⚠️ **初稿的普查漏了一处，且漏的方向正好是最要紧的**：表里原本只列 `omo_state.py:320`/`:474`
（"根 = `omo_dir`"），实测那两处**不直接写文件** —— 它把 `updates` 交给
`omo_ingress.write_system_projection_fields()`，由后者 `system_path = omo_dir/"state"/"system.yaml"`
落笔并持锁。只改调用方会留下一份"看起来改完、实际仍写检出"的差集，而且 `cmd_state_set` 那条路径
根本不经过 `omo_state` 的那两行。本轮因此把**内核侧也收成一个共享解析器**
（`omo_paths.system_yaml_for()/system_yaml_read()`），改在写点而不是改在 caller。

所以这不是"缺机制"，是**机制已有四处在用、四处绕过**（`omo_paths.STATE_SYSTEM_YAML` 就在
`:69`，`evidence-smoke._system_yaml()` 就是范例）。

### 1.2 读者普查

`git grep 'system\.yaml'` 命中的读取侧，`WORKSPACE`/`REPO_ROOT`/`omo_dir` 拼检出的初稿记为 8 处。
**实测其中 2 处是死码**，判据按"活读者"写：

| 读者 | 接线 | 定性 |
|---|---|---|
| `governance-convergence-lint.py`、`check-project-health-freshness.py`、`current-state-coherence.py`、`governance-alert-dispatch.py`（2 站点） | ✅ ci-surfaces 有 `bin-…` 条目 | ✅ 改 |
| `quarterly-report.py`、`sema-distill.py` | ❌ 未接线 | ✅ 一并改（D4） |
| `doc-ssot-lint.py` 的 `SYSTEM_YAML` 常量 | — | ⛔ **全仓零消费者**（grep 只命中定义行）→ 删常量 |
| `architecture-check.py:47` 的 `CORE_DOCS["STATE.md"]` | — | ⛔ 该 dict 本身零消费者 → 留着，不为其造判据 |

死码第三类（本轮新识别，与前两类"幻影 source_ref / 声明未接线"并列）：**"常量定义了但没人读"**。
同一类还有 `harness-omo-bridge.py` 的 `OMO_TARGETS` 映射（本轮一并删）。它的危险在于会让普查
把"改造面"算多，进而写出一条永不成立的判据。

**本轮边界外的读者（实测残留，`bin/**/*.py` 全扫，逐条在册并由 C8 的测试钉住）**：
`bin/arch-health-meter.py:142`、`bin/check_health_ssot.py:83`、`bin/gac/m1-closeout-report.py:137/171`、
`bin/panorama/panorama-collect.py:4511`（显式 `CODE_ROOT`）+ 上述两处死码 + 两份 `bin/_archive/omo-health.py`。
全部是**读者**，不写 system.yaml —— 所以它们破坏的是"读到最新值"，不是"写坏检出"，
严重性与本轮判据（写面收敛）不同级，登记为后续面。

后果是活门禁读**上次提交的快照**，越跑越 stale（任务 #98 的 G9"freshness 首跑必绿"就是症状）。

⚠️ **一条判据初稿被实测否证**：`bin/gac/state-freshness-check.py` 曾在初稿的读者名单里。实测它的
`:52-53` 注释写明"配置型文件 (如 `system.yaml`) 是 source-of-truth 不带 generated_at，**不在本检查
范围**"，且 `STATE_FILES` 里根本没有 system.yaml —— 它不是读者。把它列进改造面 = 造一条永不成立的判据。

### 1.3 双口径（T10-219 留下的必须先定的判定）

`bin/compass_radar.py:1420-1421` 把自己的 `health_score` 复制进 `health_score_evidence` 并把
`_source` 写成 `"compass_radar (synced)"`，注释自称 "R-GOV-2 convergence"；
`bin/gac/evidence-smoke.py:242` 写的是它独立测出来的 evidence 分。同一个键两个语义、后写者赢。
实测两例读数：`origin/main@a0cbf446e` 跟踪态 `health_score=46` vs `health_score_evidence=100.0`
（source=evidence-smoke），刚跑完本地门禁的工作副本 `health_score=71` 而 R-GOV-2 报
`divergence 29.0 > 5`。

## 2 判定

- **D1 · 唯一运行态落点**。`system.yaml` 的运行时写入目标是且只是
  `<state_root>/.omo/state/system.yaml`。选它而不是新造 `.omo/state/runtime/system.yaml`：
  evidence-smoke（`:219`）、`omo_paths.STATE_SYSTEM_YAML`（`:69`）、T10-219 的写者守卫
  （`omo-state-write-guard.py:30`）三者已经取这一处，再加一处就是把写面重新分成两片。
  检出那份降级为**最后提交的快照**，只读 —— 所以它**继续 tracked**，CI 与无 profile 的机器靠它兜底。
- **D2 · R-GOV-2 拆同义反复**。删 `compass_radar.py:1420-1421` 的跨键复制，
  `health_score_evidence` / `_source` 归 `evidence-smoke.py` 独占（write-owners 的 `fields:` 段
  随之从两写者收成单写者，由 T10-219 的 `check_field_ownership` 钉）。R-GOV-2 阈值 5 与
  WARN-only 分级**不动**：实测 `governance-convergence-lint.py` 的 `errors` 恒空（`:163` 只
  append warning），所以诚实化只会让警告变真，不会把门禁变红。
- **D3 · 读者 = state 根优先、检出兜底**，经新加的 `repo_root.state_file_read(rel)`：
  与 `projection_read()` 同语义，但**不**把 `system.yaml` 注册成新投影 —— 它是同一个文件的
  "快照 + 运行态镜像"，不是 canonical/legacy 两个名字，注册进去会让 `projection_name_for()`
  把快照误判成 legacy 位。未声明 profile 时 `state_root()==code_root()`，解析恒等，
  与历史布局逐字节一致（`tests/unit/test_repo_root_profile.py` 的同一条不变量）。
  - **D3a · 探 state 根的前提是 env 真的被声明**。`state_file_read` 初稿无条件探
    `state_root()`，实测会把**隔离夹具劫持**到 host 那份文件上 —— 传给 `root=` 的 tmp 检出与
    `state_root()`（未声明时 = 真实检出）本就是两个不同目录，任何 `state_file_read(rel, root=tmp)`
    都会读到 host 的 `.omo/state/system.yaml`。现判据是 `os.environ.get(STATE_ROOT_ENV)` 为假时
    直接返回 `base / relative`，并由 `test_state_file_read_never_hijacks_a_foreign_checkout` 钉住。
    这不是简化，是"能在指定根上验证写到哪"的前提。
  - **D3b · 文件级偏好安全，因为不存在半份镜像**（实测不变量，不是假设）：所有写者对
    state 根缺失的文件都是**跳过或抛错** —— `compass_radar`/`harness-bridge`/
    `self-evolution-loop`/`evidence-smoke` 跳过，`cmd_state_set` 报错，
    `write_system_projection_fields` 抛 `FileNotFoundError`，`sync_state_projection._system_payload`
    抛 `TypeError`。所以 state 根那份一旦出现就是**全集**，读者按整文件偏好读它不会读到缺字段的
    "新"状态。`harness-omo-bridge.sync_harness_closeout` 本轮据此补了 skip-if-absent（它原本会
    凭空造一份只含 `harness` 键的镜像，正好违反这条不变量）。
- **D4 · 8 个读点一起移**（§1.2 全列，含 2 个未接线的），使"检出根拼 system.yaml"在
  `bin/` 里成为**可 grep 清零**的形态，而不是"接线的那几个改了"。
- **D5 · tasks 面那一行不在本轮**。`.omo/tasks/registry/INDEX.md` 的 `Updated:` 也会脏，但
  `.omo/tasks/**` 是**任务真源**、INDEX 是其派生缓存且**按设计跟踪**（`omo_state.py:220-223`
  写明搬它的动机是根治指针漂移）。把它挪进 state 根会让检出的 tracked 缓存永不更新，
  正好复活它当初要治的病。plan B5 的判据路径是 `.omo/state`，本轮按该边界收。
- **D6 · 死副本的登记问题不能靠"改指活副本"修**（这条是本轮实测把初稿判据推翻的一处）。
  `bin/meta/compass_radar.py`（43,453B）无调用者：全仓 `bin/meta` 引用只有它自己的
  `compass_radar.yaml:2` 登记 + `sub-project-health.py` 自述；活入口是
  `services.yaml:63` 的 `bin/compass_radar.py`。而
  `bin/ssot/script-registry.py validate()` 用 `registered = set(ids)` 且
  `missing = actual_scripts - registered`（`actual_scripts` = `git ls-tree HEAD bin` 的全部
  `*.py`/`*.sh`，只跳过 `_registry`/`_` 前缀目录）。实测基线 `validate` **PASSED 713**。
  于是把 `compass_radar.yaml` 的 `id` 改指 `bin/compass_radar.py` 会同时造成
  ① 两个条目同 id（set 静默去重，不报错）② `bin/meta/compass_radar.py` 从 registered 里消失
  ⇒ `Missing registrations: 1` ⇒ 判据当场自否证。
  本轮因此只做**登记侧诚实化**：把该条目的 `description` 写成"冻结分叉副本，无调用者；活入口
  `bin/compass_radar.py`（登记 `compass_radar-bin.yaml`）"，`maturity` 从 `draft` 改 `deprecated`
  （schema 枚举实测含它），使读者不会去改那份不执行的文件。
  删文件 + 删登记是另一个动作，见 §4。
  ⚠️ 顺带实测到一条登记面事实：`validate()` **不校验 schema**（只比 id 集合），所以 57 个条目的
  `maturity` 取值（`active` 46 / `shadow` 6 / `alpha` 4 / `production` 1）全不在
  `[draft, stable, deprecated, archived]` 枚举里而无任何告警 —— `maturity` 目前是装饰。
  本轮不修这个（登记面治理，另立），只是不再新增一个枚举外的假值。
- **D7 · `projects/runtime` 那份写者本轮不改，三条实测理由**：① 它未安装 ——
  `~/Library/LaunchAgents` 与 `crontab.new` 里没有任何 runtime scheduler 条目（唯一命中是
  `.corrupted-json-backup-20260930/com.omo.model-scheduler.plist`，另一个服务），`OMO_STATE_FILE`
  这个 env seam 在 plist/cron/bin 里**一处都没设**；② 它已经有 env 出口
  （`scheduler.py:24` 读 `OMO_STATE_FILE`），改道可由 profile 注入而不必先改代码；③ 该 submodule
  在本 worktree 是 shallow（`is-shallow-repository = true`），且 `tests/unit/test_scheduler_compile_launchd_plane.py`
  / `test_gate_health_roots.py` 问责它的根，gitlink bump 与测试面都在本轮边界外。
  ⇒ 记为后续 BET，并在本轮把 `write-owners` 的**归属补齐**（见 D8），使普查不再靠叙述。
- **D8 · 声明只能补齐"文件里已有的键"**。守卫的判据是 `present == declared`
  （`undeclared-key` 与 `ghost-declaration` 双向），实测 `worktree_dirty_count` 不在
  HEAD 的 23 个键里（`omo workspace` 未在此检出跑过），所以把 `omo_workspace.py` 的
  `worktree_dirty_count` 声明进去会立刻造出一条幽灵声明、把 T10-219 的绿判据变红。
  本轮只给**已存在的键**补写者：`runtime_health_summary` / `service_online_ratio` /
  `updated_at` / `governance_feedback_last_run` 补 `script:projects/runtime/src/runtime/scheduler.py`
  （D7 的残留写者），`health_score_evidence` / `_source` 按 D2 收成单写者。

## 3 判据（每条命令形态均在本轮落台账前实跑过；"实跑"指命令可执行且失败信息指向未实现的行为，不是指现在就通过）

| # | 命令 | 期望 |
|---|---|---|
| C1 | `sync_system_yaml` 直调探针：声明 `OMOSTATION_STATE_ROOT=$D`、把检出 blob 复制进 `$D/.omo/state/`，import `bin/compass_radar.py` 后调 `sync_system_yaml(code_root(), …)` | 写出目标是 `$D/.omo/state/system.yaml`；`git diff --quiet -- .omo/state/system.yaml` 成立（检出那份逐字节未变）。同一条覆盖"落点 == `repo_root.state_root()/.omo/state/system.yaml`"这个可比断言（D1 的"同一处"不是注释） |
| C2 | 对 `harness-omo-bridge.sync_harness_closeout()` 与 `self-evolution-loop.sync_evolution_state()` 各跑同一探针 | 键（`harness` / `self_evolution`）只出现在 `$D` 那份里，检出的 23 键 blob 仍与 HEAD 相同 |
| C3 | 声明 profile 后跑真实的 omo `state sync` + `sync-tasks` | 双断言：`git status --short .omo/state` 为空 **且** `$D/.omo/state/system.yaml` 的 `updated_at` 出现本次运行的新时刻（正向落点；T10-215 教训 —— 只用"脏检出"这一个否定式当验收会被自己的 receipt 否证） |
| C4 | 读者落点探针：`$D` 放 `health_score=90 / health_score_evidence=10` 的 system.yaml，检出放差值<5 的另一份，跑 `governance-convergence-lint.py --json` | 报出的 divergence 取自 `$D` 那份；删掉 `$D` 那份则回退读检出且不报错（D3 的兜底语义） |
| C5 | 源码 + 行为双向：`git grep` 检出的 `compass_radar.py` 里不再有 `data["health_score_evidence"] = updates[` | 该行 0 命中；`--rule R-GOV-2` 仍可跑且 `errors == []`（D2 的"不会把门禁变红"） |
| C6 | `python3 bin/gac/omo-state-write-guard.py --json` | `undeclared-key`/`ghost-declaration`/`unresolvable-owner` 三类计数全 0、`present == declared == 23`（D8 的约束：补的是归属，不是新键） |
| C7 | `python3 bin/ssot/script-registry.py validate` + `make gac-local-gate` | validate 仍 PASSED（D6 的实测前置：改 id 会让它变 Missing registrations: 1）；local gate 无新增 hard fail |
| C8 | 规范化不变式检查（在 C9 的测试里执行）：AST 摊平 `/` 链后按**源码顺序**拼 tail，扫 `bin/**/*.py` 中由检出根变量锚定的 system.yaml 路径，与一份**逐条写明理由**的 allowlist 做集合相等 | 命中集合 == 8 个在册文件（§1.2 末尾那份）。初稿写的是裸 `git grep` 单一形态，实测只命中 4 处（漏掉分引号写法与 `omo_dir / "state"` 形态）—— 那样一条判据会在写者没改完时就变绿。**第二层教训**：摊平 `/` 链若用栈弹序，`OMO_ROOT / "state" / "system.yaml"` 会拼成 `"system.yaml/state"`，扫描对任何代码都返回空集、测试恒绿 —— 内核侧那条同名检查初稿就是这样，现由 `test_detector_itself_catches_a_known_offender` 先在合成源码上命中再放行 |
| C9 | `python3 -m pytest tests/unit/test_system_yaml_write_plane.py tests/unit/test_projection_reader_resolution.py tests/unit/test_repo_root_profile.py -q` + `uv run --project projects/omo pytest tests/test_omo_system_yaml_state_root.py -q` | 新测试覆盖 C1/C3/C4 三条**正向落点** + 未声明 profile 时的恒等回退 + D3a 夹具不被劫持 + D3b 不凭空造半份镜像；内核侧覆盖 `system_yaml_for/read` 的改道规则（异根 `omo_dir` 原样尊重） |

## 4 非目标

- 不把 `system.yaml` 摘出 git（D1 判定它就是"跟踪的快照 + state 根的运行态镜像"）。
- 不动 tasks 面 INDEX 的 `Updated:`，也不动 `total_tasks` 等从 `.omo/tasks/` 真源派生的稳定字段（D5）。
- 不改 `projects/runtime/src/runtime/scheduler.py` 的根（D7，另立 BET；本轮只把它的归属写进 registry）。
- 不合并 `projects/omo/src/omo/**` 里其余 `WORKSPACE_ROOT` 消费者（`omo_compass.py:104`、
  `omo_dashboard.py:31`、`omo_doctor.py:20`；plan B1 的既有 deferred debt）。
- 不改 R-GOV-2 的阈值 5 与 WARN 分级（D2），不动 `health_score` 的三写者结构。
- 不引入 `OMO_ALLOW_GIT_WRITE=0`（决策 3，属 B4b 批次 2，需逐批授权）。
- 不删 `bin/meta/compass_radar.py`、也不改它的 `id`（D6 实测：改 id 使 `validate` 报
  `Missing registrations: 1`）。删除需同时移除该文件与 `compass_radar.yaml` 两个面，另立。
- 不动 `bin/gac/harness-omo-bridge.py` 的 `OMO_GOVERNANCE_DATA` 写点：它仍钉检出根，但
  `.omo/_control/governance-data.json` 已被 `.gitignore:412` 忽略（实测），破坏面是"两个实例各写一份"
  而非"改写跟踪文件"，不属本轮判据。投影面已由 `runtime-projections.yaml` 的 `governance_data` 条目覆盖。

## 5 实测偏差（不写回台账，写在这里）

台账条目的 `write_surfaces` 是**交付集合的边界**（circuit_breaker 按它拦编辑），不是事后可以悄悄扩的清单。
本轮实现中发现两处应当改但不在 18 面内的东西，都按"登记不改"处理：

1. **§1.1 的普查修正不改变交付面** —— `omo_ingress.py` 已在 `projects/omo` 这一面里。
2. **两条 `tests/unit/**` 本地红与本 BET 无关，且 CI 看不见**：
   `test_repo_root_profile.py::test_projection_falls_back_to_committed_legacy_path` 与
   `test_projection_reader_resolution.py::test_probe_heartbeat_monitor_reports_absent_projections_without_failure`
   的前提是"仓内有一份已提交的 legacy 投影"，而 `cf6d4ac78`（#4524，T10-212 摘库）之后
   `origin/main` 不再跟踪 `.omo/state/health.yaml`（实测 `git ls-tree origin/main -- .omo/state/`
   只剩 `system.yaml` 与 `collab-dualtrack.yaml`）。`governance-check.yml:118-126` 跑的是**显式文件白名单**，
   `tests/unit/**` 不在其中，所以这条红从落地那天起没有任何门禁见过。
   与本 BET 的边界区别：`system.yaml` 仍然 tracked，D3 的"检出兜底"在它是**真兜底**；
   对已摘库的 health.yaml 类投影，兜底随摘库一起失效 —— 那是要单独修的契约，不是本轮回归。

