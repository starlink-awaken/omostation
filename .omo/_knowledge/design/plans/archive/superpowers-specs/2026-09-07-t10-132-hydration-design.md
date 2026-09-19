---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-07
last-reviewed: 2026-09-06
bet_id: BET-Y1Q4-T10-132
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T10-132 DBOS 离散状态水合与 SQLite WAL 原子调度设计

## 1. 目标

持久化 Agent 心智状态与物理显存解耦：会话上下文与认知帧持久化于
SQLite WAL，外部事件触发时 <15ms 快速水合恢复，单步执行完毕即去水合
释放显存，解决多 Agent 并发显存 OOM 与进程崩塌遗忘问题。

## 2. In scope

1. `projects/omo/src/omo/resident/hydration.py`（新文件）：
   - `HydrationStateMachine`：DORMANT → HYDRATING → ACTIVE → DEHYDRATING
     四态状态机（非法迁移 fail-closed）。
   - `hydrate(agent_id, frame)`：从 SQLite（WAL 模式）读回认知帧并
     重建内存态，计时返回（目标 ≤15ms）。
   - `dehydrate(agent_id)`：序列化当前帧写回 SQLite（事务原子写），
     释放内存引用（显存增量归 0 语义 = 无 GPU 张量持有）。
   - `probe_read_latency()`：WAL mode=ro 只读探测延迟测量。
   - 并发安全：多 agent 同库并发水合/去水合（WAL 读写不阻塞）。
2. `projects/omo/src/omo/resident/schema_v3.sql`（新文件）：认知帧表
   （agent_id 主键、frame JSON、state、updated_at，WAL 启用语句）。
3. `projects/omo/tests/test_resident_hydration.py`（新文件）：状态机
   迁移/水合往返/延迟断言/并发水合/崩溃恢复（进程模拟）。

## 3. Out of scope

- 不管理真实 GPU 显存（"显存增量 0" 以无 GPU 张量持有的代码结构保证，
  不接 CUDA/Metal API）。
- 不改既有 resident daemon 的事件循环（水合引擎为独立可调用组件）。

## 4. 验收（对齐 ledger done_when）

1. `hydration.py` 交付水合/去水合状态机（非法迁移拒绝）。
2. WAL mode=ro 只读探测延迟 ≤15ms（perf_counter 断言，含真实 SQLite）。
3. 单元与压力测试（多 agent 并发水合/去水合循环）100% 通过。
