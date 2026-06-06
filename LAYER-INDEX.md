# LAYER-INDEX.md — 5+3+1 项目分层索引

> 基于 eCOS v5 架构 · 2026-06-06 · 9 项目 · 30 包

## I0 — 集成织层

| 项目 | 角色 | 端口 | 状态 |
|------|------|------|------|
| **agora** | MCP 服务发现 + 代理 + 断路器 | 7422 (HTTP), 7431 (SSE) | 🟢 运行中 · 42 MCP 工具 |

## L0 — 协议编织

| 项目 | 位置 | 说明 |
|------|------|------|
| **protocols** | `protocols/` | 16 协议 YAML + 端口注册表 |
| **ecos** | `projects/ecos/` | SSB 签名链 + 涌现计算 · 122 tests |

## L1 — 运行时基础设施

| 项目 | 位置 | 核心模块 | 状态 |
|------|------|---------|------|
| **runtime** | `projects/runtime/` | Matrix 注册表 · 健康监控 · KEI 沙箱 · Scheduler | 🟢 171 tests |

## L2 — 内核三平面

### 治理面
| 项目 | 位置 | 说明 |
|------|------|------|
| **omo** | `projects/omo/` | Phase 管理 · 债务追踪 · 状态管理 · 221 tests |

### 引擎面 (kairon · 25 包)
| 领域 | 包 |
|------|-----|
| 知识查询 | eidos(7 MCP, 35K) · kos(26 MCP, 14K) · minerva(5 tools, 25K) |
| 知识推导 | ontoderive(5 tools, 6K) · sophia(8 tools) · kronos(9 tools) |
| 知识存储 | ssot(6 tools, 14K) · iris(8 tools) |
| 工具注册 | forge(70 tools, 8K) · codeanalyze |
| 数据模型 | core-models(1.6K, 8 包引用) |
| 支撑 | shared-lib(5 子包已拆) · engine-core · llm-gateway · sharedbrain-bridge |
| 新拆出 | kairon-lib-events · kairon-utils · kairon-plugin-sdk · kairon-observability · kairon-pipeline |

### 记忆面
| 项目 | 位置 | 说明 |
|------|------|------|
| **gbrain** | `projects/gbrain/` | TypeScript · Postgres 知识脑 · 67 MCP 工具 · 163K TS |

### 编排
| 项目 | 位置 | 说明 |
|------|------|------|
| **metaos** | `projects/metaos/` | 决策门控 · 免疫监控 · 路由 · 163 tests |

## L3 — 统一入口

| 项目 | 位置 | 说明 | 接口 |
|------|------|------|------|
| **cockpit** | `projects/cockpit/` | Agent 桥接层 · CLI + MCP + Web | CLI 18 · MCP 20 · HTTP 8090 |

## L4 — 自我层 (数据面 · 被动)

| 项目 | 位置 | 类型 |
|------|------|------|
| **CARDS** | `~/Documents/驾驶舱/CARDS/` | 目标追踪 + 优先级 + 约束 |
| **Vault** | `~/Documents/学习进化/` | 方法论 + 洞察 + 经验 |

**原则**: L4 不运行代码。Agent 通过 L3 cockpit MCP 访问 L4 数据。

---

## X 轴保障体系 (贯穿所有层)

| 切面 | 定义 | 原则 |
|------|------|------|
| **X1 审计链** | 操作是否安全 | 沙箱拦截 · 认证鉴权 · 操作审计 |
| **X2 抗熵** | 数据是否新鲜 | 健康监控 · 自愈 · 过期检测 |
| **X3 价值栈** | 投入是否合理 | 成本追踪 · 优先级驱动 |
| **X4 一致性** | 规则是否被遵守 | CLI/端口/依赖/文档/CI/Phase 全量检查 |

**实现注册表**: `.omo/_knowledge/management/x-axis-implementation-registry.md`
**加入原则**: 新机制 → X1-X4 归类 → 注册到实现表 → CI → Memory

---

*架构定义完成。实现细节见注册表。*
