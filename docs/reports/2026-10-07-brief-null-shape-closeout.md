---
schema: md/v1
status: completed
lifecycle: report
owner: governance-team
last-reviewed: 2026-10-13
type: closeout-receipt
bet_id: BET-Y2Q4-T10-236
title: BET-Y2Q4-T10-236 closeout receipt — system.yaml 空形的消费侧折叠（B5 补料侧）
---

# BET-Y2Q4-T10-236 收口 receipt — system.yaml 空形的消费侧折叠（B5 补料侧）

- **交付**：PR #4752 → squash merge `9e13a6355516187a5a1e907f9c84bc335a097f1f`（2026-10-13T11:52:52Z）
- **分支 commit**：`6c665defe0a010591034691ad481742ac448f12b`（2 files / +305），base `52608a208`
- **CI**：28 项 checks 全绿（`gac-gate` 2m2s / `governance-verify` 2m46s / `interface-check` 4m11s），
  `doc-freshness` 与 `Documents domain projects` 因 `on.paths` 过滤 skipping
- **零行为改动证明**：`git rev-parse origin/main:bin/mof/generate-brief.py` =
  `git rev-parse 6c665defe:bin/mof/generate-brief.py` = `f70a4244c35da30a961f8642c32cfd39c1e76e49`

## 1 交付面

| 文件 | 动作 | 实测 |
|---|---|---|
| `tests/unit/test_brief_null_shape.py` | 新建（14,151 B，`sha256:28287fe844b11b3a…9baf41`） | 交付树 **10 passed in 2.50s**；接线白名单前同一文件 **9 passed + 1 failed**（失败的正是 CI 可见性件），顺序即证据 |
| `.github/workflows/governance-check.yml` | 白名单第六件点名 + 读数注释 | `git grep -n test_brief_null_shape -- .github/workflows/` → `:144`（注释首行）+ `:181`（`../../tests/unit/test_brief_null_shape.py \`），rc=0 |
| `docs/plans/3y-bet-ledger.yaml` | 本条目 `status` / `done_at` / `completion_evidence` 由 `bet-ledger.py complete` 写入 | 读数见 §7 |
| `docs/superpowers/specs/2026-10-07-brief-null-shape-consumer.md` | **未改动，绑定 digest 仍有效** | 实测 `sha256:83d1af8d4e322745b63fe9526b8e2c6c7755d4239c59b27fb31c17bb84b88b11` = 台账 `content_digest` 逐字节相等 |
| `bin/mof/generate-brief.py` | **本轮未改动** | 折叠已由 #4687 → `b85ed694f` 落在 main；本轮补的是它的判据（见 §3），blob 对拍见抬头 |

## 2 判据逐条读数

| # | 判据 | 实测 |
|---|---|---|
| 1 | 等价性（I1）：absent vs 空形 两侧 rc=0 且 normalize 后逐字节相等 | 复刻树实测 `rc=0/0`，`normalize_brief_content()` 后逐字节相等；absent 臂跑完 **没有**造出 `system.yaml`（等价性不是「两边都新写了同一份」） |
| 2 | 真值不吞（I2）：`health_score: 46` → 含 `复合健康分: \`46/100\``、不含 90/100 | 三臂实测：无 flag `rc=0` `46/100`×2 `90/100`×0 `None`×0；`--protect` 同读数；`--write` 落盘件含 `` **复合健康分**: `46/100` `` 与 `` **GAC 异常扣分**: `71/100` ``、`90/100` 零次 |
| 3 | 用例全绿 | 复刻树 **9 passed + 1 deselected**（唯一被摘的是 CI 点名件，白名单尚未接线）；交付树 **10 passed in 2.50s**；`HOME=<空目录>` + `env -u OMOSTATION_*` + 最小 venv 供给依赖时同样 10 passed（不读 host profile） |
| 4 | 反基线（I5）：把折叠改回 `data.get(key, default)` → 等价性用例 FAILED 且含 NoneType | 变异在 `git archive` 复刻树里做，**交付树逐字节未动**：单处折叠回退 → **3 failed / 7 passed**，三条分别命中 I1（`rc=1` 崩在 `generate-brief.py:513 if health_score >= 90`，消息 `TypeError: '>=' not supported between instances of 'NoneType' and 'int'`）、I4 集合相等、以及 generate-brief 零站点件；两处都回退 → 4 failed / 6 passed。改回后复跑回到 10 passed，且 blob 与 `origin/main` 一致 |
| 5 | 检测器不自证为空：合成站点被点名 | 注入 `bin/gac/synthetic-consumer.py` 的 `data.get("health_score", 0)` → 扫描读数恰为 `{("bin/gac/synthetic-consumer.py", "health_score"): 1}` 且该站点**不在**清单内；反向对照件（单参 `.get` / 外来键 / `default=` 关键字）读数 `{}` |
| 6 | CI 点名 | `governance-check.yml:181` 白名单项（`git grep` rc=0）；CI `interface-check` 的「Run governance checks」步骤 26 个点名文件合计读数 **392 passed, 9 skipped in 128.33s**（11:51:23Z），日志 shell trace 内含 `../../tests/unit/test_brief_null_shape.py \` 一行 ⇒ 本件的绿自此由 CI 而非本地承担 |
| 7 | 空形语义未动：`key_set_equals_declared=True` / `empty_shape_keys=13` / ownership 三类 0 | 主区实测 `key_count=23 declared=23 undeclared=[] ghost=[]`，guard rc=0；worktree 侧 `python3 bin/gac/omo-state-write-guard.py --json` **rc=0**，`ownership` 三计数（undeclared / ghost / unresolvable-owner）在物化 `projects/runtime` 后归零 |
| 8 | 摘库未撤：`git ls-files` 空 + check-ignore 命中 `.gitignore:297` | 实测 `tracked=0`，命中 `.gitignore:297:.omo/state/system.yaml` |
| 9 | 门禁不瞎 | T10-235 四件（materializer / projection_reader_resolution / write_plane / consumer_inputs）交付树 **81 passed in 1.82s**，与主区基线 81 逐条不减；worktree `make gac-local-gate` 读数 **FAIL / 3 项**，三项均已归因（见 §6），主区同门禁 PASS（evidence score=94.0），交付 PR 的 CI `gac-gate` job PASS ⇒ 三项为环境/既有裁定类，非本轮引入 |

## 3 与 spec 的两处实测分歧（如实记，不改窄判据）

- **站点数 11 → 9**：spec §3 的 11 含 `mof/generate-brief.py:398 :399`。#4687 折叠后这两处的形状是
  `data.get(key)` + `is None` 守卫，**不再命中**「位置参数 ≥ 2」的 AST 判据。⇒ I4 的相等清单是 9 处
  （按 (文件, 键) 计数，`quarterly-report.py` 的 health_score 为 3），并另加一条结构件：
  `generate-brief.py` 在该形状上必须贡献 0 处 —— 回退折叠会同时被这条与等价性用例抓到。
- **spec §8「同批回补 T10-235 receipt §5 拆分」已在 main 上成立**：
  `docs/reports/2026-10-07-system-yaml-materializer-closeout.md:148/:187` 已写「root 11 / 子模块 13」
  并订正装置。⇒ 该路径不属本轮 write_surfaces，无需 claim，也未顺手改。
- **台账 `verify` 第 2 条按字面跑不通**：`pytest …::test_null_shape_stdout_equals_absent_shape`
  (a) 主机 `python3 -m pytest` 无 pytest（`No module named pytest`，rc=1），(b) 该函数是
  `TestNullShapeEquivalence` 的类方法，裸 `文件::函数` 不解析。类限定形式
  `…::TestNullShapeEquivalence::test_null_shape_stdout_equals_absent_shape` 实测 **1 passed in 0.38s**。
  ⇒ 记分歧而不改台账：`verify` 在 WorkPacket 投影内，`start` 之后改它即造
  `WORK_PACKET_SOURCE_DRIFT`（`bin/plan/bet-ledger.py:2336`），改窄判据换一条能跑的命令更不是修法。

## 4 边界（BET circuit_breaker 逐条自证）

未动创建者空形语义/键集、未撤 `.gitignore:297`、折叠非 `or default`（0 真值有专件）、
未把 `brief-protect` 摘出 `SOFT_CHECKS`、未为其余站点预抽 `bin/lib` 公共装置、
**不宣布 B1/B5 完成**（B5 仍有 #91/#123/#124 类待准入项）。

## 5 并发面事实

`BET-Y2Q4-T10-236` 在协调面上有 8 条历史 run，全部 `blocked` 且全部 `engineering-agent` ——
它们的 objective 是 **DCP-20 Zhixing**，源于其基线 `b884e2919`（omostation-root/main）上 T10-236 是
另一个条目；其最新 evidence 自己记录了这层 authority drift。本轮按当前 `origin/main`
（T10-236 = system.yaml 消费侧）开工，与该 BET 无路径交集。

开工窗口内 `project:` 范围锁被并发会话的 **active** run
`20261013T111716Z-project-code-change-11f8d883`（actor `codex`，objective = Cockpit gitlink
`f2d296b42` 的 push/merge）持有，心跳持续刷新。本轮**没有**用 `--force-lock` 拆别人的活锁，
也没有 `prune-locks`（阈值 3600s 只看心跳，会把别人刚起过的 run 判成 zombie）；
测量先在 `git archive` 复刻树上做完，等锁自然释放再在交付树上接线与复跑。

## 6 worktree 门禁三项 FAIL 的逐项归因

| 项 | 读数 | 归类 | 对照 |
|---|---|---|---|
| `check-cockpit-ui-dist` | `dist/index.html` 缺失 → 自愈 `bun run build` → `Script not found "build"` | 环境类：worktree 里 `projects/cockpit-ui` 检出无 build 脚本（claim 默认浅 init，`AGENTS.md` §6） | CI `gac-gate` 递归检出 → PASS |
| `service-config-drift` | `com.omostation.zhixing-projection-republisher: plist 与 services.yaml 不一致` | 既有裁定类：机器级 launchd plist 与仓内 registry 的反向漂移，属待署名项（台账 `BET-Y2Q4-T10-237` 已把同族漂移定性为 host 面，且 `bin/gac/gac-local-gate.py:201-205` 起该检查带 `ci_skip: True`（`CI_SKIP_CHECKS` 在 `:552` 导出））；与本轮交付面零交集，未碰 plist / services.yaml | 该项对 PR 的 CI 判定零影响；`gac-gate` job PASS |
| `check-evidence-freshness` | `FAIL (score=0.0, age=-1d)` ← `generation_failed — import_failed`；链：`uv sync exit 2 / bus-foundation metadata` → `No module named 'agora'` | 环境类：worktree 子模块未完整物化（`submodule update --init` 曾 rc=0 而工作树为空，需 `checkout --force <pinned>`） | 主区同检查 **PASS score=94.0**；CI `evidence-gate` PASS |

**纪律**：worktree 的门禁读数只在「与主区/CI 逐项对照」之后才可用于判定，
既不能整块当噪音，也不能整块当真回归。

## 7 台账 done 转换读数

- `bet-ledger.py lint` → **rc=0**（全台账 schema 通过）。
- `bet-ledger.py verify BET-Y2Q4-T10-236`（D0 入库面）→ **rc=0**，7 条 `write_surfaces` 全部
  `[OK] … (root index)`：`bin/mof/generate-brief.py` / `tests/unit/test_brief_null_shape.py` /
  `.github/workflows/governance-check.yml` / `docs/plans/3y-bet-ledger.yaml` / spec / retro / 本 receipt。
  ⇒ 后两件是在本轮 `git add`（进 index）之后由同一条命令量出的，不是凭「文件已存在」推的。
- `bet-ledger.py complete BET-Y2Q4-T10-236` → **rc=0**，`[complete] ✅ BET-Y2Q4-T10-236 → done`；
  台账读数 `status: pending → done`、`done_at: 2026-10-13`，claim 广播随 done 自动释放。
  其前置校验（spec binding digest 逐字节相等、`completion_evidence` 派生 `delivery_accepted`、
  `merged_reachable_commit` 在本地对象库可达 `origin/main`、vision→retro 链闭合）全部通过后才写盘。
- **digest 自指的处理**：本节是在 `complete` 之后补写的，因此本文件的 sha256 变了 —— 台账矩阵里
  6 处 receipt digest 在本节定稿后**重算并回写**，提交态由 CI `bet-done-transition` 逐字节复核；
  retro 的 digest 未经过第二次编辑，仍是 §1 记下的一次成型值。写「先测量、后填格」的顺序时，
  必须连它带来的二次摘要一起交代，否则这条链看起来像是一次成型的。
