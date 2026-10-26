---
schema: md/v1
status: completed
lifecycle: report
type: closeout-receipt
owner: governance-team
last-reviewed: 2026-10-26
bet_id: BET-Y2Q4-T10-270
---

# BET-Y2Q4-T10-270 收口 receipt — 三类静默失效形状固化进 agent 感知面

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-270`
规格：`docs/superpowers/specs/2026-10-26-bet-270-detector-base-and-digest-refresh-discipline.md`
固化腿：PR #4897 → squash `9c7d2c0fd51c41390ffc0149a62da59044159ed5`（分支 commit `56e675d6e`，3 文件 +284/−7）
收口腿：分支 `agent/governance-agent/bet270-closeout`（session `bet270-closeout`），run
`20261026T031459Z-project-doc-change-b3012366`

## 0 交付性质（先说边界）

纯文档 lane。零 `bin/` 与 `projects/*` 改动、零 gitlink 变化、本机 launchd / crontab /
`services.yaml` / `~/Library/LaunchAgents` 一行未动。准入判据沿用 T10-221 / T10-225
（复发 ≥2 次或当场让安全网静默失效，且有不依赖本机状态的指认方式）。

## 1 三条形状落位（`AGENTS.md` §7，每条证据→判据→纪律三段齐）

| 锚点（§7 条目首句特征串） | 固化的静默失效形状 | 不依赖本机状态的指认方式 |
|---|---|---|
| `尺本身会随 base 变` | 门禁读数差来自**检测器自身随检出变**：`bin/gac/check-work-landed.py` 以 `WORKSPACE = Path(__file__).resolve().parents[2]` 定根，每个检出跑自己那份 | 比较两次读数前先 `git diff --stat <baseA> <baseB> -- <脚本>`；非空 ⇒ 读数不可比 |
| `同一 BET 块内的上游排版重排` | 台账里 YAML plain scalar 换行重排落在同一块内 ⇒ 两侧语义无关却结构性冲突；`CONFLICTING` 态下 `gh pr checks` 零排队 | `gh pr view --json mergeable,mergeStateStatus` 先看；`git diff --name-only "$(git merge-base HEAD origin/main)" origin/main -- <ledger>` 非空 ⇒ 起手就换底 |
| `按字段路径定位` | 摘要刷新按「值不等于新值」反选 ⇒ 误改 `accepted_specifications[*].content_digest`（规范绑定摘要，绝不该动） | 按两类互不相交的键路径分别枚举，写回后**同时**断言两件事（证据位 = 磁盘文件、`content_digest` = spec 字节） |

顺带修掉 §6 的三处陈旧行号指针（旧：`gac-worktree.sh:507` / `:683-691` / `:780-783`；
新：`_emit_managed_successor_proposal()` 定义 `:967`、打印 `:978`、`exit 2` `:985`；
`gh pr list` `:1241`、「先 submit 开 PR」`:1244`；WP1 Wave B2 注释 `:966` 与 typed 指令 `:994`）。

## 2 收口腿的实修：判据 ② 被我自己误读过一次，措辞已收回感知面

固化腿提交后我跑 `git diff --name-only HEAD origin/main -- docs/plans/3y-bet-ledger.yaml AGENTS.md`
得到两个文件名，读成「上游动了我的对象」。实测否证：

- `git log --oneline HEAD..origin/main` → 空
- `git merge-base HEAD origin/main` → `f0c5ce934`，与 `origin/main` 同一对象 ⇒ 上游零漂移
- `gh pr view 4897 --json mergeable,mergeStateStatus` → `MERGEABLE` / `CLEAN`

即 `HEAD origin/main` 把**我自己的 commit 反向显示成上游改动**。原判据写的是 `<my-base>`，
在「起手 / 插入前」（分支零 commit）这一刻恰好等于 `HEAD`，规则本身不错 —— 错在把它搬到「提交后」。
因此本腿做了两件事：`AGENTS.md` §7 item ② 与 spec 判据正文**左端显式写成**
`"$(git merge-base HEAD origin/main)"`，并各补一句纪律：

> 判据里凡是依赖「当前分支还没有自己的 commit」这类隐含前提，必须在判据正文里显式写出左端到底是什么 ref。

spec 正文因此变化 ⇒ 规范绑定摘要必须重算（这正是 item ③ 说的两类互不相交摘要位）：

| 字段路径 | 固化腿绑定值 | 收口腿新值 |
|---|---|---|
| `accepted_specifications[0].content_digest` | `sha256:184df6af8d7242d7fe88bf7f4b79172f8397e83d75df261d231e09b4588396a4` | `sha256:ac69e229b63aabfaa90c2e517da942676dcd44e2a75f3c50464652855176c456` |

刷新方式：按字段路径单点写入（`content_digest` 只由 spec 字节导出），receipt/retro 的
`completion_evidence.axes.*.evidence.*.sha256` 各理由其自身文件字节导出；两组互不越界，
写回后双向断言（见 §3 第 3、4 行）。

## 3 验收（spec「验收」6 条逐条实测）

| # | 验收条款 | 实测读数 | 产出该读数的检出（item ① 的自用声明） |
|---|---|---|---|
| 1 | §7 含三条，每条带证据→判据→纪律 | `git show origin/main:AGENTS.md` 三个锚点各命中 1 次（`尺本身会随 base 变` / `同一 BET 块内的上游排版重排` / `按字段路径定位`） | `9c7d2c0fd`（合并后 main） |
| 2 | 条目点名的路径/符号/键名/PR 号可在当前 `origin/main` 解析 | verify-1 指名文件存在性 `missing=[]`；verify-2 行号内容断言 `bad=[]`、旧号残留 `stale_left=[]`；verify-3 `_emit_managed_successor_proposal` 内容命中 `True` | `9c7d2c0fd` |
| 3 | 新文档 frontmatter 齐备且 `owner` 在场，doc-governance 零未基线告警 | `doc-governance-check.py --no-new-warnings --scope tracked` → `PASS`，warnings 计数 **31**（与基线逐字未变） | 收口腿工作树（含 spec / receipt / retro 三面） |
| 4 | `bet-ledger.py lint` 零 error，`meta.total_bets` 与实测条目数一致 | `OK -- 566 bets, 16 tracks, no errors`；`meta.total_bets == len(bets) == 566`；重复 id `0`；上游 T10-267 的 `done 2026-10-26 delivery_accepted` 存活 | 收口腿工作树 |
| 5 | `gac-local-gate` 零 hard error，soft warn 逐条归因 | `--scope files` 对本批全部文件 → `PASS (68 checks executed, 2 SOFT WARN)`。归因：① `current-state-coherence` 缺输入 `.omo/state/system.yaml`（T10-235 摘库后是常态而非回归）② KOS db 缺席（exit 78 = 跳过） | 收口腿工作树 |
| 6 | 不改 `bin/`、不碰子模块、不碰本机 launchd/crontab/`services.yaml` | `git diff --name-status origin/main..HEAD` 仅文档面、`.py` 计数 `0`、`D` 行计数 `0`；本机面零触碰（本腿未执行任何 `launchctl` / `crontab` 写） | 收口腿分支 |

## 4 复算命令（判据全部可独立复核，不依赖本机状态）

```bash
# 三条锚点在 main 上可解析（验收 1）
git show origin/main:AGENTS.md | /usr/bin/grep -c "尺本身会随 base 变"
git show origin/main:AGENTS.md | /usr/bin/grep -c "同一 BET 块内的上游排版重排"
git show origin/main:AGENTS.md | /usr/bin/grep -c "按字段路径定位"
# 规范绑定摘要 = spec 字节摘要（验收 2 的摘要面）
python3 bin/ssot/doc-governance-check.py --no-new-warnings --scope tracked
python3 bin/plan/bet-ledger.py lint
python3 bin/gac/gac-local-gate.py --scope files --file <本批每个文件>
```

⚠️ 第 3 行的 `/usr/bin/grep` 不是笔误：本会话 shell 是 zsh 且 `grep` 别名为 `rg`，
裸 `grep -cE` 会把 `-E` 当编码参数（§7⑤ 同源）。

## 4.5 本腿遇到过的一次硬 FAIL（不是静默失效，如实记）

收口腿 5 个文件一次过 `gac-local-gate --scope files` 时**当场 FAIL**：

```
[FAIL] change-lane-check :: bin/change-lane-check.py --file …（5 files）
change-lane-check: FAIL mixed lanes=docs,docs_data,governance_state
```

定位用逐文件单跑（每条各自 `PASS`，读数 `lanes=docs` / `docs_data` / `governance_state`），
再读 `bin/change-lane-check.py:196 allowed_for()`：`:207` 是
`if "governance_state" in lanes and len(lanes) > 1: return False` —— **governance_state 必须独占一次提交**，
而 `ALLOWED_COMBOS`（`:14-21`）里 `{"docs","docs_data"}` 是合法并集（固化腿正是这一对，所以当时 PASS）。
处置按规则本身拆两次提交，而不是加 `--allow-lane` 或 `AGENT_WORKFLOW_ALLOWED_LANES` 自我授权：
`c18e04ea1`（AGENTS.md + spec + receipt + 台账，`lanes=docs,docs_data`，gate `PASS 68 checks / 2 SOFT WARN`）
与 `154e04151`（retro，`lanes=governance_state`，gate `PASS 68 checks / 2 SOFT WARN`）。
两条 soft warn 与固化腿逐字同名：`current-state-coherence` 缺 `.omo/state/system.yaml`（T10-235 摘库后的常态）、
KOS db 缺席（exit 78 = skipped，非 passed）。

同源的一次越界自纠：收口腿驱动脚本按行提取台账条目块时，块尾只找了下一条 `^- id: `，
而 T10-270 是 `bets:` 的**最后一项**、其后紧跟顶层键 `campaigns:` ⇒ 切片跨过边界，
`yaml.safe_load` 当场 `ParserError`（不是静默错值）。改为「下一条 `- id:` **或**任意顶层键」后正确。
这正是 AGENTS.md §6「bets 序列被顶层键切断」那条禁令的镜像面 —— 那条讲的是**插入**不能按行号盲插，
本轮补的是**提取**同一个块也会犯同样的错。

## 5 未做的事（与 spec 非目标一致）

- 未修 `check-work-landed.py` 的 `__file__` 定根行为（牵动 22 个本地检查的根语义，需另一次准入）。
- 未处理 `projects/family-hub` 浅克隆深度不一致（AGENTS.md §6 列为 claim 路径属性，非缺陷）。
- 未为 §7④「no checks reported」重新立条（本轮只补台账特有的触发形状）。
- **未宣布 ADR-0456 任何阶段（B1/B3/B4/B4b/B5）完成**，未宣布本 plan 收敛。

## 6 回滚

两条腿各自一次 revert 即可完全撤回（纯文档、零机器效应、零 gitlink）：
固化腿 `git revert 9c7d2c0fd`；收口腿 revert 其 squash commit。台账 `meta.total_bets` 由
`bin/gac/ledger-safe-insert.py` 按插入后 `len(bets)` 绝对写入，revert 后回到 565 / 565 自洽。
