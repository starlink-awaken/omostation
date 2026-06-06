# eCOS v5 架构落地细化方案

> 状态: revised
> 日期: 2026-06-05
> 目标: 把 eCOS v5 从“架构愿景”压成“当前 workspace 可执行蓝图”
> 约束: 以 live tree 为准，不再以旧 phase 文档、旧 inventory、旧项目名做前提

---

## 1. 结论先说

当前 workspace 已经不是“缺一套新架构图”，而是已经出现了三层事实：

1. eCOS v5 的目标架构已经成形。
2. `projects/runtime`、`projects/omo`、`projects/kairon` 里已经落了一部分骨架。
3. 入口文档、inventory、用户主路径、验证口径还没有完全收口。

所以这轮不应该继续抽象设计，也不应该继续只修 OMO 控制面。正确动作是：

- 把 live 实现映射回 eCOS v5 各层；
- 明确哪些层已经落地，哪些只是半成品；
- 按“协议 -> 运行时 -> 主路径 -> 治理/抗熵/价值”的顺序推进；
- 用可验证的主路径收口，而不是继续堆概念。

---

## 2. 当前 live 基线

### 2.1 工作区项目基线

以当前目录树为准，workspace 主体已经是：

- `projects/kairon/`：知识与研究能力栈
- `projects/gbrain/`：知识捕获/检索后端
- `projects/runtime/`：L0/L1/I0/KEI 运行时骨架
- `projects/omo/`：治理与证据工具链
- `projects/hermes-console/`：独立前端/控制台候选
- `projects/_archived/agentmesh/`：已归档
- `projects/_archived/SharedBrain-original/`：已归档

### 2.2 当前关键事实

- `kairon` 当前 live 包数是 24，不是 25/31。
- `agentmesh` 和 `SharedBrain` 已不再是 live sibling repo，应按 archived/externalized boundary 对待。
- `projects/runtime` 已经存在以下骨架，不应再把它当作纯提案：
  - `runtime/protocol.py`
  - `runtime/scheduler.py`
  - `runtime/i0.py`
  - `runtime/taskobject_adapter.py`
  - `runtime/kei.py`
- `projects/omo` 已经把 Phase15/16 的 evidence、scenario、experience、worker 链打通到当前 `.omo` 四层结构。

---

## 3. eCOS v5 到当前仓库的映射

### 3.1 L0 协议编织层

当前应以两类资产共同构成 L0：

- `projects/runtime/protocols/`
  - `L0-registry.yaml`
  - `tri-plane-registry.yaml`
  - `ecos-ontology.yaml`
- `projects/runtime/src/runtime/protocol.py`
  - 负责把协议注册表装载为运行时对象

定位：

- L0 不再是“以后要做”的层，已经有注册表和装载逻辑。
- 但它仍缺少与 `.omo/standards/`、`interface_contract.md` 的强约束对齐。

### 3.2 L1 运行时矩阵层

当前主实现已经存在于：

- `projects/runtime/src/runtime/matrix.py`
- `projects/runtime/src/runtime/scheduler.py`

定位：

- L1 已具备服务注册、存活探测、调度和健康扫描能力。
- 但它和 `.omo/state/system.yaml` / `.omo/state/system_health.yaml` 之间仍存在状态分裂风险。

### 3.3 L2 内核三平面层

当前建议固定为：

- 治理平面：`projects/omo/`
- 能力平面：`projects/kairon/`
- 知识平面：`projects/gbrain/`

设计原则：

- `omo` 不继续吞业务能力，只负责治理、证据、调度契约。
- `kairon` 不再继续泛化成“大一统 OS 名字桶”，重点收敛能力契约、路由与入口。
- `gbrain` 聚焦 capture/search/retrieval 主路径，不替代治理层。

### 3.4 L3 入口桥接矩阵层

当前 live 候选入口不是一个，而是四类：

- `projects/kairon/packages/wksp/`
- `projects/runtime/src/runtime/cli.py`
- `projects/runtime/src/runtime/mcp_server.py`
- `projects/kairon/packages/sharedbrain-bridge/`

结论：

- L3 还没有真正收敛成“一个 operator home + 一个 user home”。
- 这正是当前架构落地的主战场。

### 3.5 L4 自我层

当前 L4 真相更接近：

- `.omo/_truth/`
- `.omo/_control/`
- `.omo/_knowledge/`

L4 的问题不是“没有数据”，而是：

- 自我认知与 live inventory 偶尔漂移；
- 对外讲述还没有压成稳定入口。

### 3.6 I0 集成织物层

当前 I0 应视为两段式：

- `kairon/agora`：服务发现、路由、事件与主集成面
- `runtime/i0.py`：查询、探测、协议总览、graph 视图

结论：

- I0 已经不是缺席，而是双源并存。
- 下一步要做的是职责边界收敛，不是重写。

### 3.7 X1/X2/X3 横切面

- X1 治理安全：`projects/omo` 已具备主骨架
- X2 抗熵演化：已有 debt/freshness/dashboard 资产，但自动化还不稳定
- X3 价值堆栈：已有 ledger / costing / tier 资产，但还没收成稳定的预算/价值闭环

---

## 4. 当前真正的结构性缺口

### 4.1 缺口 A：inventory 漂移先于一切

如果包数、项目边界、归档状态都不准，任何架构图都是假图。

当前必须接受一个原则：

- 架构叙事从 live scan 生成；
- 文档跟随 live tree；
- 不允许再反过来让 live tree 迁就过期文档。

### 4.2 缺口 B：L3 入口没有收口

现在的问题不是“没有入口”，而是入口过多：

- `wksp`
- `runtime cli`
- `agora`
- `sharedbrain-bridge`
- 各包自带 CLI

这会直接导致两个后果：

1. 用户不知道该从哪进。
2. 运维不知道哪个入口代表系统主路径。

### 4.3 缺口 C：L0/L1/L4 的真相还没完全串起来

现在已经有：

- L0 protocol registry
- L1 scheduler / matrix
- L4 `.omo` truth/state

但三者之间还缺少稳定的状态桥：

- 协议变更如何影响运行时？
- 运行时状态如何回流治理面？
- 治理面如何不覆盖运行时事实？

### 4.4 缺口 D：用户价值主路径仍太窄

Phase16 锁定的 `knowledge-capture-search` 是正确方向，但还只是一个受控样本。

要落实架构，不能只证明“治理存在”，必须证明：

- 用户能输入知识；
- 系统能捕获；
- 能检索回来；
- 能解释为什么可信；
- 失败时能恢复。

### 4.5 缺口 E：X2/X3 还是偏“资产存在”，不是“闭环生效”

现在的抗熵、成本、价值层更多是：

- 有文件
- 有脚本
- 有草案

但还没有稳定证明：

- 它们持续运行；
- 它们影响主路径决策；
- 它们不会制造更多噪音。

---

## 5. 锁定后的架构落地原则

### 5.1 先收敛，再扩张

在 `knowledge-capture-search`、`wksp` 主入口、`agora` 控制面没有稳定之前，不再把重心放到新生态吸收上。

### 5.2 一层只解决一类问题

- L0 解决协议边界
- L1 解决运行时可见性
- L2 解决能力与治理分工
- L3 解决入口和桥接
- L4 解决自我认知和策略

不要让 `omo` 去补产品，不要让 `kairon` 去补治理，不要让 `gbrain` 去补入口。

### 5.3 主路径优先于覆盖率

先把一条用户主路径做深、做稳、做可证据化，再扩展第二条、第三条。

### 5.4 文档必须服务运行，不允许自嗨

后续所有架构文档都要回答四个问题：

1. 改哪个真实模块？
2. 为什么现在改？
3. 验证命令是什么？
4. 失败回滚口径是什么？

---

## 6. 执行路线

### Stage 0：冻结事实口径

目标：让所有高频入口文档先说真话。

动作：

- 修正 workspace `README.md`
- 修正 `projects/kairon/AGENTS.md`
- 将 archived boundary 写清
- 把“24 live packages”作为当前事实基线

验收：

- workspace 入口文档不再声称 31 包
- 不再把 `agentmesh` / `SharedBrain` 当成 live sibling repo

### Stage 1：L0/L1/L4 状态桥收口

目标：让协议、运行时、治理状态形成单向清晰链路。

动作：

- 固定 L0 真相源：`projects/runtime/protocols/*`
- 定义 L1 输出与 `.omo/state/` 的映射边界
- 明确 `system.yaml` 与 `system_health.yaml` 的角色区分
- 补一份状态流转图，说明谁写、谁读、谁验证

验收：

- health / protocol / state 三者职责不再重叠
- 至少一条 health state 变化链可以被复现实证

### Stage 2：L3 入口收口

目标：明确 operator home 和 user home。

建议锁定：

- operator home：`wksp`
- fabric/query home：`runtime i0` + `agora`
- user result home：Phase16 `knowledge-capture-search` 结果面

动作：

- 将 `wksp` 定义为主操作入口
- 把 `runtime` 定义为运行时观察/运维入口
- 把 `agora` 定义为集成织物与服务控制面
- 重写 `sharedbrain-bridge` 的边界说明，停止假装它还桥接一个 live sibling repo

验收：

- 能清楚回答“用户从哪进”“运维从哪看”“能力从哪接”

### Stage 3：Phase16 主路径做实

目标：用一条端到端路径证明架构不是纸面。

主路径固定为：

`输入知识 -> gbrain capture -> gbrain search -> kairon trace/binding -> .omo evidence -> 用户结果状态`

动作：

- 保持 SharedBrain/result-home 语义，但不再作为主仓边界前提
- 补全 walkthrough / recovery / closeout 的 live 验证链
- 明确 fixture-backed 和 live-backed 的分界

验收：

- 至少一条 capture/search walkthrough 可重复执行
- blocked / recovery / completed 三类状态有证据

### Stage 4：X2/X3 从资产升级为闭环

目标：让抗熵和价值层真正约束系统，而不是只存在于文档。

动作：

- 把 freshness / debt compaction / dashboard 更新接到固定调度链
- 给 costing / value tier 增加最小可见输出
- 只做软约束与告警，不在未验证前上强熔断

验收：

- 至少一个 freshness 或 debt compaction 流程可复现
- 至少一个成本或价值告警能进入可见结果

---

## 7. 近期优先级

### P0

- inventory 和入口文档口径统一
- `wksp` / `agora` / `runtime` / `sharedbrain-bridge` 的边界文案统一
- `knowledge-capture-search` 主路径证据持续可跑

### P1

- L0/L1/L4 状态桥文档化并最小实现验证
- `sharedbrain-bridge` 重新定义为 externalized boundary bridge
- runtime health 与 `.omo` 状态的角色分层

### P2

- X2 freshness / compaction 自动化
- X3 costing / value 融入主路径反馈
- 第 2 条用户主路径扩展

---

## 8. 验证矩阵

| 目标 | 证据 |
|---|---|
| 架构口径与 live tree 一致 | live scan + 入口文档一致 |
| L0 存在且被运行时消费 | `runtime/protocol.py` + `protocols/*.yaml` |
| L1 存在且可写出健康状态 | `runtime/scheduler.py` + 状态文件 |
| L3 已定义主入口 | `wksp` / runtime / agora 边界文档 |
| Phase16 主路径可验证 | walkthrough / recovery / closeout evidence |
| X2/X3 不是空壳 | 至少一条自动化或告警链路可复现 |

---

## 9. 这轮之后不该再做什么

- 不继续用过期包数和旧 sibling repo 讲故事。
- 不继续把“控制面增强”当成“用户价值提升”。
- 不继续把 `agentmesh` / `SharedBrain` 的旧 repo 结构当成当前架构前提。
- 不继续为了追求全覆盖而同时开多条主路径。

---

## 10. 最终判断

当前架构不是没落地，而是落地了三分之一到一半，剩下的问题集中在：

- 事实口径漂移
- 入口未收敛
- 状态桥未讲清
- 主路径验证还不够强

所以后续工作的正确目标不是“再发明一套 v6”，而是把 eCOS v5 压实成：

- 一个可信的 live inventory
- 一个清楚的入口矩阵
- 一条跑得通的用户主路径
- 一组真正生效的治理/抗熵/价值闭环

这才算“落实这个架构”。
