---
schema: bet-retro/v1
bet_id: B1-1-agent-federation
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-21
type: ephemeral
completed_at: 2026-09-21
---

# Retro: B1.1 Agent Federation — 跨 agent 任务 broker + load-balancer

## Summary

FORWARD-PLAN v2 §B1.1 (P2) 落地: 新增 `bin/ssot/agent-federation.py`，
提供 6 个子命令 (discover/plan/dispatch/status/complete/audit)，
实现跨 agent 任务分配、五维打分排序、配额感知降级、A2A 消息分发、审计统计。

## 数据源

| 数据源 | 用途 | 记录数 |
|--------|------|--------|
| agent profiles (_base.yaml) | agent 能力/lane/workflow 定义 | 18 |
| quota-ledger.yaml | 配额感知 + tier 映射 + 冷却期降级 | 17 runtimes |
| A2A 消息队列 (a2a-messages.jsonl) | 跨 agent 任务分发 | 累积 |
| federation-tasks.jsonl | 任务记录 + 审计 | 累积 |

## 五维评分模型

| 维度 | 权重 | 说明 |
|------|------|------|
| Lane 兼容性 | 30% | agent can_write_lanes 与 task requested_lanes 交集 |
| Workflow 权限 | 25% | agent allowed_workflows 是否包含 task workflow |
| 配额可用性 | 20% | quota-ledger last_exhausted_at + cooldown_hours 判断 |
| 能力亲和度 | 15% | agent purpose 与 task capabilities 关键词匹配 |
| 成本 Tier | 10% | T0(贵)→T4(便宜)，同分时优选低成本 |

## 关键设计决策

1. **不替代 ADR-0203**: federation 只做"谁做"分配决策，不做治理门禁
   - workflow start/claim/verify/closeout 仍走 agent-workflow.py
   - federation dispatch 后，agent 仍须走完整 workflow 生命周期

2. **配额降级**: 跳过 last_exhausted_at 在冷却期内的 runtime
   - 连续 2 次命中 exhaustion_signals → 写入 last_exhausted_at
   - cooldown_hours 内改派同 Tier 备选

3. **安全降级**: 找不到合适 agent 时返回错误，不静默跳过
   - plan 返回空列表 → dispatch 返回 exit 1
   - 避免任务丢失

4. **可审计**: 所有分配记录到 JSONL
   - task_id / assigned_agent / workflow / duration / result
   - audit 子命令统计完成率、agent 分布、workflow 分布、平均耗时

## 与现有系统关系

```
FORWARD-PLAN v2 §B1.1
  └── agent-federation.py (新增)
       ├── 复用: agent profiles (_base.yaml)
       ├── 复用: quota-ledger.yaml (multica-squad-ops)
       ├── 复用: A2A 消息队列 (a2a-adapter.py)
       ├── 新增: federation-tasks.jsonl (任务记录)
       └── 新增: script-registry 注册 (governance 类)

现有 agent 协作路径:
  ├── agent-workflow.py: 治理门禁 (start/claim/verify/closeout)
  ├── a2a-adapter.py: 跨 agent 消息 (send/recv/discover)
  ├── agent-tick-daemon.py: 持续运行 tick
  └── multica-squad-ops: 配额感知分派 (Tier → Runtime)

B1.1 补全: 从"手动选 agent"到"自动评分 + 配额感知 + 可审计"
```

## 下一步

- [ ] 与 agent-workflow.py claim 集成 (dispatch 后自动 start+claim)
- [ ] 与 cockpit CLI 集成 (cockpit federation <command>)
- [ ] 加入 gac-gate 作为 audit check (审计 federation 决策质量)
- [ ] 与 health-predict 集成 (预测 agent 负载)
- [ ] 12 周实战验证 (FORWARD-PLAN v2 §A1 反馈循环)

## 版本

- **v1** (2026-09-21): 初始实现, 6 子命令 + 五维评分 + 配额降级 + A2A 分发