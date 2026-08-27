---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 7 — 让工具跑起来

> **周期**: 4周 (Wave 7.1: 2周, Wave 7.2: 1周, Wave 7.3: 1周)
> **负责人**: TBD
> **目标**: 所有已上线工具真正被用起来，用户走通5条核心链路
> **前置**: Phase 1-6 (L4/L3/X3工具已上线)
> **门禁**: D2≥85, D9≥60, D6≥80, 健康总分≥75
> **风险**: Hermes集成新工具有兼容性问题、成本追踪影响性能

---

## 依赖关系

```
Wave 7.1 (2周) — 完整用户旅程
  ├── T099 Hermes config接入self_inject.sh
  ├── T100 Hermes集成TaskObject
  ├── T101 共识自动标记
  ├── T102 保鲜Cron首份报告
  └── T103 D2场景重评

Wave 7.2 (1周) — 成本可见 (可与7.3并行)
  ├── T104 token计数器
  ├── T105 usage.db
  ├── T106 cost summary CLI
  └── T107 日报cron

Wave 7.3 (1周) — 熵增自动化 (可与7.2并行)
  ├── T108 保鲜Cron结构化输出
  ├── T109 报告写入KOS
  └── T110 D6评分更新

回滚策略:
  - Hermes config改坏 → 恢复~/.hermes/config.yaml备份
  - token计数器影响性能 → 关闭计数功能
  - 保鲜Cron误报 → 调整阈值或暂停cron
```

---

## Wave 7.1 — 完整用户旅程 (14天, 5 Tasks)

### T099: Hermes接入self_inject (~2天)

**问题**: L4 Self Domain的3个MCP工具已上线，但Hermes从来没有自动调用它们。
用户说话时Hermes不知道"当前是什么角色"。

**方案**: 在Hermes config中配置 `context_preload`。

```yaml
# ~/.hermes/config.yaml 追加
context_preload:
  schedule: "daily_first"  # 每天第一次交互时加载
  sources:
    - source: "mcp:self.get_vision_summary"
      inject_at: "user_message"
    - source: "mcp:self.get_current_role"
      format: "## 用户当前角色\n{result}"
    - source: "mcp:self.get_profile"
      fields: ["person", "roles"]
      format: "## 用户画像\n{result}"
```

**验证**:
```bash
# 1. config语法检查
hermes config validate

# 2. 发送一条消息，检查system prompt中是否包含"用户当前角色"
# （手动测试）
hermes chat "你好" --debug 2>&1 | grep "用户当前角色"

# 3. 没有context_preload时的行为和有时是否一致
# （回归测试）
```

**验收标准**:
```
☐ hermes config validate 通过
☐ 每天第一次交互，prompt中包含L4上下文（角色/愿景）
☐ 第二次及后续交互不含L4上下文（避免浪费token）
☐ 切换时间到"工作日"→自动识别为角色1，到"晚上"→角色2
```

### T100: Hermes集成TaskObject (~5天)

**问题**: L3 Collab的6个MCP工具已上线，但Hermes从来不创建TaskObject。
复杂任务仍然单步推理，不会自动拆解。

**方案**: 在Hermes中增加"复杂任务→自动拆解→创建TaskObject"的流程判断。

```python
# Hermes决策逻辑扩展
def should_create_task(user_input: str) -> bool:
    """判断是否需要创建TaskObject"""
    # 以下情况创建Task:
    # - 包含多个步骤的描述 ("先调研再设计最后编码")
    # - 需要外部Agent协作 ("让Claude Desktop来做UI")
    # - 任务预计超过30分钟
    # - 用户明确要求 ("帮我分解这个任务")
    complexity = estimate_complexity(user_input)
    return complexity.level in ("L2", "L3")

def decompose_to_task(user_input: str) -> dict:
    """调用LLM将用户输入分解为TaskObject"""
    # 用LLM分析用户输入
    # 输出: {title, goal, subtasks: [{id, title, status}]}
    # 然后调用 collab.create_task
```

**验证**:
```bash
# 1. 简单查询→不创建Task
hermes chat "KOS地址是什么" --debug 2>&1 | grep -c "create_task"
# 期望: 0 (不创建)

# 2. 复杂任务→自动创建Task
hermes chat "帮我审计一下Forge的代码质量，再写个报告" --debug 2>&1 | grep "Task created"
# 期望: 出现Task ID

# 3. collab工具可用
python3 -c "
from kos.collab.api import create_task, get_task
t = create_task('测试','验证集成','user:hermes')
print('OK:', t['task_id'])
"
```

**验收标准**:
```
☐ 简单查询不创建Task (不浪费)
☐ 复杂任务自动拆解为subtasks并创建TaskObject
☐ 创建的Task可通过 collab.get_task 查询
☐ Task的timeline包含创建记录
```

### T101: 共识自动标记 (~2天)

**问题**: X3 Consensus的4个MCP工具已上线，但Hermes完成任务后从不标记共识。
用户验证通过的方案没有留下"可信标记"。

**方案**: Hermes在完成以下操作后自动创建consensus:
- 用户说"好的/可以/确认/对的"→L2共识
- KOS搜索结果被用户采纳→L1共识
- 红队对抗通过→L3共识

```python
def auto_consensus(user_feedback: str, entity_id: str):
    """用户确认后自动创建共识"""
    positive = ["好的", "可以", "确认", "对的", "继续", "ok", "yes", "就是这样"]
    if any(kw in user_feedback.lower() for kw in positive):
        consensus.create(
            entity_id=entity_id,
            agreed_by=["user:老王", "agent:hermes"],
            agreement=f"用户确认: {user_feedback[:100]}",
            level=2
        )
```

**验证**:
```bash
# 用户说"好的"→L2共识创建
hermes chat "就这样，确认" --debug 2>&1 | grep "consensus created"
```

**验收标准**:
```
☐ 用户积极反馈→自动创建L2共识
☐ 消极反馈→不创建
☐ 共识创建后可查询
```

### T102: 保鲜Cron首份报告 (~2天)

**问题**: `freshness_check.sh`已上线，但没跑出过第一份报告，不知道系统实际腐烂速度。

**方案**: 手动触发+分析首份报告，建立D6基线。

**验收标准**:
```
☐ freshness_check.sh 可正常运行
☐ 输出第一份熵增报告（JSON格式）
☐ 报告中包含: 过期实体数、共识过期率、孤立实体数
☐ 报告已写入 KOS
```

### T103: D2场景覆盖度重评 (~2天)

**验收标准**:
```
☐ 5条核心链路全部可用
☐ D2评分从57→85+
```

---

## Wave 7.2 — 成本可见 (7天, 4 Tasks)

### T104: token计数器 (~2天)

**位置**: `agentmesh/packages/model-orchestrator/accounting.py`

```python
@dataclass
class ResourceUsage:
    call_id: str
    caller: str
    service: str
    tokens_input: int
    tokens_output: int
    cost_usd: float
    timestamp: str
```

**验收**:
```
☐ 每次MCP调用记录token消耗
☐ 记录包含caller/service/input/output
```

### T105: usage.db (~2天)

**位置**: `~/.kos/accounting/usage.db`

```sql
CREATE TABLE resource_usage (
    call_id TEXT PRIMARY KEY,
    caller TEXT,
    service TEXT,
    tokens_input INTEGER,
    tokens_output INTEGER,
    cost_usd REAL,
    timestamp TEXT
);
```

**验收**:
```
☐ 数据库创建成功
☐ 记录可写入/查询
```

### T106: cost summary CLI (~2天)

```bash
cost summary --today
# 输出:
# 今日总消耗: 12,345 tokens ($0.37)
# 按服务: minerva 8,000 ($0.25), kos 3,000 ($0.08)...
# 按调用者: hermes 10,000 ($0.30), cron 2,345 ($0.07)

cost summary --week
cost summary --by-service minerva
```

**验收**:
```
☐ --today 输出当日汇总
☐ --week 输出本周汇总
☐ --by-service 按服务过滤
```

### T107: 日报cron (~1天)

每天早上推送token消耗到微信。

**验收**:
```
☐ cron正常运行
☐ 微信收到日报（无异常时也可静默）
```

---

## Wave 7.3 — 熵增自动化 (7天, 3 Tasks)

### T108: 保鲜Cron结构化输出 (~3天)

```bash
# 当前: freshness_check.sh 输出文本
# 改为: freshness_check.sh 输出JSON + 文本

freshness_check.sh --json
# {
#   "total_entities": 15000,
#   "expired_consensus": 23,
#   "stale_knowledge": 145,
#   "unreferenced_entities": 312,
#   "freshness_score": 78,
#   "generated_at": "2026-06-01T08:00:00+08:00"
# }
```

**验收**:
```
☐ --json 输出结构化数据
☐ 无参数时输出人类可读报告
```

### T109: 报告写入KOS (~2天)

保鲜报告自动写入KOS consensus域，可历史追踪。

**验收**:
```
☐ 报告写入KOS
☐ 可查询历史报告: `consensus.get("freshness:2026-06-01")`
```

### T110: D6评分更新 (~2天)

基于首份报告计算D6得分并更新HEALTH_DASHBOARD。

**验收**:
```
☐ D6评分≥80
☐ HEALTH_DASHBOARD已更新
```

---

## 门禁条件

```
Phase 7 完成需要全部满足:

☐ D2 ≥ 85/100 (当前57)
☐ D9 ≥ 60/100 (当前0/盲区)
☐ D6 ≥ 80/100 (当前50)
☐ 健康总分 ≥ 75/100 (当前66.80)

☐ Hermes每天首次交互自动加载L4上下文
☐ 复杂任务自动创建TaskObject
☐ 用户确认后自动创建共识
☐ 保鲜Cron产出第一份结构化报告
☐ cost summary CLI可用
```

---

## TASK_POOL 映射

| ID | Task | Wave | 预估 |
|----|------|------|------|
| T099 | Hermes config接入self_inject.sh | 7.1 | 2天 |
| T100 | Hermes集成TaskObject | 7.1 | 5天 |
| T101 | 共识自动标记 | 7.1 | 2天 |
| T102 | 保鲜Cron首份报告 | 7.1 | 2天 |
| T103 | D2场景重评 | 7.1 | 2天 |
| T104 | token计数器 | 7.2 | 2天 |
| T105 | usage.db | 7.2 | 2天 |
| T106 | cost summary CLI | 7.2 | 2天 |
| T107 | 日报cron | 7.2 | 1天 |
| T108 | 保鲜Cron结构化输出 | 7.3 | 3天 |
| T109 | 报告写入KOS | 7.3 | 2天 |
| T110 | D6评分更新 | 7.3 | 2天 |

**总计**: 12 Tasks, 4周, ~1500LOC
