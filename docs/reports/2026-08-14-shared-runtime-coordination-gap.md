---
title: 多 Agent 共享运行时状态的缺口——为什么「拓扑改造」不够
type: analysis-and-strategy
owner: 夏明星
created: 2026-08-14
lifecycle: report
related:
  - docs/reports/2026-08-06-multi-agent-git-topology.md
  - .omo/_truth/registry/swarm-coordination.yaml
  - docs/plans/3y-bet-ledger.yaml#BET-Y1Q1-T1-05
  - docs/local-compute/omlx-cluster-architecture.md
note: >
  本文是对 2026-08-06《多 Agent 并行的 Git 拓扑分析与根治方案》的延伸，
  聚焦该报告里定义但未展开的「L3 状态面」。数据为 2026-08-14 实测
  （git ls-files 计数、.gitignore 核对、swarm-coordination.yaml 现状）。
---

# 多 Agent 共享运行时状态的缺口——为什么「拓扑改造」不够

## 0. 一句话结论

你的直觉是对的，而且比"要不要加一个共享区"更严重：**T1-05 拓扑改造如果不配套做协调层，落地后会让现有的任务协调机制静默失效，而不是变好。** 这不是新战线，是 T1-05 范围内一个被漏掉的前置。

---

## 1. 现状实测

2026-08-06 的报告已经把共享可变状态分了三层：

| 层   | 共享的东西 | 现有隔离 | 该报告的判定 |
| --- | --- | --- | --- |
| L1 仓库 | HEAD / index / 工作树 | git worktree | 1/8 在用，仍在共享主树上互相冲突 |
| L2 子模块 | `.git/modules/<sub>/HEAD` | PASW | 3/18 覆盖，其余 15 个裸奔 |
| **L3 状态面** | **`.omo/` 锁 / run / state** | **文件锁 + TTL** | **全覆盖但脆：写锁非原子、无心跳、失败不回滚** |

该报告给 L1/L2 开了完整药方（独立 clone），给 L3 只开了一味止痛药（M5：锁原子化 + 心跳 + stale 清理）。今天实测了一下 L3 的真实构成，发现问题比"锁不原子"更根本：

- `.omo/state/` 下 **39 个文件是 git-tracked**，`.omo/_truth/registry/` 下 **87 个文件是 git-tracked**。
- 这两个目录里躺着大量本质是**实时运行时数据**、而非配置的东西：agent 心跳/日志（`agent-tick-daemon.jsonl`）、跨 agent 消息（`a2a-messages.jsonl`）、健康状态（`health.yaml`）、持续增长的指标（`metrics-store.jsonl` 32KB、`mesh-consumer-trace.jsonl` 203KB）、`memory-os.yaml` 的 belief/snapshot 计数。
- 对比：只有 `runtime/omo/event-ledger.sqlite3` 和 `kos/kos-index.sqlite` 被正确地放进了 `.gitignore`，是这个仓库里**唯一两处**"活的运行时数据不进 git"的正确样板，其余大量同类数据仍在被当成"该版本化的文件"对待。
- 顺带解释了一个今天顺手发现但没深究的异常：清理 workspace 时,本地未提交版本的 `.omo/_truth/registry/memory-os.yaml` 时间戳更新（2026-08-14T10:13）但计数从 19/43 掉到 1/1,当时判定为"另一个数据健康问题,建议你自己查"。现在看，这很可能就是同一个病根的另一个症状——运行时投影数据被塞进了 git 版本化的文件里，在多个并发 checkout/reset 之间必然互相踩踏。

**D2「分支占用锁」/ D3「共享树 claim」的实现细节**（`swarm-coordination.yaml::gates`）：锁文件写在 `.omo/_delivery/`。这个目录本身正确地进了 `.gitignore`，但它是**相对当前 checkout 的本地目录**，不是**跨所有 checkout 物理共享的目录**。这是本文最关键的一个发现，见下节。

---

## 2. 核心发现：T1-05 一旦落地，会让 D2/D3 协调机制静默失效

引用 2026-08-06 报告 3.1 节的方案原文：每个 agent 会有自己独立的 clone（`~/agents/<id>/ws`），彼此 **refs / HEAD / index / modules 完全独立**。这解决了 git 层面的冲突（E1、E6），完全正确，不需要改。

但 D2/D3 锁靠的前提是"大家在同一个物理 checkout 里，能看见彼此写在 `.omo/_delivery/` 里的锁文件"。一旦每个 agent 有了独立 clone：

```
~/agents/atlas/ws/.omo/_delivery/branch-claims/   ← atlas 自己的，codex 看不见
~/agents/codex/ws/.omo/_delivery/branch-claims/   ← codex 自己的，atlas 看不见
```

这两个目录是**物理上不同的两份文件**，互相不可见。报告 3.2 节把 D2/D3/D5 排进了"D3 减法阶段"直接退役，理由是"物理复制之后不需要锁了"——这个理由对 git 冲突层面成立，但 **D2/D3 解决的其实是"任务认领"这个业务协调问题，不是"git 冲突"这个技术问题**，两者在报告里被合并处理了。任务认领的协调需求不会因为仓库变成多实例而消失，只是**失去了原来（虽然脆但好歹能用）的实现载体**，而且失效方式比现在更隐蔽：

> agent A 在自己 clone 里认领了某个 bet，这个认领记录只存在于 A 的 clone 本地。agent B 在自己 clone 里跑 `claim-check`，读不到 A 的锁，判定这个 bet 没人做，也去认领。两个 agent 同时做同一个 bet，互相不知道，**不会在认领时报错，会在两份 PR 都提出来时才炸出来**——比今天的冲突更晚发现、更难定位。

`swarm-coordination.yaml` 里 `topology_migration.transition.retirement_requires` 已经列了退役 D2/D3/D5 的前提条件（`real_clone_pilot_verified` / `all_active_agents_migrated` / `integration_root_agent_reflog_window_clean`），但这些条件里**没有一条检查"迁移后跨 clone 的任务认领是否还能互相看见"**。这是一个真实的验收盲区。

---

## 3. 需要的架构：git 之外的共享运行时层

结论：不是"要不要建"，是"必须在 T1-05 D1 试点阶段就位"，否则从 D2（全员迁移）开始会有一段协调真空窗口，且不会有报错提示你它已经失效。

### 3.1 设计要点

**位置**：一个所有 agent clone 和主仓都能访问、但不属于任何一个 git 工作树的路径，与 `~/agents/<id>/ws` 平级，例如 `~/agents/_shared/runtime/`。不能放在任何一个 clone 内部（哪怕是主仓 `~/Workspace`），否则又会变成"谁的 checkout 恰好在跑就以谁为准"。

**存储**：SQLite + WAL 模式。WAL 原生支持多进程并发读 + 串行化写，这正是协调层需要的东西——不需要在业务层用"临时文件 + rename"手搓一套弱化版事务（M5 想解决的 E2，本质就是在重新发明数据库该干的事）。

**内容迁移**（从"git-tracked 但本质是运行时数据"搬过去）：

| 现状（git-tracked） | 迁移后 |
| --- | --- |
| `.omo/_delivery/adr-claims/`、`branch-claims/`、`swarm-conflicts/events.jsonl` | 共享 SQLite 的 `claims` / `conflict_events` 表 |
| `.omo/state/health.yaml`、`agent-tick-daemon.jsonl` | 共享 SQLite 的 `agent_health` 表（心跳写入，TTL 判活） |
| `.omo/state/a2a-messages.jsonl` | 共享 SQLite 的 `messages` 表 |
| `.omo/state/metrics-store.jsonl`、`mesh-consumer-trace.jsonl`、`autoloop-trace.jsonl` | 共享 SQLite 的 `metrics` / `trace` 表 |
| `workers.yaml` 里"谁在线/在做什么"的实时字段 | 共享 SQLite；`workers.yaml` 只保留配置性质字段 |
| `memory-os.yaml` 的计数投影 | 若确认是运行时生成物，迁到共享 SQLite；建议先查一下它当前的生成路径 |

**不动的（继续留在 git，这些需要版本历史和审计）**：`swarm-coordination.yaml` 这类策略配置、`3y-bet-ledger.yaml`、ADR、retros、`AGENT-BRIEF.md`。判断标准很简单：**这份数据是"需要 diff review 的决策"，还是"下一秒就会被覆盖的状态快照"**——前者留 git，后者进共享层。

### 3.2 访问方式：两个选项

- **轻量**：每个 clone 直接用绝对路径打开同一个 SQLite 文件（WAL 模式，无需额外进程）。本机多 agent 场景够用，最省事。
- **规范但重一点**：起一个小 daemon（Unix socket，单写者）。这正好是你们在 omlxc v3 里已经验证并上生产的模式——Task 5 runtime："private, versioned, single-writer SQLite store with durable Job/event recovery... 独立 AnyIO 事件订阅、fail-closed health freshness、keyed single-flight"。协调层的写入量级（多 agent 心跳/claim/消息）跟 omlxcd 的负载性质接近，**建议直接复用这个已经踩过坑的设计，不用重新发明**。

选哪个取决于一个开放问题：协调层要不要覆盖跨主机的 agent（tailnet 上的远程节点）。只在本机多进程 → 直接 SQLite 文件够用；要跨机 → 需要 daemon + 网络层，这时候 omlxcd 的模式几乎可以照抄。

---

## 4. 战略层建议

1. **别把这个当成 T1-05 之外顺手做的事**——建议直接补进 T1-05 的 `done_when`，或者拆一个强依赖的前置 bet（比如 `BET-Y1Q1-T1-05a` 共享运行时层），要求在 **D1 试点阶段**就有，不能等到 D2 全员迁移完才发现协调断了。
2. **复用已验证模式，不新建一套**：omlxc Task 5 runtime 已经是"single-writer SQLite + durable event/job + fail-closed health"的完整实现，是你们自己已经上生产、验证过的东西。这条路线跟 Y1「表面积净负增长」的目标不冲突——净增一个共享库/daemon，换掉的是 D2/D3/D5 三层纪律加一堆脆弱的文件锁逻辑，净值大概率是减的，可以按 D2 铁律记账验证。
3. **把 `memory-os.yaml` 的计数异常一并核查**——19→1、43→1 那次异常，很可能不是孤立 bug，是这个架构缺口已经在发作的证据，值得作为这个分析的第一个真实案例。
4. 你是 T1-05 的 `human_gate`，建议**在批准开工前先确认执行方案里包含协调层这部分**，不要等 D2 全员切完 clone 之后才发现锁失效——那时候的排查成本会比现在高很多。

---

## 5. 待验证的开放问题（不是我能替你判断的）

- `workers.yaml` 里哪些字段是"配置"该留 git、哪些是"实时状态"该搬走，需要过一遍现有 schema 逐字段判断。
- 协调层要不要对 Orca / Codex 等非 Claude agent 暴露同样接口，还是各自适配——涉及已有的 `bin/gac/codex-worker-adapter.py` / `bin/gac/orca-codex-supervisor.py` 这条线，需要跟那边的设计对齐。
- daemon 方案 vs 直接 SQLite 文件访问：取决于协调层未来要不要支持跨主机 agent，这是个产品/规划决策，不是纯技术判断。
