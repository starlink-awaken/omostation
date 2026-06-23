---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: T119 — 三Agent协作E2E

> 类型: P8 Task | 预估: 3天 | Wave: 8.3 | Phase: 8
> 前置: T117 (Claude Desktop接入) + T118 (Codex CLI接入)

## 一、目标

Hermes+Claude Desktop+Codex三Agent同跑一个Task，各自认领擅长的subtask，完成协作闭环。

## 二、测试场景

### 场景: "开发Mac mini监控面板"

```yaml
task:
  title: "Mac mini监控面板"
  goal: "开发Web监控面板，显示CPU/内存/磁盘/GPU状态"
  subtasks:
    - id: "research"
      title: "调研现有Mac监控方案"
      tags: ["research"]
      → Hermes认领
    - id: "ui-design"
      title: "设计监控面板UI原型"
      tags: ["ui-design", "frontend"]
      → Claude Desktop认领
    - id: "coding"
      title: "编码实现后端+前端"
      tags: ["coding", "python", "html"]
      → Codex认领
    - id: "wechat-integration"
      title: "接入微信告警推送"
      tags: ["coding", "api"]
      → Codex认领 (依赖coding完成)
```

### 执行流程

```python
def e2e_test():
    # Step 1: Hermes创建Task
    task = mcp_call("collab.create_task",
        title="Mac mini监控面板",
        goal="Web监控面板+微信告警",
        subtasks=[
            {"id": "research", "title": "调研现有方案", "status": "pending", "tags": ["research"]},
            {"id": "ui-design", "title": "设计UI原型", "status": "pending", "tags": ["ui-design"]},
            {"id": "coding", "title": "编码实现", "status": "pending", "tags": ["coding"], "depends_on": ["research", "ui-design"]},
            {"id": "wechat", "title": "微信告警", "status": "pending", "tags": ["coding"], "depends_on": ["coding"]},
        ],
        creator_id="user:老王",
        visibility="team:starlink-core"
    )
    task_id = task["task_id"]
    
    # Step 2: Hermes认领research
    mcp_call("collab.claim_subtask", task_id=task_id, subtask_id="research", assignee="agent:hermes")
    mcp_call("collab.complete_subtask", task_id=task_id, subtask_id="research", assignee="agent:hermes",
             output="/tmp/research-summary.md")
    
    # Step 3: Claude Desktop感知到research完成 → 认领ui-design
    # (Claude Desktop手动操作或自动)
    
    # Step 4: Codex感知到research+ui-design完成 → 认领coding
    # (Codex CLI自动或手动)
    
    # Step 5: 验证
    task = mcp_call("collab.get_task", task_id=task_id)
    assert task["progress"] == 100, f"Progress: {task['progress']}%"
    print("E2E: ALL PASSED")
```

### 验证脚本

```bash
# 集成测试脚本
cat > /tmp/phase8_e2e.py << 'PYEOF'
...上述代码...
PYEOF

python3 /tmp/phase8_e2e.py
```

## 三、验收标准

```
☐ Hermes创建TaskObject → 可见于collab.list_tasks
☐ Hermes完成research → 进度更新
☐ Claude Desktop可认领ui-design (MCP配置正确)
☐ Codex CLI可认领coding (依赖检查通过)
☐ 所有subtask完成后Task自动completed
☐ 用户可查询完整timeline
```
