---
lifecycle: active
owner: governance-team
last_updated: 2026-08-27
title: AGE-v2 Agent Cell — 使用指南
type: doc
---

# AGE-v2 Agent Cell — 使用指南

> 面向用户和 Agent 的完整业务流程

---

## 一、快速开始

### 1.1 CLI 入口

```bash
# 通过 cockpit (推荐)
cockpit cell plan "分析项目结构"
cockpit cell execute '{"tasks":[{"action":"scan","target":"docs/"}]}'
cockpit cell verify '{"results":[{"ok":true}]}'
cockpit cell govern commit_code

# 通过 omo
omo cell plan "修复 CI 失败"
omo cell pdp deploy_production    # 策略评估
omo cell pep commit_code          # 策略执行
omo cell memory process '{"episode_id":"ep-001"}'
omo cell replay shadow "测试意图"

# 监控仪表板
cockpit cell dashboard
```

### 1.2 MCP 入口 (Agent 调用)

```python
# 通过 Agora MCP 调用
cell_plan(intent="分析 README.md")
cell_execute(plan={"tasks":[{"action":"scan","target":"docs/"}]})
cell_verify(result={"results":[{"ok":true}]})
cell_govern(action="commit_code")

# 高级功能
cell_dag_execute(dag_definition="...")
cell_memory_publish(cell_id="cell-001", content="重要发现")
cell_memory_search(query="architecture")
cell_governance_audit(config='{"max_cells":4}')
cell_governance_report()
```

### 1.3 BOS URI 入口

```bash
# 直接通过 BOS 路由
bos://agent-cell/plan
bos://agent-cell/execute
bos://agent-cell/verify
bos://agent-cell/govern
bos://agent-cell/pool/status
bos://agent-cell/dag/execute
bos://agent-cell/memory/publish
bos://agent-cell/governance/report
```

---

## 二、业务流程

### 2.1 单任务流程 (最常见)

```
用户意图 → Plan → Govern → Execute → Verify → Memory
   │         │        │         │        │       │
   └→ Cell ──┴→ PDP ──┴→ PEP ──┴→ Result ┴→ Verdict ┴→ Candidate
```

**示例: 分析项目结构**

```bash
# 1. 创建执行计划
cockpit cell plan "分析 docs/ 目录结构"
# 输出: {"plan_id": "plan-xxx", "tasks": [...], "risk_assessment": "R0"}

# 2. 执行计划
cockpit cell execute '{"tasks":[{"action":"scan","target":"docs/"}]}'
# 输出: {"execution_id": "exec-xxx", "results": [...]}

# 3. 验证结果
cockpit cell verify '{"results":[{"ok":true,"output":"[...]"}]}'
# 输出: {"verdict": "accept", "quality_score": 0.9}

# 4. 完成 Episode (自动触发记忆整合)
# 记忆候选已生成到 .omo/state/agent-cell-memory/candidates.jsonl
```

### 2.2 多 Cell 协作流程 (DAG)

```
            ┌→ Cell B (修复 CI) ─┐
Cell A (分析) ─┤                    ├→ Cell D (验证)
            └→ Cell C (更新文档) ─┘
```

**示例: 项目治理任务**

```bash
# 定义 DAG
cat > /tmp/dag.json << 'EOF'
{
  "dag_id": "project-governance",
  "cells": [
    {"cell_id": "analyze", "intent": "分析项目结构", "depends_on": []},
    {"cell_id": "fix-ci", "intent": "修复 CI 失败", "depends_on": ["analyze"]},
    {"cell_id": "update-docs", "intent": "更新文档", "depends_on": ["analyze"]},
    {"cell_id": "verify", "intent": "验证所有改动", "depends_on": ["fix-ci", "update-docs"]}
  ]
}
EOF

# 执行 DAG
cell_dag_execute(dag_definition=$(cat /tmp/dag.json))
```

### 2.3 治理审批流程

```
动作请求 → PDP 评估 → 风险分级 → 决策
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
            R0 (自动)      R1 (审计)      R2/R3 (人工)
              │               │               │
              ▼               ▼               ▼
           直接执行        执行+记录      等待审批
```

**示例: 提交代码**

```bash
# 1. 评估风险
cockpit cell govern commit_code
# 输出: {"risk_level": "R2", "decision": "human_approve"}

# 2. 需要人工审批
# 主人确认后执行
cockpit cell pep commit_code
# 输出: {"allowed": true, "requires_human": true}

# 3. 主人确认后完成
# 执行实际操作...
```

### 2.4 记忆网络流程

```
Episode 完成 → 生成候选 → 冲突检测 → 整合记忆
                │           │          │
                ▼           ▼          ▼
            candidates    conflicts   memories
            .jsonl        .jsonl      .jsonl
```

**示例: 跨 Cell 记忆共享**

```python
# Cell A 发布记忆
cell_memory_publish(
    cell_id="cell-a",
    content="架构决策: 使用微服务模式",
    tags=["architecture", "decision"]
)

# Cell B 搜索记忆
results = cell_memory_search(
    query="架构",
    tags=["decision"]
)
# 返回: [{"memory_id": "mem-xxx", "content": "...", "cell_id": "cell-a"}]
```

---

## 三、监控与可观测

### 3.1 Cell Pool 状态

```bash
# 查看池状态
cockpit cell dashboard
# 或
python3 bin/bc-os/weekly-value-report.py

# 输出示例:
# ════════════════════════════════════════════════════════════
#   AGE-v2 Agent Cell Dashboard
# ════════════════════════════════════════════════════════════
# ── Cell Pool ──
#   Cells: 2/4 (min: 1)
#   Active Episodes: 1
#   Utilization: 25%
#   Auto-scale: ON
# ── Metrics ──
#   Utilization: 25%
#   Total Dispatches: 42
#   Last 1h: 5
# ── Health Check ──
#   ✓ planner
#   ✓ executor
#   ✓ verifier
#   ✓ governor
# ════════════════════════════════════════════════════════════
```

### 3.2 治理报告

```bash
# 生成治理报告
cell_governance_report()

# 输出示例:
# {
#   "generated_at": "2026-08-27T10:00:00Z",
#   "total_audits": 15,
#   "compliant": 14,
#   "violations": 1,
#   "compliance_rate": 93.3,
#   "by_type": {"config_audit": 10, "action_audit": 5}
# }
```

### 3.3 价值证明报告

```bash
# 周度价值报告
python3 bin/bc-os/weekly-value-report.py

# 输出示例:
# Weekly Value Report — 2026-W35
#   Status: PROVABLE
#   Composite Score: 85/100
#   Hours Saved (30d): 35.8h
#   Decisions (30d): 5
#   BET Done: 96.5%
```

---

## 四、域 Cartridge 使用

### 4.1 卫健委域 (weijian-governance)

```bash
# 评估域动作
python3 projects/omo/src/omo/resident/cell_cartridge.py --demo

# 输出示例:
# === Cartridge Governance Demo ===
#   ✓ read_file → R0 | auto_execute
#   ✓ scan → R0 | auto_execute
#   ⚠ commit_code → R2 | human_approve
#   ✗ deploy_production → R3 | reject
```

### 4.2 自定义域策略

```python
from omo.resident.cell_cartridge import CartridgeGovernance

gov = CartridgeGovernance()

# 评估域特定动作
result = gov.evaluate_cartridge_action(
    "cartridge-weijian-v1",
    {"action": "deploy_staging", "target": "production"},
    policies=[
        {"id": "RULE-WEIJIAN-DATA-01", "severity": "CRITICAL", "constraint": "..."}
    ]
)
```

---

## 五、故障恢复

### 5.1 Cell 崩溃恢复

```python
from omo.resident.cell_pool import CellPool
from omo.resident.cell_state import CellStateManager

# 1. 查看保存的状态
manager = CellStateManager()
states = manager.list_states()

# 2. 从快照恢复
pool = CellPool()
cell = pool.recover_cell(states[0]["state_id"])

# 3. 继续工作
print(f"Recovered cell: {cell.cell_id}, state: {cell.state}")
```

### 5.2 状态清理

```python
# 清理过期状态 (TTL=24h)
manager = CellStateManager()
cleaned = manager.cleanup_stale(max_age_hours=24)
print(f"Cleaned {cleaned} stale states")
```

---

## 六、常见场景

### 场景 1: 文档分析

```bash
# 分析 README.md
cockpit cell plan "分析 README.md 文档结构"
cockpit cell execute '{"tasks":[{"action":"read_file","target":"README.md"}]}'
cockpit cell verify '{"results":[{"ok":true,"output":"..."}]}'
```

### 场景 2: CI 修复

```bash
# 修复 CI 失败
cockpit cell plan "修复 CI 中 ruff format 失败"
cockpit cell execute '{"tasks":[{"action":"query_status","target":"ci"}, {"action":"format_code","target":"src/"}]}'
```

### 场景 3: 技术债务审计

```bash
# 多 Cell 协作审计
cell_dag_execute(dag_definition='{
  "dag_id": "debt-audit",
  "cells": [
    {"cell_id": "scan", "intent": "扫描技术债务", "depends_on": []},
    {"cell_id": "analyze", "intent": "分析债务优先级", "depends_on": ["scan"]},
    {"cell_id": "fix", "intent": "修复高优先级债务", "depends_on": ["analyze"]}
  ]
}')
```

### 场景 4: 治理审批

```bash
# 提交代码 (需审批)
cockpit cell govern commit_code
# → R2, human_approve

# 主人确认后
cockpit cell pep commit_code
# → allowed=true, requires_human=true
```

---

## 七、最佳实践

### 7.1 任务设计

1. **意图明确**: `"分析 README.md"` 优于 `"分析文件"`
2. **风险预判**: 高风险动作前先 `cockpit cell govern <action>`
3. **记忆利用**: 重复任务前先 `cell_memory_search(query="...")`

### 7.2 池管理

1. **自动扩缩容**: 保持 `auto_scale=True` (默认)
2. **监控利用率**: 定期查看 `cockpit cell dashboard`
3. **手动调整**: 需要时 `cell_pool_scale(target=8)`

### 7.3 治理合规

1. **R0/R1 自动执行**: 无需等待
2. **R2 需审批**: 主人确认后执行
3. **R3 需同步确认**: 必须同步确认后执行

---

## 八、故障排查

| 问题 | 检查 | 解决 |
|------|------|------|
| Cell 池满 | `cell_pool_status()` | 等待或手动扩容 |
| 执行失败 | `cell_health()` | 检查具体模块 |
| 记忆丢失 | `cell_memory_search()` | 检查 candidates.jsonl |
| 治理拒绝 | `cell_governance_audit()` | 修复配置 |
| BOS 路由失败 | 检查 admission_meta | 更新配置 |

---

**文档版本**: 2026-08-27
**状态**: 活跃
