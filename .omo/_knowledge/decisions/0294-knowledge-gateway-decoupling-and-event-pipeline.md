---
id: ADR-0294
title: 知识网关解耦与增量事件索引管道
status: ACCEPTED
lifecycle: spec
owner: engineering-agent
last-reviewed: 2026-08-01
type: ssot
---

# ADR-0294: 知识网关解耦与增量事件索引管道

**状态**: accepted  
**日期**: 2026-08-01  
**决策者**: engineering-agent  
**Workflow Run**: 20260801T124502Z-project-code-change-08a2ee87  
**关联 PR**: starlink-awaken/omostation#740  

---

## 背景与动机

在 PR #740 之前，`cockpit` 的 `/api/knowledge/search` 路由通过 Python 编译时 `import` 直接耦合到 `cockpit.adapters.agora` 内部模块，形成 **L3（cockpit）→ L2（agora 内核）** 的非法跨层强依赖，违反了 `LAYER-CALL-DIRECTION` 规范。

具体问题：
1. **非法层间依赖**：cockpit（L3）直接调用 agora（I0/L2）内部 Python 模块，破坏了分布式服务边界；
2. **单测不可隔离**：所有针对 `/api/knowledge/search` 的单测必须完整初始化 agora 内部依赖树；
3. **写入事件缺失**：`/api/knowledge/put` 落盘 Markdown 后无任何通知，LanceDB / KOS 向量索引必须轮询扫描才能感知变更，导致知识检索存在 **冷启动窗口**。

---

## 决策

### A. BOS URI 解析层间通信解耦（网络优先 + 兼容降级）

在 `cockpit/web/api_knowledge.py` 中实现 `_resolve_bos_uri_network_or_compat(uri, payload)` 网络优先解析策略：

```
┌────────────────────────┐       HTTP POST /bos/resolve       ┌─────────────────────────┐
│   cockpit (L3)         │ ─────────────────────────────────► │   Agora (I0 Gateway)    │
│   api_knowledge.py     │   timeout=2s, async                 │   :7422                 │
│                        │ ◄─────────────────────────────────  │                         │
└────────────────────────┘       200 OK / 超时/网络异常        └─────────────────────────┘
              │                                                
              │ (降级路径: 仅在连接失败/单测环境)              
              ▼                                                
  cockpit.adapters.agora.resolve_bos_uri()  (进程内兼容适配)   
```

**环境变量**：`AGORA_HTTP_ENDPOINT`（默认 `http://127.0.0.1:7422`）

### B. PUT 写后增量事件广播（Producer 端）

`/api/knowledge/put` 成功写入 `data/cards/{slug}.md` 后，触发非阻塞事件通知：

```
POST {AGORA_HTTP_ENDPOINT}/bos/emit
{
  "uri": "bos://brain/events/card_updated",
  "payload": {
    "slug": "<slug>",
    "title": "<title>",
    "path": "data/cards/<slug>.md",
    "action": "upsert"
  }
}
```

超时 1.5s，Fire-and-forget（写失败不阻塞 HTTP 响应）。

### C. 写后增量事件消费（Consumer / Indexer 端）

在 `cockpit/web/knowledge_indexer.py` 实现 `KnowledgeIndexer`，在 cockpit 启动时向 EventBus 注册对 `bos://brain/events/card_updated` 的订阅，并在回调中触发 KOS 向量索引更新。

---

## 接口契约

### 生产者契约（`/api/knowledge/put` 写出）

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `uri` | `str` | `bos://brain/events/card_updated` |
| `payload.slug` | `str` | 知识卡片唯一标识 |
| `payload.title` | `str` | 卡片标题 |
| `payload.path` | `str` | 相对于 WORKSPACE_ROOT 的文件路径 |
| `payload.action` | `str` | 固定值 `"upsert"` |

### 消费者契约（Indexer 订阅侧）

- **订阅模式（pattern）**：`bos://brain/events/card_updated`
- **Callback**：cockpit 内部处理，不需要 HTTP push callback URL
- **幂等性**：Indexer 必须保证对同一 slug 的重复 upsert 为幂等操作

---

## 层间调用方向声明

```
cockpit (L3) → I0/L2 Agora Gateway: 仅通过 HTTP 协议通信（合法）
cockpit (L3) → cockpit.adapters.agora (L3 compat): 仅在降级路径（合法）
```

**禁止**：cockpit 直接 `import` agora 内部模块（不经网络边界）。

---

## 变更影响

- `projects/cockpit/src/cockpit/web/api_knowledge.py`：核心变更文件
- `projects/cockpit/src/cockpit/web/knowledge_indexer.py`：新增消费者
- `projects/cockpit/src/cockpit/tests/test_api_health_knowledge_sandbox.py`：新增 2 个专项单测

---

## 替代方案（已拒绝）

| 方案 | 拒绝原因 |
|:---|:---|
| 保持进程内直接 import | 违反 LAYER-CALL-DIRECTION，无法独立单测 |
| 采用 Celery / Redis 队列 | 引入外部重量级依赖，违背 Indie Efficiency 原则 |
| 轮询 + 文件 mtime 扫描 | 冷启动窗口不可控，且重复 I/O |

---

## 验收标准

- [x] `check-layer-call-direction.py` 全库 3432 文件无新 L3→I0 越权 import 报出
- [x] 21 个 pytest 用例 100% PASS（含 `test_search_via_http_network_resolver`、`test_put_emits_card_updated_event`）
- [x] ADR 本文档沉淀于 `.omo/_knowledge/decisions/` SSOT 决策库
- [ ] `knowledge_indexer.py` Consumer 实现并通过单测（本 Workflow Run 待落地）

---

## 相关资源

- `docs/operations/knowledge-foundry-sop.md`：知识处理完整操作手册
- `projects/agora/src/agora/core/event_bus.py`：EventBus Pub/Sub 实现
- `projects/cockpit/src/cockpit/web/api_knowledge.py`：Producer 实现
