---
schema: md/v1
status: active
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-25
type: operations
created: 2026-09-25
scope: precommit-hook-registry-split
---

# 两份 hook 注册表的分裂（report-only，不处置）

> **状态更新（见 §6）**：本文写作时是 report-only；principal 选定选项 A 后，"把声明做诚实"
> 这一半已落地，B / C 仍未处置。原标题与正文的测量结论不改（当时的真值记录）。

> 结论先行：本仓有**两份互不重叠的 hook 注册表**。生效的那份是
> `.omo/_truth/registry/hook-manifest.yaml` → `bin/gac/hook-runner.sh`；
> `.pre-commit-config.yaml` 是第二份，它的 29 条声明**只有 1 条真正经过 pre-commit 框架执行**
> （`check-yaml`），其余 28 条的约束力完全来自"同样的命令在别处也跑了一遍"。
> 按这条判据量下来：20 条有直接消费者、2 条经 `governance-dashboard --tools` 传递可达、
> **7 条在根仓任何可执行面上都没有消费者**。
>
> 本文只报告测量与三个可选处置，不改任何配置：把 28 条声明变成真生效是大爆半径动作，
> 而给它加机器断言要动 `governance-checks.yaml` —— 两者都不在本 agent 的授权范围内。

## 1. 机制：为什么 `.pre-commit-config.yaml` 不是本地触发面

`core.hooksPath=.githooks`（本仓设置，机制 22c / BET-Y1Q4-T6-24，2026-09-06）。

| 环节 | 事实 |
|------|------|
| git 实际执行哪个 hook | `.githooks/pre-commit`（`git rev-parse --git-path hooks` → `.githooks`，不是真实 git-dir/hooks） |
| 它做什么 | `bash "$ROOT/bin/gac/hook-runner.sh" --hook pre-commit`，**不调用 `pre-commit`** |
| `hook-runner.sh` 读哪张表 | `.omo/_truth/registry/hook-manifest.yaml`（7 个 stage、27 条检查项，pre-commit 8 检查 + 1 advisory） |
| `hook-runner.sh` 里有 `pre-commit run` / `markdownlint` 吗 | 没有（13 个 `run_check` 名全是 hook-manifest 侧的 id） |
| 谁调用 pre-commit 框架 | 全仓可执行面里恰好一处：`.github/workflows/ci-lint.yml:102` `pre-commit run --all-files check-yaml` |
| 有 `pre-commit install` 吗 | 没有。而且即便装了也白装：`hooksPath` 已经把 `.git/hooks` 遮掉 |

两份注册表的 id 交集为空（脚本核过：`set(pre-commit ids) & set(hook-manifest ids) == ∅`）。也就是说它们不是
"一份的两种视图"，而是两套互不知情的检查声明。

## 2. 7 条在根仓无消费者的声明

快照：`HEAD = 7444a2d18`（含 `origin/main @ debf06d9c`）。

| hook id | 探测串（entry 里最具体的可执行令牌） | 备注 |
|---------|--------------------------------------|------|
| `health-ssot-consistency` | `bin/check_health_ssot.py` | 脚本存在，根仓无调用面 |
| `swarm-claim-check` | `bin/gac/swarm-discipline-cli.py` | CLI 存在且被 skill 文档大量引用，但不在任何 gate 里 |
| `mof-drift-check` | `bin/mof/mof-drift` | 可执行文件存在，无调用面 |
| `omo-doc-archival-suggestions` | `lint doc-archival-suggestions` | 同门其余 9 个 `lint <gate>` 都在 `governance-check.yml` 里，只漏这一个 |
| `markdownlint` | `pymarkdown` | 见 §4 —— 这条同时是"文档没说清"的源头 |
| `verify-spaces` | `bin/ssot/verify-spaces.py` | **声明已断**：该路径既不在盘上也不在 index 里，脚本只存在于 `bin/_archive/verify-spaces.py` 与 `bin/_archive/migrated_low_value/verify-spaces.py`（归档件）。这条不是"没人调"，是"调了必挂" |
| `mof-schema-validate` | `src/ecos/ssot/tools/mof-schema-validate.py` | 相对 `projects/ecos`（文件在子模块内存在）；根仓无调用面 |

**测量边界（必须一起读）**：语料集是根仓的 `.github/workflows/**` + `Makefile` +
`.omo/_truth/registry/ci-surfaces.yaml`。子模块（`projects/omo` / `projects/ecos`）**自带的 CI** 不在语料内，
所以 `mof-schema-validate`、`omo-doc-archival-suggestions` 这两条可能在子模块内部是被执行的；
"根仓无消费者" ≠ "全系统无消费者"。另外 `advisory`/`suggestions` 语义的检查本来就不该阻断，
无消费者未必是缺陷，可能是有意的软提示。
7 条里 entry 目标脚本**真实存在**的是 4 条：`bin/check_health_ssot.py`、
`bin/gac/swarm-discipline-cli.py`、`bin/mof/mof-drift`、以及 `projects/ecos` 内的
`mof-schema-validate.py`；`markdownlint` / `omo-doc-archival-suggestions` 走的是
`-m` 模块形式（无脚本路径可查）；只有 `verify-spaces` 是断链。
（注意别把传递可达那 2 条 `x2-rule-lint` / `mof-m2-coverage` 混进这 7 条 —— 它们经
`governance-dashboard --tools` 有消费者。）

**本次自测里另有一条未解释观察**：对同一个新增文档跑
`gac-local-gate --scope files --file <doc> --json`，第一次 `ok=false`，随后两次 `ok=true`
（`hard_fails=[]`，68 项检查零失败）。第一次的原始 JSON 因为当时被我管道进了解析脚本而没有留档，
所以现在无法指认是哪一项。n=1 且证据未保存，**不据此断言 gate 抖动**，只记录这个不可追的观测本身
—— 这与 I5 记的"run record 随 worktree 销毁"是同一类灭失：命令式测量若不重定向落盘，结论就不可复核。

复跑判据（同一 HEAD 上应得到 20 / 2 / 7）：对每条 hook 取 entry 里最具体的令牌
（`lint <gate>` 取 gate 名；否则取 `bin/…` 或 `scripts/…` 路径；否则取 hook id），
在上述三个面里做字符串包含检查；再把 `governance-dashboard --tools` 名单作为第二跳。
探测串粒度是这份数据唯一的敏感变量 —— 本轮用 `projects/omo` 当令牌会得 22 条可达、
用 `…/mof-m2-coverage.py` 得 19 条不可达，只有换成本表这一粒度才稳定。**引用这类计数必须带判据**。

## 3. 顺带纠一条历史留痕（不删原文，只标注）

- `.omo/_knowledge/audits/2026-06-28-debt-status-delta.md:25` 把"pre-commit 钩子全部失效"标成已解决
  （"`pre-commit 4.6.0` 已安装，26 个 hooks 注册生效，`pre-commit run` 可达"）。
  该结论在 22c（2026-09-06）落地后**静默失效**了 —— 注册生效 ≠ 有触发面，`pre-commit run` 可达 ≠ 有人调它。
  这条历史审计不改（它是当时的真值记录），但引用它的人会拿到过期结论。
- `.omo/DOC-LIFECYCLE.md:237` 仍把 `.pre-commit-config.yaml:omo-doc-lifecycle-gate` 描述成一条**生效的**
  pre-commit 钩子。实测该 gate 的检查内容确实在 `.github/workflows/governance-check.yml` 里跑
  （`lint doc-lifecycle`），所以**约束没丢**，丢的是"本地提交时拦截"这个承诺。

## 4. 本轮自查：同一个口径错误第四次命中我

写这份报告前，我在上一轮复盘里断言"本仓没有任何 markdownlint"，依据是只 grep 了
`.github/`、`bin/`、`Makefile` 三处。这条断言是错的 —— `.pre-commit-config.yaml` 明确声明了
`markdownlint` hook。同一轮里我给出的"14 条无消费者"也是判据未定的产物（换三次判据得到 14 / 19 / 22 / 7）。

前几次是台账与 run record 的计数口径，这次是**我自己写复盘时的口径**。四次的根因同一个：
引用记住的数量，而不是重新解析快照。故 §2 末把判据写进正文，而不是只写数字。

已落到指令层的对策（本 PR 的另一半）：`ci-red-triage` skill 与 p75 pattern 现在写明 markdownlint 的
真实工具（Python `pymarkdown`，不是 node `markdownlint-cli`）与真实 `files:` 作用域
（只 `README|CLAUDE|AGENTS|ARCHITECTURE|LAYER-INDEX`，`docs/**` 故意不 lint）。
我上一轮就是拿 node `markdownlint-cli` 去 lint 一个 `docs/` 下的文件，收到 20+ 条本仓根本不承认的 `MD060`。

## 5. 三个可选处置（等 principal 定）

| 选项 | 动作 | 半径 |
|------|------|------|
| A | 承认现状：把 `.pre-commit-config.yaml` 顶部注释改成"声明表 / 仅 check-yaml 经框架执行，其余由 ci-surfaces 承担"，并删掉 `DOC-LIFECYCLE.md` 里失效的本地钩子承诺 | 小；只改文档，不改约束力 |
| B | 让框架真生效：`hook-runner.sh` 增加一步 `pre-commit run`，或去掉 `core.hooksPath` | **大**；28 条声明瞬间变成本地硬闸，存量债会立刻挂（含 §2 的 7 条与 ruff/markdownlint 存量噪音），且违反"不擅自改 git config" |
| C | 收敛成一份表：把 §2 的 7 条按"该不该有消费者"分流 —— 该生效的接进 `ci-surfaces.yaml`，纯软提示的从声明表移到 `bin/_registry/scripts/` 登记 | 中；要逐条判断 owner，且动 registry 需授权 |

我的建议是 **A**：当前真正缺的不是检查，而是"声明表在 advertised 一个它没提供的保证"。
A 用最小改动消灭下一次误判，且不会把存量债一次性引爆。B/C 都需要先量存量红多少条。

## 6. 处置结果（2026-09-25，principal 选 A）

| 动作 | 落点 |
|------|------|
| 顶部注释改成"声明表 / 全仓唯一框架调用是 `ci-lint.yml` 的 `check-yaml` / 其余执行面由 `ci-surfaces.yaml` 承接"，并删掉 `Installs: pre-commit install` 与假设性的 per-commit 性能承诺 | `.pre-commit-config.yaml` |
| §关联 里"pre-commit 钩子"这条失效承诺改成并列两条：真强制面 `governance-check.yml` 跑 `lint doc-lifecycle`，与"声明表条目（非生效钩子）" | `.omo/DOC-LIFECYCLE.md` |
| 把"verify 失败先分诊 → 预存则 `--status blocked` 如实入账 → 禁自签豁免"写成指令层规则 | `.agents/skills/bet-closeout-chain/SKILL.md` |

**有意留在 A 之外**：§3 的历史审计 `.omo/_knowledge/audits/2026-06-28-debt-status-delta.md` 按其时点
真值保留、不改写；§2 的 `verify-spaces` 断声明与无消费者条目属 B/C 范围，动它们之前要先量存量红；
B（真接框架）还额外撞"不擅自改 git config"这条约束。

