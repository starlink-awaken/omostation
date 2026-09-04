---
title: 多仓库 × 多子仓 × 多 Agent 协作复盘 v2 — 差量与决策
type: report
owner: governance-team
created: 2026-08-15
lifecycle: history
related:
  - docs/reports/2026-08-06-multi-agent-git-topology.md
  - docs/architecture/blueprint-collab-consolidation-v1.md
  - .omo/_knowledge/retros/SESSION-RETROSPECTIVE-20260814-15.md
context: >-
  08-06 报告定下「多实例单写者」根治方案后 9 天的差量复盘：哪些落地了、哪些没走、
  新出了什么事故、暴露了什么报告没覆盖的病根。产出 D2 铺开决策备忘。
---

# 多仓库协作复盘 v2 — 2026-08-15

## 0. 一句话结论

**方案是对的，但只走了一半——`~/agents/` 独立 clone 已存在且零事故，而全部事故仍发生在旧 worktree 路径上。双轨并存 9 天 = 事故面敞开 9 天。瓶颈不是设计，是迁移没有截止日。**

---

## 1. 08-06 方案落地率审计（五件事对照）

| 事项 | 方案 | 落地状态 | 证据 |
|---|---|---|---|
| P0 主树封写 | pre-commit 拒绝 agent 写入 | 🟡 **工具已备未激活** | `bin/gac/agent-clone.py guard` 已实现（D1 pilot），主仓仍在被 agent 直接改文件（本轮 T2-03 主仓对齐就是例子） |
| P0 git 入口收口 | PATH shim → swarm-git | 🟡 部分 | swarm-git 存在，但本轮仍见 raw git push 被 hook 拦（说明入口没收死，靠 hook 补漏） |
| P1 拓扑改造 | 每 agent 独立 clone | 🟡 **半成品** | `~/agents/` 有 5 个 clone（含 blueprint-control-loop），但 6 个心跳 agent 仍共享主仓 worktree 路径 |
| P1 PASW 扩面 | 3 → 18 覆盖 | ✅ 大体落地 | gac-local-gate 44 checks 全绿常态 |
| P2 锁原子化+心跳 | 协调层 | ✅ **超额落地** | T1-05A SQLite 协调层 shadow 运行（6 agent 心跳 fresh），远超原方案设计 |

**判定：止血层（P0/P2）基本就位，根治层（P1 拓扑）卡在半程。**

## 2. 08-06 后新事故差量（按 E1-E6 归因）

| # | 事故 | 日期 | E 归因 | 成本 |
|---|---|---|---|---|
| A1 | worktree 被并发 agent 清除 ×2（r2 轮 + T2-03 轮） | 08-14/15 | E1 共享实例 | 2×30min 重建 |
| A2 | stash 误弹共享栈（pop 了别人的 stash@{0}） | 08-15 | E1 共享实例（stash 栈全局共享） | 20min 恢复 |
| A3 | 主仓 HEAD 被并发 agent 切到他人分支 | 08-15 | E1 共享实例 | 绕行（文件级对齐）+ 15min |
| A4 | 4 个已 merge worktree + 分支泄漏 | 08-15 | E1 无清理机制 | 靠人工清（本轮已清） |
| A5 | 前任 agent 预算耗尽暴毙，`ws-blueprint-agent-governance` 目录消失、无交接 | 08-15 | **E7（新）** | 接手盘点 1h |
| A6 | omo venv 里 ecos 是 08-08 旧拷贝（版本号未变不重装） | 08-15 | **E8（新）** | 排障 20min |
| A7 | bump-fast 测试污染真实 repo | 08-14 | 测试纪律（已制度化 AGENT-BRIEF §3.2） | 已修 |

**合计直接时间成本 ≈ 3.5h / 9 天，全部落在旧路径（A1-A4）或报告未覆盖面（A5-A7）。**

## 3. 报告未覆盖的两个新病根

### E7 — Agent 生命周期终结无交接协议

前任 agent 暴毙时的状态：worktree 无痕消失（无 delete 记录）、活着的 Orca codex worker 无人知道（本轮靠 `orca terminal list` 翻出来）、T1-18 任务卡 in_progress 挂空、方案文档只写了一半。

**这不是拓扑问题**——独立 clone 拓扑下 agent 暴毙同样会留孤儿。缺的是「退役清单」：
- agent 停工前必须产出 handoff 文档（哪些 worktree/worker/claim 在途）
- Orca terminal/agent 有生命周期标识（孤儿 worker 超时回收）
- 本轮 SR-06b 恰好把这个孤儿 worker 复用成了演习 executor——是运气不是机制

### E8 — 多子仓 venv 缓存失真

`uv` 以版本号判断依赖新鲜度，ecos 子仓加了文件但版本号没动 → omo 的 venv 里是 7 天前的旧拷贝 → import 静默失败。**多子仓 + path 依赖 + 版本号不动 = 缓存陷阱**，每个 agent clone 都会独立踩一遍。

**修法**（低成本）：子仓 CI 或 agent-clone create 后固定跑 `uv sync --reinstall-package <本地 path 依赖>`；或子仓提交时必 bump patch 版本（后者太重，前者一行命令）。

## 4. D2 铺开决策备忘（本复盘的直接产出）

**决策：按 blueprint-collab-consolidation-v1.md §6 节拍执行——08-21 T1-05A 收口 → 渐进周（新 claim 引导走 clone）→ 08-28 硬收口（激活 agent-clone guard 主仓封写）→ D3。**

决策依据：
1. 事故 100% 在旧路径（§2），新路径（~/agents/）零事故——迁移方向被数据背书
2. 双轨 9 天成本 3.5h，按当前 agent 并发密度（6 心跳），敞到月底 ≈ 再损失 6-8h
3. 硬收口的工具（guard）已存在零开发量，剩下的只是决心
4. 渐进周同时是协调层 warning 阶段的实战期（T1-05A shadow→warning 衔接）

**配套（本复盘新增项）**：
- D2 迁移附带「agent 退役清单」协议（治 E7）：handoff 文档 + Orca worker 孤儿回收
- agent-clone create 流程内嵌 `uv sync --reinstall-package`（治 E8）
- janitor（PR-C）上线后双轨残留量化进入周 checkpoint（janitor dry-run 输出即曲线）

## 5. 长期解（回答「有没有更好的方案」）

现状三层结构（主仓 + 19 子仓 gitlink + N agent 实例）的根本成本在**子仓指针同步**——本轮 T9-01 两次 bump-pointer 折腾（远端可达校验失败/缓存 SHA）都是 gitlink 语义的复杂度。

替代拓扑对比（结论：维持现方案，但记录判据）：

| 方案 | 优点 | 致命伤 | 判定 |
|---|---|---|---|
| 现方案：submodule + 独立 clone | 职责边界清晰、CI 可达性校验成熟 | 指针操作繁琐、venv 缓存陷阱 | ✅ 维持（E8 一行修复后成本可控） |
| monorepo 全并 | 零指针成本 | 归并判定未做完（T1-01/T1-02 才刚顺延）、19 仓权限边界重画 | ❌ 时机未到（Y1Q3 T6-01 归并后重评） |
| git subtree | 指针隐式 | 历史污染、回滚困难，违背蓝图「ref 集成」不变量 | ❌ |
| bare repo + worktree 池（机器级共享） | 省 90% 磁盘 | refs/HEAD 又共享了——回到 E1 | ❌ 08-06 已否 |

**真正的长期解不是换拓扑，而是让「多实例单写者」跑完整**：I1-I3 三不变量全部物化（guard 激活 = I1）+ 协调层转 fail 模式（I3 的运行时保障）+ agent 退役协议（补 I2 的生命周期缺口）。

## 6. 给下一个 agent 的清单

1. 08-28 硬收口前：确认 janitor（PR-C）已上线并有 3 天以上 dry-run 数据
2. D2 迁移脚本注意 E8：每个新 clone 建好后强制 reinstall 本地 path 依赖
3. E7 退役协议落地前，接手别人工作先跑 `orca terminal list` + `ls ~/agents/` 盘点活资产
4. 本复盘 §4 决策已挂 MILESTONES-2026Q3Q4.md M2 里程碑，执行时勿再讨论方案本身

## 6.1 08-16 差量补录 — 共享 checkout 并发吸收 staged 工作（E9）

**事故**：bin/scripts convergence 高频轮次域（round8→round13 数小时推进）的并发 agent 在共享 checkout 上执行 `git add -A && git commit`，把**我 staged 的 round9 登记（audit `_is_internal_module` 修复 + manifest 141 镜像对）连同其 round11 工作**打包成一个混合 commit（8ead84ce0），reflog 出现非主动 commit。

**判定**：内容无损 — 我的改动随 8ead84ce0→#1569→#1570→#1573 链合入 main（manifest 233 条），无重复 PR。被吸收 ≠ 失败，但暴露了 §1 P0 判定「主仓仍在被 agent 直接改文件」的持续化——共享 checkout 仍是 agent 的可写面。

**E9 处理范式（已写入 AGENTS.md §1.6.2 / CLAUDE.md §B.3）**：
1. 发现非主动 commit 不贸然 reset — 先 `git reflog -8` + `git show <sha> --stat` 审查
2. 验证工作是否已合入 main：`git show origin/main:<path>` 对比
3. 已合入 → `agent-workflow close <run-id> --status blocked --evidence "..."` 记录，不重复交付
4. 本地 main 被并发直接 push 成非远端 commit（`rev-list --left-right --count origin/main...main` 分叉）→ **勿 reset --hard**，保留由并发 agent 处理

**给团队的提醒**：
- 该域（bin/scripts convergence、台账、SSOT）作业前先 `git worktree list` + `agent-workflow status` 查并发 worktree 与 active runs
- 提交前 `git show origin/main:<path>` 核对 main 最新版，防重复登记
- 完整范式见 memory `feedback_shared_checkout_concurrent_absorb_20260816.md`

## 7. Changelog

| 日期 | 变更 |
|---|---|
| 2026-08-15 | v1: 五件事落地率审计 + 7 事故差量归因 + E7/E8 新病根 + D2 决策 + 拓扑替代方案对比 |
| 2026-08-16 | v2.1: §6.1 补录 E9 共享 checkout 并发吸收 staged 工作（8ead84ce0 事件）— 处理范式已固化到 AGENTS.md §1.6.2 / CLAUDE.md §B.3 |
