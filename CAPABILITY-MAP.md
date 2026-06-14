# Agora 能力地图

> I0 Service Convergence Hub (服务网格 Mesh) · 服务发现 · BOS URI 统一路由

---

## 一、架构定位

```
┌─────────────────────────────────────────────────────────────┐
│                    Agora — I0 MCP Hub                        │
├─────────────────────────────────────────────────────────────┤
│  服务发现  │  统一路由  │  治理免疫  │  BOS代理             │
│  Registry │  BOSRouter│  Governance│  BOS Middleware      │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、核心能力 (Phase 45 演进)

| 能力领域 | 核心机制 | 状态 |
|---------|---------|------|
| **统一路由 (Unified Routing)** | 基于 Trie 树的最长前缀匹配 (`BOSRouter`)，支持动态注册与 `bos://{domain}/{package}/{action}` 通配转发 | 🟢 Ready |
| **BOS代理 (BOS Proxy)** | 统一暴露四大核心 MCP 工具: `resolve_bos_uri`, `read_resource`, `mutate_resource`, `list_bos_resources` | 🟢 Ready |
| **安全与免疫 (Immunity)** | 注册表驱动的 BOS 域鉴权机制 (`_bos_domain_authorized`)，彻底摆脱硬编码；内置限流、熔断与缓存策略 | 🟢 Ready |
| **治理网关 (Governance Hub)** | 集成 `mof_agora_hook`，执行所有 L0 审计与前置校验拦截 (SSB) | 🟢 Ready |
| **事件总线 (Event Bus)** | `watch_resource` 事件订阅机制，异步发布调用轨迹 | 🟢 Ready |

---

## 三、核心 MCP 工具清单

| 类别 | MCP 工具 | 说明 |
|------|----------|------|
| **资源交互** | `resolve_bos_uri` | 将 BOS URI 解析为后端实际调用 |
| | `read_resource` | 获取资源（代理/POC 降级模式） |
| | `mutate_resource` | 写操作并自动触达 L0 审计与事件总线 |
| **发现与检索** | `list_bos_resources` | 列出已注册的全部 BOS URI |
| | `get_bos_schema` | 查询 BOS URI 参数规范（对接 M1 Workflow） |
| **可观测性** | `bos_metrics_status` | 查看 BOS 路由命中、成功率、延时指标 |
| | `bos_middleware_status` | 熔断/限流状态诊断 |
| **订阅机制** | `watch_resource` | 订阅 BOS 资源变更事件 |

---

## 四、底层测试覆盖 (P45 更新)

| 测试维度 | 范围 | 用例规模 |
|----------|------|----------|
| **BOS 路由链** | `test_bos_routing_chain.py`，涵盖前缀匹配、代理降级 | 100% 覆盖 |
| **端到端测试** | `test_bos_e2e.py` / `test_bos_e2e_real.py` | 验证真实网格连通性 |
| **中间件机制** | `test_bos_middleware.py` (限流/熔断/缓存 TTL) | 深度覆盖 |
| **全局全景测试**| 全部 `agora` 测试集 (`pytest tests/`) | **1300+ Passing** |

---

*版本: 4.5.0 · 更新: 2026-06-14*
