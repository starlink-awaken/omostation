---
id: ADR-0319
title: External Connection Fabric 观察与候选评审产品边界
status: ACCEPTED
date: 2026-08-03
owner: architecture-governance
scope: Workflow Mesh / Cockpit / External Connection Fabric
lifecycle: spec
last-reviewed: 2026-08-03
type: ssot
---

# ADR-0319: External Connection Fabric 观察与候选评审产品边界

- 状态: **ACCEPTED**
- 日期: 2026-08-03
- 范围: Workflow Mesh / Cockpit / External Connection Fabric

## 背景

External Connection Fabric 已具备 Agora descriptor 发现、健康投影、OMO 观察持久化、Scene
Card 候选生成和 proposal-only 评审脚本，但产品前端先行出现了目录与评审页面，Cockpit 后端
路由尚未形成真实闭环。这会让“文档已声明能力”和“运行时可消费能力”再次分叉。

## 决策

Cockpit 正式提供两个只读/候选边界：

1. `GET /api/external-resources` 优先读取 OMO 最新的
   `external-resource-observation/v1`，没有受治理观察时才回退到 Agora 的动态目录发现。
   回退只允许显式声明的只读健康探针；接口不持久化观察、不调用 provider 业务方法、不启动
   worker，并始终返回 `activation=forbidden`。
2. `GET /api/scene-cards` 读取 `scene-card-candidate/v1` 候选投影；
   `POST /api/scene-cards/review` 调用纯评审契约生成 `scene-card-review/v1` 回执。评审备注
   只进入摘要哈希，接口不写 OMO、不创建 WorkflowRun、不激活外部连接。即使提交 `approve`，
   返回状态仍为 `blocked`，必须补齐业务证据后再走 Agora Scene Card gate 和 OMO admission。

产品链路收敛为：

```text
OMO observation / safe discovery -> Cockpit catalog -> Scene Card candidate
                                -> human review receipt -> formal admission (future)
```

## 取舍与边界

- OMO 仍是持久观察与运行状态真相，Agora 仍拥有外部 descriptor、健康和路由事实，Cockpit
  只负责产品投影与人工消费。
- 当前不在 HTTP 请求中写观察日志，不引入外部连接缓存、业务数据复制、自动准入或真实写操作。
- OMO 最新观察优先，保证产品页面消费可审计证据；无观察时的动态发现用于启动阶段和诊断，
  不等价于已持久化证据。
- 目录和候选接口的不可用状态必须显式返回，禁止用空列表伪装正常运行。

## 验证

- Cockpit 定向测试覆盖 OMO 优先、动态发现回退、发现不可用、候选投影、评审 blocked 和
  缺少候选标识等路径。
- Phase 26 使用临时隔离依赖环境运行：15 项 Cockpit API/Workflow Mesh 测试通过。
- 路由注册进入 `router_health.ROUTER_MODULES`，由 Cockpit dashboard 的统一装载机制加载。
