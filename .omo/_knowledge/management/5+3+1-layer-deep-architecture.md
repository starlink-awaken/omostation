# 5+3+1 逐层深度架构分析

> 2026-06-07 | 模块级精度
> 范围: L0/L1/L2/I0/L3/X1-X3 每层的内部模块关系

---

## L0 — 协议编织层 (Protocol Weave)

### 模块组成

```
projects/runtime/protocols/
├── L0-registry.yaml          (12K) — 20 协议的主注册表 (SSOT)
├── ecos-meta-model.yaml      (2.7K) — 元模型定义 (类型/关系/实例)
├── ecos-ontology.yaml        (3.2K) — 本体定义 (6类型×6关系)
├── governance-constraints.yaml (2.2K) — 治理约束
├── kei-extensions.yaml       (3.3K) — KEI扩展定义
├── task-object-v1.md         (7.3K) — TaskObject v1.0 规范
└── tri-plane-registry.yaml   (4.1K) — 三平面注册

projects/runtime/src/runtime/
└── protocol.py               (130 lines) — 运行时加载器+验证器
```

### 核心依赖

```
L0-registry.yaml ←─ protocol.py (加载器)
                  ←─ mcp_server.py (runtime_protocol_list/get 工具)
                  ←─ omo_standard.py (omo standard list)
                  ←─ validate_protocol_registry.py (CI 脚本)

protocol.py ←─ PyYAML (解析)
            ←─ dataclasses (ProtocolEntry 类型)
```

### 运行时接口

| 接口 | 方式 | 位置 |
|------|------|------|
| load_protocols() | Python | protocol.py |
| get_protocol(name) | Python | protocol.py |
| validate_protocol_message(name, msg) | Python | protocol.py → CLI |
| runtime_protocol_list | MCP tool | mcp_server.py |
| runtime_protocol_get | MCP tool | mcp_server.py |
| omo protocol validate | CLI | omo_i0.py |

### 核心流程

```
1. 启动加载: protocol.py:load_protocols() → yaml.safe_load(L0-registry.yaml)
             → [_normalize_protocol() for each] → list[ProtocolEntry]
             → 缓存在模块级变量 L0_PROTOCOLS

2. 查询:     mcp_server.py TOOLS 注册 → runtime_protocol_list
             → protocol.get_protocol(name) → 返回详情

3. 验证:     omo protocol validate MCP '{"version": "2025-03-26"}'
             → protocol.validate_protocol_message('MCP', {...})
             → 检查协议名存在、必填字段、传输层 → (ok, msg)

4. CI 门禁:  validate_protocol_registry.py → yaml.safe_load → 逐个检查
             - 每个协议有 name/version/category/status/description
             - 无重复名
             - status/category 在允许集合
```

---

## L1 — 运行时矩阵 (Runtime Matrix)

### 模块组成 (16 modules, 3,723 lines total)

```
projects/runtime/src/runtime/
├── matrix.py              — Matrix 服务注册表 (读写+解析)
├── scheduler.py           — MatrixScheduler (连续扫描+自愈+抗熵)
├── mcp_server.py          — JSON-RPC MCP 服务器 (22 工具)
├── kei_sandbox.py         — Python audit hook 运行时沙箱
├── protocol.py            — L0 注册表加载器
├── cli.py                 — 主 CLI (argparse, 11 子命令)
├── cli_i0.py              — I0 Fabric CLI
├── bus_consumer.py        — Agora SSE 事件消费
├── taskobject_adapter.py  — TaskObject v1.0 适配器
├── i0.py                  — I0 查询接口
├── kei.py                 — KEI manifest 定义
├── e2e.py                 — 端到端健康检查
├── dashboard_server.py    — HTTP 仪表板
├── kei_service_registration.py — KEI 服务注册
├── __init__.py            — 版本: 0.1.0
└── __main__.py            — python3 -m runtime
```

### 内部依赖图

```
cli.py
  ├──→ matrix.py           (list_services, ServiceEntry)
  ├──→ protocol.py         (L0_PROTOCOLS, get_protocol, validate_protocol_message)
  ├──→ kei.py              (load_manifest)
  └──→ mcp_server.py       (main → MCP 启动)
        └──→ kei_sandbox.py (record_audit)
        └──→ protocol.py   (protocol tools)
        └──→ i0.py         (I0 query functions)
        └──→ matrix.py     (matrix tools)
        └──→ taskobject_adapter.py (dispatch processing)

scheduler.py
  └──→ matrix.py           (健康扫描用服务数据)

bus_consumer.py
  └──→ Agora (SSE stream)  (外部依赖)

taskobject_adapter.py
  └──→ mcp_server.py       (subprocess 调用)
```

### 核心流程

```
Matrix 服务注册:
  matrix.py:list_services() → 读取 matrix.yaml
    → 环境变量展开 ($HOME, $PORT 等)
    → 返回 list[ServiceEntry{name, type, port, status}]

调度器循环:
  scheduler.py:MatrixScheduler._run_cycle()
    → scan_once() → 按端口检查健康
    → _check_stale_services() → freshness 阈值检测
    → 连续失败→ _autoheal_service() → autoheal.sh
    → 等待 interval → 下一循环

MCP 请求:
  stdin → mcp_server.py:main() → json.loads(line)
    → handle_request(req) → 匹配 method:
      - tools/list → TOOLS 列表
      - tools/call → TOOL_MAP[tool_name]["handler"](args)
      - ping → 返回 result: {}
      - initialize → capabilities
    → send_response(resp) → stdout

KEI 审计:
  enable_sandbox() → sys.addaudithook(_audit_hook)
    → 截获文件/网络/子进程操作
    → 检查 kei.yaml 权限规则
    → record_audit() → kei_audit.jsonl
```

### MCP 工具列表 (runtime MCP server)

```
runtime_health         — 健康检查
runtime_matrix_list    — 服务矩阵列表
runtime_matrix_get     — 单个服务详情
runtime_service_ctl    — 服务启停
runtime_protocol_list  — L0 协议列表
runtime_protocol_get   — 协议详情
runtime_ontology_get   — 本体查询
i0_status              — I0 集成织层状态
i0_services            — I0 服务列表
i0_events              — I0 事件列表
i0_protocols           — I0 协议列表
i0_graph               — I0 依赖图
```

---

## L2 — 内核三平面

### OMO 治理面 (15K lines, 70 modules)

```
模块分组:

1. CLI 入口层:
   cli.py (72 lines) — 路由分发: 匹配 args[0] → 对应的 main()

2. 平面 CLI 模块 (本轮新增, 13 modules, ~1,500 lines):
   omo_goal.py          — Phase 目标管理
   omo_state.py         — 系统状态 + 服务健康
   omo_knowledge.py     — 知识面文档
   omo_delivery.py      — 交付物管理
   omo_standard.py      — 标准管理
   omo_i0.py            — Agora 集成查询
   omo_observability.py — 日志搜索/统计
   omo_event.py         — 事件总线查询
   omo_alert.py         — 告警阈值检测
   omo_dashboard.py     — Web 仪表板
   omo_task.py          — 任务列表
   omo_evidence.py      — 证据文件列表
   omo_cost.py          — LLM 成本估算

3. 债务子系统 (15 子模块, ~4,000 lines):
   omo_debt.py               — 主入口 (register/schedule/dispatch/...)
   omo_debt_registry.py      — 注册表管理
   omo_debt_dispatch.py      — 分发逻辑
   omo_debt_reporting.py     — 报告生成
   omo_debt_review_queue.py  — 审查队列
   omo_debt_owner_routing.py — 负责人路由
   omo_debt_action_packet.py — 行动包
   omo_debt_campaign.py      — 债务活动
   omo_debt_approval.py      — 审批流程
   omo_debt_execution.py     — 执行记录
   omo_debt_metrics.py       — 指标
   omo_debt_weight.py        — 权重计算
   omo_debt_reporting_diff.py — 差异报告
   omo_debt_reporting_history.py — 历史报告
   omo_debt_reporting_trend.py   — 趋势报告

4. 治理层 (3 模块):
   omo_governance.py (主)
   omo_governance_overlay.py (覆盖)
   omo_rules.py (规则引擎)

5. 基础设施:
   omo_io.py    — YAML 原子读写
   omo_shared.py — 通用工具
   omo_redaction.py — 脱敏
   omo_metrics.py — 指标
   omo_discovery.py — 发现

6. Worker 调度:
   omo_worker.py (2,142 lines, 最大模块)

7. 其他:
   omo_capability.py    — 能力注册表
   omo_metacognition.py — 元认知
   omo_phase*py         — Phase 执行
   omo_cards.py         — CARDS 集成
   omo_ledger.py        — 治理账本
   omo_bridge.py        — 桥接
   omo_gc.py            — GC
```

### CLI 路由机制

```python
# cli.py — main()
def main(argv=None):
    args = argv or sys.argv[1:]
    if args[0] == "goal":      → omo_goal.main(args[1:])
    if args[0] == "state":     → omo_state.main(args[1:])
    if args[0] == "knowledge": → omo_knowledge.main(args[1:])
    if args[0] == "delivery":  → omo_delivery.main(args[1:])
    if args[0] == "standard":  → omo_standard.main(args[1:])
    if args[0] == "i0":        → omo_i0.main(args[1:])
    if args[0] == "alert":     → omo_alert.main(args[1:])
    if args[0] == "event":     → omo_event.main(args[1:])
    if args[0] == "dashboard": → omo_dashboard.main(args[1:])
    if args[0] in ("log","metric"): → omo_observability.main(args)
    if args[0] in ("capability","registry","scenario","pkg"):
        → omo_capability.main(args)
    if args[0] == "metacognition": → omo_metacognition...
    if args[0].startswith("phase"): → omo_phase*.main()
    → omo_worker.main(args)  # 默认路由
```

---

## L3 — 入口桥接层

### 组件列表

```
wksp/ (kairon 内, 15K)     — workspace CLI (15+ 子命令)
runtime MCP (3.7K)         — JSON-RPC stdio MCP 服务器 (22 工具)
hermes-console (1.4K TS)   — React Web 面板 (构建失败)
runtime mcp_server stdout  — 所有 MCP tool call/invoke
```

### 入口间关系

```
用户/AI Agent
     │
     ├─→ wksp CLI (workspace research/knowledge/status/dashboard)
     │   └─→ Agora (MCP routing) → kairon × gbrain
     │
     ├─→ Runtime MCP (stdio, JSON-RPC)
     │   └─→ 22 tools → matrix/scheduler/kei/protocol
     │
     └─→ hermes-console (Web)
         └─→ MCP SDK client → Agora
```

### TaskObject 路由管线

```
Agent调用 → TaskObject 信封 → taskobject_adapter.py
  → dispatch_taskobject() → _validate_taskobject()
  → _mcp_call(tool_name, params)
  → subprocess: mcp_server.py (stdin JSON-RPC)
  → handle_request() → TOOL_MAP[tool] → run & return
```

---

## X1/X2/X3 — 跨切面

### X1 治理安全 (审计链)

```
kei_sandbox.py:
  _load_kei_rules(kei.yaml)     — 加载权限规则
  enable_sandbox()               — 启用 Python audit hook
  _audit_hook(event, args)       — 拦截文件/网络/子进程
  record_audit()                 — 写 kei_audit.jsonl (16,795条)

通知:
  omo alert check --threshold 10  — 检测阻断率
  notify-alerts.sh                — 推送骨架 (webhook 未配置)

数据流:
  sys.addaudithook → _audit_hook → 检查 kei.yaml → record_audit() → JSONL
  → omo log search → omo alert check → notify-alerts.sh
```

### X2 抗熵 (保鲜)

```
scheduler.py:
  _freshness[service_name] = timestamp    — 记录最后健康时间
  _check_stale_services()                 — 检测 stale (>连续3次)
  _autoheal_service(name)                 — 调用 autoheal.sh 重启

omo state health — 显示 freshness 状态
omo goal list    — Phase 27 4/4 done (所有目标完成)
```

### X3 价值栈 (成本)

```
llm-gateway/providers/base.py:
  record_llm_cost(model, input_tokens, output_tokens)
  → ~/.runtime/data/llm_cost.jsonl

omo cost estimate --period 7:
  → _estimate_cost(model, inp, out) → 按模型定价表计算
  → 输出: 总调用数/Token/各模型成本明细
```

---

## I0 — 集成织层 Agora (159 文件, 38K 行)

### 模块组成

```
src/agora/
├── server/mcp.py          (1,715行) — FastMCP Server, 39个 @mcp.tool()
├── mcp_tools.py           (819行)   — BOS MCP 工具注册表 (20+工具)
├── root/                  (17,948行) — 顶层模块: ws_server, gateway, api, hermes
│                                          agent_registry, pipeline, tracing, calendar
│                                          federation, compressor 等
│
├── extensions/            (2,724行) — Git集成, 跨节点互操作, 签名验证
├── cli/                   (2,414行) — CLI: 16个子命令组
├── core/                  (2,370行) — Router(542行), Registry(387行), Discovery(385行),
│                                          EventBus(262行), ServiceBase, CircuitBreaker
├── auth/                  (2,302行) — OAuth2(691行), MCP认证, 租户, mcp_gateway
├── mcp/                   (1,880行) — KNOWN_SERVICES(19个), 协议实现, 传输层
├── mcp_registry/          (1,854行) — SmartRouter(LLM驱动), ToolCatalog(SQLite)
│                                          LifecycleManager, Orchestrator
├── mcp_proxy/             (1,503行) — ProxyManager, Client(stdio+HTTP), IdleTimeout
├── web/                   (1,121行) — FastAPI app(710行), dashboard
├── tools/                 (799行)   — mail_tool(696行)
├── metrics/               (345行)   — 指标收集
├── growth/                (335行)   — Outlook适配器
├── a2a/                   (257行)   — A2A TaskManager
└── adapters/              (113行)   — NodeAdapter
```

### 核心依赖

```
FastMCP Server ←─ Router ←─ Registry ←─ EventBus
       │              │           │
       ├─→ mcp_gateway (8个内部服务)
       ├─→ KNOWN_SERVICES (19个外部服务)
       ├─→ mcp_proxy (子进程管理)
       └─→ mcp_registry (工具目录 + 语义路由)
```

### MCP 请求全链路

```
客户端 tools/call "minerva.research_now"
  ↓
FastMCP Server (server/mcp.py) [AuthMiddleware]
  ↓
route_call() / proxy_call() / agora_execute()
  ↓
Router.route() (core/router.py)
  ├─ resolve(tool_name) → routes表 + 前缀匹配
  ├─ _next_instance() → round-robin + CircuitBreaker 跳过故障节点
  ├─ 服务缓存降级 → service_cache
  ├─ Accounting → ResourceAccountDB + EU计费
  ├─ EventBus → "route:call.succeeded/failed"
  ├─ Compressor → 响应压缩
  └─ trace_log.jsonl → 追踪记录
  ↓
dispatch() (mcp_protocol.py)
  ├─ mcp  → httpx POST JSON-RPC tools/call
  ├─ rest → HTTP REST
  ├─ grpc → gRPC
  ├─ websocket → WebSocket
  └─ stdio → ProxyManager 子进程
```

### 代理初始化流程

```
Phase 1: mcp_bootstrap.scan_and_launch()
  → KNOWN_SERVICES(19) → 检查PATH → uv/npx/docker 启动子进程
  → ProxyManager.start() 批量连接

Phase 2: ProxyRegistry.register_from_registry()
  → 同步 ServiceRegistry → ProxyRegistry

Phase 3: _register_proxy_tools()
  → 每个下游工具 → ProxyForwardTool → 注册为 FastMCP Tool

后台: _proxy_sync_loop() 每10s扫描, 失败退避120s
```

### KNOWN_SERVICES (19个)

| 类型 | 服务 |
|------|------|
| Kairon (10) | agent-runtime, codeanalyze, eidos, iris, kos, kronos, metaos, minerva, sophia, cron-service |
| npm (5) | mcp-server-sqlite, apple-events, zai, chrome-devtools, serena |
| Docker (1) | docker-mcp-gateway (73 tools) |
| Homebrew (1) | gitnexus |
| Agent CLI (2) | claude-mcp-serve, codex-mcp-server |

### MCP 工具 (41 个)

```
代理管理 (6): proxy_connect/call/status/list_tools/add_service/remove_service
服务管理 (6): register_service, list_services, check_health, add_route, list_routes, route_call
事件总线 (3): publish_event, subscribe_event, get_event_log
审计     (2): audit_query, audit_stats
API Key  (3): create_api_key, list_api_keys, revoke_api_key
推送     (1): register_push_notification
A2A任务  (4): a2a_send_task, get_task, cancel_task, list_tasks
Agent卡  (2): list_agent_cards, get_agent_card
仓库     (7): repo_search/discover/status/install/load/unload/pipeline
生命周期 (5): lifecycle_status/start_watch/stop_watch/load_all/unload_all
智能路由 (1): agora_execute (direct/recommend/auto)
Hermes   (6): search, agent.list/tasks/chat, health.services/alerts
```

### HTTP REST API (/v1 前缀, 14 端点)

```
GET  /v1/health, /v1/health/detailed
POST /v1/tasks, GET /v1/tasks/:id, POST /v1/tasks/:id/cancel
POST /v1/scheduler
POST /v1/pipeline
POST /v1/spaces, GET /v1/spaces/:id
POST /v1/agents, GET /v1/agents/:id
```

### 服务入口

| 入口 | 端口 | 协议 |
|------|------|------|
| main() | stdio | MCP stdio |
| http_main() | 7422 | HTTP |
| sse_main() | 7431 | SSE |
| mcp_gateway.main() | 子进程 | 8 个内部服务 |


