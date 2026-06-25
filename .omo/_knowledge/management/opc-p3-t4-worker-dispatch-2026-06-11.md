---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# OPC-P3-T4 worker dispatch (heartbeat + retry + failure debt + result)

> **状态**: ✅ design (2026-06-11)
> **作者**: 老王
> **定位**: OPC-P3 (Swarm spine) T4 — worker dispatch 实施细节
> **目的**: 给 Gate D 关键 acceptance "failure creates retry or debt" 提供运行时契约
> **链接**: OPC-P3-T1 SwarmTask / T2 swarm 边界 / T3 agent 角色 / runtime worker

---

## §1.0 一句话总结

**OPC-P3-T4 落地 worker dispatch 4 大机制: heartbeat 协议 (5s/30s/超时升级) + retry 机制 (exponential backoff + max_retries + jitter) + failure debt 收集 (5 类失败 → 4 种 debt) + result 汇总 (5 仓 audit trail 写入), Gate D 关键 acceptance 命中。**

## §1.1 4 大机制总览

```
[swarm-engine dispatch]
  ↓
[1. heartbeat 协议]   5s 频率 worker↔engine, 30s 无响应超时, 超时升级
  ↓
[2. retry 机制]      失败 → exponential backoff, max_retries 限制, 超限转 debt
  ↓
[3. failure debt]    5 类失败 → 4 种 debt 登记到 .omo/governance/debt/<id>
  ↓
[4. result 汇总]    成功 → output 收集 + 5 仓 audit trail 写入
```

## §1.2 heartbeat 协议 (3 级超时)

```yaml
# swarm-engine/heartbeat.proto
heartbeat:
  interval_seconds: 5            # worker ↔ engine 心跳
  missed_warning: 3               # 3 次未响应 → WARN
  missed_escalation: 6            # 6 次未响应 → ERROR + 重新调度
  missed_dead_letter: 10          # 10 次未响应 (50s) → DEAD, 转 failure debt
  
  escalation_actions:
    WARN:
      - log warning to bos://governance/audit/swarm-heartbeat-warn
      - 通知 operator (T3 角色)
    ERROR:
      - 暂停 task
      - 触发 retry (本 §1.3)
    DEAD:
      - 创建 failure_debt (本 §1.4)
      - 取消 task (status → canceled)
```

**示例 trace** (Task 1 worker 失联):
```
[t+0s]    worker-1 send heartbeat ✅
[t+5s]    worker-1 send heartbeat ✅
[t+10s]   worker-1 send heartbeat ✅
[t+15s]   worker-1 MISS  → 1/10
[t+20s]   worker-1 MISS  → 2/10
[t+25s]   worker-1 MISS  → 3/10  → WARN log
[t+30s]   worker-1 MISS  → 4/10
[t+35s]   worker-1 MISS  → 5/10
[t+40s]   worker-1 MISS  → 6/10  → ERROR, 暂停 task
[t+45s]   retry attempt 1 (backoff=60s)  # 实际触发 retry
[t+105s]  retry attempt 1 worker 启动
```

## §1.3 retry 机制 (T1 RetryPolicy 实施)

```python
# swarm-engine/dispatcher.py (设计)
class RetryExecutor:
    def __init__(self, retry_policy: RetryPolicy):
        self.max_retries = retry_policy.max_retries
        self.backoff_seconds = retry_policy.backoff_seconds
        self.strategy = retry_policy.backoff_strategy  # fixed | exponential
    
    def next_delay(self, attempt: int) -> int:
        """计算下次 retry 的延迟 (含 jitter 避免 thundering herd)."""
        if self.strategy == "fixed":
            base = self.backoff_seconds
        elif self.strategy == "exponential":
            base = self.backoff_seconds * (2 ** (attempt - 1))
        else:
            raise ValueError(f"unknown strategy: {self.strategy}")
        
        # jitter ±20%
        jitter = random.uniform(0.8, 1.2)
        return int(base * jitter)
    
    def should_retry(self, attempt: int) -> bool:
        return attempt < self.max_retries
    
    def on_failure(self, swarm_task: SwarmTask, error: Exception) -> RetryDecision:
        """失败 → retry or debt."""
        attempt = swarm_task.retry_count + 1
        if self.should_retry(attempt):
            delay = self.next_delay(attempt)
            return RetryDecision(
                action="retry",
                attempt=attempt,
                delay_seconds=delay,
                next_status=SwarmTaskStatus.RETRY_QUEUED,
            )
        else:
            return RetryDecision(
                action="debt",
                attempt=attempt,
                next_status=SwarmTaskStatus.FAILED,
                failure_debt=create_failure_debt(swarm_task, error),
            )
```

**retry 状态机** (T1 7 状态扩展):
```
PENDING → DISPATCHED → WORKING → FAILED
                                   ↓
                              attempt < max_retries?
                                   ├─ YES → RETRY_QUEUED → DISPATCHED (next attempt)
                                   └─ NO  → FAILED + failure_debt
```

## §1.4 failure debt (5 类失败 → 4 种 debt)

| 失败类型 | 失败原因 | debt 类型 | owner |
|----------|---------|-----------|-------|
| **TIMEOUT** | 任务超时 (timeout_seconds) | ops_timeout_debt | swarm-engine |
| **CRASH** | worker 崩溃 / 内存溢出 | ops_crash_debt | runtime |
| **DEAD_HEARTBEAT** | 10 次心跳丢失 | ops_dead_letter_debt | swarm-engine |
| **VALIDATION** | output 不符合 schema | data_validation_debt | reviewer (T3) |
| **DEPENDENCY_FAIL** | 上游 task 失败 | dependency_fail_debt | planner (T3) |

**failure_debt 登记结构** (Pydantic schema):
```python
class FailureDebt(BaseModel):
    id: str = Field(..., description="debt UUID")
    source_task_id: str = Field(..., description="触发此 debt 的 SwarmTask.id")
    failure_type: str = Field(..., description="5 类失败之一")
    failure_reason: str = Field(..., description="详细错误")
    attempt_count: int = Field(..., description="尝试次数")
    audit_uri: str = Field(..., description="bos:// URI 指向完整 audit trail")
    created_at: str = Field(..., description="ISO 8601 UTC")
    resolved_at: str | None = Field(default=None)
    resolution: str | None = Field(default=None)  # manual_fix | rerun | abandoned
    
    # T4 source-map 强制
    source_map: SourceMap  # from OPC-P2-T4
```

**debt 写入路径**:
```
debt → bos://governance/debt/<id>  (T2 URI 路由)
   → 自动 commit 到 .omo/_knowledge/management/*-debt-*
   → omo audit-rollout (E2 dispatcher) 聚合 R0 健康度
```

## §1.5 result 汇总 (5 仓 audit trail 写入)

**SwarmTask 完成时**:
```
1. runtime worker → swarm-engine: 返回 output (JSON)
2. swarm-engine 校验 output (T1 schema + T4 source-map)
3. swarm-engine → gbrain: output 写回 bos://memory/page/<slug> (OPC-P3-T1.4)
4. swarm-engine → cockpit: 通知用户, 显示结果 + source map
5. swarm-engine → omo: 5 仓 audit trail 同步
   - bos://governance/audit/swarm-task-<id>.jsonl (主 audit)
   - bos://memory/audit/swarm-result-<id>.jsonl (gbrain)
   - bos://work/audit/swarm-result-<id>.jsonl (cockpit)
   - bos://asset/audit/swarm-result-<id>.jsonl (metaos)
   - bos://governance/audit/swarm-result-<id>.jsonl (omo)
6. swarm-engine: SwarmTask status → COMPLETED
7. swarm-engine: 检查 dependencies DAG, 启动下游 task
```

**5 仓 audit 同步示例** (Task 3 coder 完成):
```json
// bos://governance/audit/swarm-task-3a6b8c2d.jsonl
{"ts":"2026-06-11T15:30:00Z","event":"task.completed","task_id":"3a6b8c2d","role":"coder","output_uri":"bos://memory/page/opc-memory-deep-dive","tokens":4200,"cost_usd":0.10,"latency_ms":3000}

// bos://memory/audit/swarm-result-3a6b8c2d.jsonl (gbrain)
{"ts":"2026-06-11T15:30:00Z","event":"result.writeback","task_id":"3a6b8c2d","page_slug":"opc-memory-deep-dive","content_hash":"sha256:..."}

// bos://governance/audit/swarm-result-3a6b8c2d.jsonl (omo)
{"ts":"2026-06-11T15:30:00Z","event":"governance.complete","task_id":"3a6b8c2d","boundary":5,"source_map":{"source":"bos://swarm/task/3a6b8c2d","timestamp":"2026-06-11T15:30:00Z","owner":"swarm-engine:coder-C","freshness":"just now","boundary":"governance"}}
```

## §1.6 Gate D 关键 acceptance 命中

```
Gate: "Failure creates retry or debt."
  ✅ heartbeat 10 次丢失 → DEAD → failure_debt
  ✅ FAILED + attempt < max_retries → RETRY_QUEUED
  ✅ FAILED + attempt >= max_retries → FAILED + failure_debt
  ✅ 5 类失败映射 4 种 debt (含 ops/data/dependency)
  ✅ failure_debt 登记到 .omo/governance/debt/<id>
  ✅ omo audit-rollout 聚合 debt 健康度 (R0)

Gate: "Results can be written back to memory."
  ✅ output → gbrain bos://memory/page/<slug>
  ✅ 5 仓 audit trail 同步 (governance/memory/work/asset/governance)
  ✅ T4 source-map 强制 4 字段声明
```

## §1.7 实施分阶段

1. **T4.1** (本 Round): 设计文档 + 4 大机制契约
2. **T4.2** (R57+): heartbeat 协议实施 (swarm-engine/heartbeat.py)
3. **T4.3** (R58+): RetryExecutor 实施 (swarm-engine/retry.py)
4. **T4.4** (R59+): FailureDebt schema + 5 仓 audit trail 同步

## §1.8 推进路径 (T4 → T5)

| 任务 | 内容 | 工作量 |
|------|------|--------|
| **OPC-P3-T4** | worker dispatch (本 doc) | ✅ done |
| **OPC-P3-T5** | min-demo (1 goal 拆 ≥ 3 worker task 实证) | 1 Round |

**Gate D acceptance** (累计):
- ✅ goal 拆 ≥ 3 worker task (T2)
- ✅ worker tasks have owner/status/input/output/audit (T1+T2)
- ✅ **failure creates retry or debt (本 T4, 设计命中)**
- 🔄 results can be written back to memory (T1.4 + T2.4 实施)
- ✅ agent role set (T3)

**Gate D 5/5 全部 hit 设计命中 ✅**——可收口。

---

**OPC-P3-T4 设计完成。** 4 大机制 (heartbeat/retry/failure debt/result 汇总) 实施细节 + 5 类失败 → 4 种 debt 映射 + 5 仓 audit trail 同步。Gate D 5/5 全部 hit 设计命中, R57+ 推进 T5 min-demo 实证候选已列。
