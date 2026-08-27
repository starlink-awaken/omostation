---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# 29 — OMO 联邦健康度、预算与 Load-Shedding 治理 Playbook

> **状态**: 提案草案 · 待审查
> **日期**: 2026-06-01
> **作者**: worker-3 (omo-federation-wave-research)
> **领域**: I0 — 集成层 · 联邦治理
> **上游依赖**: Agora `federation.py` FederationManager, `peers` 表, `agent_cards` 表, KOS 健康监控
> 本文档是历史提案草案，保留当时对联邦预算、健康信号与减载策略的设计思路，不是当前联邦运行时、当前预算配置或当前治理状态 SSOT。
> 当前实现与治理状态请以相关项目代码、`/.omo/goals/current.yaml`、`/.omo/state/system.yaml` 和当前审计结果为准。

---

## 1. 问题陈述

当前 Agora 联邦 (`federation.py`) 实现了基础的 AgentCard 发现与对等实例通信，但**缺少联邦运行时的健康治理能力**：

| 缺失能力 | 风险 |
|---------|------|
| 联邦预算 | 无资源上限，单个失控 peer 可耗尽本地资源 |
| 饱和度监控 | 无降速机制，过载时继续接受新请求 |
| 队列压力 | 无背压信号，背压时仍盲目拉取 |
| 健康信号 | 无多维健康度量，坏 peer 与好 peer 同权 |
| Load-Shedding | 无有序减载，过载时只能硬失败 |
| 优雅坍缩 | 无降级路径，联邦层面崩溃导致全系统不可用 |

Phase 17 候选包 `P17-W1-BOUNDED-FEDERATION`、`P17-W2-SELECTIVE-EXPANSION` 直接依赖此治理能力。

---

## 2. 核心设计原则

1. **单实例自治优先**：联邦不应比本地更重要。本地饱和时，联邦请求优先被丢弃。
2. **显式预算**：资源消耗必须有硬边界，且每周期重置。
3. **健康优先于吞吐**：健康信号下行比上行优先——本地可宣告自己过载，让 peer 降速。
4. **减载有序**：由低价值到高价值逐级减载，先非关键查询，后核心同步。
5. **坍缩有底线**：联邦完全不可用时，本地代理降级为单实例模式，不影响已有能力。

---

## 3. 联邦预算 Governance

### 3.1 预算维度

| 维度 | 单位 | 默认预算（每轮） | 说明 |
|------|------|----------------|------|
| **发现预算** | 请求数 | 10 | 每轮同步可拉取的 AgentCard 上限 |
| **同步预算** | 字节 | 1 MB | 每轮写入 federation.db 的数据量上限 |
| **出站预算** | 请求/秒 | 5 | 对同一 peer 的每秒最大请求数 |
| **入站预算** | 请求/秒 | 10 | 接受所有 peer 的总入站请求数上限 |

### 3.2 预算存储

新增 `federation_budget` 表到 `federation.db`：

```sql
CREATE TABLE IF NOT EXISTS federation_budget (
    budget_id TEXT PRIMARY KEY,          -- 'discover' | 'sync' | 'outbound' | 'inbound'
    limit_value REAL NOT NULL,           -- 预算上限
    current_usage REAL DEFAULT 0,        -- 当前用量
    reset_period_seconds INTEGER DEFAULT 60,  -- 重置周期（秒）
    last_reset_at TEXT DEFAULT '',        -- 上次重置时间
    description TEXT DEFAULT ''
);
```

### 3.3 预算消费流程

```
请求到达 → 查 budget.current_usage < limit_value?
  ├── 是 → 消费 budget.current_usage += cost, 继续
  └── 否 → 记录 BudgetExceeded 事件, 返回 429 / 跳过本轮
```

### 3.4 预算溢出策略

| 溢出程度 | 操作 |
|---------|------|
| < 120% 预算 | 软拒绝 —— 标记请求为"超出预算"，但执行后记录 |
| 120-200% 预算 | 硬拒绝 —— 返回 429，写入 `budget_exceeded` 事件 |
| > 200% 预算 | 熔断 —— 切断该 peer 的出站通道，触发健康衰减 |

---

## 4. 饱和度管理

### 4.1 饱和度信号（本地节点）

| 信号 | 阈值 | 级别 | 动作 |
|------|------|------|------|
| CPU 使用率 | > 80% | WARN | 标记健康度为"繁忙"，降低出站发现频率 |
| CPU 使用率 | > 95% | CRIT | 停用联邦出站，拒绝新入站请求 |
| 内存使用率 | > 85% | WARN | 只允许高价值请求（capability 匹配度 > 0.6） |
| 内存使用率 | > 95% | CRIT | 进入减载模式 |
| SQLite 写延迟 | > 500ms | WARN | 缩减同步批量大小 |
| SQLite 写延迟 | > 2s | CRIT | 暂停联邦写入，只读模式 |

### 4.2 饱和度广播协议

每个节点通过健康端点广播自身饱和度：

```
GET /federation/health
→ {
    "instance_id": "agora:starlink-core",
    "saturation": {
        "cpu": 0.72,        # 0-1
        "memory": 0.81,     # 0-1
        "queue_depth": 15,
        "budget_usage": {
            "discover": 0.3,
            "sync": 0.6,
            "outbound": 0.9,
            "inbound": 0.7
        }
    },
    "health_status": "warn"   # "ok" | "warn" | "critical"
}
```

### 4.3 远程 Peer 饱和度响应

| 收到 peer 状态 | 本地响应 |
|---------------|---------|
| `warn` | 对该 peer 的出站频率减半 |
| `critical` | 暂停对所有该 peer 的出站，停止拉取其 AgentCard |

---

## 5. 队列压力管理

### 5.1 队列类型与监控

| 队列 | 来源 | 压力信号 | 最大深度 |
|------|------|---------|---------|
| 入站联邦请求 | 远程 peer → 本地 | 排队等待数量 | 100 |
| 出站发现队列 | 本地 → 远程 peer | 等待发送数量 | 50 |
| 同步写入队列 | federation.db 写操作 | pending 事务数 | 20 |

### 5.2 背压传递链

```
入站队列满 (depth > 80)
    → 返回 503 Service Unavailable 给请求方
    → 请求方收到 503 后标记该 peer 健康衰减
    → 健康衰减 → 降低对该 peer 的出站权重
```

### 5.3 队列压力事件日志

```sql
CREATE TABLE IF NOT EXISTS federation_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,      -- 'queue_pressure' | 'budget_exceeded' | 'saturation_warn'
    severity TEXT NOT NULL,        -- 'info' | 'warn' | 'critical'
    peer_id TEXT DEFAULT '',
    message TEXT DEFAULT '',
    payload TEXT DEFAULT '{}',     -- JSON
    created_at TEXT NOT NULL
);
```

---

## 6. 联邦健康信号

### 6.1 健康度评分（每个 peer）

```python
@dataclass
class FederationHealthScore:
    instance_id: str
    # 通信健康
    last_response_time_ms: float     # 最新响应时间
    avg_response_time_ms: float      # 窗口平均响应时间
    success_rate_1m: float           # 过去1分钟成功率 (0-1)
    # 数据健康
    staleness_hours: float           # AgentCard 最后同步距今小时数
    schema_version_match: bool       # AgentCard schema 版本匹配
    # 信任健康
    trust_score: float               # 累计信任分 (0-1), 初始 0.5
    budget_exceeded_count: int       # 预算溢出次数
    # 综合
    composite_health: float          # 加权综合 (0-1)
```

### 6.2 综合健康度计算

```
composite_health = (
    0.30 * success_rate_1m +
    0.25 * max(0, 1 - avg_response_time_ms / 5000) +
    0.20 * trust_score +
    0.15 * max(0, 1 - staleness_hours / 24) +
    0.10 * (1 if schema_version_match else 0)
)
```

### 6.3 健康度阈值

| 综合健康度 | 等级 | 路由行为 |
|-----------|------|---------|
| ≥ 0.75 | GREEN | 全功能路由 |
| 0.50 - 0.74 | YELLOW | 只路由非关键请求 |
| 0.25 - 0.49 | ORANGE | 仅路由只读查询 |
| < 0.25 | RED | 暂停所有路由，标记非活跃 |

### 6.4 健康衰减机制

每次健康检查失败（超时/错误/饱和度响应）：

```python
def apply_health_decay(peer_id: str, reason: str):
    """健康衰减：每次失败降低信任分 0.1，最低 0.0"""
    # 自然恢复：每成功一次恢复 0.02，上限 0.5
    # 快速失败：连续 3 次失败直接标 RED
    # 冷却期：RED 状态 5 分钟内不再路由
```

---

## 7. Load-Shedding 策略

### 7.1 减载层次（由低到高逐级触发）

| 优先级 | 操作 | 触发条件 | 影响范围 |
|--------|------|---------|---------|
| L1 | 停止非关键发现 | 入站队列 > 60 或 CPU > 85% | 降低发现频率，不影响已发现 peer |
| L2 | 停止出站同步 | 同步预算 > 80% 或 SQLite 延迟 > 500ms | 不拉取新 AgentCard，缓存有效 |
| L3 | 拒绝低信任请求 | 入站流量 > 80% 预算 | trust_score < 0.3 的请求返回 503 |
| L4 | 暂停联邦出站 | 综合健康度 < 0.4 或 CPU > 95% | 本地不发起任何联邦请求 |
| L5 | 关闭入站联邦端口 | 队列满且持续 30s | peer 无法连接本地，本地优先 |
| L6 | 联邦坍缩 → 单实例模式 | 连续 3 次减载后仍过载 | 完全断开联邦，本地代理降级运行 |

### 7.2 减载恢复（L4 → L1）

```
每 60s 尝试升一级恢复：
  L6 → L5 → L4 → L3 → L2 → L1 → 正常运行
  任一升恢复操作失败 → 回到当前级别再等 60s
  连续升级成功 3 次 → 加快恢复周期到 30s
```

### 7.3 减载事件审计

每次减载/恢复触发需写入 `federation_events` 表，字段包含：

| 字段 | 值示例 |
|------|--------|
| event_type | `load_shed` / `load_restore` |
| severity | `warn` / `critical` |
| shed_level | `L1`-`L6` |
| trigger_reason | `cpu_95pct` / `queue_full_30s` |
| affected_peers | 3 |

---

## 8. 优雅坍�（Graceful Collapse）

### 8.1 坍缩入口

当任一条件满足时触发 L6：

| 条件 | 检测方式 |
|------|---------|
| 本地饱和度 CRIT 持续 > 60s | health endpoint 自检 |
| 联邦层异常导致本地主逻辑阻塞 | watchdog 超时检测 |
| 数据库写失败 | SQLite 操作异常计数 |

### 8.2 坍缩行为

```python
def collapse_to_single():
    """优雅坍缩到单实例模式"""
    # 1. 广播 farewell 信号给所有 peer
    broadcast_farewell()
    # 2. 关闭入站联邦端口
    close_inbound_port()
    # 3. 清空联邦队列
    drain_queues()
    # 4. 保存联邦状态快照
    save_federation_snapshot()
    # 5. 写入坍缩事件
    log_collapse_event()
    # 6. 设置状态标志，让上层路由回退到本地
    set_single_instance_mode()
    # 7. 继续处理本地请求（不接联邦请求）
```

### 8.3 恢复入口

```python
def recover_from_collapse():
    """从单实例模式恢复联邦"""
    # 1. 本地资源确认可用
    assert cpu < 70% and memory < 75%
    # 2. 加载联邦状态快照
    snapshot = load_federation_snapshot()
    # 3. 逐级恢复 peer 连接（每次最多 2 个 peer，间隔 5s）
    for peer in snapshot.peers[:2]:
        reconnect_peer(peer)
    # 4. 等待所有重连 peer 健康度 ≥ YELLOW
    wait_until_healthy(min_health=0.5)
    # 5. 恢复剩余 peer
    reconnect_remaining()
    # 6. 恢复事件
    log_recovery_event()
```

---

## 9. 关键 Metrics 与告警

| Metric | 粒度 | 告警阈值 | 说明 |
|--------|------|---------|------|
| `federation.health.composite` | per-peer | < 0.5 → warn, < 0.25 → critical | 综合健康度 |
| `federation.budget.usage` | per-budget | > 0.8 → warn, > 0.95 → critical | 预算使用率 |
| `federation.queue.depth` | per-queue | > 60 → warn, > 90 → critical | 队列深度 |
| `federation.shed.level` | global | ≥ L4 → warn, ≥ L6 → critical | 减载等级 |
| `federation.peer.count` | global | 0 → info (联邦空), < 2 → warn | 活跃 Peer 数 |
| `federation.sync.staleness` | per-peer | > 12h → warn, > 48h → critical | 同步陈旧度 |

---

## 10. 与 Phase 17 的关系

| Phase 17 候选包 | 本 Playbook 的支撑能力 |
|----------------|----------------------|
| `P17-W1-BOUNDED-FEDERATION` | §3 预算 §4 饱和度 §7 Load-Shedding |
| `P17-W2-SELECTIVE-EXPANSION` | §6 健康信号 —— 用健康度选择扩展目标 |
| `P17-W3-VALUE-LOOP-CONSOLIDATION` | §9 度量与告警 —— 用指标衡量联邦价值 |

---

## 11. 实施路径

| 步骤 | 内容 | 预估工作量 | 风险 |
|------|------|-----------|------|
| 1 | 在 `federation.db` 新增 `federation_budget` 和 `federation_events` 表 | 小 | 低 |
| 2 | 实现 `FederationHealthMonitor` 类（添加于 `federation.py`） | 中 | 低 |
| 3 | 实现预算消费逻辑（`budget_consume()` / `budget_check()`） | 小 | 低 |
| 4 | 实现健康端点 `GET /federation/health` | 中 | 中（需端到端测试） |
| 5 | 实现减载控制器 `LoadShedController` | 中 | 中（边界条件复杂） |
| 6 | 实现优雅坍缩恢复流程 | 大 | 高（与主流程耦合深） |
| 7 | 编写测试（单元 + 集成） | 中 | 低 |
| 8 | 编写文档 | 小 | 低 |

---

## 12. 不涉及的范围（明确排除）

| 内容 | 排除原因 |
|------|---------|
| 联邦级分布式事务 | 超出 BOUNDED-FEDERATION 边界 |
| Peer 间 ACL / 认证 | 属于 identity/admission 治理，不同 Playbook |
| 联邦数据一致性协议 | 属于 Phase 12 protocol federation 范围 |
| 跨实例知识融合 | 属于 KOS 联邦而非 Agora 联邦 |

---

*本 Playbook 为提案文档，不修改任何运行系统文件。待审查通过后转入实施。*
