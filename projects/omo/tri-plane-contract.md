# eCOS v5 L2 — Tri-Plane 协作契约

> 定义 OMO(治理平面) / kairon(引擎平面) / gbrain(记忆平面) 的协作边界和接口。
> Phase 8.4 · 填补 DEBT-L2-002
> 状态: design-locked

---

## 一、协作流程

```
L3 Entry Bridge → I0 (Agora) → L2 Tri-Plane Bus
                                    │
                        ┌───────────┼───────────┐
                        ▼           ▼           ▼
                     OMO         kairon       gbrain
                   治理平面      引擎平面      记忆平面

协作顺序:
  1. kairon 接收请求 → 解析意图
  2. OMO 预检: 场景是否已登记? 是否在允许边界? 是否需要审批?
  3. gbrain 执行: capture / search / retrieval
  4. OMO 审计: 写入证据 + 状态代码
  5. 响应返回 L3
```

## 二、接口契约

### OMO → kairon

| 输入 | 输出 |
|------|------|
| scenario_id | ready / needs_approval / blocked |
| request_intent | guardrail_context |
| guardrails | block_reason (if blocked) |

### kairon → gbrain

| 输入 | 输出 |
|------|------|
| normalized_query | search_results |
| capture_payload | capture_receipt |
| retrieval_request | retrieval_data |

### gbrain → OMO

| 输入 | 输出 |
|------|------|
| execution_result | evidence_refs |
| retrieval_result | audit_log_id |
| error_detail | status (completed/failed_with_recovery/failed) |

## 三、通信协议

所有三面间通信通过 I0 (Agora) MCP 协议完成。禁止直接调用。

- OMO ↔ kairon: MCP (SSE)
- kairon ↔ gbrain: MCP (SSE)
- 全部: 经由 I0 Agora 路由

## 四、状态代码

| 代码 | 含义 | 主决定者 |
|:----:|------|:-------:|
| `ready` | 场景通过预检 | OMO |
| `running` | 请求已进入执行链 | runtime |
| `needs_approval` | 治理边界要求人工确认 | OMO |
| `blocked` | policy 阻塞或 capability 缺失 | OMO / kairon |
| `failed_with_recovery` | 执行失败但恢复路径已给出 | OMO |
| `completed` | 结果、状态、证据已收口 | OMO |
