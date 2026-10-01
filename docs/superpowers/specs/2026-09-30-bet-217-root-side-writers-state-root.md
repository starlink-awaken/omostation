---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-217 — bin/ 侧根写手挂 state_root，消灭仓根 env 私有别名
bet_id: BET-Y2Q4-T10-217
status: accepted
lifecycle: contract
last-reviewed: 2026-09-30
owner: governance-team
---

# BET-Y2Q4-T10-217 — bin/ 侧根写手挂 state_root

ADR-0456 的双根契约（`code_root()` 读 / `state_root()` 写）已在 `bin/lib/repo_root.py` 落好，
`projects/omo` 的写入侧由 T10-215 收敛。本 BET 收 **`bin/` 侧剩下的写手**，并把它们各自
私有的「仓根」env 别名折进规范名。plan 决策 2 把它列为「待消灭的重复定义」，决策 4 把它列为
「把剩余消费者接进去」。

## 0 前置实测（先跑一次，再写进契约）

### 0.1 根的解析语义（`bin/lib/repo_root.py`）

`code_root()` 由 `__file__` 上溯两层（`:67-69`）；`state_root()` 读 `$OMOSTATION_STATE_ROOT`、
**未声明 profile 时返回 `code_root()`**（`:86-91`）；`canonical_root()` 在无 `~/Workspace`
且无 `$OMOSTATION_ROOT` 时 **抛 RuntimeError**（`:80-83`）；`install_root()` 缺标记文件时
返回 `None`（`:111`）。⇒ CI 里没有 `~/Workspace`，本轮一律用 `code_root()` / `state_root()`，
不引入 `canonical_root()`。

### 0.2 worktree 里的实测读数

claim 后跑 `python3 bin/lib/repo_root.py --json` 得 `code_root == state_root == <worktree>`、
`canonical_root == /Users/xiamingxing/Workspace`、`state_root_declared: false`、
`install_root: /Users/xiamingxing/.local/opt/omostation`。未声明 profile 时二者相等
⇒ 本轮改动对今天的运行态**逐字节无效应**。

### 0.3 别名计数（本轮纠正了一次误记）

初次盘点把 `WORKSPACE_ROOT` 记成「7 处」是**错的**：`WORKSPACE_ROOT` 作为**变量名**在 `bin/` 里
出现 180+ 次，而其中绝大多数是 `Path(__file__).resolve().parents[2]` 的本地计算，**不读 env**。
真正的 env 读取点用 `environ.get("WORKSPACE_ROOT"|…)` 精确匹配后是 **5 个模块 6 行**：

| 位置 | 别名 | 本轮处置 |
|---|---|---|
| `bin/mof/generate-brief.py:10` | `OMOSTATION_WORKSPACE_ROOT` | 去 |
| `bin/gac/agent-presence.py:23` | `OMO_WORKSPACE_ROOT` | 不在本轮（见 §2） |
| `bin/gac/task-inventory.py:30` | `WORKSPACE_ROOT` | 去 |
| `bin/ssot/generate-docs-index.py:31` | `WORKSPACE_ROOT` | 去 |
| `bin/ssot/agent-tick-daemon.py:36,55` | `WORKSPACE_ROOT` | 不动（见 §2） |

另有 `bin/_archive/**` 3 处（归档，不在面内）。setter 面：`OMOSTATION_WORKSPACE_ROOT` 只出现在
`crontab.new:76`；`OMO_WORKSPACE_ROOT` 全仓**零 setter**；`WORKSPACE_ROOT` 的 6 处 setter 是
`.github/workflows/ecos-ci.yml:48,59` 与 `mof-update.yml:68,77,87,96`，喂的对象是
`src/ecos/ssot/tools/*.py` 与 `bin/ssot/check-hardcoded-ports.py`，**不喂**本轮触碰的任一读者。

### 0.4 写面的 git 现状（`git ls-files --error-unmatch` + `git check-ignore -v` 逐项实测）

| 路径 | 状态 |
|---|---|
| `.omo/_delivery/evidence-smoke` | untracked + **ignored** |
| `BRIEF.md` | untracked + **ignored**（`.gitignore:413`） |
| `.omo/_knowledge/governance-history.jsonl` | **TRACKED**、未被忽略 |
| `.omo/_knowledge/omo-events.jsonl` | **TRACKED**、未被忽略 |
| `runtime/agents/` | 目录不存在、untracked、未被忽略 |
| `runtime/coordination/handoffs/` | **TRACKED**（仅 `test-run-001.json` 一个 fixture） |
| `runtime/task-inventory/**` | untracked、未被忽略 |
| `docs/generated/doc-inventory.md` | **TRACKED**（入库生成文档） |

`omo-events.jsonl` 的 TRACKED 与 `bin/gac/knowledge-foundry-cron.py:397` 的注释
「omo-events.jsonl gitignored (.omo/_knowledge/*.jsonl)」**直接矛盾** —— 注释是错的，
本轮以 `git ls-files` 为准，不改该注释（它指向的是另一件事的论证）。

### 0.5 决定本轮边界的规则（写面可独移，读面须与它的写者同移）

一个路径**只有在它自己的写者改根时**才能跟着改根，否则制造新的错位：写进 state root、
读者仍指检出 ⇒ 声明 profile 后读者静默读旧数据，且没有任何测试会红。据此逐个量写/读：

- `evidence-smoke.py` 的 `OUTPUT_DIR`(`:108`)：**只被本脚本写**，外部只有
  `bin/compass_radar.py:485` / `bin/meta/compass_radar.py:448` 把它当**子进程**调用并读 stdout，
  无人按路径读那批 json ⇒ 可独移。
- `evidence-smoke.py` 的 `GOV_LOG`(`:109`) / `EVENTS_LOG`(`:110-112`)：**TRACKED + 全仓 15+ 读者**
  （`bin/compass_radar.py:426-427`、`bin/meta/compass_radar.py:389-390`、
  `bin/gac/{governance-history-insight,governance-history-stats,governance-trend-report,
  gate-roi-report,convergence-pulse,sema-distill,rule-adapt(p),event-loop-lint,
  gac-coverage-lint,p0-event-listener}.py`、`bin/panorama/panorama-collect.py:3805`、
  `projects/omo/src/omo/{omo_paths.py:176,omo_event.py:19,omo_history.py}` 等）⇒ **不能独移**，
  属 §2 的未摘库生成态 cohort。
- `system.yaml` 的**写者已全部挂 state_root**：`bin/gac/evidence-smoke.py:217`
  （`runtime_state_root()`）、`bin/gac/unified-health-score.py:396-397`、
  `projects/omo/src/omo/omo_ingress_state.py:244` ⇒ 它的**读者**必须跟上，否则读者永远看
  最后一次提交的快照。本轮只跟上 `generate-brief.py:11` 这一个读者（其余读者属 #98 的 cohort）。
- `collab-dualtrack.yaml` 的写者 `bin/collab/export-dualtrack.py:31` 是 `REPO`（`__file__` 反推，
  即 code_root），**没动** ⇒ `generate-brief.py:327` 的读保持 code_root。
- `task-registry.yaml` 全仓**查不到写者**（仅 `task-inventory.py:31` 与
  `panorama-collect.py:3198` 两个读者）⇒ `task-inventory.py:31` 的读保持 code_root，
  只移它自己的产物 `SNAP_DIR`(`:32`) / `DRIFTS`(`:33`)（外部唯一相关者是
  `bin/ssot/governance-scanner.py:341`，它按子进程调用、不按路径读产物）。

### 0.6 `crontab.new:76` 这条本身已是死路径（实测）

实时 `crontab -l` 有 39 条作业行，含 `generate-brief` 的 **0** 条、含 `OMOSTATION_` 的 **0** 条；
且该行 `cd` 目标 `~/.local/share/omostation/accepted-20260908` 的 `.git` 是指向已不存在父检出的
文本指针（`git -C <该目录> rev-parse` → `fatal: not a git repository`），主仓
`git worktree list` 也不含它 ⇒ 一个**僵尸 worktree**，删除属破坏性操作，本 BET 不碰。

### 0.7 写操作清单（不是「它引用了什么」而是「它落笔在哪」）

`bin/mof/generate-brief.py` 只有 `:34-35` 写 `BRIEF_MD`；对 `system.yaml`(`:375`) 与
`collab-dualtrack.yaml`(`:325-327`) 都是 `is_file()` 守卫后的**只读**。

## 1 交付

1. `bin/gac/evidence-smoke.py`：`WORKSPACE`(`:43`) 由 `__file__` 反推改 `code_root()`；
   `OUTPUT_DIR`(`:108`) 改挂该模块**已 import** 的 `runtime_state_root()`(`:53`)，与它
   `:217` 已有的正确写法同形。`GOV_LOG` / `EVENTS_LOG` 保持 `WORKSPACE`，并在两处留一行
   指回 §0.5 的约束（避免下一个 agent 把它们「顺手」也移了）。
2. `bin/mof/generate-brief.py`：`WORKSPACE`(`:10`) 去 `OMOSTATION_WORKSPACE_ROOT` 改 `code_root()`；
   `SYSTEM_YAML`(`:11`) 改挂 `state_root()`（依 §0.5：写者已在 state root）；`BRIEF_MD`(`:12`)
   保留 `OMOSTATION_BRIEF_OUTPUT` 覆盖、缺省仍 `code_root()/BRIEF.md`（已 gitignore，且是
   与人共读的落地文件名，不改名不改位）；`:325` 的 dualtrack 读保持 code_root（写者未移）。
3. `bin/gac/task-inventory.py`：`WORKSPACE`(`:30`) 去 `WORKSPACE_ROOT` 别名改 `code_root()`；
   `SNAP_DIR`(`:32`)、`DRIFTS`(`:33`) 改挂 `state_root()`；`REGISTRY`(`:31`) 保持 code_root。
4. `bin/ssot/generate-docs-index.py`：`ROOT`(`:31`) 去 `WORKSPACE_ROOT` 别名改 `code_root()` ——
   它的产物 `docs/generated/doc-inventory.md` 是**入库文档**，必须落 code root；CI 在
   `doc-gov-check.yml:26,29` 直接跑它且未设该 env。
5. 测试随契约改：`tests/test_generate_brief_workspace_output.py` 现在**正面断言**
   `OMOSTATION_WORKSPACE_ROOT` 生效（`:12,14,33`），删别名即必红 —— 改为断言
   ① `BRIEF_MD` 只被 `OMOSTATION_BRIEF_OUTPUT` 决定、② `WORKSPACE` 恒等于 `SCRIPT.parents[2]`
   （即输出覆盖不得把根一起拖走）。`tests/test_evidence_smoke_paths.py` 与
   `tests/unit/mof/test_generate_brief_no_host_paths.py` 以 `module.WORKSPACE` 为 monkeypatch
   锚点，故 `WORKSPACE` 这个名字必须保留（值改、名不改）。新增 3 条落点断言：
   声明 profile 后 `OUTPUT_DIR`/`SNAP_DIR`/`DRIFTS` 均落在 state root 且不在检出内、
   未声明时路径字符串与改前逐字节一致（复用该两文件既有判据形状）。
6. 台账登记（不修）两条外溢债：
   `OMO_WORKSPACE_ROOT`/`agent-presence` 的协调面（§2）；`WORKSPACE_ROOT` 在
   `projects/omo/src/omo/**` 有 ≥10 处读者且缺省 `Path.home()/"Workspace"`，CI 未显式设置即
   解析到不存在路径，收敛需子模块 commit + gitlink bump。

## 2 非目标

- **不移 `agent-presence.py`。** 实测三个理由：① 它写的 `runtime/agents/*.json` 有仓外读者
  `bin/gac/ci-local-fast.py:539`（`WORKSPACE / "runtime" / "agents"`，`__file__` 反推），只移写者
  即断在场检测；② 它写的 `runtime/coordination/handoffs/` 是 **git 跟踪目录**，其准入由
  `bin/gac/omo-runtime-stamp-policy.py:34-45` 的 `ALLOW_PATHS` 白名单管，而
  `runtime/runtime-space-boundary.yaml` / `runtime/system-runtime-boundary.yaml` 两个
  `allowed_runtime_roots` 只声明 `runtime/run-continuation` 与 `runtime/logs` —— 白名单与边界
  声明本身就不一致，改根前得先定这个；③ `OMO_WORKSPACE_ROOT` 零 setter ⇒ 移它没有当下收益。
  ⇒ 协调面属于「先定边界、再改根」，另立 BET。
- **不移 `GOV_LOG` / `EVENTS_LOG`**（§0.5 的 15+ 读者），不 `git rm --cached` 任何文件，
  不改 `.gitignore`；`system.yaml` 与这两个 jsonl 的摘库属 #98 cohort（已有一份 system.yaml
  读者穷尽清单，CI 硬阻塞项唯一是 `.github/workflows/state-goals-enforce.yml:28` 的
  `current-state-coherence.py`，rc 2）。
- **不动** `bin/ssot/agent-tick-daemon.py:36,55` —— 它把该值写进机器级配置，语义是「配置项」
  而非「本脚本的根」；混改会把 worktree 路径写死进配置，正是 `canonical_root()` docstring
  记录的两起事故形状。
- **不动** `projects/omo/**`、`projects/ecos/**`、`.github/workflows/**`、`crontab.new`、
  `bin/collab/export-dualtrack.py`、`bin/panorama/panorama-collect.py`。
- 不删 `~/.local/share/omostation/accepted-20260908` 僵尸检出，不 prune 任何并发会话的锁。

## 3 验证（done_when 的测量口径）

1. `OMOSTATION_STATE_ROOT=<tmp> python3 -c "import …evidence-smoke"` 断言
   `OUTPUT_DIR`、`task-inventory.SNAP_DIR/DRIFTS` 落在 `<tmp>` 下，且 `WORKSPACE`、`REGISTRY`、
   `BRIEF_MD`（未设 output 时）不落在那儿。
2. 未设 `OMOSTATION_STATE_ROOT` 时，四个脚本上述常量的 `str()` 与改前
   `git show origin/main:<file>` 版本逐字节一致（无效应判据）。
3. `uv run pytest tests/test_generate_brief_workspace_output.py
   tests/test_evidence_smoke_paths.py tests/unit/mof/test_generate_brief_no_host_paths.py -q` 全绿。
4. `bin/` 内 `environ.get("OMOSTATION_WORKSPACE_ROOT"` / `environ.get("WORKSPACE_ROOT"`
   的命中集合 = `bin/ssot/agent-tick-daemon.py:36,55` 两行（其余别名读者清零）。
5. `make gac-local-gate` 绿；`git diff --name-only origin/main...HEAD` 不含 `.omo/state/**`
   与 `BRIEF.md`。
