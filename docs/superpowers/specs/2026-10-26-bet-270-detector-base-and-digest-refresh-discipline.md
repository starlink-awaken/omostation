---
schema_version: specification/v1
spec_version: 1.0.0
title: 门禁读数的「尺基线」与台账摘要刷新的定位纪律 —— 三类会静默失效的形状固化进 agent 感知面
bet_id: BET-Y2Q4-T10-270
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-26
---

# 目标

把 BET-Y2Q4-T10-267 收口腿实测暴露的三类形状固化进 `AGENTS.md` §7，使下一轮 agent 不必再靠一次
错误的因果归因才发现它们。准入判据沿用 T10-221 / T10-225：**复发 ≥2 次或当场让安全网静默失效，
且有不依赖本机状态的指认方式**。本 BET **不新增代码**，只改感知面文档与台账/规格/回执。

## 背景：为什么这三条值得进 §7

T10-267 的收口腿在两天内产出了两次互相矛盾的读数、一次结构性冲突、以及一次我自己写下的错误归因，
全部在**交付动作内部**发生。三条都有"当场就错、输出却完全正常"的特征，因此不能只留在 retro 里。

---

## ① 门禁读数差可能来自「检测器本身随 base 变」，而不是被测对象变

**证据（全部为本轮实测）**

- `docs/reports/2026-10-23-zhixing-external-dependency-contract-closeout.md` §5 的初版把
  `bin/gac/check-work-landed.py` 在两棵 worktree 上的读数差（`FAIL settled=112 warn=2 blocking=13`
  vs `PASS settled=127 warn=0 blocking=0`）归因为「两天里并发 agent 与 cron 把这些 run 的 landing
  补齐了」。该归因**未经测量即被写进交付文档**。
- 复测否证它：两棵 worktree 的 `RUNS_DIR` 都 `resolve()` 到同一份 canonical 目录、各 350 个 run 文件
  （`.omo/_delivery` 是 symlink 桥，AGENTS.md §7 T10-215 条）；根仓 `git rev-list origin/main` 两侧同为
  **8734**。被点名的 15 条 run 的 **16 个 sha 凭证在两棵树里都不在**任何仓的 landed 集合中 —— landing
  没有被事后确认。
- 真因：`bin/gac/check-work-landed.py:31` 以 `WORKSPACE = Path(__file__).resolve().parents[2]` 定根，
  ⇒ **每个 worktree 执行的是自己检出里那一份脚本**。`git show 51c9ed62e:bin/gac/check-work-landed.py`
  里 `RETROS_DIR` / `_bet_log_refs` 命中数为 **0**，`26a904504` 那份为 **7**；
  `git diff --stat 51c9ed62e 26a904504 -- bin/gac/check-work-landed.py` = **111 insertions(+)**，来自
  `eb3e48c34`「fix(gac): check-work-landed 加 BET 落地兜底…(#4885)」(2026-10-25)。
- 顺带量到、但**不是**本次判别量的第二面：`projects/family-hub` 的 `rev-list origin/main` 在两树分别
  **1** 与 **75** 条（浅克隆深度由 claim 路径决定，AGENTS.md §6）。它确实会让 landed 集合按检出变化，
  但本批 15 条无一落在里面。**"扫源码的门禁其覆盖面会随检出深浅变"这一面仍成立**，只是与本次读数差无关。

**判据**

- 比较任何两次门禁读数前，先跑 `git diff --stat <baseA> <baseB> -- <该检查脚本路径>`；
  **非空 ⇒ 两次读数不可比**，必须各带自己 base 分别记录。
- 行为化探测（不依赖记忆）：`python3 -c "import importlib.util as u;s=u.spec_from_file_location('m','<脚本>');
  …;print(hasattr(m,'<该检查的特征符号>'))"` 在每棵树上各跑一次；缺席 ⇒ 尺不同。
- receipt/retro 里任何门禁读数必须写成「读数 + 产出该读数的那份检测器所在的 base」。

**纪律**：这是 §7「凡两次探测结果不同，先疑基线动了」的加强版 —— 先前只教人怀疑**数据**基线，
本轮证明**动的可以是尺本身**，且本地专用检查（`ci-surfaces.yaml` 里 `workflow: (none)` + `triggers: []`）
最容易这样，因为它没有 CI 那份统一检出替所有人对齐尺。

---

## ② 台账里「上游把长标量重排」会让同块并发交付结构性冲突，且冲突态下 CI 根本不排队

**证据**

- PR #4892（T10-267 收口腿第一版，base `51c9ed62e`）实测 `mergeable=CONFLICTING` /
  `mergeStateStatus=DIRTY`，`gh pr checks` 零排队。冲突点不是新增行撞新增行，而是上游对
  `docs/plans/3y-bet-ledger.yaml` 做了 **YAML plain scalar 换行重排**，重排范围**落在同一个
  `BET-Y2Q4-T10-267` 块内**，于是我的 evidence 行与上游的重排行无法自动合并。
- 处置按既有先例 #4745 → #4749：本仓禁止用 rebase/merge/pull 吸收上游
  （`bin/gac/gac-worktree.sh` 的 `MANAGED_SUCCESSOR_REQUIRED` 发射点，本轮实测在 `_emit_managed_successor_proposal()`
  定义 `:967`、打印 `:978`、`exit 2` `:985`，AGENTS.md §6 原引的 `:507` 已陈旧并在本轮就地修正），
  因此**从当前 `origin/main` 重做受控后继**（本轮为 #4894），并把旧 PR 标注 superseded 关闭。
- §7④ 已记录「no checks reported 的第一因是 CONFLICTING」；本条补的是**台账特有的触发形状**
  （同块内的纯排版改动），它比"两侧同时追加尾项"更隐蔽，因为两侧 diff 语义上毫不相干。

**判据**

- push 后台账类 PR 先看 `gh pr view --json mergeable,mergeStateStatus`，再谈 CI。
- `git diff --name-only <my-base> origin/main -- docs/plans/3y-bet-ledger.yaml` 非空 ⇒ 视为高冲突概率，
  起手就按最新 `origin/main` 整份为底重做，而不是等冲突出现后再补救。

**纪律**：台账交付的基线新鲜度是**前置条件**而非补救项；受控后继是正解，rebase/merge 是违令。

---

## ③ 刷新台账里的文件摘要：必须按字段定位，不得按「值不等于新值」批量替换

**证据（本轮自伤，已检出并回退）**

- receipt 正文改版后，其在台账 6 个证据位的 `sha256:` 需同步。我写的驱动脚本用
  `stale = [d for d in 块内所有 64 位摘要 if d != 新receipt and d != 新retro]` 反选「陈旧值」，
  于是把 `accepted_specifications[0].content_digest`（`97d88876…`，**规范绑定摘要，与 receipt 无关且绝不能变**）
  也一并改成了新 receipt 摘要。
- 该错误形状与 §7③「按构造就绿」同族：脚本自己的成功断言（各 axis 摘要等于磁盘文件）**不覆盖**
  被误改的那一位，因为它不在被断言的集合里。检出靠的是额外补的一条**回读对拍**
  （`content_digest == "sha256:" + sha256(spec 文件字节)`），随后回退该单行，
  最终 `git diff` 恰为 6 处 receipt 摘要位、零其他改动。

**判据**

- 台账内 `sha256:` 出现的位置有两类且**互不相交**：`completion_evidence.axes.*.evidence.*.sha256`
  （随 receipt/retro 变）与 `accepted_specifications.*.content_digest`（随 spec 正文变，
  由 `bet-ledger.py complete` 的绑定校验强制）。刷新脚本必须**按这两类路径分别枚举键名**，
  禁止"块内出现即候选"的值匹配替换。
- 任何摘要写回后，必须**同时**断言两件事：每个 receipt/retro 位等于对应磁盘文件、
  `content_digest` 等于 spec 文件字节摘要；两者缺一即视为该次写回未完成。

**纪律**：把"排除法"用在标识符集合上是危险形状 —— 缺席的原因（本来就不同步）与命中原因（陈旧）
在输出里同形。这与 §7 T10-239 条「抽样探测的覆盖面上限是它的样本集」是同一根因的另一面。

---

## 验收（done_when 的可执行形态）

1. `AGENTS.md` §7 含这三条，每条都带**证据 → 判据 → 纪律**三段，且指认方式不依赖本机状态。
2. 条目内点名的每个文件路径、脚本符号名、YAML 键名、PR/commit 号，均可用 `git show` / `grep`
   在**当前 `origin/main`** 上解析命中（引用行号前先取该行内容核对，见 §7⑥）。
3. 新增的跟踪文档（spec 与本 BET 的 receipt）frontmatter 齐备且 `owner` 在场，
   `bin/ssot/doc-governance-check.py --no-new-warnings --scope tracked` 零未基线告警。
4. `python3 bin/plan/bet-ledger.py lint` 零 error，`meta.total_bets` 与实测条目数一致。
5. `make gac-local-gate` 零 hard error；已知 soft warn 逐条归因，不写「时序问题」了事。
6. 本 BET 不改任何 `bin/` 代码、不碰 `projects/*` 子模块、不碰本机 launchd/crontab/`services.yaml`。

## 非目标

- 不修 `check-work-landed.py` 的 `__file__` 定根行为（那是另一次准入：它牵动 22 个本地检查的根语义）。
- 不处理 `projects/family-hub` 浅克隆深度不一致（§6 已把它列为 claim 路径属性，不是缺陷）。
- 不为 §7④ 的「no checks reported」重新立条（本轮只是给同条补台账形状）。
- 不宣告 ADR-0456 任何阶段（B1/B3/B4/B4b/B5）完成。
