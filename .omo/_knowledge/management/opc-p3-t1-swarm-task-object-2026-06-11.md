---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# OPC-P3-T1 swarm task object 契约

> **状态**: ✅ design (2026-06-11)
> **作者**: 老王
> **定位**: OPC-P3 (Swarm spine) T1 — SwarmTask 统一契约
> **目的**: 跨 5 仓 + swarm-engine + cockpit + runtime + gbrain 统一 task 抽象, 满足 Gate D "worker tasks have owner/status/input/output/audit"
> **链接**: OPC-P2-T1 memory-boundary / T2 memory-uri / T4 source-map / §19 治理任务

---

## §1.0 一句话总结

**OPC-P3-T1 落地 SwarmTask 统一契约: Pydantic + zod 双栈, 9 字段 (id/owner/status/input/output/dependencies/timeout/retry_policy/audit_uri/source_map), 与 §19 governance 任务 + OPC-P2 T4 source-map + T2 memory-uri 跨边界对齐。**

## §1.1 SwarmTask 9 字段 (Pydantic schema)

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Any
from datetime import datetime

class SwarmTaskStatus(str, Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    RETRY_QUEUED = "retry_queued"

class RetryPolicy(BaseModel):
    max_retries: int = 3
    backoff_seconds: int = 60
    backoff_strategy: str = "exponential"  # fixed | exponential

class SwarmTask(BaseModel):
    """OPC-P3 T1: 统一 SwarmTask object 契约 (跨 5 仓 + swarm-engine + cockpit + runtime + gbrain).
    
    9 字段覆盖 Gate D acceptance:
      1. owner (string)            — Task owner (服务名 + ID)
      2. status (enum)             — 7 状态机
      3. input (dict)              — 输入参数
      4. output (dict|None)        — 输出 (working/completed 时填充)
      5. dependencies (list[str])   — Task ID 列表 (DAG)
      6. timeout_seconds (int)     — 超时
      7. retry_policy (RetryPolicy) — 重试策略
      8. audit_uri (str)            — bos:// URI 指向 audit trail (R50 AppendOnlyLog)
      9. source_map (SourceMap)     — T4 4 字段 (source/timestamp/owner/freshness/boundary)
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "required": [
                "id", "owner", "status", "input", "dependencies",
                "timeout_seconds", "retry_policy", "audit_uri", "source_map",
            ],
        }
    )
    
    # 1. id (跨仓唯一)
    id: str = Field(..., description="跨仓唯一 task ID, UUID v4")
    
    # 2. owner (Gate D acceptance 1)
    owner: str = Field(..., description="Task owner, 格式: <service>:<agent-id>")
    
    # 3. status (7 状态机)
    status: SwarmTaskStatus = Field(default=SwarmTaskStatus.PENDING)
    
    # 4. input (任意 JSON)
    input: dict[str, Any] = Field(default_factory=dict)
    
    # 5. output (Gate D acceptance 4)
    output: dict[str, Any] | None = Field(default=None)
    
    # 6. dependencies (DAG)
    dependencies: list[str] = Field(default_factory=list)
    
    # 7. timeout
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    
    # 8. retry_policy
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    
    # 9. audit_uri (T2 memory-uri 跨边界)
    audit_uri: str = Field(..., description="bos:// URI 指向 audit trail JSONL")
    
    # 10. source_map (T4 4 字段)
    source_map: SourceMap  # from OPC-P2-T4
```

## §1.2 7 状态机 (state machine)

```
PENDING → DISPATCHED → WORKING → COMPLETED ✅
                       ↓         FAILED ❌
                       ↓         ↓
                       ↓     RETRY_QUEUED → DISPATCHED (next retry)
                       ↓
                       ↓
                    CANCELED ❌ (人工取消)
```

**转换规则**:
- PENDING → DISPATCHED: swarm-engine worker pool 接收
- DISPATCHED → WORKING: worker 真正开始执行
- WORKING → COMPLETED: 成功完成, output 填充
- WORKING → FAILED: 异常失败, 走 retry_policy
- WORKING → CANCELED: 人工/超时取消
- FAILED → RETRY_QUEUED: 重试次数 < max_retries
- RETRY_QUEUED → DISPATCHED: 重试发起

## §1.3 zod schema (TypeScript 仓, gbrain/swarm-engine)

```typescript
import { z } from "zod";
import { SourceMapSchema } from "./opc-p2-t4-source-map";  // T4

export const SwarmTaskStatusSchema = z.enum([
  "pending", "dispatched", "working", "completed",
  "failed", "canceled", "retry_queued"
]);

export const RetryPolicySchema = z.object({
  max_retries: z.number().int().min(0).max(10).default(3),
  backoff_seconds: z.number().int().min(1).max(86400).default(60),
  backoff_strategy: z.enum(["fixed", "exponential"]).default("exponential"),
});

export const SwarmTaskSchema = z.object({
  id: z.string().uuid(),
  owner: z.string().regex(/^[a-z-]+:[a-z0-9-]+$/),  // <service>:<agent-id>
  status: SwarmTaskStatusSchema.default("pending"),
  input: z.record(z.any()).default({}),
  output: z.record(z.any()).nullable().default(null),
  dependencies: z.array(z.string().uuid()).default([]),
  timeout_seconds: z.number().int().min(1).max(86400).default(300),
  retry_policy: RetryPolicySchema.default({}),
  audit_uri: z.string().regex(/^bos:\/\//),  // T2 URI
  source_map: SourceMapSchema,
});
```

## §1.4 与 §19 治理任务对齐

`SwarmTask.id ↔ .omo/governance/task/<id>` (T2 路由)
- SwarmTask 创建时, 自动生成 governance URI
- omo 仓负责 SwarmTask 状态机的"治理面" (gate 校验, 跨仓追溯)
- 业务仓 (gbrain/cockpit/swarm-engine) 负责 SwarmTask 的"执行面"

**5 边界 × SwarmTask 跨边界读写**:

| 边界 | SwarmTask 字段 | 操作 |
|------|----------------|------|
| memory (gbrain) | input/output (内容) | 写 |
| ontology (kairon) | dependencies (类型关系) | 写 |
| work (cockpit) | owner/status (会话状态) | 写 |
| asset (metaos) | input/output (数字资产) | 写 |
| governance (omo) | audit_uri/source_map (治理) | 写 |

## §1.5 Gate D acceptance 命中

```
Gate: "Every worker task has owner, status, input, output, and audit."
  ✅ owner 字段 (string, service:agent-id)
  ✅ status 字段 (enum, 7 状态)
  ✅ input 字段 (dict, 任意 JSON)
  ✅ output 字段 (dict, working/completed 时填充)
  ✅ audit 字段 (audit_uri → bos:// URI 指向 JSONL audit trail)

Gate: "Failure creates retry or debt."
  ✅ retry_policy 字段 (max_retries + backoff_strategy)
  ✅ 失败 → RETRY_QUEUED (max_retries 内) 或 debt (超 max_retries)

Gate: "Results can be written back to memory."
  ✅ output 字段 (dict) 写回 bos://memory/page/<slug>
  ✅ T4 source_map 强制 4 字段声明
```

## §1.6 实施分阶段 (T1 → 落地)

1. **T1.1** (本 Round): 设计文档 + 双栈 schema
2. **T1.2** (R57+): Pydantic schema 实装到 kairon/swarm-engine/runtime/omo 仓
3. **T1.3** (R58+): zod schema 实装到 gbrain 仓
4. **T1.4** (R59+): SwarmTask 跨边界引用 (cockpit 创建 → gbrain output 写回) 实证

## §1.7 推进路径 (T1 → T2-T5)

| 任务 | 内容 | 工作量 |
|------|------|--------|
| **OPC-P3-T1** | SwarmTask 统一契约 (本 doc) | ✅ done |
| **OPC-P3-T2** | swarm 边界 (cockpit → agora → swarm-engine → runtime → gbrain) | 1 Round |
| **OPC-P3-T3** | agent 角色集 (6 角色) | 2 Round |
| **OPC-P3-T4** | worker dispatch (heartbeat + retry + failure debt + result 收集) | 2 Round |
| **OPC-P3-T5** | min-demo (1 goal 拆 ≥ 3 worker task) | 1 Round |

**Gate D acceptance** (累计):
- ✅ worker tasks have owner/status/input/output/audit (T1 实质化)
- 🔄 failure creates retry or debt (T4 实施)
- 🔄 results can be written back to memory (T1.4 + T2 实施)

---

**OPC-P3-T1 设计完成。** SwarmTask 9 字段 + 7 状态机 + 双栈 schema + 跨边界路由 + Gate D 3 项 acceptance 命中设计就位。R57+ 推进 T1.2 Pydantic 实装候选已列。
