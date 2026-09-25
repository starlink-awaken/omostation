---
schema: md/v1
status: active
lifecycle: history
owner: agent-skills-team
last-reviewed: 2026-09-25
type: ssot
name: git-discipline
description: "多 agent 并行下的 git 纪律：隔离工作树、交付三段式（add/commit/tag）、逃生口、子模块、僵尸锁、合并型交付补 claim、agent 自身 git 写能力自检。当你要提交代码、切换分支、碰子模块、做分支合并、遇到门禁拦截或 claim 冲突、或发现自己的文件消失 / git 行为诡异 / **命令成功但没做事**时使用。Triggers on: git commit, git merge, git checkout, 合并, 分支被切走, 文件消失, 提交丢了, claim 失败, 锁被占, index.lock, Operation not permitted, no-verify, 门禁拦截, D3, swarm-d3, submodule, 子模块, worktree, PASW, swarm-git, escape, unbound variable, ff-only, fast-forward, 同步后没生效, HEAD 没动, 分叉, diverge, git add -A, 裹入, stash, update-ref, reflog。"
last_updated: 2026-09-21
---


# Git Discipline — 多 Agent 并行纪律

**分析依据**: `docs/reports/2026-08-06-multi-agent-git-topology.md`
**台账对应**: `BET-Y1Q1-T1-00 / T1-05 / T1-06 / T1-07`

---

## 0. 你面对的现实

`~/Workspace` 是**一个物理仓库实例，同时服务 3–4 个 agent**。2026-08-06 实测：

| 现象 | 数据 |
|---|---|
| 移动地基 : 产出 | **2.5 : 1**（rebase 60 + checkout 49 + reset 22 vs commit 53） |
| worktree 有效性 | 8 个中 **7 个 prunable**——建了没用，工作全回落共享主树 |
| 子模块隔离覆盖 | **3 / 18**（PASW 只管 gbrain/cockpit/agora） |
| 当天交付物丢失 | **4 次**（含已 commit 被分支 rebase 挤掉 1 次） |

**下面的规则不是建议。** 每一条都对应一次真实事故。

---

## 1. 绝不在主仓 `~/Workspace` 直接工作

开工第一件事：

```bash
bash bin/gac/gac-worktree.sh claim <你的-session-id>
```

然后 `cd` 进它给的隔离树，之后所有操作在那里做。

**在主仓永远不要执行：**

| 命令 | 后果 |
|---|---|
| `git checkout` / `switch` | 把别人的地基换掉（当天在主树上切了十几次分支） |
| `git reset --hard` | 删掉别人**已暂存**的工作 |
| `git clean -fd` | 删掉别人**未入库**的文件（当天发生 4 次，`journey-runner.py` 601 行永久丢失） |
| `git stash -u` | 同上 |
| `git rebase` | 把别人**已 commit** 的工作挤出历史（E6） |

完工后 `bash bin/gac/gac-worktree.sh submit <session-id>`。
**别留着不清理**——现在 8 个 worktree 里 7 个是废弃的。

> **注意 worktree 的能力边界**：它隔离主仓工作树，但**不隔离** `refs`、`reflog`、
> `.git/modules/<sub>/HEAD`。所以「在自己的 worktree 里」不等于「绝对安全」，
> 见 §4 和 §5。根治方案是每 agent 独立 clone（`BET-Y1Q1-T1-05`）。

---

## 2. 交付三段式：`add` → `commit` → `tag`

**少一段都不算交付。**

```bash
git add <每个产物>      # 写完一个文件立刻做，不要攒着
git commit
git tag -a <name> -m ...   # ← 这一段不是可选项
```

理由分三层，每层都实测过：

| 假设 | 被什么推翻 |
|---|---|
| 「写了就有」 | `git clean -fd` 删掉未入库文件 |
| 「add 了就安全」 | `git reset --hard` 连暂存区一起摧毁 |
| 「commit 了就安全」 | 共享分支被 rebase，提交脱离历史、内容从工作树消失 |

**tag 的 ref 不随分支重写消失**，这是当前拓扑下的持久化下限。

### 提交掉了怎么找回

```bash
git merge-base --is-ancestor <sha> HEAD   # 非 0 = 已脱离分支
git show <sha>:<path> > <path>            # commit 对象仍在，可直接取回
git reflog                                # 找回被 reset 掉的 sha
```

---

## 3. 逃生口只有一个入口

要 `--no-verify` 时**必须**走：

```bash
SWARM_ESCAPE_ID=<白名单里的id> bin/gac/swarm-git commit --no-verify ...
```

白名单在 `.omo/_truth/registry/swarm-coordination.yaml::escape_hatch_exemptions`（**权限类**）。
`swarm-git` / pre-push 会先跑预检，把失败写成 fingerprint `(surface, check_id, signature)` 再决定能否跳（ADR-0422）。
台账 `.omo/_delivery/swarm-escape/<ts>-<id>.json` 必须带 fingerprint 字段，不只是白名单 reason。

权限类：`partial-worktree` 只能跳 `uninitialized-submodule:*`；预存 GaC 走 `local-preflight-preexisting` + `gate-known-debt.yaml`。
`emergency-human-hotfix` 在 `AGENT_ID` / shim 路径立即拒绝，除非一次性 `SWARM_ESCAPE_TOKEN`。

```bash
python3 bin/gac/swarm-discipline-cli.py escape-token-issue
python3 bin/gac/escape-digest.py --dry-run
```

**直接用 raw `git --no-verify` 会绕过整套机制**——能跑通，但白名单不校验、台账不落盘，
审计链断，视为违规。

> 这个缺口是 registry 自己记录的已知未修项：
> `gates.d4_escape_hatch.entry` 原文写着 `Bare git --no-verify still skips hooks`。
> `BET-Y1Q1-T1-07` 会用 PATH shim 堵上它。

---

## 4. 子模块

- `gbrain` / `cockpit` / `agora` 走 PASW（ADR-0371）：改动必须在 `.subtrees/<sub>/` 内完成
- **其余 15 个子模块目前没有隔离**：所有 worktree 共用 `.git/modules/projects/<sub>/HEAD`，
  你在这边切子模块 commit，别人那边跟着变
- 所以：**非必要不碰子模块指针**；要碰先说一声
- 提交时用 `git commit --only <paths>` 做路径限定提交，避免顺手带上别人的子模块指针

### 4.1 删子模块远程分支前先查 gitlink 悬空（2026-08-21 实证）

PR 合并后顺手删远程分支是惯例，但**子模块分支被删后，指向它的根仓 gitlink 立即悬空**——
即使那个 SHA 已经进过别的 PR 也一样（如果它只在被删分支上）。悬空的 gitlink 会让：
- 其他 PR 的 `gac-gate` / `test` 报 `unreachable: not contained in fetched origin branches`
- CI 的 `submodule-reachability` 全线红

**删除前必查**（在根仓执行）：
```bash
# ① 该 SHA 是否已在子模块 origin/main 上（merge-base 判定）
git -C projects/<sub> merge-base --is-ancestor <SHA> origin/main && echo "安全: 已在 main" || echo "危险: 仅存在于待删分支"
# ② 仍要删时，先确认根仓没有任何分支/PR 的 gitlink 指着它
git ls-tree origin/main projects/<sub>   # main 的指针
gh pr list --state open --json headRefName  # 逐个查 open PR 的树
```

SHA 不在子模块 main 上 → **别删分支**，先把该内容通过子模块自己的 PR 合进 main。
本次事故链：删 `bet-t1-19-canary` → gitlink `9a40a5a` 悬空 → PR #1806 两个 gate 红 →
被迫临时恢复分支（`bet-t1-19-canary-restore`）+ 开子模块 PR 补合。多花 40 分钟。

### 4.2 跨仓强校验的时序竞态（2026-08-21 实证）

当 A 仓（如 ecos）给共享 schema（如 work-packet/v2）加**必填**校验、而消费方（omo / 根仓
bin/）的适配还在另一个分支上没合时，**main 会整体红**：所有触发该检查的 PR 全挂同一个错。

规矩：**消费方先合、生产方后合**（或同 PR 双仓）。已经红了的急救姿势：
1. 从滞留分支 cherry-pick 消费方修复进你的 PR（不要等原作者）
2. 子模块指针 bump 到子模块 main 最新（釜底抽薪，别追过时的中间 SHA）

---

## 5. 卡住时的处置

### claim 被拒

```bash
cat .omo/_delivery/agent-workflows/locks/path_<路径下划线化>.lock.yaml
```

看 `created_at`：

- **早于你的 run 创建时间** → 僵尸锁（上次 claim 失败残留）。claim 的失败路径不原子：
  先写 path 锁，删 update 锁时崩溃就会留下它。删掉重试。
- **晚于/接近** → 活锁，持有者在跑。等，或换任务。

TTL 是 24h，不要干等。

### 门禁被拦

先判断**它拦的是不是你这次改的东西**：

```bash
git diff --cached --name-only
```

- **不是**（例如 18 个子模块 rewind，而你只改了 2 个 doc）→ 走 §3 的正规逃生口，并确认 fingerprint 属于「与 diff 无关」或已在 known-debt
- **是** → 修，别绕。预存债登记 known-debt（owner+过期），不要把 `--no-verify` 当标准答案

### lane 不匹配

`change-lane-check` 不允许 `{code, docs}` 混在一个 commit。判定：

```bash
python3 bin/change-lane-check.py --file <path> --json
```

注意 `docs/` 下的 `.yaml` 会被判成 **code** lane（已知问题，`BET-Y1Q1-T1-04`）。
文档 + 配套数据要拆成两个 commit，各走 `project-doc-change` / `project-code-change`。

### 分支被切走

**停下，报告，不要自己 checkout 回去。** 你切回去会再次换掉别人的地基。

### 合并型交付被 D3 拦下

claim 的粒度是「**我打算改什么**」，merge 的作用域是「**这个分支携带了什么**」。两者不重合。

2026-08-07 实测：合并 12 个提交进 main，D3 报 74 个路径里 5 个未 claim，
其中两个（`bin/gac/check-llm-gateway-only.py`、`docs/plans/2026-08-06-agora-p2-deepening-plan.md`）
是**别的 agent 在被合并分支上的产物**——起 run 时不可能预见。

处置顺序：

```bash
# ① 先看清缺哪些（D3 报错的 violations 段就是清单）
# ② 确认既有 run 还活着，能续用就别新起
grep -m1 '^status:' .omo/_delivery/agent-workflows/runs/<run-id>.yaml
# ③ 逐个补 claim
uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path <path>
```

**不要走逃生口。** 逃生口是给门禁误伤用的；claim 漏了不是误伤，绕过去只会在
`.omo/_delivery/swarm-escape/` 留一条本不该有的记录，还丢掉这条发现。

合并前预检（省一轮往返）：

```bash
git diff --name-only $(git merge-base HEAD <branch>) <branch>
```

---

## 5b. Agent 自身工具链的能力边界（先查自己，再怪环境）

**2026-08-06 教训：一整天的「git 行为异常」全部由 agent 自己造成，被误判为并发干扰。**

```bash
touch .git/_probe   # → OK
rm -f .git/_probe   # → Operation not permitted
```

sandbox 对 `.git/` 能建不能删。git 的锁协议是「建 `.lock` → 干活 → unlink」，
第三步永远失败：**一次 `git status` 在 17 个子模块留 17 个僵尸 `index.lock`**，
此后该仓库任何 git 写操作直接失败。

当时的归因是「并发 agent 在删我的文件」，并据此写了 T1-00 的部分结论。

**开工自检（30 秒，省一整天）：**

```bash
touch .git/_probe && rm -f .git/_probe && echo "✅ git 写能力完整" \
  || echo "❌ 本环境不能做 git 写操作 —— 只读分析，写操作交人类终端"
```

只读操作一律加：

```bash
export GIT_OPTIONAL_LOCKS=0    # git status/diff 不再抢锁，不留残留
```

清理残留：

```bash
find . -name index.lock -not -path "*/node_modules/*" -print -delete
```

> **推论**：agent 报告「环境有并发干扰」时，先验证自己工具链在该环境下的完整性，
> 再归因外部。这是 D1（声明 vs 事实）在「自我能力」维度的投影，原 D1 未覆盖。
> 台账证据 `BET-Y1Q1-T1-00::E16`。

---

## 5c. 语法检查 ≠ 能跑

**凡「解析得过、执行才炸」的构造，必须有一条真正执行它的验证路径。**

本轮实测命中两类：

**① shell 里全角字符紧跟变量名** —— `bash -n` 查不出（语法完全合法）

```bash
echo "==> 合并 $BRANCH（$AHEAD 个提交）"
#                    ↑ bash 把「（」当成变量名的一部分 → set -u 下 unbound
```

开工前扫一遍，中英混排的脚本必查：

```bash
grep -nP '^\s*[^#].*\$[A-Za-z_][A-Za-z0-9_]*[^\x00-\x7F]' <script>
```

> 这条规则在 2026-08-06 一晚命中同一个人写的脚本 **3 次**。命中率高于人工复查。
> 修法：`${BRANCH}（`。

**② CI 配置里的内联脚本** —— YAML 合法，脚本跑不了，`yamllint` 全过

`.github/workflows/agora-ci.yml` 两侧同一个 job，差异只在内联 Python 写法：
单行 `python3 -c '...'` 能跑，多行缩进 `python3 -c "..."` 直接 `IndentationError`
（`-c` 的第一行带前导空格）。只有真把那段喂给解释器才暴露。

改 CI 里的 `run:` 块后，把内联脚本单独执行一次再提交。台账证据 `BET-Y1Q1-T1-00::E17`。

---

## 6. 新门禁上线三段式

今天的教训（E5）：`ADR-0380 CR-SUBMODULE-REWIND` 门禁先于存量清理上线，
立刻检出 18 个 rewind，把主干锁死——所有无关提交都提交不了。

**任何新门禁必须走：**

```
1. shadow   只记录不阻断，跑满 1 周，产出存量清单
2. warning  报警但不阻断，给出清理期限
3. fail     存量清零后才转硬门
```

跳过 1、2 直接上 fail 的，须人类批准并记录理由。

---

## 7. 一句话总则

**违反任何一条，先停下报告，不要"补救"** —— 补救动作本身通常就是下一次事故。

---

## 2026-08-30 增补：多 Agent 撞车与指针纪律（T4-04/T4-05 战役实录）

### 撞车检测（claim 前必查）

同 BET 多 agent 并行时，动手前先查 main 最新 commit：
```bash
git fetch origin main -q && git log origin/main --oneline -5 | grep -i "<bet关键词>"
```
发现并行实现已合入 → **关闭自己的 PR 交叉验证对方**，绝不重复交付（T4-04 #115 vs #116 实录：关闭重复 PR 是正确动作）。

### 指针 bump 纪律（指针污染 ×2 根治）

见 `.omo/standards/submodule-pointer-bump-contract.md`（强约束）。
一句话版：**bump sha 唯一来源 = 子仓 fetch 后的 origin/main 头**。

### Diverged 分支假 diff 检测

分支基于旧 main 时，`git diff origin/main..HEAD` 会出现"删除别人文件"的假 diff。
push 前必查：diff 中出现**大量删除且非你删的** → 先 rebase 再推。

### 治理工具自身 bug 的报告纪律

complete/lint 等 gate 工具报错时：先本地最小复现（手动 git 命令对照），
确认是工具 bug 而非交付问题后修工具（T4-07 complete 子串匹配 bug 实录——
waiver 注释文本触发误判）。工具 bug 修复与交付同 PR 记录，不静默绕过。

---

## 2026-09-21 增补：「看起来成功了」的三类静默失效（本人一天内连踩）

前面几节讲的是**别人的操作毁掉你的工作**（分支被切走、假 diff）。本节讲另一种更难的
情况：**你自己的 git 命令返回 0、无报错、输出正常，但实际没做事**。

它们的共同点是失败发生在 git 的**建议性输出**里，而不是退出码里。所以只要你依赖
`&&` 链或 `2>/dev/null`，就会一路误判下去。2026-09-21 我一天内因此**误读了 4 次**。

### A. `merge --ff-only` 在分叉态静默失败 ★ 最隐蔽

```bash
git merge --ff-only origin/main   # 分叉时: 只打印 hint, 不报错
echo $?                            # ← 你以为是 0
```

真实行为（2026-09-21 四态实测，非推断）：

| 状态 | 领先/落后 | 输出 | 退出码 | HEAD |
|---|---|---|---|---|
| 可快进 | 0/1 | `Updating a..b` + `Fast-forward` | 0 | **移动** |
| 已同步 | 0/0 | `Already up to date.` | 0 | 不动（正确） |
| **仅领先** | 1/0 | `Already up to date.` | **0** | 不动 ← 陷阱 |
| **分叉** | 1/1 | `hint: Diverging…` + `fatal: Not possible to fast-forward, aborting.` | **128** | 不动 |

**两个独立的坑，别混为一谈**：

1. **仅领先态 exit=0 且输出 `Already up to date.`** —— 与"已同步"**逐字相同**，但
   你的本地有未推送提交。把它读成"我已经最新了"是错的：你脚下多了别人没有的东西，
   而你以为地基是共享的。
2. **分叉态确实 exit=128，但退出码会被管道吞掉** —— 这是今天 4 次误读的**真机制**：

```bash
git merge --ff-only origin/main 2>&1 | tail -1   # 显示 fatal: ... 但管道 exit=0
git merge --ff-only origin/main >/dev/null 2>&1 && echo "同步成功"   # 永远打印成功
```

> 我起初把这条写成"git 不报错"，**那是错的** —— git 报了（128 + fatal），是我用
> `| tail -1` 和 `>/dev/null` 把报告扔了。**别把"我没看退出码"归因成"工具没报错"**；
> 这个归因错误会让人去修工具，而真正该修的是自己的调用方式。

分叉的成因往往是**另一个 agent 直接在共享工作区的 main 上提交**（见下 B）。后果是全局性的：

> 共享工作区的 `main` 一旦领先 `origin/main`，**所有** agent 的
> `git merge --ff-only origin/main` 从此全部静默失效 —— 各方都以为拿到了最新代码，
> 实际停在旧提交上。2026-09-21 实证：该状态持续近 1 小时无人察觉，期间我反复
> "同步"却看不到自己的改动生效，还误判成工具坏了。

**纪律**：同步后**必须验证 HEAD 真的动了**，且**不要让管道吃掉退出码**：

```bash
before=$(git rev-parse HEAD)
git merge --ff-only origin/main        # ← 不要 | tail / 不要 >/dev/null
rc=$?                                   # ← 紧跟着一行取码, 中间不要插命令
[ "$(git rev-parse HEAD)" = "$before" ] && echo "⚠️ HEAD 未移动 (rc=$rc)"
git rev-list --count origin/main..HEAD  # >0 = 本地领先, 必须停下来查 (即使 rc=0)
```

**判读表**：`rc=0 且 HEAD 动` = 正常快进｜`rc=0 且 HEAD 没动 且 领先=0` = 本就同步｜
`rc=0 且 HEAD 没动 且 领先>0` = **仅领先陷阱**｜`rc≠0` = 分叉，停下来。

**该纪律块实测有效**（隔离仓库四态验证，非纸面）：
- 仅领先态 → `rc=0` 但 `⚠️ HEAD 未移动` + `领先: 1` **仍触发警告**（只看 exit 必漏）
- 真分叉态 → `rc=128` + 警告 + `fatal: Not possible to fast-forward` → 判读表指向"停下来"

**判据**：`git rev-list --count origin/main..HEAD` 是这条链路上唯一可靠的体检。
非 0 就**不要继续工作** —— 你脚下的地基不是你以为的地基。

### B. 共享工作区禁止 `git add -A`（会裹入他人 45 个文件）

`git add -A` 在共享工作区里裹进的是**所有 agent 的未提交改动**，不只是你的。
2026-09-21 实证：我一次 `git add -A` 裹入 45 个文件，含他人的
`.omo/_control/governance-data.json`、十几个 retro 文档、以及**别人尚未落库的
新脚本**（那两个脚本后来由对方经 #4087 正常提交 —— 我的裹入纯属多余，却让对方
的工作一度挂在我的提交上）。

**纪律**：
1. 一律**显式列路径**：`git add <file1> <file2>`（我今天的每个 PR 都这么做，
   只有这一次图省事）
2. 提交前 `git diff --cached --stat` 核对**文件数与自己的改动面一致**
3. 裹入后发现 → 立即 `git reset --mixed` 还原索引，逐路径重加

### C. 不要在共享工作区 stash / update-ref（会动到别人的地基）

今天因此连出两件事：

- `git stash` 把**别人未提交的改动**一起卷走，我随后 `git stash drop` 销毁了它。
  侥幸没丢（内容仍在别处），但这是**运气不是流程**。
- `git update-ref refs/heads/main origin/main` 用于"强行同步" —— 我在没检查分叉
  的情况下执行，把**另一个 agent 未推送的提交从分支 ref 上移走了**。

**纪律**：
- 共享工作区**只读**；要动 git 状态就在自己的 worktree 里
- 需要"同步"时用 A 节的验证式流程，不要用 `update-ref` 强行搬 ref
- 万一搬了：`git reflog` 一定能找回来，**立刻**钉扎（`refs/wip/`）并建可见分支
  `recover/<name>`，不要等 gc。今天的恢复就是这样完成的

### D. 先量化，再相信自己的判断（跨节通用）

今天我被自己的直觉打脸 6 次，全部发生在**"我觉得这个改动很简单"**的时刻：

| 我的判断 | 实测 |
|---|---|
| "把门禁扫向真实注册表就行" | 会误报 19 个真实项 —— 必须先做使能修复 |
| "cockpit 是跨仓消费者，要小心" | 它 `required=False` 优雅降级，根本不用改 |
| "这些 exec-*.json 是测试垃圾" | 是**测试污染入仓证据面**的症状 |
| "这个指针 bump 该做" | 已被另一个 PR 覆盖，做了就是回退风险 |
| "stash 掉改动就能验证基线" | 已提交的不受 stash 影响 —— 验证无效 |
| "有 8 个 freshness 守卫，够了" | 没有一个覆盖 `.omo/` |

**纪律**：改任何东西前，先跑一次**只读的量化**（数一下会影响多少对象）；
验证"是否预存在"时，**不要用 stash 来还原已提交的改动**。
