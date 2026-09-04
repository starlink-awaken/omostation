---
lifecycle: active
owner: governance-team
last_updated: 2026-08-26
title: AGE-v2 Agent Cell 操作指南
type: doc
---

# AGE-v2 Agent Cell 操作指南

> AGE-v2 (Agent Generation Evolution v2) 是 omostation 的 Agent 执行单元，提供规划-执行-验证-治理-记忆-回放全生命周期管理。

## 快速开始

### CLI 入口

```bash
# 通过 cockpit 入口
cockpit cell plan "分析项目结构"
cockpit cell execute '{"tasks":[{"action":"scan","target":"docs/"}]}'
cockpit cell verify '{"results":[{"ok":true}]}'
cockpit cell govern read_file

# 通过 omo 入口
omo cell plan "修复 CI 失败"
omo cell pdp deploy_production    # 策略评估
omo cell pep commit_code          # 策略执行
omo cell memory process '{"episode_id":"ep-001"}'
omo cell replay shadow "测试意图"
```

### BOS URI

| URI | 功能 |
|-----|------|
| `bos://agent-cell/plan` | 意图解析 + 任务分解 |
| `bos://agent-cell/execute` | 按计划执行 |
| `bos://agent-cell/verify` | 结果验证 |
| `bos://agent-cell/govern` | 风险评估 |
| `bos://agent-cell/pdp/evaluate` | 策略决策 |
| `bos://agent-cell/pep/enforce` | 策略执行 |
| `bos://agent-cell/memory/process` | 记忆处理 |
| `bos://agent-cell/memory/consolidate` | 记忆整合 |
| `bos://agent-cell/replay/run` | 回放 |
| `bos://agent-cell/replay/shadow` | 影子运行 |
| `bos://agent-cell/replay/eval` | 评估 |
| `bos://agent-cell/pool/status` | 池状态 |
| `bos://agent-cell/pool/submit` | 提交 Episode |
| `bos://agent-cell/pool/scale` | 扩缩容 |
| `bos://agent-cell/config/list` | 配置列表 |
| `bos://agent-cell/config/create` | 创建配置 |

### MCP 工具 (18 个)

通过 Agora MCP 访问:

| 工具 | 功能 |
|------|------|
| `cell_plan` | 创建执行计划 |
| `cell_execute` | 执行计划 |
| `cell_verify` | 验证结果 |
| `cell_govern` | 风险评估 |
| `cell_pdp_evaluate` | PDP 策略评估 |
| `cell_pep_enforce` | PEP 策略执行 |
| `cell_memory_process` | 记忆候选生成 |
| `cell_memory_consolidate` | 记忆整合 |
| `cell_replay` | Episode 回放 |
| `cell_shadow` | 影子运行 |
| `cell_eval` | 批量评估 |
| `cell_pool_status` | 池状态查询 |
| `cell_pool_submit` | 提交 Episode |
| `cell_pool_scale` | 池扩缩容 |
| `cell_config_list` | 配置列表 |
| `cell_config_create` | 创建配置 |

## 架构

### 核心模块

```
projects/omo/src/omo/resident/
├── cell.py              # Episode 生命周期 + 角色 handoff
├── cell_pool.py         # 多 Cell 智能调度池
├── cell_state.py        # 状态持久化 + 故障恢复
├── cell_cli.py          # CLI 入口
├── planner.py           # 意图解析 + 任务分解 + 风险评估
├── executor.py          # 三后端执行 (local/pi-worker/multica)
├── verifier.py          # 三维评分 (完整性/正确性/质量)
├── governor.py          # R0-R3 风险分级
├── pdp_pep.py           # 策略决策点 + 策略执行点
├── memory_pipeline.py   # 记忆整合四阶段
├── replay.py            # 回放/影子/评估框架
├── cell_handler.py      # Resident → Cell 事件路由
├── cell_dag.py          # 跨 Cell DAG 编排
├── cell_cartridge.py    # Cartridge 治理桥接
└── agent_presence.py    # 在场感知同步
```

### 执行流程

```
Intent → Plan → Govern → Execute → Verify → Memory
  │         │        │         │        │       │
  └→ PDP ──┘        └→ PEP ───┘        └→ Consolidate
```

### 风险分级

| 等级 | 描述 | 决策 |
|------|------|------|
| R0 | 只读、无副作用 | auto_execute |
| R1 | 低风险、可逆 | auto_execute + audit |
| R2 | 中等风险、需审批 | human_approve |
| R3 | 高危、需同步确认 | human_approve + sync |

## 治理规范

| 规则 | 描述 |
|------|------|
| CR-AGE-BOS-01 | 核心链路必须经 BOS 路由 |
| CR-AGE-POLICY-01 | R2/R3 必须经 PDP/PEP |
| CR-AGE-MEMORY-01 | 记忆管道必须完整运转 |
| CR-AGE-REPLAY-01 | 回放框架必须支持三种模式 |
| CR-AGE-EVENT-01 | 必须订阅四类事件 |

## 故障恢复

### Cell 崩溃恢复

```bash
# 1. 查看保存的状态
omo cell state list

# 2. 从快照恢复
python3 projects/omo/src/omo/resident/cell_state.py --action list

# 3. 恢复特定 Cell
python3 -c "
from omo.resident.cell_pool import CellPool
pool = CellPool()
cell = pool.recover_cell('<state_id>')
"
```

### 状态持久化

- 位置: `.omo/state/agent-cell/cell_states.json`
- TTL: 24h (过期自动清理)
- 格式: JSON (cell_id → snapshot)

## 常见问题

**Q: Cell Pool 满了怎么办？**
A: Pool 自动复用空闲 Cell。可通过 `cell_pool_scale` 增加 max_cells。

**Q: 如何查看 Cell 执行历史？**
A: 检查 `.omo/state/agent-cell/cell_states.json` 中的 handoff_log。

**Q: R3 动作如何执行？**
A: 需先通过 PDP 评估，再经主人同步确认，最后 PEP 强制执行。

## 参考

- ADR-0401: AGE-v2 架构决策记录
- `docs/plans/age-v2-long-term-roadmap.md`: 长期路线图
