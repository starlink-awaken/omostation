---
schema: md/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-30
type: report
bet_id: BET-Y2Q4-T10-215
title: BET-Y2Q4-T10-215 closeout — omo 写入侧单根（投影写面在调用图内闭合）
---

# BET-Y2Q4-T10-215 closeout — F1 投影写侧改挂 `state_root`

契约：`docs/superpowers/specs/2026-09-29-bet-215-omo-write-side-single-root.md`（v1.0.0，
`status: accepted`，`lifecycle: contract`，digest `sha256:f1fac56c79377e23da16c1f00969211107ea47d063d6ec4bd386c49f4484005d`）
交付：omo 子模块 PR **#204** squash 为 `56cfc5b014035f511a3df96fde3d7c733107d8ec`（2 files，**+192 / −53**）
→ 根仓 PR **#4571**（commits `c1fd53980c` 写面与证据 / `7e1d8a7a58` gitlink bump / `13e3ab5e26` frontmatter 修复）
squash 为 **`6b2776535c0e399969d8cd9cebf0c9bdb7fde844`**（2026-09-30T01:33:06Z，5 files，**+333 / −7**）
复盘：`.omo/_knowledge/retros/BET-Y2Q4-T10-215.md`
run 链：`20260929T164024Z-project-code-change-92c82f3c`（10 条路径 claim，本 BET 唯一绑定 run）
→ `20260930T013757Z-project-doc-change-7114939b`（为 PR-2 另起的 run，**blocked 关闭**：三条目标路径
已被上面那个 run 活动 claim 占有，`A2A Path Lock Collision` —— 没有落任何改动）

## 1 这一轮把哪一面翻了

ADR-0456 的双根契约里，**读**跟检出、**写**跟 profile。B1 把根侧解析器
（`bin/lib/repo_root.py`）做完了，omo 内核却还留着一条由入参根派生的写面 ——
`sync_state_projection(code_root, …)` 把四件投影和 `runtime/omo/**` 镜像根一律挂在**检出**下，
于是 dev profile 每跑一次 `omo state sync` 就脏一次检出。本轮改的就是这一处：

| 面 | 改前 | 改后 |
|---|---|---|
| 写出根 | `code_root` 入参直接派生 | `_resolve_write_root`：**显式 `state_root` 入参 > env `OMOSTATION_STATE_ROOT` > 检出根** |
| 四件投影 | `<检出>/.omo/state/runtime/{health.yaml,system.yaml,brief.md,governance-data.json}` | `<state_root>/…` 同结构 |
| 镜像根 | `<检出>/runtime/omo/**` | `<state_root>/runtime/omo/**` |
| 读侧 | `projection_path()` canonical→legacy、`_build_health_projection` / `_build_brief_content` / `build_governance_data`、`.omo` 存在性检查 | **逐条不动**（spec C5；根侧 `test_projection_reader_resolution.py` 18 passed 钉住） |

根侧配套一处：`bin/gac/evidence-smoke.py` 的 `system.yaml` 写目标由模块常量 `SYSTEM_YAML`
改为 `_system_yaml()`（`:210` → `:217` 经 `repo_root.state_root()` 解析）。
这不是可选装饰 —— 见 §2。

## 2 为什么"只翻投影写侧"不够（C6 的真实内容）

C6 要求的是**调用图内闭合**，判据是"声明 profile 跑一次真实 CLI 后检出的 `git status` 与运行前逐行相同"。
只翻 `omo_ingress_state.py` 时这条**不成立**，链路是：

```
omo state sync
  └─ omo_ingress_state.py:96 _build_health_projection
       └─ bin/compass_radar.py:1062 build_health_projection
            └─ :1113 _collect_feedback_liveness
                 └─ :482 subprocess.run([... evidence-smoke.py --json])   ← 不传 env=
                      └─ bin/gac/evidence-smoke.py:913 _write_health_score_evidence()
                           └─ 原 :227 SYSTEM_YAML = WORKSPACE_ROOT/.omo/state/system.yaml  ← 写回检出
```

`git status` 里那个 `M .omo/state/system.yaml`（`health_score_evidence_generated_at` 时间戳）
的作者就是这个 subprocess。它靠 **env 继承**拿到 `OMOSTATION_STATE_ROOT`，所以修复方式是让
它也跟着 `state_root()` 走，而不是在 `omo_ingress_state.py` 里加规则。

链节能闭合还有一个**不被复述的前提**：`bin/compass_radar.py:482` 的 `subprocess.run` 不传 `env=`。
若那里改成显式 env 白名单，C6 会静默断掉 —— 已写进 spec §2 C6 正文，作为下一轮读代码时的告警。

## 3 端到端读数

台账 5 条 `verify` 逐条跑，**串行**（原因见 §5-4）。原始输出分两份：
`/tmp/t10-215-verify.txt`（首轮，跑在 code 侧 worktree `ws-t10-215-omo-write-root`）与
`/tmp/t10-215-verify-clean.txt`（判据 3/4 的串行复跑）。首轮里 1/2/5 与 omo 全量套件并发，
因此下表三行读数**在本 closeout worktree 里串行复跑复核**（见 §3.3），复核与首轮一致。

| # | 命令 | 实测读数 | 判定 |
|---|---|---|---|
| 1 | `pytest tests/unit/test_repo_root_profile.py -q` | `1 failed, 859 passed` | 与登记时 main（`53ecf86c6`）逐字相同的读数；失败项见 §3.1。**单文件 859 不奇怪**：该守卫对 `bin/**/*.py` 逐文件参数化（`:87-91` `rglob`），一个用例 = 一个脚本 |
| 2 | `pytest tests/unit/test_projection_reader_resolution.py -q` | `18 passed` | C5 读侧不动 |
| 3 | `OMOSTATION_STATE_ROOT=<tmp> omo state sync --dry-run --json` + `git status --short` 前后比对 | sync exit 0；`writes[] count=4`，四条 path **全部**在 `<tmp>` 下（`runtime/health.yaml`、`system.yaml`、`runtime/brief.md`、`runtime/governance-data.json`）；`diff` 退出码 **0**（检出逐行相同） | 判据 6 + 判据 7 成立 |
| 4 | 预热 state 根后跑**真实**（非 dry-run）sync | state 根 `system.yaml`：`health_score: 39`、`health_score_evidence: 100.0`、`_source: bin/gac/evidence-smoke.py`、`_generated_at: '2026-09-30T01:43:58.014449+00:00'`；检出的 `git diff -U0` **只有一处 hunk** `@@ -14 +14 @@ updated_at: '2026-09-27T08:22:42Z' → '2026-09-30T01:43:58Z'`；`grep health_score_evidence` 在检出 diff 里 **零命中**（LEAK=no） | 判据 9 成立（见 §3.2 的措辞修正） |
| 5 | `pytest tests/test_evidence_smoke_paths.py -q` | `5 passed`（3 条既有 `_check_stdio` 用例不变 + 2 条新增：declared-profile 落点 / undeclared 路径字符串） | expect[5] 成立 |

真实 sync 落在 state 根的全部产物（9 个文件，字节数）：

```
.omo/state/runtime/brief.md 2579      .omo/state/runtime/health.yaml 1840
.omo/state/runtime/governance-data.json 939   .omo/state/system.yaml 582
runtime/omo/_delivery/ingress/ingress-audit.jsonl 709
runtime/omo/_delivery/ingress/ingress-trail.jsonl 304
runtime/omo/_delivery/ingress/ingress.lock 0
runtime/omo/_delivery/ingress/state/state-sync-2026-09-30T01-42-26Z.yaml 1186
runtime/omo/change-log/mutations.jsonl 929
```

### 3.1 一条预存红，本轮未修（不在 write_surfaces）

`tests/unit/test_repo_root_profile.py::test_projection_falls_back_to_committed_legacy_path`
断言 `projection_path("health")` 在 legacy 目录存在时回退到 `<检出>/.omo/state/health.yaml`，
而 B5 摘库（`cf6d4ac78`）之后该回退目标已不是磁盘事实。main `53ecf86c6` 上同红
（`1 failed, 859 passed`，与本轮读数相同）→ **非本轮引入**，且 `tests/unit/**` 未接 CI，
所以 CI 里它是静默的。登记进 #98 的残余项（与"六个检出侧读者""`OUTPUT_DIR`"同批收口）。

### 3.2 读数把契约里的一句话否证了

spec 判据 9 原文写的是"检出的 `system.yaml` 那份**不含**这三行 evidence 字段"。
实测 `git show HEAD:.omo/state/system.yaml` 第 3–5 行**就有**这三行
（`_generated_at: 2026-09-27T08:42:13.059879+00:00`，跟踪态里上一次生产运行的读数）。
所以"不含"是个错误的判据 —— 正确的判别量是**同一字段的值只在 state 根滚动**：
检出的 evidence 三行逐字未变，新时刻只出现在 `<tmp>`。
这条比原措辞更强（既证明写落点，又证明检出没被回写），已据此改写 spec 判据 8/9，
并顺手把 8/9 的编号顺序摆正（原先 9 插在 8 前面）。绑定 digest 随之重算：
`f1fac56c…` → `4dafbac67adce96ef9bcde62f3d2046475c29783a1f0eedbfbd7f4dfa83c9408`（台账已同步）。

### 3.3 done_when 第 6 条的两条读数（串行复核）

- **omo 全量测试绿**：在 closeout worktree 的 `projects/omo` 里
  `uv run --quiet pytest -q -p no:cacheprovider` → **`2873 passed, 216 skipped in 655.01s`**，exit 0。
- **根侧两个守卫读数不变**：上表 1/2/5 三行首轮与 omo 全量套件并发跑过，因此套件结束后
  在本 worktree 串行复跑一遍 —— `1 failed, 859 passed` / `18 passed` / `5 passed`，
  与首轮逐字相同；复跑前后 `git status --short` 逐行相同（根侧 pytest 不写任何跟踪文件）。
- 套件与复跑期间写脏的 5 个跟踪文件（`projects/omo/.omo/state/agent-cell*` 四件 +
  根侧 `.omo/_knowledge/governance-history.jsonl` 被追加一行）在提交前 `git checkout --` 还原，
  **不进 PR-2**；这是 §5-4 那条测量纪律的落地动作，不是被交付的改动。


## 4 契约边界：本轮实测到的、不属于 F1 的两件事

登记为不解，不顺手改（改它们会突破本 BET 的 write_surfaces 与 non_goals）：

1. **tasks 面的两枚时间戳仍落检出。** 真实（非 `--dry-run`）sync 会脏
   `.omo/state/system.yaml` 的 `updated_at` 与 `.omo/tasks/registry/INDEX.md`
   —— 作者是 `projects/omo/src/omo/omo_state.py:449`（sync 内部调 `sync-tasks`）
   → `:218`（回写任务计数与 `updated_at`）→ `:232`/`:283`（重建 INDEX 的 Active/Planned/Blocked 表）。
   脏量是**纯时间戳**：`blocked_tasks 0→0`、`total_tasks 304→304`、`completed 303→303`，
   计数逐字未变。不搬 `.omo/tasks/`（709 个跟踪文件）是 non_goals 第 1 条，
   台账 `circuit_breaker` 已据此加了同名例外 —— 否则 breaker 会因自己的非目标而误触发。
2. **六个检出侧读者仍从检出读 `system.yaml`**（`governance-convergence-lint.py:32`、
   `check-project-health-freshness.py:12`、`omo-state-write-guard.py:20`、
   `bin/mof/generate-brief.py:11`、`doc-ssot-lint.py:36`、`governance-alert-dispatch.py:43`）。
   声明 profile 后它们读到的是**最后一次提交的快照**，这正是决策 4 要的 dev 侧语义
   （`health_score` 与 `health_score_evidence` 同源同快照，不会自造分歧）；
   摘库（#98）时与读侧解析一起收口。`evidence-smoke` 自己的 `OUTPUT_DIR`（`:103`，
   落 `.gitignore` 的 `_delivery/*`）同理不动 —— 单翻写侧会让它的两个读者读数断链。

另记两条与本轮相邻的既有缺陷（不在 write_surfaces，故只登记）：
`projects/omo/src/omo/omo_state.py:101-138` 里 `state refresh` 仍写死
`Path.home()/"Workspace"/"projects"/"runtime"`；`tests/unit/**` 未接 CI
（只有 `integration.yml:46-47` 与 `worktree-hygiene.yml:17` 引用），所以 §5 那条红在本仓 CI 里是静默的。

## 5 本轮被实测否证、因而改写契约的断言

1. ❌「C6 = 跑完 dry-run 看 `git status` 无 diff」→ ✅ **否定式不能当证明**。
   判据 7（无 diff）与判据 9（正向落点）是两条：后者要求 state 根的 `system.yaml`
   **含** `health_score_evidence` / `_source` / `_generated_at` 三行、检出副本**不含**，
   写落点才算被正面钉住。spec §4 加了判据 9，台账 done_when 加了对应一条。
2. ❌「真实 sync 也应当零 diff」→ ✅ 这是我把 C6 的适用范围写宽了。实测脏两枚
   tasks 面时间戳，属 non_goals 1 的面，不是 C6 漏网。据此把 spec C6 措辞限定为
   **投影面**在调用图内闭合，并把判据 7 拆成"dry-run 不变量成立"与"真实运行的边界"两句。
3. ❌「`done_when` 里 C6 那条只写'闭合'就够了」→ ✅ 台账 `circuit_breaker` 与 `non_goals`
   自相矛盾（breaker 禁止任何落检出的写，non_goals 却允许 tasks 面时间戳）。已把例外写进 breaker。
4. ⚠️ 测量卫生：**并发跑 pytest 会让 `git status` 类判据失效**。本轮第一次 verify 批跑时
   并行起了 `projects/omo` 全量测试，`git status` 里就多出一行 ` m projects/omo`
   （测试写 `projects/omo/.omo/state/agent-cell*` 跟踪文件）。因此 §3 的读数取自
   **串行 clean re-run**，第一次跑的读数只作为参考留在附录。
