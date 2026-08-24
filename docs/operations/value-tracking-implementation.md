# 价值度量落地说明 (Value Dimension Implementation)

> 目标: 将 value 维度从 25% 提升到 85%+
> 关键路径: principal_id 接入 → 时间追踪 → North Star 数据积累

---

## 当前状态

- **UHS value 分数**: 25% (North Star 返回 `collecting` 因为有了 principal_id)
- **目标**: 85% (North Star 返回 `proven`)
- **阻碍**: 需要 4 周 × 每周 3 个 qualifying episodes

---

## 已完成的准备工作

### 1. Constitution (principal_id 定义)
- 文件: `.omo/constitution.yaml`
- principal_id: `xiamingxing`
- 角色: architecture-governance, engineering-lead, product-strategist
- 时间追踪配置: 已启用

### 2. UHS 评分更新
- `bin/gac/unified-health-score.py` 已支持 value 维度评分
- 评分逻辑:
  - `proven` = 100%
  - `collecting` = 50%
  - `not_ready` = 25%
  - `unprovable` = 0%

---

## 需要执行的步骤

### Step 1: Agent Workflow Closeout 记录时间节省

修改 `bin/agent-workflow.py` 的 closeout 流程, 在关闭 run 时记录:

```python
# 在 closeout 逻辑中添加
value_evidence = {
    "principal_id": "xiamingxing",  # 从 constitution.yaml 读取
    "review_duration_seconds": <用户审核时间>,
    "estimated_time_saved_seconds": <系统估计节省时间>,
    "verdict": "accept" | "edit" | "reject" | "defer",
    "run_id": "<run-id>",
    "timestamp": "<iso-timestamp>"
}
# 写入 .omo/_delivery/ingress/value-evidence.jsonl
```

### Step 2: North Star 集成

修改 `bin/bc-os/north_star_meter_v2.py`:

```python
# 读取 principal_id from constitution
constitution = yaml.safe_load(open(".omo/constitution.yaml"))
principal_id = constitution.get("principal_id", "unknown")

# 传入 observe_principal
observation = service.observe_principal(principal_id=principal_id)
```

### Step 3: 4 周数据积累

| 周 | 目标 | 验证 |
|----|------|------|
| W1 | ≥ 3 qualifying episodes | `north_star_meter_v2.py --status` |
| W2 | ≥ 3 qualifying episodes | `north_star_meter_v2.py --status` |
| W3 | ≥ 3 qualifying episodes | `north_star_meter_v2.py --status` |
| W4 | ≥ 3 qualifying episodes | `north_star_meter_v2.py --status` → `proven` |

### Qualifying Episode 标准

一个 episode 必须满足:
1. 信号源触发 (非合成)
2. `Action.Succeeded` (PDP producer)
3. `accept` verdict
4. 系统证据来源
5. 完整的负担记录 (review + saved)
6. review < saved (净时间节省)
7. 有效的修订收据

---

## 验证命令

```bash
# 查看 North Star 状态
python3 bin/bc-os/north_star_meter_v2.py --status

# 查看 UHS value 维度
python3 bin/gac/unified-health-score.py --json | jq '.scores.value'

# 查看 qualifying episodes 数量
cat .omo/_delivery/ingress/value-evidence.jsonl | wc -l
```

---

## 预期时间线

| 时间 | 里程碑 | UHS value |
|------|--------|-----------|
| W0 | Constitution 创建, principal_id 接入 | 25% → 50% |
| W1 | 首个 qualifying episode | 50% |
| W2 | 累计 3 episodes | 50% |
| W3 | 累计 6 episodes | 50% |
| W4 | 累计 9 episodes | 50% |
| W5 | 累计 12 episodes (4周×3) | 50% → 75% |
| W8 | 持续积累 | 75% → 100% |

---

## 关联文件

- Constitution: `.omo/constitution.yaml`
- UHS 计算器: `bin/gac/unified-health-score.py`
- North Star: `bin/bc-os/north_star_meter_v2.py`
- Agent Workflow: `bin/agent-workflow.py`
- Value Evidence: `.omo/_delivery/ingress/value-evidence.jsonl` (运行时生成)
