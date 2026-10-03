---
schema: md/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-10-02
type: report
bet_id: BET-Y2Q4-T10-221
title: BET-Y2Q4-T10-221 closeout — 两根写面收敛轮的仓库事实与判定装置性质固化进 agent 感知面
---

# BET-Y2Q4-T10-221 closeout — ADR-0456 F3 感知固化

契约：`docs/superpowers/specs/2026-10-02-bet-221-two-root-write-plane-perception.md`
（v1.0.0，`status: accepted`，`lifecycle: contract`，digest
`sha256:feae56363371fb7a07b2a662b575b5106823204b2da29cd38d49752497a00ccd`）。
交付：主仓 PR #4608（squash → `origin/main@3225290e9cdadd01d3435e06f2cecca9621dc6f5`），
3 个 commit 按 lane 拆分：`5c972b441`（ADR-0456 附录）/ `e8c32e0dd`（AGENTS.md §7 + spec + 台账）/
`af05f21fd`（台账 verify-1 命令修正）。
run：`20261002T093828Z-project-doc-change-5991e571`（governance-agent）。
复盘：`.omo/_knowledge/retros/BET-Y2Q4-T10-221.md`。

## 1 一条契约命令被自己的执行否证 —— 这是本轮最有价值的产出

台账 verify 第 1 条（指针解析检查）第一版写成这样：

```python
pts = sorted(set(re.findall(r'([A-Za-z0-9_./-]*\.(?:py|md|yaml|json|sh|asset|gitignore)):[0-9]+', …)))
bad = [p for p in pts if not pathlib.Path(p.split(':')[0]).exists() or int(p.split(':')[1]) > …]
```

`re.findall` 在模式含**一个**捕获组时只返回该组内容，返回的 `pts` 因此是**不带 `:NN` 的路径**，
`p.split(':')[1]` 当场 `IndexError: list index out of range`，rc=1。

这个 rc=1 完全可以被读成"契约引了一个不存在的行" —— 也就是本轮刚写进 AGENTS.md 的那条"文字漂移"
的形状 —— 于是会去改文字，而真相是**测量装置坏了**。区分两者只花一次执行：把命令跑一遍看 traceback。

同一条教训在同仓已有正确实现：T10-215 的同名检查命令写成**两个**捕获组并解包
（`bad=[f'{p}:{l}' for p,l in pts …]`，台账 `:38692`）。我没抄邻居、重新造了一个，于是重造了一个 bug。
这与本轮固化进 AGENTS.md 的「新文档 frontmatter 抄同批已绿的邻居，不抄 checklist」是同一条纪律在
**命令面**的版本。

顺带查出一个静默漏洞：扩展名 alternation 里没有 `yml`，而本轮新写的指针里有
`governance-check.yml:118` —— **一个"通过"的指针门禁可以只是没看见东西**。修正同时补上 `yml`。

## 2 交付形状：感知面三条线，零 `.py`

| 面 | 落点 | 内容 |
|---|---|---|
| agent 每次编辑前读的 | `AGENTS.md` §7 | 5 条带日期带指针的仓库事实（见 §3） |
| 架构契约本体 | `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md` | 追加一节 Addendum（两根读面命名不对称 + `system.yaml` 反选） |
| 台账 | `docs/plans/3y-bet-ledger.yaml` | T10-221 条目 + spec 绑定（`content_digest` 逐字节对得上） |

`git diff --name-only origin/main...HEAD | /usr/bin/grep '\.py$'` 为空 —— 本轮不动任何脚本，
所以它不改变任何运行时行为，只改变下一个 agent 的判断成本。

## 3 写进契约的五类读数（每条都实测过，不是推断）

| # | 读数 | 为什么值得固化 |
|---|---|---|
| 1 | 声明的 17 条投影路径里，`origin/main` 只跟踪 **1** 条，且那条是权限面 `.omo/_truth/registry/memory-os.yaml`；16 条被忽略 | 「已提交的 legacy 兜底」不是这份仓库的性质。`projection_read()` 的兜底分支（`bin/lib/repo_root.py:201`）只在**跑过写者的检出**里存在，新克隆上它指向一个既不在 git、也不在磁盘的文件 |
| 2 | `1 failed, 1 passed`（不是"两个红"） | 红的那条按构造不可满足：期望目标 `.omo/state/health.yaml` 被 `.gitignore:411` 显式忽略且未跟踪，而被测的 `projection_path()` 是**写侧**解析器、本就不做读兜底；绿的那条之所以绿是 fixture 自己写出了 legacy 文件 ⇒ 纪律：**测兜底先物化** |
| 3 | `R-GOV2-WARN-only 159`（处理函数只 `warnings.append`，`errors` 初始化后原样返回） | 拆掉跨键复制不会把门禁变红，不需要先登记 known-debt —— 关掉"诚实化有风险"这个错觉 |
| 4 | CI 的 pytest 面是显式文件白名单（`governance-check.yml:118`–`:127`），不含 `tests/unit/**` | 本地红不会在 CI 复现 ⇒ 别把 CI 绿当"没有红"，也别说"CI 抓不到所以不算债" |
| 5 | `change-lane-check`：`.omo/**` 归 governance_state（`bin/change-lane-check.py:141-142`），且 `len(lanes) > 1` 直接拒（`:207-208`）；`ALLOWED_COMBOS`（`:14-21`）里没有任何含 governance_state 的组合 | 一个 4 文件的感知 PR 必须按 lane 拆 commit，否则本地门禁红 —— 而 `.github/workflows/` 与 `.githooks/` 对它的引用实测**零**，#4608 跨 PR 混 lane 的 `gac-gate` job 仍 pass ⇒ 它是本地 `--scope staged` 形状的门禁，不是 PR 形状的门禁 |

ADR-0456 那节记录的是另一族：`projection_read()` 兜底**换文件名**、`state_file_read()` 兜底
**换根不换名**，两条缝不是同一条契约；`:217` 的 env 闸门与"三个写者都不凭空造镜像"
（`bin/gac/evidence-smoke.py:239`、`bin/compass_radar.py:1415`、`bin/gac/harness-omo-bridge.py:193`）
是"整份文件优先 state 根"成立的**前提**，一旦有人改成写子集，读侧静默读到残缺状态且没有任何测试会红。

## 4 判据实测（7 条 verify 全部跑出声明的读数）

| # | 读数 | rc |
|---|---|---|
| 1 | `38 pointers, bad=[]` | 0 |
| 2 | `paths=17 tracked=['.omo/_truth/registry/memory-os.yaml'] ignored=16 generated_tracked=[]` | 0 |
| 3 | `1 failed, 1 passed`（`tests/unit/test_repo_root_profile.py:150: AssertionError`） | 0 |
| 4 | `R-GOV2-WARN-ONLY 159` | 0 |
| 5 | `git diff --stat origin/main...HEAD -- bin/README.md ARCHITECTURE.md` 空 | 0 |
| 6 | 分支增量里 `.py` 路径空 | 0 |
| 7 | `doc-governance-check: PASS (4539 files, 146 warnings)` | 0 |

`gac-local-gate --scope staged` 三个 lane 分片各跑一遍：68–69 checks PASS，1 SOFT WARN
（KOS db 缺席，exit 78 = skipped，非本轮引入）。CI 20 项 checks 全绿。

## 5 生成态剔除（一次，不是零次）

跑 gate 会让 `bin/gac/evidence-smoke.py` 在**未声明 profile** 的 worktree 里改写检出的
`.omo/state/system.yaml`（`health_score_evidence_generated_at` 纯时间戳）—— 这正是 D1 之后
仍存在的形状：`state_root() == code_root()` 时写者落检出自家。每次 commit 前
`git checkout -- .omo/state/system.yaml`，最终 `git diff --name-status origin/main..HEAD`
只有 4 条（3 M + 1 A），零生成态。

## 6 合并后的回读失败不是合并失败

`gh pr merge 4608 --squash` 报 `Post "https://api.github.com/graphql": net/http: TLS handshake timeout`
且 exit 1 —— 但它发生在合并**之后**的状态回读上。判据是
`gh pr view --json state,mergedAt,mergeCommit` → `MERGED / 2026-10-02T10:20:01Z / 3225290e9`。
按 AGENTS.md §7 既有的"合并本身发生在失败之前"同一条读数处理：确认 MERGED 再继续，不重跑一轮合并。

## 7 回滚

单个 PR、纯文档，无运行时副作用（不改脚本、不改 plist/cron、不改任何写落点）：

```bash
git revert --no-edit 3225290e9cdadd01d3435e06f2cecca9621dc6f5   # 感知面 + ADR + spec
# 台账：BET-Y2Q4-T10-221 的 status 从 done 改回 pending、done_at 置空、completion_evidence 回占位矩阵
```

## 8 未做（避免被读成已做）

- **没翻 ADR-0456 的 `status`**（仍 `PROPOSED`）—— PROPOSED→ACCEPTED 属 principal 决定，非本轮范围。
- **没动 `!.omo/state/system.yaml` 这条反选本体**（`.gitignore:294`）—— 摘它要连带 7 个读侧读者与
  R-GOV-2 门禁同批改，属独立一轮；本轮只把"为什么这块比投影面难"写清（仍挂 task #98）。
- **没修 `tests/unit/test_repo_root_profile.py:150` 那条按构造不可满足的断言** —— 本轮只固化它的
  性质；修它属 T10-212 摘库残面（task #105）。
- **没登记 known-debt** —— §3-3 的读数说明 R-GOV-2 结构上只会 WARN，没有可登记的债。
- 8 个 out-of-surface 读者、`OMO_GOVERNANCE_DATA` 仍钉检出根、`projects/runtime/scheduler.py`
  的 D7 一条，均未触碰。
