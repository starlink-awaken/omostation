---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# L0/L1/L4 状态桥设计

> 状态: proposed
> 日期: 2026-06-05
> 范围: `projects/runtime/protocols/*`, `projects/runtime/src/runtime/scheduler.py`, `.omo/state/*`, `scripts/sync_omo_state.py`
> 目标: 消除协议、运行时、治理状态三套事实互相漂移的问题
> 本文档是历史设计提案，保留当时对状态桥分层与写入边界的设计判断，不是当前 runtime/治理状态分工的唯一实现真相。
> 当前实现仍需以相关代码、`/.omo/state/`、`/.omo/goals/current.yaml` 及最新治理标准为准。

---

## 1. 问题定义

当前系统已经有三套状态资产：

### L0

- `projects/runtime/protocols/L0-registry.yaml`
- `projects/runtime/protocols/tri-plane-registry.yaml`
- `projects/runtime/src/runtime/protocol.py`

### L1

- `projects/runtime/src/runtime/matrix.py`
- `projects/runtime/src/runtime/scheduler.py`
- `runtime/matrix_state.json`

### L4 / 治理面

- `.omo/state/system.yaml`
- `.omo/state/system_health.yaml`
- `.omo/_truth/goals/current.yaml`
- `scripts/sync_omo_state.py`

问题不在于“没有状态”，而在于：

1. 谁是结构真相，谁是运行时快照，谁是治理摘要，没有完全讲清。
2. `scheduler.py` 会写 `.omo/state/system_health.yaml`。
3. `sync_omo_state.py` 会写 `.omo/state/system.yaml`。
4. 上层文档和工具有时把两者都当“系统当前状态”。

这会造成典型的状态分裂：

- health 变了，但治理摘要没更新；
- phase/gate 变了，但 runtime snapshot 不知道；
- 文档只看一种状态文件就得出过强结论。

---

## 2. 设计原则

### 2.1 结构、运行、治理必须分层

- L0：定义系统有哪些协议与边界
- L1：描述系统现在是否活着、是否健康
- L4：描述系统现在认为什么是当前阶段、当前任务、当前 readiness

### 2.2 同一种状态只允许一个主写入者

- protocol registry 只能由 L0 资产维护
- runtime health snapshot 只能由 L1 写
- governance summary 只能由治理同步器写

### 2.3 可以派生，但不能反写污染

允许：

- L4 摘要读取 L1 健康快照
- L1 查询 L0 注册表

不允许：

- L4 直接覆盖 L1 runtime snapshot
- L1 直接改 phase/goal/gate 语义

---

## 3. 角色划分

### 3.1 L0：结构真相源

资产：

- `projects/runtime/protocols/L0-registry.yaml`
- `projects/runtime/protocols/tri-plane-registry.yaml`
- `projects/runtime/protocols/ecos-ontology.yaml`

职责：

- 定义协议、层间映射、注册项
- 描述“系统应该如何通信”

不负责：

- 服务是否在线
- phase 是否完成
- health score 是多少

### 3.2 L1：运行时快照

资产：

- `runtime/matrix_state.json`
- `.omo/state/system_health.yaml`

职责：

- 记录服务探测结果
- 记录端口监听、health check、runtime freshness
- 提供接近实时的运行态事实

不负责：

- 当前 phase/wave
- readiness 结论
- debt / score / policy gate 计算

### 3.3 L4：治理摘要态

资产：

- `.omo/state/system.yaml`
- `.omo/_truth/goals/current.yaml`

职责：

- 记录当前 phase / wave / milestone / score / blockers / debt summary
- 汇总运行时、测试、债务、任务等信号，形成可决策状态

不负责：

- 替代实时 runtime snapshot
- 替代 protocol registry

---

## 4. 状态流设计

### 4.1 建议链路

```text
L0 protocol registry
  -> runtime.protocol / runtime.matrix consume
  -> scheduler scans services
  -> writes runtime/matrix_state.json
  -> writes .omo/state/system_health.yaml
  -> sync_omo_state.py reads:
       - goals
       - tasks
       - debt
       - test output
       - optional runtime health snapshot
  -> writes .omo/state/system.yaml
```

### 4.2 单向依赖

- `L0 -> L1`：允许
- `L1 -> L4`：允许
- `L4 -> L1`：禁止直接回写
- `L4 -> L0`：禁止直接回写

---

## 5. 文件级契约

### 5.1 `.omo/state/system_health.yaml`

定义：

- runtime snapshot mirror
- 接近实时
- 由 `projects/runtime/src/runtime/scheduler.py` 主写

应包含：

- service health
- runtime status
- port listening
- freshness_seconds
- scan timestamp

不应包含：

- current phase
- debt score
- promotion blockers
- readiness summary

### 5.2 `.omo/state/system.yaml`

定义：

- governance summary
- 非实时，但可决策
- 由 `scripts/sync_omo_state.py` 主写

应包含：

- phase/wave/milestone
- health_score / debt_weight / divergence_flags
- task counts
- planned/active/done summaries
- readiness / blockers / promotion gate summary

可派生读取：

- `.omo/state/system_health.yaml`
- `.omo/_truth/goals/current.yaml`
- debt registry
- test output

### 5.3 `runtime/matrix_state.json`

定义：

- runtime 本地状态缓存
- 给 runtime 工具链和守护流程使用

它是运行时内部状态，不应被误当成治理 SSOT。

---

## 6. 当前实现与目标实现的差距

### 已经存在

- `runtime/protocol.py` 已经能装载 L0 registry
- `runtime/scheduler.py` 已经能写 `system_health.yaml`
- `scripts/sync_omo_state.py` 已经能写 `system.yaml`

### 还缺

1. `system_health.yaml` 和 `system.yaml` 的 schema 边界没有被写死
2. `sync_omo_state.py` 是否以及如何读取 `system_health.yaml` 没有明确契约
3. 文档层没有统一告诉使用者：
   - 看 runtime 健康去哪
   - 看治理 readiness 去哪
   - 看协议定义去哪

---

## 7. 实施建议

### Step 1：文档收口

先在架构和 README 层明确：

- `system_health.yaml` = runtime snapshot
- `system.yaml` = governance summary

### Step 2：最小 schema 契约

为两个状态文件分别定义最小必填字段集，至少保证：

- 不混放 phase 与 service probe
- 不混放 debt summary 与 port health

### Step 3：同步器桥接

让 `sync_omo_state.py` 可选读取 `system_health.yaml`，但只提炼有限字段：

- runtime health summary
- online/offline counts
- stale alerts

不直接搬运整份 service snapshot 到 `system.yaml`。

### Step 4：验证链

构造一次最小验证：

1. 模拟一个 runtime 服务状态变化
2. 触发 `system_health.yaml` 更新
3. 运行 `sync_omo_state.py`
4. 验证 `system.yaml` 中只出现摘要，不出现快照污染

---

## 8. 验证口径

### 结构验证

- `system_health.yaml` 与 `system.yaml` 的字段职责清楚分离
- L0/L1/L4 文件不再承担彼此职责

### 行为验证

- scheduler 状态变化只更新 runtime snapshot
- sync_omo_state 只生成治理摘要

### 使用验证

能稳定回答三个问题：

1. 协议定义看哪里？ -> L0 registry
2. 服务活没活看哪里？ -> `system_health.yaml`
3. 当前阶段 ready 不 ready 看哪里？ -> `system.yaml`

---

## 9. 最终结论

L0/L1/L4 的正确关系不是三套平行状态，而是一条单向状态桥：

- L0 给结构
- L1 给活性
- L4 给决策摘要

只要这条桥稳定，系统就不会再因为“状态都在，但意思都不一样”而继续漂。
