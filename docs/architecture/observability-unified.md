---
lifecycle: entry
owner: governance-team
last_updated: 2026-08-18
type: ssot
last_updated: 2026-09-03
---
# 统一可观测性架构 — 可观测 × 事件 × 治理三体系联动设计

> 状态: PROPOSED | 日期: 2026-08-08 | Owner: governance-team
> 前置调研: 事件体系 8 通道盘点、治理体系事实通道盘点、可观测四维现状审计（日志/监控/告警/trace）

---

## 0. 现状基线（三体系盘点结论）

### 0.1 可观测性四维现状（2026-08-08 实测）

| 维度 | 现状 | 断链 |
|------|------|------|
| 日志 | 多层 JSONL 审计（KEI 149K 条、ingress-audit、mutation-ledger、foundry metrics）+ launchd 守护 stdout；`omo observability log` 可查 | ❌ 无集中采集、无轮转、6+ 路径分散 |
| 监控 | agora `/health`（audit_chain 71/71、bos_registry、backends 存活）、`/metrics`（Prometheus）、cockpit dashboard（8090）、omo panorama 7D、metrics-store.jsonl | ❌ 指标仅 8 个（4 业务），无 RED、无 TSDB 存储 |
| 告警 | 检测链齐全（anomaly-detector / problem-detector / alert-engine），`governance-alerts.yaml` 有 X1-X4 规则 | ❌ webhook/email disabled → 到人断链；无常态调度 |
| trace | bus-foundation W3C 传播（envelope.trace_id/span_id）、agora trace_id 贯穿、kairon-observability 包 | ❌ Langfuse 栈死亡（server 未跑、db 0 行）、无 exporter |

### 0.2 事件体系：8 个独立通道（无统一 schema）

| # | 通道 | 信封 | 可订阅 |
|---|------|------|--------|
| A | Agora EventBus（事实中央总线） | `{id,time,source,type,trace_id,payload}` | ✅ HTTP+hook+poll |
| B | bus-foundation（OmniEnvelope 三平面） | `{id,plane,topic,source_uri,payload,trace_id,timestamp,version}` | ✅ backend 可插拔 |
| C | AppendOnlyLog JSONL 族 | 各 ad-hoc `{ts,kind,source,payload}` | ❌ 只读文件 |
| D | swarm broadcast-bus.jsonl | `{msg_id,sender_id,channel,event_type,content,timestamp}` | ❌ 轮询 |
| E | signal-poller 触发 | `{ts,source_id,bos_uri,transport,signal,hash}` | ❌ stdout |
| F | transition_log（内存） | `{id,timestamp,service,state_from,state_to,reason,source}` | ❌ 查询 |
| G | metaos trace_log（SQLite） | `{id,asset_id,event,detail,timestamp}` | ❌ 本地 |
| H | MOS 认知桥 | world_snapshot / decision_outcome | 弱 |

### 0.3 治理体系：事实通道（半统一入口）

| 通道 | 文件 | 写者 | 消费 |
|------|------|------|------|
| 检测时序 | `.omo/state/metrics-store.jsonl` | gac-local-gate `--metrics` | adaptive-gate/anomaly/predictive/dashboard |
| 规则级门禁 | `.omo/state/rule-vitality.jsonl` | gac-local-gate | rule-vitality/gate-effectiveness |
| 审计 | `governance-history.jsonl`/`omo-sync.jsonl`/`ssot-audit-log.jsonl` | omo audit/sync/ssot-watcher | evidence-smoke/dashboard |
| 债务 | `.omo/debt/items/*.yaml` | omo_debt_lifecycle/ingress/self-healing | X3Checker/audit/cockpit |
| 健康分 | `system_health.yaml → health.yaml → system.yaml::health_score → governance-data.json` | runtime health_scan/compass_radar/omo_state | BRIEF/cockpit |
| 蜂群事件 | `swarm/broadcast-bus.jsonl` | agora swarm_mesh | swarm-dashboard |

**结论**：三体系各自成环但互不打通——可观测发现不了治理结果，治理不知道运行时状态，事件通道彼此隔离。**缺一个统一枢纽**。

---

## 1. 设计目标与原则

### 1.1 目标（TO-BE）

1. **全覆盖**：日志/监控/告警/trace 四维对 17+ 项目统一覆盖，无死角
2. **事件归一**：8 个事件通道 → 统一事件面（一个 schema、一个入口、可订阅、可追溯）
3. **治理闭环**：可观测异常 → 治理事实（债务/门禁/审计）自动生成；治理结果回流为可观测指标
4. **trace 贯穿**：trace_id 从运行时事件贯穿到治理审计，端到端可追溯

### 1.2 原则

- **复用不新建**：中央总线用 Agora EventBus（事实标准），物理写盘用 AppendOnlyLog（跨仓契约），时序用 metrics-store.jsonl（复用最广）——不做第 4 套总线
- **归一化在边界**：适配器只做 envelope 翻译，不改各通道内部
- **治理优先**：任何可观测信号要么进统一事件面、要么进治理事实，不落"无人消费的洞"
- **减法方向（ADR-0389）**：不新增独立监控平台（不引 Prometheus 全家桶），用统一事件面 + 现有 JSONL 时序 + cockpit 聚合

---

## 2. 总体架构（三层）

```
┌─────────────────────────────────────────────────────────────────┐
│  L3 消费/联动层  (governance-dashboard / cockpit / alert 到人)    │
│   ┌────────────┐ ┌───────────┐ ┌──────────┐ ┌────────────────┐  │
│   │ 告警路由    │ │ 债务自动   │ │ 健康分    │ │ 大盘聚合        │  │
│   │ alert-router│ │ 生成 debt │ │ 复合回流  │ │ panorama/dashboard│ │
│   └────────────┘ └───────────┘ └──────────┘ └────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  L2 统一事件面 Unified Event Surface (schema v1)                 │
│   .omo/_delivery/observability/events.jsonl (AppendOnlyLog)      │
│   + agora EventBus 可订阅投影 + metrics-store 时序索引            │
│   {id, ts, domain, type, severity, source, trace_id,             │
│    payload, schema_version}                                      │
├─────────────────────────────────────────────────────────────────┤
│  L1 归一化适配器 (8 通道 → 统一事件面)                             │
│   agora_bus │ swarm │ signal │ scene │ transition │ metaos_trace │
│   gate_result │ debt_ledger │ health_score                       │
├─────────────────────────────────────────────────────────────────┤
│  L0 采集探针 (17 项目)                                            │
│   结构化日志规范 │ /metrics exporter 规范 │ trace_id 传播 │ 轮转   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心枢纽：统一事件面（Unified Event Surface）

### 3.1 统一 schema（v1）

```yaml
schema: observability-event/v1
id: evt_<epoch>_<hex6>          # 全局唯一
ts: ISO-8601                    # 事件时间
domain:                         # 来源域
  - runtime                     # 运行时服务/进程
  - governance                  # 门禁/治理检查
  - swarm                       # 蜂群 agent 事件
  - perception                  # 信号感知
  - scene                       # 场景执行
  - knowledge                   # 知识事件 (bos://.../events/)
  - debt                        # 债务生命周期
type: string                    # <domain>:<action> 如 governance:gate_failed
severity: info|warning|degraded|critical|recovered
source: string                  # 产生者 (服务/脚本/agent)
trace_id: string?               # 贯穿 ID (bus-foundation W3C)
payload: {}                     # 领域数据
schema_version: 1
```

### 3.2 物理落点（复用现有原语，不新建总线）

| 角色 | 落点 |
|------|------|
| 物理写盘（权威） | `.omo/_delivery/observability/events.jsonl`（AppendOnlyLog：append+fsync+锁） |
| 可订阅投影 | Agora EventBus `publish_event`（`bos://observability/events/*`）→ HTTP 订阅者 |
| 时序索引 | metrics-store.jsonl 追加 `{timestamp, check: <event.type>, ok, duration_ms}` 行 |
| 审计面 | `omo event emit`（现有，`ts/kind/source/payload`）作为降级写入口 |

### 3.3 8 通道适配器（L1）

| 通道 | 适配器 | 归一化映射 |
|------|--------|-----------|
| Agora EventBus | 直接已归一（envelope 缺 severity/trace_id 则补） | `domain=runtime\|knowledge, type=<event.type>` |
| bus-foundation | EventBusBackend 已有 A→B 转换，反方向补 | `domain=runtime, plane→payload.plane` |
| swarm broadcast | 新适配器读 broadcast-bus.jsonl 增量 | `domain=swarm, type=swarm:<event_type>` |
| signal-poller | 新适配器（stdout→改为 AppendOnlyLog 写面） | `domain=perception, type=perception:signal` |
| scene-outcome | scene-outcome-recorder 追加写事件面 | `domain=scene, type=scene:<adjudication>` |
| transition_log | 新适配器（内存→定时 dump 或 hook） | `domain=runtime, type=runtime:transition` |
| metaos trace_log | 新适配器（SQLite 增量读） | `domain=runtime, type=metaos:<event>` |
| MOS 认知桥 | 已写 .omo，补事件面镜像 | `domain=knowledge` |

**增量指针**：每个适配器维护 `.omo/state/observability-adapters/<channel>.offset`（JSONL 行号 / SQLite rowid / mtime），避免全量重读。

---

## 4. 与事件体系联动（TO-BE）

1. **统一订阅入口**：`bos://observability/events/*` 经 Agora EventBus 暴露，任意消费者（cockpit/knowledge-indexer/监控）用现有 `subscribe_event` 订阅，不再各自轮询文件
2. **trace 贯穿**：所有适配器从 envelope/记录提取 `trace_id` 写入统一事件面 → 查询 `omo observability trace <trace_id>` 可串起 运行时→事件→治理 全链
3. **事件↔治理回流**：治理动作（ADR 创建/debt 关闭/gate 通过）也发事件面事件 → 事件消费者可感知治理变化（如 debt:closed → 更新 dashboard）
4. **scene/感知闭环**：signal 触发 → journey 执行 → scene outcome 记录 → 统一事件面（已有 MOS 桥，补事件面镜像），让场景执行可观测

---

## 5. 与治理体系联动（TO-BE）

### 5.1 门禁 → 事件 → 告警（闭环核心）

```
gac-local-gate 失败
  → metrics-store.jsonl (已有)
  → 统一事件面 governance:gate_failed {check, rule_id, severity, trace_id}
  → alert-router 匹配 governance-alerts.yaml rules
  → 微信/飞书 webhook 到人 (新接通)
  → rule-vitality.jsonl (已有)
  → 治理审计 governance-history.jsonl (已有)
```

### 5.2 异常 → 债务 → 治理（自动闭环）

```
anomaly-detector / problem-detector 发现异常
  → 统一事件面 governance:anomaly {type, service, severity}
  → omo_debt_lifecycle 自动创建 debt item (带 evidence=事件面 trace_id)
  → X3 价值核算 / debt-dashboard 更新
  → governance-data.json 投影刷新
  → (可选) 事件面 debt:opened 通知治理 agent
```

### 5.3 健康分复合回流

```
runtime health_scan → system_health.yaml (已有)
compass_radar → health.yaml (已有)
  → 新增: observability 信号 (gate 失败率/告警数/事件异常率) 并入复合分
  → system.yaml::health_score → governance-data.json (已有链路)
  → cockpit / BRIEF 展示
```

### 5.4 治理结果 → 可观测指标

```
治理动作 (ADR 创建/债务关闭/workflow closeout/门禁通过)
  → 统一事件面 governance:<action>
  → metrics-store 追加 (check=governance:<action>, ok=true)
  → governance-dashboard / 事件面消费者可见
```

---

## 6. 覆盖矩阵（四维 × 三体系）

| 维度 | 运行时项目（17） | 事件体系 | 治理体系 |
|------|-----------------|---------|---------|
| 日志 | 统一结构化规范 + 集中目录 + 轮转（新） | 事件面审计日志（新） | gate 结果/审计 JSONL（已有） |
| 监控 | /metrics exporter 规范 + RED 指标（新） | 事件面速率/异常率指标（新） | metrics-store/rule-vitality（已有） |
| 告警 | 服务异常 → 事件面 → 到人（新接通） | 事件触发告警（新） | governance-alerts.yaml 规则（已有） |
| trace | trace_id 传播（已有）+ OTel→Langfuse（修复） | envelope trace_id → 事件面（新） | 审计条目带 trace_id（新） |

---

## 7. 实施路线

### Phase 1 — 地基（止血 + 枢纽落地）
- [x] P1.1 统一事件面 schema（`observability-events.yaml`）+ `bin/ssot/observability-events.py`（emit/search/trace/adapters）+ events.jsonl（AppendOnlyLog+fcntl）— **2026-08-08 落地**
- [x] P1.2 日志轮转 `bin/ssot/log-rotate.py` + `make log-rotate`（实测 agora sse-stdout 已达 243MB）— **2026-08-08 落地**
- [ ] P1.3 observability 栈决策：配 `.env` 修复 Langfuse 或正式退役 — **TODO**
- [ ] P1.4 agora /metrics 补 RED 指标（QPS/延迟直方图/错误率）— **TODO**

### Phase 2 — 联动闭环
- [x] P2.1 适配器框架 + 4 通道落地（swarm/gate/debt/health）+ 增量指针（`.omo/state/observability-adapters/*.offset`）；signal/scene 已注册待接线，metaos/transition 默认关闭 — **2026-08-08 落地**
- [x] P2.2 告警到人：channel 连接器体系（alert-connectors.py: slack/feishu/wecom/generic + deliver/receipt + 事件面回写）+ alert-router 接通 + cron 08:30 调度 — **2026-08-08 落地（URL 待配 env）**
- [x] P2.3 门禁失败 → 事件（gac-local-gate 失败发 governance:gate_failed，PASS 发 gate_passed）— **2026-08-08 落地**
- [x] P2.4 `observability-events.py trace <trace_id>` 跨链查询 — **2026-08-08 落地**

### Phase 3 — 治理深度联动
- [x] P3.1 异常 → 债务自动闭环（problem-detector 升级：检测→事件面 governance:anomaly→debt item 自动创建，幂等）— **2026-08-08 落地**
- [x] P3.2 健康分复合（compass_radar 并入统一事件面近 24h critical/degraded 事件到 anomaly_count）— **2026-08-08 落地**
- [ ] P3.3 OTel span → Langfuse（若 P1.3 选择修复）— **TODO**
- [ ] P3.4 cockpit 可观测页聚合统一事件面（替代分散 /api/logs /api/alerts）— **TODO**

---

## 8. 关键设计决策（ADR 候选）

| # | 决策 | 理由 |
|---|------|------|
| D1 | 统一事件面用 AppendOnlyLog + Agora EventBus 投影，不新建总线 | 复用跨仓契约 + 事实中央总线（原则 1） |
| D2 | 告警通知接入微信/飞书 webhook（而非自建邮件/SMS） | 零基础设施，复用现有聊天入口 |
| D3 | 不引入 Prometheus TSDB/Grafana，用 metrics-store.jsonl + cockpit 聚合 | 减法方向（ADR-0389）；当前规模平文件足够 |
| D4 | trace 走 bus-foundation W3C trace_id（已有）而非强制 OTel 全家桶 | 逻辑 trace 已贯穿；OTel 仅作为可选导出层 |
| D5 | 适配器增量指针落 `.omo/state/observability-adapters/` | 幂等增量，避免全量重读 |

---

## 9. 成功度量

- 覆盖：17 项目 100% 接入统一事件面（Phase 2 末）
- 告警到人：P0/P1 告警 5 分钟内到达（Phase 2 末）
- 债务自动率：可观测异常 → debt 自动创建 ≥ 80%（Phase 3 末）
- trace 可追溯：跨服务事件 100% 带 trace_id 且可查询（Phase 2 末）
- 日志轮转：0 无限增长文件（Phase 1 末）
