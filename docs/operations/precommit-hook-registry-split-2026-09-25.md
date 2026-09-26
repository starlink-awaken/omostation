---
schema: md/v1
status: active
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-26
type: operations
created: 2026-09-25
scope: precommit-hook-registry-split
---

# 两份 hook 注册表的分裂（report-only，不处置）

> **状态更新（见 §6–§8）**：本文写作时是 report-only；principal 选定选项 A 后，"把声明做诚实"
> 这一半已落地，B / C 仍未处置，但 §7 用 PR #4346 的 CI 实证把 B/C 的前置量（存量红的形状与条数）跑了出来。
> §8 是 2026-09-26 的后续：4 条断声明已就地标注（含"失踪 / 退役 / 假阳性"分型），
> known-debt 与 B/C 的主体仍在 principal 手上（原因见 §8 末）。
> 原标题与正文的测量结论不改（当时的真值记录）；§7.1 修正了 §2 判据漏掉的一个维度。

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

**有意留在 A 之外**：§3 的历史审计 `.omo/_knowledge/audits/2026-06-28-debt-status-delta.md` 按其时点真值
保留、不改写；§2 的 `verify-spaces` 断声明与无消费者条目属 B/C 范围，动它们之前要先量存量红；
B（真接框架）还额外撞"不擅自改 git config"这条约束。

## 7. B/C 的前置量已经跑出来了（PR #4346 的 CI 实证，2026-09-25）

本 PR 是 6 个文件、**零 `.py`、零 gitlink** 的文档/注释改动。CI 上 `Pre-commit hooks check`
（即 `pre-commit run --all-files`）**7 条 hook 全红**，而整份日志里指到我这 6 个路径的行数为 **0**
（逐路径 `grep -c` 各 0 命中，两个 head SHA 各量一次一致）。也就是说这 7 条红是 §5 里
"B 会立刻引爆存量债"的**实测样本**，不必等 B 落地就能看到存量红的形状。

| 失败 hook | 根因 | 与本 diff 的关系 |
|-----------|------|------------------|
| `port-hardcode-check` / `cross-deps-check` / `future-annotations` / `verify-spaces` | entry 指向的脚本**在 main 上根本不存在**（见 §7.1） → `python3: can't open file …: No such file`，exit 2 | 无关 |
| `health-ssot-consistency` | `system.yaml 缺 health_score_ref 字段`（`bin/check_health_ssot.py`） | 无关；main 现状同缺 |
| `ruff` | 根仓 13 个 `bin/**.py` 的 E741 / F405 等存量（`check-pitfall-gat006.py`、`repo-health-metrics.py`、`session-handoff.py` …），且该 hook 带 autofix → CI 额外报 `files were modified by this hook` | 无关 |
| `markdownlint` | 只命中根文档：`CLAUDE.md` 39、`AGENTS.md` 33、`README.md` 18、`ARCHITECTURE.md` 14、`LAYER-INDEX.md` 9 条 | 无关（`docs/**` 按 `files:` 作用域故意不 lint，见 §4） |

### 7.1 断声明的实测计数比 §2 更多

§2 用字符串搜索只抓到 1 条断链（`verify-spaces`）。CI 日志直接给出 **4 条**，且三条是 §2 判据下
"有消费者"的：

```
$ for p in scripts/check-vault-paths.py scripts/check-cross-deps.py \
           scripts/check-future-annotations.py bin/ssot/verify-spaces.py; do
      git cat-file -e origin/main:$p 2>/dev/null && echo "EXISTS $p" || echo "MISSING $p"; done
MISSING scripts/check-vault-paths.py        # entry of hook id: port-hardcode-check
MISSING scripts/check-cross-deps.py         #                    cross-deps-check
MISSING scripts/check-future-annotations.py #                    future-annotations
MISSING bin/ssot/verify-spaces.py           #                    verify-spaces
```

这修正 §2 的一个口径偏差：**"有没有消费者"和"entry 目标存不存在"是两个独立维度**，
前一节的探测串判据只看前者，所以漏了后者的 3 条。B/C 动手时两条都要量。

### 7.2 ruff 红可在子模块 pin 上本地复现（判预存的通用手法）

`Ruff lint (tracked projects)` 的 66 条 `F405` 全在 `projects/cockpit/src/cockpit/cli.py` 一个文件里。
本分支的 cockpit gitlink 与 `origin/main` **完全相同**（`d33aab44c`），于是可以直接在 pin 上复算，
不必猜：

```
$ git ls-tree origin/main projects/cockpit   # d33aab44c…
$ git ls-tree HEAD        projects/cockpit   # d33aab44c…   ← 同
$ cd projects/cockpit && ruff check --no-cache --select F src/cockpit/cli.py | tail -1
Found 68 errors.        # 其中 F405 = 66，与 CI 报数一致（本地 ruff 0.16.8 / CI 0.16.9）
```

### 7.3 两条子模块门禁红来自 main 侧，本分支无法自证清白

`test` 与 `gac-gate` 都停在 `submodule-reachability`：
`projects/omlxc: 05d860569 unreachable: not contained in fetched origin branches`。
真值方向与直觉相反 —— **坏的是 main，不是我**：

| ref | `projects/omlxc` pin | 对 omlxc `main` 的位置关系 |
|-----|----------------------|----------------------------|
| `origin/main`（含 `faaf782e9` #4336） | `05d860569` | `diverged`（ahead 4 / behind 2）→ 只在旁支上，不在任何被 fetch 的分支里 |
| 本分支 base `2f7ea9af8` 与本分支 tip | `676392753` | `behind`（ahead 0）→ 是 omlxc `main` 的祖先，可达 |

判据命令：`gh api repos/starlink-awaken/omostation-omlxc/compare/main...<pin> -q .status`。

因为 GitHub 的 `pull_request` CI 跑的是 **main 合进分支的 auto-merge 提交**，gitlink 这一侧
main 变了、我未变 → 取 main 的坏 pin。所以**这条红在本分支上不可修**：要么 omlxc lane 的 owner
把 main 重新 pin 回可达提交，要么我改 gitlink —— 后者是抢坑（`faaf782e9` 几分钟前刚落地），
且会把单 lane 提交性质打破。

**反向教训**：为"消陈旧 base 红"而 `git merge origin/main` 之前，先量两侧 gitlink 谁可达。
本轮实测 merge 后 HEAD 反而从可达的 `676392753` 变成不可达的 `05d860569`，
随即 `git reset --hard <origin tip>` 回退（目标 == 远端分支 tip、工作树仅该项脏、脏态本身是 merge 造成的）。


## 8. 4 条断声明落地标注 + 分型（2026-09-26，含一次自我更正）

principal 授权"把 §7 量出来的东西处理掉、最后我来确认"。动手前把 §7.1 那 4 条按
**"目标为什么不存在"**重新分型 —— 这一步改变了处置结论，否则会把"能力改名遗留的断指针"、
"能力真的失踪"和"主动退役"当成同一件事抹掉。

### 8.1 分型（四型，不是三型）

| 型 | hook id | 实测判据 | 处置含义 |
|----|---------|----------|----------|
| **指针过期**（能力改名后存活） | `port-hardcode-check` | entry `scripts/check-vault-paths.py` 不存在，**但** `bin/ssot/check-hardcoded-ports.py` 在盘上且 ci-surfaces `status: active`；`port-registry-enforce.yml` 头注释自认"复用 bin/ssot/check-hardcoded-ports.py（与本地 pre-commit 同一检查）" | 正解是**把 entry 指回新路径**，不是宣告死亡 |
| **真失踪**（无替代品） | `cross-deps-check`、`future-annotations` | `git ls-tree -r origin/main \| grep cross-deps` 只剩 workflow 文件本身；ci-surfaces 独立判定这两条 `status: orphan` | 只能宣告死亡或重建能力，指不回别处。`cross-deps-check` 尤其值得留痕：它下方的 P47+ 注释详细描述了"跨层 enforce"规则，而执行面一个字节都不存在 |
| **主动退役后遗留** | `verify-spaces` | 只存在于 `bin/_archive/verify-spaces.py` 与 `bin/_archive/migrated_low_value/verify-spaces.py` | 1 条。归档 = 有人判断过它该退，声明是漏删的尾巴 |
| ~~假阳性~~ | `mof-schema-validate` | 根仓零命中，**但** `git -C projects/ecos cat-file -e HEAD:src/ecos/ssot/tools/mof-schema-validate.py` 存在 | 1 条。它的路径相对子模块根，在根仓测必然 MISSING —— 我第一版测量就把它错归进了 4 条 |

### 8.2 更正：这 4 条**确实执行**，而且每个 PR 都在 CI 里红

§7 和本文更靠前的一版把"本文件无 per-commit 调用面"（顶部 banner，讲的是**本地 git commit**
被 `core.hooksPath=.githooks` 接管）读成了"这 4 条从未执行、是静默无副作用的死声明"。
**这是错的，而且错的方向恰好掩盖了真正的代价。** CI 有 job `Pre-commit hooks check` 跑
`pre-commit run --all-files`，2026-09-26 在 PR #4365 run 36206145971 逐条实测：

```
hook id: port-hardcode-check    → can't open file '.../scripts/check-vault-paths.py'
hook id: cross-deps-check       → can't open file '.../scripts/check-cross-deps.py'
hook id: future-annotations     → can't open file '.../scripts/check-future-annotations.py'
hook id: verify-spaces          → can't open file '.../bin/ssot/verify-spaces.py'
```

该 job 共 8 个 hook id 失败，**其中 4 个正好就是这 4 条断声明**（另 4 个 check-yaml /
markdownlint / ruff / health-ssot-consistency 与本文件无关）。所以这 4 条的真实代价不是"噪音"，
而是**每一个 PR 的 `Pre-commit hooks check` 恒红** —— 它们是"每次都红一次的断指针"，
不是"安静躺着的死声明"。

### 8.3 顺带量出来的第二个缺陷：`ci-check-runner` 不认 `also_in`

`bin/gac/ci-check-runner.py:65` 的选择条件是 `s.get("workflow") == workflow`，只看主
`workflow` 键，**完全忽略 `also_in` 列表**。后果实测（本地直跑，非推断）：

| workflow | 登记表绑定的 surface | runner 实际选中 | 退出码 |
|----------|--------------------|----------------|--------|
| `cross-deps-enforce.yml` | 仅 1 条，`status: orphan` | **0 checks** | **0（绿）** |
| `port-registry-enforce.yml` | 1 active（其主 workflow 是 `mof-update.yml`）+ 1 orphan | **0 checks** | **0（绿）** |

即 job "port hardcode check" **在 PR 上恒绿**，尽管它头注释声称在 enforce 端口注册。
真正会跑扫描器的只有 `mof-update.yml`，而它 `on: schedule (周一 06:00) + workflow_dispatch`
—— **不在 PR 门禁路径上**。端口硬编码因此没有任何 per-PR 执行面。

### 8.4 做了什么 / 刻意没做什么

给 4 条各加一段 `# ⚠️ …（2026-09-26 实测 + CI 实证）` 注释，写明所属分型 + 复验命令；
`port-hardcode-check` 那条额外写清"能力存活于何处 / 为什么仍需在别处修"。纯增行：
`git diff -U0` 统计**非注释新增 0 行、删除 0 行**，`yaml.safe_load` 后仍是 2 repos / 29 hooks，
4 条 id 全部保留。

- **不删**：删掉只是让噪音消失，同时**销毁"这个能力不见了 / 这个指针过期了"的唯一现场证据**。
  标注严格优于删除 —— 后续要删随时可删，删了就问不回来了。
- **不把 `port-hardcode-check` 的 entry 改指 `bin/ssot/check-hardcoded-ports.py`**：技术上是一行
  修复，但它是**行为变更** —— 本文件在 CI 真的执行，重定位会让一个从未成功跑过的检查突然开始
  跑，直接冲击共享门禁退出码（治理红线：翻转共享门禁退出码要先停下来）。且 `--check-ports` 语义
  在改名迁移后是否等价于旧 vault-paths，需要 owner 判断。→ 留给 principal。

### 8.5 仍然在 principal 手上的

1. **`port-hardcode-check` entry 重定位**（§8.4 说明了为什么不自作主张）+ 确认 `--check-ports`
   语义迁移是否完整。
2. **`ci-check-runner.py:65` 支持 `also_in`**，或反向把 `port-registry-enforce.yml` /
   `cross-deps-enforce.yml` 这类恒绿空 job 显式摘掉。这是"CI 报绿但没检查"的信任问题，
   比断声明本身严重。
3. **`cross-deps-check` / `future-annotations` 是重建能力还是正式宣告死亡** —— 前者牵涉一套真实
   跨层 import 规则（cockpit→kairon / agora→cockpit / ecos→kairon / omo→kairon），后者牵涉 pyright 面。
4. **known-debt 指纹登记**：escape 条件是 `SWARM_ESCAPE_ID=local-preflight-preexisting && human_gate`，
   `human_gate` 那半边按定义不能由 agent 代签。`gate-known-debt.yaml` 的 `growth_policy: shrink_only`
   也说明它只能由人往里加。
5. **选项 B**（让框架真生效）：要动 `core.hooksPath`，撞"不擅自改 git config"这条硬约束。
6. **选项 C 的剩余部分**：把 §2 那 7 条无消费者声明逐条判 owner 后接进 `ci-surfaces.yaml`。
   §7 现在两条维度都量齐了（谁有消费者 / entry 目标存不存在），可以动手，但每条要 owner 判断，
   且改 registry 是另一级授权。
