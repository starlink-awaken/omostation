---
lifecycle: spec
owner: engineering-agent
last_updated: 2026-08-28
title: 全生态价值流深度分析 — 断链诊断与串联方案 (2026-08-28)
type: doc
---

# 全生态价值流深度分析 — 断链诊断与串联方案 (2026-08-28)

> 数据基线: 事件流 3787 条(96%心跳) · 北极星 proposal_adoption_rate=0.0 · A2A messages=0 · claims 停摆于 08-18 · 964 提案 0 采纳 · retro 引用率 1/15

## 一、诊断：五条断链（数据实锤，非感觉）

### 断链 ① 知识沉淀 → 价值转化 【最严重】

```
产生侧: 964 个提案 (new) + 187 个 retro + 700+ 分类历史  ← 大量生产
消费侧: 0 adopted / 0 executed / 0 verified               ← 零消费
         retro_referenced: 1/15 (6.7%)
```

**症状**: 知识库在疯狂堆积，但没有任何机制把提案变成行动。
北极星的 `proposal_adoption_rate: 0.0` 不是"还没跑"，是**跑了但结果是零**。

**根因**: 提案 (964 个 new) 没有出口——没有"提案→BET→执行"的管道，
也没有"提案→蜂群任务"的分发。知识生产者和消费者之间**没有桥**。

### 断链 ② 六蜂群 → 实际工作 【心脏在跳，手脚不动】

```
心跳: 6/6 Active (01:55 新鲜)      ← 活着
claims: 最新 2026-08-18 (10天前)   ← 没在抢活
messages: 0 条                    ← 从未互相通信
真实产出: 3 个 WorkflowRequested   ← 几乎没干活
```

**症状**: 六 agent 心跳完美但**不干活**。claims 表停在 8/18（93 个过期 active），
A2A messages 一次没用过。

**根因**: 蜂群有"活着的机制"（heartbeat）但没有"取活的机制"（Goal 模式
未启动 + AGENT-TEMPLATES 派单没有调度方 + 提案池没接到任务分发）。

### 断链 ③ 事件流 → 智能决策 【信噪比灾难】

```
最近 500 条: system.alive 480 (96%) + 真实工作 20 (4%)
StepFailed: execute ×2 (无人处理)
```

**症状**: 事件流是体系的"神经系统"，但 96% 是心跳噪音。真实信号
（StepFailed ×2）淹没在里面无人响应。

**根因**: 心跳和业务事件混在一条流里（一个 brain 应该有感觉神经和
运动神经的区分）；没有事件分级路由。

### 断链 ④ AGE-v2 Cell → 一切 【十个模块的幽灵】

```
代码: cell/pool/dag/cartridge/governance/memory_network/replay/handler/state/config (10 模块)
运行时: agent-cell/ 目录空
```

**症状**: DAG 编排、记忆网络、回放——最高级的 agent 基础设施全部 dormant。

**根因**: Cell 体系是为"蜂群开战"设计的，但 blueprint §3 判定"当前不具备
直接开蜂群的条件"——于是造了引擎没造点火系统。

### 断链 ⑤ 信号源 → 业务闭环 【单一且枯竭】

```
信号源: 仅邮件 (Apple + 网易)
任务邮件: 700 封中 1 封 (0.14%)
auto-journey: 0 次触发
BCOS 信号路由: 建了没跑
```

**症状**: 整个数字大脑只有邮件一个信号源，且真任务近乎为零。
P0 工作域的"敌人"根本没来。

**根因**: OA/日历/IM 信号源未接入；邮件又主要是 JetBrains 刷屏（已修）。

## 二、根因归纳：一个模式

五条断链背后是同一个模式：

```
      ┌─ 基础设施层 ─┐         ┌── 价值循环层 ──┐
      │ 心跳/锁/事件 │ ███████ │ 提案→采纳→执行 │
      │ 流/场景卡    │ 建成了  │ →沉淀→再利用   │ ← 没建成
      └─────────────┘         └───────────────┘
```

**"造好了血管，没有血液"**——所有"感知/记录/存储"的单向设施都建成了，
所有"消费/转化/循环"的双向闭环都没闭合。这不是某个组件的 bug，
是**建设优先级系统性偏向 infrastructure 而非 value loop**。

历史佐证（AGENT-BRIEF 自己写的）:
- "自出题自答冒充能力证据: 221 个协作场景是自造夹具"
- "代理指标冒充真实指标"
—— 体系自己早已诊断出这个病，但治理动作（减法）砍掉了假指标，
没有接上真价值。

## 三、串联方案：三条价值动脉

原则: **不建新组件，只接断点**（用户的"dormant 要用起来"+"扩展现有架构"）。

### 动脉 A: 提案→行动 管道（治断链①②，价值最高）

```
现有: proposal pool (964 new) ──✕──> 无出口
                │
接上: ┌─────────▼──────────────────────────────┐
      │ proposal-triage (周度, 复用 BCOS evolve │
      │  四阶段 observe→propose→evaluate→approve)│
      │  1. 每周从 964 个 new 里筛 top-N        │
      │  2. 高价值 → 建 BET (T7-SCENE 轨道)     │
      │  3. 派给六蜂群 (AGENT-TEMPLATES 模板)   │
      └─────────┬──────────────────────────────┘
                ▼
      六蜂群 Goal 模式 (AGENT-GOALS-4X 已有模板, 启动即可)
                ▼
      PR 合并 = adopted (北极星 adoption_rate 开始动)
```

**改动量**: 1 个 triage 脚本 + 启动 Goal 模式 cron。**零新架构**。

### 动脉 B: 事件分级路由（治断链③，让神经系统能反应）

```
现有: events.jsonl 一锅烩 (96% 心跳)
                │
接上: ┌─────────▼────────────────┐
      │ 事件分级 (改 resident-routes)│
      │  P0: StepFailed/alert     │──> governor 立即处理
      │  P1: Workflow*            │──> sediment 沉淀
      │  P2: system.alive         │──> 降采样 (5min→1h 聚合)
      └───────────────────────────┘
```

**效果**: 事件流信噪比从 4% → 90%+；StepFailed 不再无人管。

### 动脉 C: Cell 接线点火（治断链④，激活十个 dormant 模块）

```
现有: cell_* 10 模块 dormant
                │
接上: ┌─────────▼─────────────────────────┐
      │ 最小点火: 把动脉A的蜂群任务改成     │
      │ Cell DAG 形态 (cell_dag 已支持)    │
      │   proposal-triage 本身做成第一个    │
      │   Cell DAG: 提取→评分→排序→派发    │
      │ 记忆: cell_memory_network 接       │
      │   classification-history (已有700条)│
      └────────────────────────────────────┘
```

**点火条件**: 动脉 A 先跑通（有真实任务流）→ Cell 才有 DAG 可编排。
**顺序不能反**——这是 blueprint §3 判定"不开蜂群"的正确原因。

### 动脉 D (P2): 信号源扩展（治断链⑤）

```
邮件 (已修黑名单) → Seeyon OA 抓取 → 日历读取 → ...
```
依赖用户单位环境的可达性，独立推进。

## 四、迭代路径（价值排序）

| 阶段 | 动作 | 判据 (北极星能测) |
|------|------|-------------------|
| **S1 (1周)** | 动脉B 事件分级 (最小改动) | 事件信噪比 4%→90% |
| **S1 (1周)** | 动脉A 提案 triage 脚本 + 首轮 top-5 | proposal adopted 0→5 |
| **S2 (2周)** | 六蜂群 Goal 模式启动 (接动脉A) | claims 恢复活跃, messages >0 |
| **S2 (2周)** | auto-journey 真实验证 (等首封任务邮件) | journeys 0→1 |
| **S3 (3周)** | Cell DAG 点火 (proposal-triage 做首 DAG) | agent-cell/ 有状态 |
| **S3 (3周)** | retro 引用机制 (sediment 提取→下次 prompt 注入) | retro_referenced 1→10+ |
| **S4** | 信号源扩展 OA/日历 | 任务信号 >1/周 |

## 五、一句话总结

**体系不缺器官，缺循环**——26 个常驻服务是器官，五条断链是没接的血管。
先接"提案→行动"这条主动脉（北极星 adoption_rate 从 0 变 1 就是第一滴血），
其他动脉按价值排序依次接上。全部用现有组件，零新架构。

## 附: 断链×组件映射（什么already exists能接什么）

| 断链 | 已有组件 (直接复用) | 缺的只是 |
|------|---------------------|----------|
| ①提案→行动 | BCOS evolve 四阶段 / BET 台账 / AGENT-TEMPLATES | triage 脚本 1 个 |
| ②蜂群干活 | Goal-4X 模板 / claims 表 / D2 锁 | 启动 cron + 首批 goal |
| ③事件分级 | resident-routes.yaml / governor | 路由规则 + alive 降采样 |
| ④Cell 点火 | cell_dag / cell_pool / memory_network | 一个真实 DAG 场景 |
| ⑤信号源 | mail-daemon 架构 / BCOS signal_router | OA/日历 connector |
