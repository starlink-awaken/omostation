---
name: git-discipline
description: "多 agent 并行下的 git 纪律：隔离工作树、交付三段式（add/commit/tag）、逃生口、子模块、僵尸锁、合并型交付补 claim、agent 自身 git 写能力自检。当你要提交代码、切换分支、碰子模块、做分支合并、遇到门禁拦截或 claim 冲突、或发现自己的文件消失 / git 行为诡异时使用。Triggers on: git commit, git merge, git checkout, 合并, 分支被切走, 文件消失, 提交丢了, claim 失败, 锁被占, index.lock, Operation not permitted, no-verify, 门禁拦截, D3, swarm-d3, submodule, 子模块, worktree, PASW, swarm-git, escape, unbound variable。"
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

白名单在 `.omo/_truth/registry/swarm-coordination.yaml::escape_hatch_exemptions`。
`swarm-git` 会校验 id 并写审计台账 `.omo/_delivery/swarm-escape/<ts>-<id>.json`。

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

- **不是**（例如 18 个子模块 rewind，而你只改了 2 个 doc）→ 走 §3 的正规逃生口
- **是** → 修，别绕

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
