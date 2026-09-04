---
title: Knowledge to Action 运转契约
owner: engineering-team
last_updated: 2026-08-02
lifecycle: contract
type: doc
---

# Knowledge to Action 运转契约

## 目标

把研究和检索结果变成可追踪的受治理任务，同时保留“知识被引用”和“任务确实创建”的证据。
这是一条 J2 产品路径，不是新的工作流引擎，也不是自动执行外部业务动作的通道。

```text
Kos search -> user selects references -> governed task -> action receipt -> Workflow Mesh request
```

## 事实边界

| 对象 | 事实来源 | 本契约允许 | 本契约禁止 |
| --- | --- | --- | --- |
| 知识原文 | KOS / 外部知识源 | 临时展示、引用 `ref` | 复制进任务、回执或 OMO |
| 任务 | OMO task ingress | `knowledge_refs: string[]` | 用引用推断任务已执行 |
| 行动回执 | OMO append-only log | 引用元数据、查询哈希、场景和关联 ID | 原文、prompt、模型输出、凭据 |
| WorkflowRun | Workflow Mesh 事件日志 | 后续显式请求和运行关联 | 页面直接改运行态 |

## `knowledge-action/v1`

允许的 `action_kind`：

* `retrieved`：发生过一次知识检索，允许无场景绑定。
* `cited`：用户明确选择了知识引用。
* `task_created`：引用已承接为任务，必须有 `scene_binding` 和 `task_ref`。
* `workflow_requested`：任务进入工作流请求，必须有 `scene_binding` 和 `workflow_run_id`。
* `result_feedback_recorded`：结果回写，必须有 `scene_binding` 和 `result_feedback_id`。

引用只允许以下字段：

```json
{"ref":"kos:delivery-1","title":"交付复盘","source_type":"kos","rank":1}
```

查询只能以 `sha256:` 摘要进入落盘记录。服务端会拒绝 `raw_content`、`raw_input`、`raw_output`、
`prompt`、`model_output`、token 和 password 等字段。日志文件为
`_knowledge/knowledge-mesh/actions.jsonl`，写入采用 append-only + 文件锁，重复同一身份返回
`deduplicated`，不会重复制造行动事实。

## 产品入口与操作

Cockpit `/knowledge-action` 提供：

1. 检索 KOS 候选并选择引用。
2. 填写任务、风险等级、场景、旅程和结果指标。
3. 创建 OMO planned task，并把引用标识写入 `knowledge_refs`。
4. 记录 `task_created` 回执并跳转任务中心。

接口：

* `GET /api/knowledge/action-operations?scene_id=...`：只读漏斗投影。
* `POST /api/knowledge/action-receipt`：写入隐私安全行动回执。
* `POST /api/tasks`：只承接字符串引用列表，最多 20 项。

任务创建成功而回执写入失败属于“部分完成”：前端必须显示任务已创建、回执未记录，并支持人工
重试；不能把失败包装为成功，也不能自动触达 OA、邮件、短信或其他外部资源。

## 运营指标

`build_knowledge_action_snapshot()` 从日志派生：

* `query_count`：去重后的查询摘要数量。
* `unique_source_count`：被引用的知识标识数量。
* `funnel`：检索、引用、任务、工作流请求、结果回执各阶段计数。
* `task_count`：去重后的关联任务数量。

这些指标衡量产品路径是否真实发生，不等同于任务完成、WorkflowRun 成功或业务结果被消费。
业务价值仍以 `outcome-feedback/v1` 的显式消费回执为准。

## 晋升与延期

当前只开放到 `task_created`。进入 `workflow_requested` 前必须同时具备真实场景、明确结果指标、
审批策略、允许的操作级别和证据计划；外部资源还必须通过 External Connection Fabric 的健康、
来源、权限和 proposal-only 准入。没有真实业务需求时保持静默，不凭空接入私有 OA、邮箱、SMS、
OCR 或外部模型。

## 验证

```bash
cd projects/omo
PYTHONPATH=src uv run --no-project --python 3.13 --with pytest --with pytest-asyncio --with pyyaml --with httpx pytest tests/test_knowledge_action.py -q

cd projects/cockpit
PYTHONPATH="src:../omo/src" uv run --no-project --python 3.13 --with pytest --with fastapi --with httpx pytest src/cockpit/tests/test_api_knowledge_actions.py -q

cd projects/cockpit-ui
bun run test:unit -- src/components/__tests__/KnowledgeActionView.test.tsx
bun run build
```
