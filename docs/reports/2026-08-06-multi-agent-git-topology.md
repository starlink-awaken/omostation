---
title: 多 Agent 并行的 Git 拓扑分析与根治方案
type: analysis-and-strategy
owner: 夏明星
created: 2026-08-06
lifecycle: report
related:
  - .omo/_knowledge/decisions/0220-swarm-coordination-discipline-m1-gate.md
  - .omo/_knowledge/decisions/0371-pasw-submodule-isolation.md
  - .omo/_truth/registry/swarm-coordination.yaml
  - docs/plans/3Y-BET-LEDGER.md
note: >
  所有数据为 2026-08-06 实测，附录 A 给取证命令。
  本文只诊断与给方案，执行拆解见台账 BET-Y1Q1-T1-00/05/06/07。
---

# 多 Agent 并行的 Git 拓扑分析与根治方案

## 0. 一句话诊断

> **一个物理仓库实例，在服务 N 个逻辑 agent。**
>
> 已有的所有机制——worktree、PASW、D1–D5 纪律、文件锁——都是在给一个**共享可变资源**做**可选加入的分区**。可选加入的分区必然泄漏，而每次泄漏都用"再加一层分区"来补，复杂度上升但泄漏率不降。

这不是纪律问题，是拓扑问题。**继续加规则不会收敛。**

---

## 1. 实测：系统在忙什么

### 1.1 移动地基 vs 产出 = 2.5 : 1

最近 200 条 reflog 的操作分布：

| 操作 | 次数 | 性质 |
|---|---|---|
| rebase | 60 | 移动地基 |
| checkout | 49 | 移动地基 |
| reset | 22 | 移动地基 |
| **小计** | **131** | |
| commit | 41 | 产出 |
| commit (merge) | 12 | 产出 |
| **小计** | **53** | |
| pull | 10 | 同步 |
| merge | 4 | 集成 |

**每产出 1 次，要移动地基 2.5 次。** 一个健康的单人仓库这个比例通常小于 0.3。

### 1.2 Worktree 机制建了但没在用

```
/Users/xiamingxing/Workspace           [work/governance-phase12-hotfix]   ← 大家都在这
/Users/xiamingxing/ws-agora-p1          prunable
/Users/xiamingxing/ws-agora-p1-bump     prunable
/Users/xiamingxing/ws-atlas-llm         prunable
/Users/xiamingxing/ws-cockpit-cli-help  prunable
/Users/xiamingxing/ws-memory-os-p11     prunable
/Users/xiamingxing/ws-omo-bump          prunable
/Users/xiamingxing/ws-round-0381        prunable
/Users/xiamingxing/ws-wave2-3-split     prunable
```

**8 个中 7 个 prunable**（目录已不存在，只剩管理记录）。也就是说：agent 按流程 claim 了隔离树，然后没在里面干活、或干完没清理，**实际工作全部回落到共享主树**。

主树今天的分支轨迹：

```
main → work/governance-phase9 → -phase9-dimension → -phase10
     → phase4-root-level-cleanup → main → fix/submodule-rewind-4662b95a5
     → main → work/governance-phase11-enforcement → work/governance-phase12-fields
     → fix/submodule-rewind-detection → work/governance-phase12-fields
     → work/governance-phase12-hotfix
```

一天之内在主树上切了十几次分支。**任何在主树上工作的 agent，地基每隔几分钟就被换一次。**

### 1.3 三层共享可变状态

| 层 | 共享的东西 | 现有隔离 | 覆盖率 | 泄漏方式 |
|---|---|---|---|---|
| **L1 仓库** | HEAD / index / 当前分支 / 工作树文件 | `git worktree` | **1/8 在用** | 大家仍在主树上 checkout / reset / clean |
| **L2 子模块** | `.git/modules/projects/<sub>/HEAD` + 子模块工作树 | PASW (ADR-0371) | **3/18** | 非 PASW 的 15 个子模块跨 worktree 共享 HEAD |
| **L3 状态面** | `.omo/` 锁 / run / state | 文件锁 + TTL | 全覆盖但脆 | 写锁非原子、无心跳、失败不回滚 |

**L2 是最隐蔽的一层。** `git worktree` 只隔离主仓的工作树，**不隔离子模块**——所有 worktree 共用 `.git/modules/projects/<sub>/`，包括那里的 `HEAD`。在 worktree A 里 checkout 子模块的另一个 commit，worktree B 里的同一个子模块也跟着变。ADR-0371 的 PASW 正是为解决这个而生，但它只覆盖 gbrain / cockpit / agora 三个，剩下 15 个裸奔。

### 1.4 逃生口的缺口是已知未修项

`swarm-coordination.yaml::gates.d4_escape_hatch` 自己写着：

```yaml
entry: .githooks/pre-push (CI_LOCAL_SKIP) + bin/gac/swarm-git (--no-verify fail-closed).
       Bare git --no-verify still skips hooks
```

**"Bare git --no-verify still skips hooks"** —— 这句是设计者自己记下的。`bin/gac/swarm-git` 会校验白名单、写 `.omo/_delivery/swarm-escape/` 台账；但 `git` 本身还在 PATH 里，绕过它零成本。

### 1.5 今天实测到的六种失效（E1–E6）

| # | 失效 | 层 | 后果 |
|---|---|---|---|
| E1 | 共享主树可写，任何人可 `git clean` / `reset --hard` | L1 | 未入库产物被删 4 次，v10 交付物永久丢失 |
| E2 | claim 失败路径非原子：先写 path 锁，删 update 锁时崩溃 | L3 | 僵尸锁只能等 24h TTL，报错不区分活锁/僵尸锁 |
| E3 | `docs/` 下 `.yaml` 判为 code lane | — | 文档+配套数据被迫拆两个 commit |
| E4 | 逃生口 opt-in，raw git 可绕过白名单与台账 | L1 | 审计链断 |
| E5 | 门禁先于存量上线（ADR-0380 检出 18 个 rewind） | L2 | 主干被锁死，所有无关提交被拦 |
| E6 | 共享分支 rebase 把已提交的工作挤出历史 | L1 | commit 成功但内容消失，靠 `git show <orphan>` 找回 |

**E6 推翻了"commit 就安全"这个假设。** 在共享分支上，commit 只是暂时安全；分支被 rewrite，提交就脱离历史。真正的持久化下限是 **tag 或独立分支**——ref 不随分支重写消失。

---

## 2. 根因：分区 vs 复制

### 2.1 现在走的路是"分区"

```
                 一个物理仓库
                      │
        ┌─────────────┼─────────────┐
        │             │             │
    worktree A    worktree B    worktree C     ← L1 分区（opt-in）
        │             │             │
        └──── 共享 .git/modules ────┘          ← L2 未分区（PASW 覆盖 3/18）
        └──── 共享 .omo/ 锁 ────────┘          ← L3 文件锁
```

每加一个 agent，就要多一层分区规则。已经有：D1 ADR 号原子认领、D2 分支占用锁、D3 共享树写面 claim、D4 逃生口白名单、D5 PASW 子模块隔离。**五层规则，仍然漏。**

**因为分区的前提是「所有人都遵守分区」，而这恰恰是分区想解决的问题。** 循环论证。

### 2.2 该走的路是"复制"

```
   agent-1 clone      agent-2 clone      agent-3 clone     ← 各自完整实例
        │                  │                  │              (含独立 .git/modules)
        └──────────────────┼──────────────────┘
                           ↓ push / PR
                    ~/Workspace（集成点）                    ← 不再是任何人的工作区
                           ↓
                        origin/main
```

**复制之后，物理上不可能互相干扰**——不需要纪律，不需要锁，不需要 claim。冲突只在 merge 时出现，那是 git 本来就擅长处理的地方。

### 2.3 为什么 worktree 不够，必须 clone

| 维度 | worktree | clone |
|---|---|---|
| 主仓工作树 | ✅ 独立 | ✅ 独立 |
| 主仓 HEAD / index | ✅ 独立 | ✅ 独立 |
| **`.git/modules/<sub>/HEAD`** | ❌ **共享** | ✅ 独立 |
| **refs / branches** | ❌ **共享**（A 删的分支 B 也没了） | ✅ 独立 |
| **reflog** | ❌ 共享 | ✅ 独立 |
| 磁盘 | 省 | 每份约 1–2 GB |
| 同步成本 | 无 | `git fetch` |

**refs 共享是 E6 的技术根因**：agent B 在共享 refs 上 rebase `work/governance-phase12-fields`，agent A 提交在该分支上的 commit 就掉了。worktree 隔离不了这个。

代价是磁盘：18 个子模块 + 98 万行代码，一份 clone 大约 1–2 GB。**3–4 个 agent 也就 4–8 GB**，对比今天一整天的调试成本，这个价格便宜到不需要讨论。

---

## 3. 方案

### 3.1 战略层：仓库拓扑从「单实例多租户」改为「多实例单写者」

**三条不变量（invariant），一旦确立，上面五层纪律里的大部分可以退役：**

| # | 不变量 | 怎么保证 |
|---|---|---|
| **I1** | `~/Workspace` 是集成点，不是任何 agent 的工作区 | pre-commit 在主仓拒绝一切 agent 身份的写入 |
| **I2** | 每个 agent 拥有一个完整、独立的仓库实例 | `~/agents/<agent-id>/ws`，独立 clone（含子模块） |
| **I3** | 集成只经由 ref（push + PR），不经由共享文件系统 | 主仓 `main` 只接受 fast-forward |

对应的组织形态：

```
~/Workspace                  ← 人类的窗口 + 集成点。agent 只读
~/agents/atlas/ws            ← agent atlas 的独立 clone
~/agents/codex/ws            ← agent codex 的独立 clone
~/agents/claude/ws           ← agent claude 的独立 clone
```

每个 clone 用 `--reference ~/Workspace` 共享对象库（省 90% 磁盘），但 refs / HEAD / modules 完全独立。

```bash
git clone --reference ~/Workspace --dissociate=false \
  --recurse-submodules ~/Workspace ~/agents/<id>/ws
```

> `--reference` 只共享 object store（只增不改，天然并发安全），不共享 refs / HEAD / index / modules。这正好是我们要的切分面。

### 3.2 战术层：五件事，从止血到根治

| 优先级 | 动作 | 解决 | 工作量 |
|---|---|---|---|
| **P0 止血** | 主树封死：pre-commit + pre-checkout 拒绝 agent 在 `~/Workspace` 写入/切分支 | E1、E6 | 0.5 天 |
| **P0 止血** | git 入口收口：agent 环境 PATH 里 `git` → `bin/gac/swarm-git` shim | E4 | 0.5 天 |
| **P1 根治** | 仓库拓扑改造：每 agent 一个 clone，主仓降级为集成点 | E1、E6，并使 L2 问题消失 | 2 天 |
| **P1 补齐** | PASW 覆盖 3 → 18（过渡期用，拓扑改造后可退役） | E5 及 L2 泄漏 | 1 天 |
| **P2 加固** | 锁原子化（临时文件 + rename）+ 心跳 + stale 一键清理 | E2 | 1 天 |

**注意 P1 拓扑改造完成后，D2/D3/D5 三条纪律可以退役**——它们存在的唯一理由是共享树。这是一次**净减法**：用 2 天换掉三层规则和一堆锁逻辑，符合 Y1 的表面积目标。

### 3.3 具体机制设计

#### M1 · 主仓写入闸（I1）

`~/Workspace/.git/hooks/pre-commit` 首行：

```bash
# 主仓是集成点，不是工作区
if [ "$(git rev-parse --show-toplevel)" = "$HOME/Workspace" ] && [ -n "${AGENT_ID:-}" ]; then
  echo "❌ 主仓只读。请在 ~/agents/$AGENT_ID/ws 工作后 push + PR" >&2
  exit 1
fi
```

同样的检查放进 `pre-checkout`（用 `post-checkout` 检测并告警，git 无 pre-checkout 钩子，需靠 shim 拦 `git checkout`）。

人类不设 `AGENT_ID`，因此不受限——这条件把"谁在写"变成了可判定的事实，而不是靠自觉。

#### M2 · git 入口收口（I1 + E4）

agent 的启动环境里加一个 shim 目录，置于 PATH 最前：

```
~/agents/<id>/bin/git   →  exec ~/Workspace/bin/gac/swarm-git "$@"
```

`swarm-git` 已经有白名单校验和 escape 台账，只是没人被强制走它。**shim 把「记得用 wrapper」变成「只有 wrapper 可用」。**

同时在 `swarm-git` 里加拦截：`clean -fd` / `reset --hard` / `stash -u` / `rebase`（共享分支上）一律要求 escape id。

#### M3 · 交付持久化下限（E6）

**"commit 即安全"这个假设作废。** 新规则：

```
交付物 → git add → commit → tag（或 push 到独立远端分支）
```

台账 CLI 已经有 D0 检查（`git ls-files`），需要升级为 D0+：

```bash
bet-ledger.py verify <bet-id>   # 现在只查 tracked
                                # 应加查：是否被某个 tag 或远端分支覆盖
```

拓扑改造完成后这条会自然缓解（自己的 clone 没人 rebase），但作为兜底应保留。

#### M4 · 子模块隔离（L2，过渡期）

拓扑改造前，PASW 从 3 个扩到 18 个。改造后，因为每个 clone 有自己的 `.git/modules`，**这条整体退役**。

判据：`PASW_ISOLATED_SUBS` 应该在拓扑改造完成的同一个 PR 里被删掉，而不是留着。

#### M5 · 锁的原子性与可自愈（L3 / E2）

三处改动：

```
写锁：  open(tmp) → write → fsync → rename(tmp, lock)     # rename 是原子的
读锁：  记录 last_heartbeat，超过 2×心跳周期视为 stale
报错：  区分「活锁（持有者进程在跑）」与「僵尸锁（上次失败残留）」
清理：  agent-workflow status --locks 列出 stale 并给一键清理
```

### 3.4 门禁上线规程（E5）

今天 ADR-0380 的教训：**门禁先于存量清理上线，会把主干锁死。**

新规程写进 `.omo/standards/`：

```
新门禁上线三段式：
  1. shadow：只记录不阻断，跑满 1 周，产出存量清单
  2. warning：报警但不阻断，给出清理期限
  3. fail：存量清零后转硬门
任何跳过 1、2 直接上 fail 的门禁，须人类批准并记录理由
```

---

## 4. 分阶段落地

| 阶段 | 时间 | 动作 | 判据 |
|---|---|---|---|
| **D0 止血** | 当天 | M1 主仓写入闸 + M2 git shim | 主仓 `git status` 连续 24h 干净 |
| **D1 试点** | 2 天 | 1 个 agent 切到独立 clone，跑通一个 bet 全流程 | 该 agent 全程零 claim 冲突 |
| **D2 铺开** | 1 周 | 全部 agent 迁到独立 clone；主仓转只读 | reflog 中主仓 checkout/reset 归零 |
| **D3 减法** | 2 周 | 退役 D2/D3/D5 纪律与 PASW；锁逻辑简化 | 表面积净减（脚本 / 规则 / 文档行数） |
| **D4 加固** | 持续 | M3 tag 兜底 + M5 锁自愈 + 门禁上线规程 | 72h 观察窗零 conflict（沿用 ADR-0220 的 M1 判据） |

**D3 是这个方案最重要的一步，也是最容易被跳过的一步。** 如果只做了 D0–D2 而不退役旧纪律，结果是拓扑改了、规则还在，表面积不降反增——那就白做了。

---

## 5. 预期效果与验证

| 指标 | 现状 | D2 后 | D3 后 |
|---|---|---|---|
| 移动地基 : 产出 | 2.5 : 1 | < 0.5 : 1 | < 0.3 : 1 |
| 主仓 checkout/reset 次数（日） | ~30 | 0 | 0 |
| worktree prunable 比例 | 7/8 | — （机制退役） | — |
| PASW 覆盖需求 | 3/18 且不够 | 18/18 | 0（不再需要） |
| swarm 纪律条数 | D1–D5 | D1–D5 | D1、D4（保 2 条） |
| 交付物丢失事件（日） | 4 | 0 | 0 |

**主验证问题**：连续 72 小时，`conflict_event_kinds` 里的 `unclaimed_write` / `orphan_commit` / `branch_hijack` 计数是否为 0。这个判据 ADR-0220 已经定义好了（`observation.window_hours: 72`，`m1_pass_requires: elapsed_hours >= 72 AND conflict_count == 0`），现在有条件真正跑通它。

---

## 6. 反对意见与回应

**「clone 太占磁盘」**
→ `--reference` 共享 object store 后每份增量约 200–400 MB。4 个 agent 不到 2 GB。今天一天的调试时间成本远高于此。

**「worktree 就是为这个设计的」**
→ worktree 解决的是「一份代码多个检出」，不是「多个写者互不干扰」。它不隔离 refs、不隔离 `.git/modules`、不隔离 reflog。E6 就发生在 refs 共享上。

**「已经有 D1–D5 了，再加一层不如把现有的执行好」**
→ 恰恰相反。D1–D5 是五层可选加入的分区，今天实测到 6 种失效方式（E1–E6），其中 E4 是设计者自己记录的已知缺口。**方案的价值不在于新增，而在于让 D2/D3/D5 可以被删掉。**

**「主仓只读了，我自己怎么用」**
→ 闸门条件是 `AGENT_ID` 非空。人类不设这个变量，完全不受影响；主仓反而回归成一个稳定的、不会被随时切走分支的窗口。

---

## 7. 与三年规划的关系

这件事属于 **Y1 「收敛与接通」的前置**，不是新增战线：

- 它是 **Y1 唯一硬目标（表面积净负增长）的直接贡献项**——D3 阶段退役三条纪律与 PASW，是纯减法。
- 它是 **所有其他 bet 的前提**。今天已经验证：在当前拓扑下，任何 bet 的产物都可能在交付后消失。不修这个，58 个 bet 的执行结果都不可信。
- 它**不扩容能力供给侧**，符合 §9「明确不做」的边界。

台账对应：`BET-Y1Q1-T1-00`（止血）、`T1-05`（拓扑改造）、`T1-06`（子模块隔离与退役）、`T1-07`（git 入口收口）。

---

## 附录 A · 取证

| 断言 | 命令 |
|---|---|
| 移动地基 : 产出 = 2.5:1 | `git reflog -200 \| awk '{for(i=1;i<=NF;i++) if($i ~ /^(checkout:\|reset:\|commit:\|commit\|merge\|pull\|rebase)/) {print $i; break}}' \| sort \| uniq -c \| sort -rn` |
| 7/8 worktree prunable | `git worktree list \| grep -c prunable` |
| 主树分支轨迹 | `git reflog -50` |
| 子模块 git dir 共享 | `ls .git/modules/projects/` |
| PASW 覆盖 3/18 | `grep PASW_ISOLATED_SUBS bin/gac/gac-worktree.sh`；`git submodule status \| wc -l` |
| D4 已知缺口 | `.omo/_truth/registry/swarm-coordination.yaml::gates.d4_escape_hatch.entry` |
| E6 提交脱离历史 | `git merge-base --is-ancestor 49d3ffed5 HEAD` → 非 0；`git show 49d3ffed5` → 仍可读 |
| 72h 零冲突判据 | `.omo/_truth/registry/swarm-coordination.yaml::observation` |
