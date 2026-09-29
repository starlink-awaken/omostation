---
schema: md/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-29
type: report
bet_id: BET-Y2Q4-T10-214
title: BET-Y2Q4-T10-214 closeout — BET-212 证据完整性修复
---

# BET-Y2Q4-T10-214 closeout — BET-212 closeout 证据完整性修复

契约：`docs/superpowers/specs/2026-09-29-bet-214-closeout-evidence-integrity.md`（v1.0.0，
`status: accepted`，`lifecycle: contract`）
交付：PR **#4561**，分支 head `18c64e3b0`，squash 合并为 `b24c353c3`
（`2026-09-29T13:08:17Z`），4 files changed / **+315 / −14**
复盘：`.omo/_knowledge/retros/BET-Y2Q4-T10-214.md`
run 链：`20260929T112658Z-project-doc-change-79b25579`（登记+修复）→
`20260929T131728Z-project-doc-change-9c4255b5`（closeout，blocked）→
`20260929T132534Z-project-doc-change-904712c4`（closeout 后继）

## 1 修了什么（三处，全部实测过）

| # | main 上的缺陷（修复前） | 修复后 |
|---|---|---|
| 1 | `BET-Y2Q4-T10-212.completion_evidence` 里 6 条指向 PR-3 closeout 报告的 receipt 摘要**全部陈旧**：`0fd5034b…`×5（`engineering.tests/diff/rollback`、`operational.live_canary/fresh_receipt`）+ `0e3c4bcb…`×1（`operational.cleanup`） | 6 条全部重算为报告编辑后的**文件字节**摘要 `sha256:15ba278f44b1fb1e6aba5ba3a884db987bd1a602ef54481b1af22ad56c32dd69`；口径写明是 `shasum -a 256`，**不是** `git hash-object`（后者含 `blob <len>\0` 对象头，逐字节不可能等于内容摘要） |
| 2 | `verify[0].cmd` = `uv run --with pyyaml python -m pytest …` 原样跑报 `No module named pytest`；且未记 `projects/omo` 须 init 的前置 | `uv run --with pyyaml --with pytest python -m pytest tests/unit/test_projection_reader_resolution.py -q`，同条目 `expect` 写明前置与原因（三个用例把 `projects/omo/src` 放进 `sys.path`） |
| 3 | `verify[0].expect` 引用 `PR-3 closeout report §10`，而该报告终节就是 §9 | 锚点改为 **§9 第 8 条** |

## 2 报告里两处被实测推翻的断言（不是排版，是事实错误）

登记本 BET 时我先写了两句话，随后被自己的测量否证，故在 §9-9 与 spec §1/G1 中改写：

1. ❌「没有工具比对 receipt `sha256` 与文件内容」→ ✅ **`bin/ssot/sync-bet-digests.py` 早已存在**
   且逐条比对，并被 `tests/test_sync_bet_digests_integrity.py` 钉住（只改摘要 / status 会变即拒 /
   bet 被删即拒，实测 **3 passed**）。缺的是**接线**：registry 条目
   `bin/_registry/scripts/governance/sync-bet-digests.yaml` 的 `triggers: []`，且 `.github/`、
   `Makefile`、`.omo/_truth/registry/` 对该脚本**零调用点**。
2. ❌「缺口修法二选一 —— lint 逐条比对，或钉 `git://`」→ 顺序错了。`--report` 实测全库存量债
   （登记批读数 **1,882 条 mismatch / 329 个 BET**）。**当时的括号注解「本 BET 与 T10-213 各 0 条」
   是过期读数，closeout 批复跑已否证**：那次 `--report` 跑在登记批编辑
   `2026-09-29-projection-plane-phase2-pr3-closeout.md`（`b24c353c3` 里 54/3）**之前**，而该报告一被
   编辑，T10-213 的 5 条 receipt 立即陈旧 —— 那就是 G2。现在复跑：T10-212 **0 条**（本 BET 的修复项，
   已归零）、T10-213 **5 条**、T10-214 **6 条**（本报告摘要在编辑中，属本批瞬态，见 §4 同类）——
   摘要回钉后复跑降至 **0 条**，全库从 1,893 条 / 331 个 BET 降到 **1,887 条 / 330 个 BET**。
   把它直接做成仓级硬门禁会让 CI 第一天就红。**先量存量债，再接线**：
   ① 按 diff 范围核对（只查本 PR 触碰的文件被哪些 receipt 引用）；
   ② 存量走 `gate-known-debt.yaml` 登记；
   ③ 新 receipt 优先钉 `git://<commit>:<path>`（该脚本本来就跳过 `git://`，不制造新比对债）。

## 3 我自己复现了本 BET 要修的那一类缺陷（C7 的来源）

`BET-Y2Q4-T10-214.verify[0]` 初稿写成 `uv run --with pyyaml python -m pytest
tests/test_sync_bet_digests_integrity.py -q` —— **`No module named pytest`**，
正是 §1 第 2 条描述的缺陷类型，在登记修复它的 BET 时复发。按台账原样逐字复跑草稿命令时被抓到，
现在记录的命令实测通过。据此在 spec 增加 **C7**：本 BET 写进台账 `verify[].cmd` 的每一条命令，
都必须**在写入之前**从当前检出逐字执行一遍。

## 4 计数在交付过程中过期（已修正）

报告 §9-9 初稿写 `508 bets` 与「本批 diff 里 `- id:` 增删为 0」，那是**插入 `BET-214` 之前**的读数。
插入后：`bet-ledger.py lint` = **`OK -- 509 bets, 16 tracks, no errors`**；
交付 diff 里 `- id:` 为 **+1 / 删除 0**（新增的是 `BET-Y2Q4-T10-214`，`in_progress` 态，非 `done`），
`meta.total_bets` 由 `ledger-safe-insert.py` 按插入后 `len(bets)` **绝对派生**为 509
（脚本内注释禁 `old+1`：GAT-006 / #4189→#4201 实证「若 meta 已漂移，increment 只会把错误平移一位」）。
故 `META_TOTAL_BETS_DRIFT` 与 `BET_DONE_*` 均不触发。

## 5 边界与熔断的遵守（未做的事，及为什么）

- **未动 `BET-Y2Q4-T10-213` 的 5 条 receipt**。它们钉 `sha256:bd2ed573…`，本报告摘要一变即陈旧 ——
  这是**计算结果而非推测**。不动它是因为 T10-212 的 `circuit_breaker` 把
  「backfill of lifecycle evidence for any other bet」列为停止条件；越界改别人的 evidence 比
  留一条可复现的陈旧指针更贵。登记为 **G2**，并给出接手所需的精确两个值（旧 `bd2ed573…` →
  新 `15ba278f44b1f…`，即本报告所引 PR-3 摘要）。
- **未新增 CI 检查、未改 `bin/plan/bet-ledger.py`、未改任何 `.github/workflows/**`**（spec §3）。
- **未动 `.omo/state/**` 与 `BRIEF.md`**：跑门禁期间 hook 把 `.omo/state/system.yaml` 的
  `health_score_evidence_generated_at` 从 `2026-09-27T08:42…` 推到 `2026-09-29T11:27:30`（1 行），
  交付前 `git checkout --` 剔除，最终 diff 里生成态 0 文件（#4346/#4359 同条纪律）。
- **未重写 §9 第 6 条**（C4）：那条是并发 PR #4544 对 workflow run 时间线的事实更正，
  逐字节比对 `origin/main` 与 `HEAD` 两侧**一致**（本批报告被编辑三次，每次都重验）。
- **未改 T10-212 的 `status`/`done_at`/spec binding/retro**（C5）：`status: done`、
  `done_at: 2026-09-29`、`merged_reachable_commit: git://origin/main@ebea1fd187…` 原样。

## 6 验证（合并后在 main 上复跑，非交付前读数）

| 判据 | 命令 | 结果 |
|---|---|---|
| C1 receipt 逐键一致 | 读台账，对每个 `receipt://`/`repo://` 键比 `sha256` 与文件字节（已落地的取 `git show origin/main:` 的字节，本批新引入的取工作树字节） | 登记批读数：T10-212 **8/8 match**，T10-214 spec binding **1/1 match**，合计 9 match / 0 mismatch / 0 missing。closeout 批终态读数（报告摘要重算并回钉之后）：**T10-212 8/8、T10-214 8/8**（1 spec binding + 7 receipt 键），`sync-bet-digests.py --report` 对这两个条目各报 **0 条**；T10-213 仍 5 条（= G2，别人的活） |
| 台账可读 + 计数 | `python3 bin/plan/bet-ledger.py lint` | 登记批读数：`OK -- 509 bets, 16 tracks, no errors`，`meta.total_bets: 509` == `len(bets)`。closeout 批复跑：`meta.total_bets == len(bets)` 仍成立，但**全局 `no errors` 已被别人的铸造证伪** —— 10 条 ERROR 全部属于 `BET-Y2Q4-T4-06`（#4564 铸造：spec 文件未落地 + 7 条 receipt ref 不解析 + 由此推出的 `OVERALL_STATE_MISMATCH`/`BET_DONE_REQUIRES_DELIVERY_ACCEPTED`），而本 BET 修的 T10-212/T10-214 两侧 **0 条 ERROR**。故 `verify[2]` 从"整仓 OK"改成**逐条归属判据**，T4-06 登记为 §8 G7 |
| C2 verify 可逐字跑 | 台账 `verify[].cmd` 原文执行 | `3 passed`（`test_sync_bet_digests_integrity.py`）、`18 passed`（`test_projection_reader_resolution.py`） |
| C3 无死锚 | 报告终节为 §9，`expect` 指向 §9 第 8 条 | 无 `§10` 引用 |
| 合并树无冲突/无回退 | 只读 `git merge-tree --write-tree` 对推进后的 `origin/main` 探测；合并后比对 bet 集合 | 干净；登记时点 main bets == 分支 bets，重复 id 0，差异**只有** `BET-Y2Q4-T10-214` 新增 |
| 门禁 | `make gac-local-gate` | 登记批读数：PASS（69 checks，6 项 known-unavailable skip），lane = `docs` + `docs_data`（`bin/change-lane-check.py --staged`）；closeout 批读数见 §6.1 |
| 安全 | L3 深度评审（提交态变更集） | 无发现 |
| CI | `gh pr checks 4561` | 全部 pass（`doc-freshness` 与一个 docs domain job 按 `on.paths` skipping），合并前零非 pass 项 |

### 6.1 closeout 批次（本 retro/report/台账面所在交付）的门禁读数

本 BET 的契约是"不把不可验证的断言写进持久证据"，因此对 `verify[5]`
（"no new hard failures relative to baseline"）逐条分诊，而不是把它当噪音跳过：

| 读数 | 分类判据（同机同内容，只换调用方式或基线） | 定性 |
|---|---|---|
| `check-evidence-freshness` FAIL | 单跑返回 `detail: No module named 'pydantic'`、`source: bin/gac/evidence-smoke.py (partial: agora import failed)`、`report_path: None`；**零改动的 pristine 安装位 clone**（`~/.local/opt/omostation`，detached `1b5f02cb3`）同样 `score=50` | 环境缺依赖，非本批引入 |
| `governance-semantic-gate` → `service-config-drift` FAIL | 同一 worktree 同一内容：`uv run python bin/mof/gen-service-configs.py --validate` → 1 条 `omostation.morning-brief: interpreter 含 uv 临时路径 …/builds-v0/.tmpDtiDHB/bin/python3`；裸 `python3` 同命令 → `ok: true, violation_count: 0`。`.tmpXXXX` 每次调用都换 | 调用环境产物，非仓内事实（详见 §8 G6） |
| `change-lane-check --staged` FAIL `mixed lanes=docs,docs_data,governance_state` | 读 `bin/change-lane-check.py`：`ALLOWED_COMBOS` 含 `{docs, docs_data}`（`:19`），而 `governance_state` 参与混合即拒（`:207`） | 真实约束，按 lane 拆 commit 解：台账+报告一 commit，retro 单独一 commit |
| `check-work-landed` / `auto-fix-loop` / `doc-governance` / `check-conflict-markers` 在批量门禁里 FAIL | 四条单跑全部 exit 0 | 并发负载/超时抖动，非失败 |

**本批还修了自己台账条目里的一处死锚**（正是本 BET 要修的那一类，出现在我自己的 `verify[3]` 上）：
原 `verify[3]` 是 `git diff HEAD --numstat -- docs/plans/3y-bet-ledger.yaml`，
期望"只出现 T10-212 verify 块 + 6 条 report receipt + 新条目"。合并后在 `main` 上逐字重跑，
该命令返回**空输出**（工作树干净），期望永不可验 —— 它只在"提交前一刻"有意义。改法不是放宽措辞，
而是把判据钉到**已落地的 commit** 上，两条批次各自可验：

- `verify[3]` → `git show --numstat --format= b24c353c3 -- docs/plans/3y-bet-ledger.yaml`
  （登记批，`b24c353c3` = #4561 squash 落地 SHA）
- `verify[6]` → `python3 bin/plan/bet-ledger.py show BET-Y2Q4-T10-214`
  （closeout 批，判据是**条目自身的状态**：`status: done` + `done_at` + 7 条 verify +
  6 条 `write_surfaces` + `completion_evidence.overall_state` 求值为 `delivery_accepted`）

判据固化（三级，本批实测逐级收紧）：**①「diff 工作树」合并后必然不可验** —— 工作树干净，命令返回空。
**②「钉 commit 范围」（`b24c353c3..HEAD`）仍不可靠** —— 范围会把 base 漂移期间别人落地的 commit
一起算进来：实测该范围的台账 diff 里含 `BET-Y2Q4-T4-06`（#4564 铸造）的条目行，而那些行不是本批写的
（故此处刻意不写 numstat 数字 —— 它随下一条 mint 过期，同 ④）。
**③ 只有两种形态能在任意时刻逐字复验**：单个落地 commit 的自 diff（`git show --numstat <merge-sha>`，
squash 合并保证它恰等于本批）与对已落地内容的**结构断言**。登记批的合并 SHA 已知 → 走 ③ 前者；
closeout 批写条目时自己的合并 SHA 还不存在 → 走 ③ 后者。
**④ 全局性判据不能写进条目级 verify** —— "整仓 no errors"、写死的 bet 计数都会被别人的铸造证伪，
而证伪时本批并没有错：实测 `lint` 在 main 上因 #4564 的 `T4-06` 报 10 条 ERROR（§6 表 + G7）。
判据形态因此改成**逐条归属**。改前后逐条比对：其余条目 parse 后与原文件
**逐项相等**，`- id:` 边界计数不变。

### 6.2 closeout 批的台账重对齐（base 漂移，实测驱动）

登记后 `origin/main` 前进 5 个 commit，其中 **#4564 铸造 `BET-Y2Q4-T4-06`** —— 与台账同文件。两点后果：

1. `meta.total_bets` 在 main 上是 **510**、我的分支 509。`verify[2]` 若把数字写死，就会随并发 mint
   变成假红，故改为 `<N>` + `meta.total_bets == len(bets)` 的一致性判据（"计数"类期望同理不可写死）。
2. 台账 blob 必须重对齐到 main 再交付：未对齐时 `git diff --numstat origin/main -- <台账>` 是
   `43 / 74` —— 那 74 行就是别人刚铸的条目，squash 合并会把它抹掉。做法是取
   `git show origin/main:<台账>` 为底，只把 `BET-Y2Q4-T10-214` 条目段替换为终版，然后断言除
   T10-214 外其余 509 条 parse 结果与 main **逐位、逐项相等**，非 `bets` 的每个顶层键不变。

**这一批我自己踩到的边界**：第一次替换用"下一个 `- id: ` 锚点"当条目终点，而 main 里 `bets` 段最后
一个条目后面紧跟顶层键 `campaigns:`，于是 `campaigns:` 那行被当成本条目的一部分搬走，把 `T4-06`
挤进了 `campaigns` 段 —— AGENTS.md「bets 序列被顶层键切断，盲插会把条目塞进错误段落」记录的那类事故，
用"锚点感知"的写法仍复现了一遍。判据：条目终点 = **下一个 col-0 `- ` 项** 与 **下一个 col-0 顶层键**
二者取先；替换后 `[b['id'] for b in bets]` 必须与 main 逐位相等。

## 7 回滚

单 commit `18c64e3b0`（squash 后 `b24c353c3`），4 文件全为文档/台账，无代码、无 CI、无生成态：
`git revert --no-commit b24c353c3` 即回到修复前状态。回滚的后果是**可预期的**：T10-212 的 6 条
report receipt 重新变陈旧、`verify[0]` 重新跑不起来 —— 即回到本 BET 要修的起点；
`BET-Y2Q4-T10-214` 条目消失且 `meta.total_bets` 减 1（该值由 `len(bets)` 派生，不会留偏；登记时点 509→508，main 现因 #4564 铸 `T4-06` 为 510）。
子模块指针未触碰，`git submodule status` 在 revert 后不受影响。

closeout 批次（本 retro/report/台账面）在它自己的 commit 里，回滚方式相同：revert 该 commit 会把
`completion_evidence` 退回 `overall_state: evaluating` / engineering `NOT_STARTED`、`status` 退回
`in_progress` 并去掉 `done_at`（这三项即 `origin/main@b24c353c3` 上的实际值）。它不携带任何代码或
生成态，因此单独 revert 不影响上面的修复。

## 8 后续项（登记，不在本 BET 修）

- **G1 receipt 摘要检测器存在但未接线**，且存量债巨大（登记批 1,882 条 / 329 个 BET；closeout 批
  终态 1,887 条 / 330 个 BET —— 净增的 5 条恰是本批编辑 PR-3 报告后 T10-213 变陈旧的那 5 条，
  即 G2；本批自己的 6 条在摘要回钉后归零）。两条读数都是瞬态，接线时以当时的
  `--report` 为准。接法见 §2 的三步顺序。
- **G2 `BET-Y2Q4-T10-213` 的 5 条 receipt 需从 `bd2ed573…` 重算为 `15ba278f44b1f…`**。
- **G3 `#`-静默截断**：`done_when`/`non_goals` 标量含 `" #"` 会被当注释吃掉后半段且无报错
  （T10-213 登记时实证，#4553 用引号修复）。新条目一律经 `yaml.safe_dump` 构造并**回读解析**核对。
- **G4 D0 表达不了删除类交付**：`bet-ledger.py complete` 要求每个 `write_surfaces` 字面量在主索引
  可解析，于是一次成功的摘库 BET 会被自己的成功证据判失败（PR-3 报告 §9 第 3 条）。
- **G5（本批新增）BET 登记时就该把 closeout 产物写进 `write_surfaces`**。本 BET 漏了自己的
  retro 与本报告，closeout 时扩面导致已绑定 work packet 漂移
  （`WORK_PACKET_SOURCE_DRIFT`），只能 `closeout --status blocked` 释放 docs 锁后起后继 run。
  对照 T10-212 的 26 条面里明确含它自己的 retro —— 这是可前置的规则，不是运气。
- **G6（closeout 批次新增）`omostation.morning-brief` 是唯一用裸 `python3` 声明 interpreter 的
  enabled 条目**，于是 `gen-service-configs.py --validate` 的答案随**调用方式**变化：`uv run` 下
  `shutil.which("python3")` 命中 uv 的 ephemeral build dir，触发 `resolve_interpreter` 的
  uv 临时路径守卫（`bin/mof/gen-service-configs.py:188`），`governance-semantic-gate` 因此在一棵
  干净的树上报 blocking 红；裸 `python3` 调用同一命令为 `ok: true`。实测注册表里 interpreter 规格
  分布：`stable-python3` 19 条、`python3` 1 条（就是它）。修法是一行改 `stable-python3`（别名在
  `:82`），但 `services.yaml` 不在本 BET 的 `write_surfaces` 内，且该红是本批交付的环境底噪，
  故只登记不顺手改。判据留给下一个人：**看到 service-config-drift 红先问"用哪个解释器调的"**。
- **G7（closeout 批次新增）`BET-Y2Q4-T4-06` 让 `lint` 在 main 上不再是 `no errors`**：#4564 铸造的
  条目绑定 `docs/superpowers/specs/2026-09-28-summary-four-sections.md`（该文件从未落地），7 条
  `completion_evidence` ref 不解析，由此派生 `OVERALL_STATE_MISMATCH: declared='delivery_accepted'
  derived='blocked'` 与 `BET_DONE_REQUIRES_DELIVERY_ACCEPTED`，`bet-ledger.py lint` 汇总为
  `10 个问题`（全部 owner = `T4-06`，本 BET 的 212/214 两侧 0 条）。不动它：本 BET 的
  `circuit_breaker` 把"给别的 bet 回填生命周期证据"列为停止条件，与 G2 同一条边界。接手要做的是
  补 spec 文件（或改 `spec_ref`）并把 7 条 ref 指向真实落地的 receipt —— 而这正是 G1 那条**未接线**
  的检测器（`bin/ssot/sync-bet-digests.py`）本该在登记时就拦住的形态。
