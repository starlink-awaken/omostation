---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 8 — 多Agent真实协作

> **周期**: 6周 (Wave 8.1: 2周, Wave 8.2: 2周, Wave 8.3: 1周, Wave 8.4: 1周)
> **负责人**: TBD
> **目标**: Hermes+Claude Desktop+Codex三Agent同跑一个Task，各司其职
> **前置**: Phase 7 (工具已集成到Hermes)
> **门禁**: 三Agent协作E2E跑通, Memory/Skill标准化MCP可达, 降级模式验证通过
> **风险**: Claude Desktop和Codex CLI的MCP协议兼容性、跨进程状态同步

---

## 依赖关系

```
Wave 8.1 (2周) — Hermes Collab深度集成
  ├── T111 Hermes TaskObject全流程
  ├── T112 Task状态跟踪+进度推送
  └── T113 子任务完成自动触发下一个

Wave 8.2 (2周) — Memory/Skill标准化MCP (与8.1可部分并行)
  ├── T114 Memory MCP Service
  ├── T115 Skill MCP Service
  └── T116 Agora注册+跨Agent验证

Wave 8.3 (1周) — 外部Agent接入 (依赖8.1, 8.2)
  ├── T117 Claude Desktop接入
  ├── T118 Codex CLI接入
  └── T119 三Agent协作E2E

Wave 8.4 (1周) — 降级模式 (依赖8.3)
  ├── T120 Agora→A2A降级
  └── T121 混沌测试

回滚策略:
  - Memory/Skill MCP化失败 → 退回Hermes内部memory
  - Claude Desktop不兼容 → 手动桥接
  - 降级模式不稳定 → 不启用
```

---

## Wave 8.1 — Hermes Collab深度集成 (2周, 3 Tasks)

### T111: TaskObject全流程打通

**当前**: Hermes可以创建TaskObject但还不能完整跟踪全生命周期。

**目标**: 从创建→认领→进度更新→完成→共识标记，全自动。

```python
# ~/.hermes/plugins/task_orchestrator.py

class TaskOrchestrator:
    def create_and_manage(self, user_input: str) -> str:
        """创建TaskObject并管理全生命周期"""
        # 1. 分析意图，创建Task
        task_data = self.decompose(user_input)
        task = mcp_call("collab.create_task", **task_data, creator_id="user:老王")
        task_id = task["task_id"]
        
        # 2. 标记Hermes可做的subtasks
        for st in task_data["subtasks"]:
            if self.can_do(st):
                mcp_call("collab.claim_subtask", task_id=task_id, 
                         subtask_id=st["id"], assignee="agent:hermes")
        
        # 3. 推送事件到EventBus
        mcp_call("agora.publish_event", event_type="collab:task.created",
                 payload={"task_id": task_id, "available_subtasks": [...]})
        
        return f"Task已创建: {task_id}\n子任务: {[s['title'] for s in task_data['subtasks']]}"
    
    def can_do(self, subtask: dict) -> bool:
        """判断Hermes自己能做的子任务"""
        hermes_capabilities = ["research", "knowledge_search", "analysis", 
                              "writing", "audit", "summarize"]
        tags = subtask.get("tags", [])
        return any(t in hermes_capabilities for t in tags)
```

**验收**:
```
☐ 复杂任务自动拆解并创建TaskObject
☐ Hermes自动认领自己能做的subtask
☐ 事件推送到Agora EventBus
☐ 其他Agent可感知到新Task
```

### T112: Task状态跟踪+进度推送

**目标**: 当Task的subtask状态变化时，自动推送进度给用户。

```python
def progress_report(task_id: str) -> str:
    """生成Task进度报告"""
    task = mcp_call("collab.get_task", task_id=task_id)
    total = len(task["subtasks"])
    done = sum(1 for s in task["subtasks"] if s["status"] == "completed")
    in_prog = sum(1 for s in task["subtasks"] if s["status"] == "in_progress")
    return f"📊 进度: {done}/{total} ({task['progress']}%)\n" + \
           f"完成: {done} | 进行中: {in_prog} | 待处理: {total-done-in_prog}"
```

**验收**:
```
☐ 每完成一个subtask自动推送进度
☐ 用户可手动查进度: "任务xxx进度如何"
☐ Task全部完成时自动通知
```

### T113: 子任务完成自动触发下一个

**目标**: 当一个subtask完成，自动触发下一个依赖它的subtask。

```python
def on_subtask_completed(task_id: str, completed_subtask_id: str):
    """子任务完成回调"""
    task = mcp_call("collab.get_task", task_id=task_id)
    for st in task["subtasks"]:
        if st["status"] == "pending":
            deps = st.get("depends_on", [])
            # 如果所有依赖都完成了，自动认领
            all_deps_done = all(
                any(d["id"] == dep and d["status"] == "completed" 
                    for d in task["subtasks"])
                for dep in deps
            )
            if all_deps_done and st["id"] not in completed_subtask_id:
                mcp_call("collab.claim_subtask", task_id=task_id,
                         subtask_id=st["id"], assignee="agent:auto")
```

**验收**:
```
☐ subtask完成后自动触发依赖解除
☐ 可触发的下一个subtask自动被认领
☐ 无依赖的pending subtask保持等待
```

---

## Wave 8.2 — Memory/Skill标准化MCP (2周, 3 Tasks)

### T114: Memory MCP Service

**当前**: Hermes的memory tool只有Hermes自己能调。
**目标**: 暴露为MCP服务，任何Agent都能查询/写入。

```python
# ~/.hermes/memory/mcp_server.py
from hermes.memory import Memory

MEMORY_TOOLS = {
    "memory.get": {
        "description": "查询持久记忆条目",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "关键词或自然语言查询"},
                "limit": {"type": "integer", "default": 5}
            },
            "required": ["query"]
        }
    },
    "memory.set": {
        "description": "写入持久记忆条目",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "记忆内容"},
                "tags": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["content"]
        }
    },
}

MEMORY_HANDLERS = {
    "memory.get": lambda **kw: Memory.search(kw["query"], kw.get("limit", 5)),
    "memory.set": lambda **kw: Memory.save(kw["content"], kw.get("tags", [])),
}
```

**验收**:
```
☐ memory.get 可查询Hermes的记忆
☐ memory.set 可写入新记忆
☐ 运行在独立进程，注册到Agora
```

### T115: Skill MCP Service

**当前**: Hermes的skill_view/manage只有Hermes能用。
**目标**: 暴露为MCP服务，任何Agent都能查询/匹配skill。

**验收**:
```
☐ skill.list 列出所有可用skill
☐ skill.match 根据任务描述匹配合适的skill
☐ 注册到Agora
```

### T116: Agora注册+跨Agent验证

```bash
# 注册Memory Service
agora service register \
  --name "hermes-memory" \
  --command "python3" \
  --args "-m hermes.memory.mcp_server"

# 注册Skill Service
agora service register \
  --name "hermes-skills" \
  --command "python3" \
  --args "-m hermes.skills.mcp_server"

# 验证
agora tool list | grep "memory\|skill"
```

**验收**:
```
☐ Agora list_tools 显示 memory.* 和 skill.*
☐ 可直接通过Agora调用memory.get
```

---

## Wave 8.3 — 外部Agent接入 (1周, 3 Tasks)

### T117: Claude Desktop接入

**目标**: Claude Desktop能感知TaskObject，认领UI设计类subtask。

```bash
# Claude Desktop MCP配置 (~/Library/Application Support/Claude/claude_desktop_config.json)
{
  "mcpServers": {
    "workspace": {
      "command": "python3",
      "args": ["-m", "kos.mcp.server"],
      "env": {"KOS_HOME": "/Users/xiamingxing/Workspace/kos"}
    }
  }
}
```

**验证**:
```
☐ Claude Desktop能看到collab.*和self.*工具
☐ 可调用collab.list_tasks查看可用Task
☐ 可调用collab.claim_subtask认领任务
```

### T118: Codex CLI接入

**目标**: Codex CLI能认领编码类subtask。

**验收**:
```
☐ Codex CLI能调用collab工具
☐ 编码完成后调用complete_subtask
☐ 产出物通过add_artifact上传
```

### T119: 三Agent协作E2E

**终极验证**: Hermes+Claude Desktop+Codex同跑一个Task。

```bash
# E2E测试脚本
python3 phase8_e2e_test.py

# 测试用例:
# 1. 创建Task: "开发Mac mini监控面板"
#    - subtask research → Hermes认领
#    - subtask ui-design → Claude Desktop认领  
#    - subtask coding → Codex认领
# 2. Hermes完成research → 进度更新
# 3. Claude Desktop感知→完成ui-design
# 4. Codex感知→完成coding
# 5. 所有done → Task自动completed
```

**验收**:
```
☐ 三Agent各自完成自己的subtask
☐ Task progress从0→100%
☐ 用户可随时查进度
☐ 整体耗时<原本串行50%
```

---

## Wave 8.4 — 降级模式 (1周, 2 Tasks)

### T120: Agora→A2A降级

**目标**: Agora挂掉时，Agent之间通过A2A直连。

```python
# ~/.hermes/adapters/agora_fallback.py

class AgoraFallback:
    """Agora不可用时的降级通信"""
    
    def __init__(self):
        self.direct_peers = {
            "agent:claude-desktop": {"host": "localhost", "port": 8765},
            "agent:codex": {"host": "localhost", "port": 8766},
        }
    
    def call_tool(self, agent_id: str, tool: str, args: dict) -> dict:
        """通过A2A直连调用"""
        if not self._agora_healthy():
            peer = self.direct_peers.get(agent_id)
            if peer:
                return self._a2a_call(peer, tool, args)
        return self._agora_call(agent_id, tool, args)
    
    def _agora_healthy(self) -> bool:
        """健康检查: 超时1秒"""
        try:
            resp = requests.get("http://localhost:7430/health", timeout=1)
            return resp.status_code == 200
        except:
            return False
```

**验收**:
```
☐ Agora正常时走Agora
☐ Agora挂掉后自动切A2A直连
☐ 恢复后自动切回Agora
```

### T121: 混沌测试

```bash
# 1. Agora正常运行 → 验证协作正常
hermes chat "审计代码质量"
# 2. 停掉Agora
kill $(pgrep -f "agora")
# 3. 再发一个任务 → 应该通过A2A降级继续工作
hermes chat "再审计一下"
# 4. 重启Agora
agora start
# 5. 再发一个任务 → 应该自动切回Agora
hermes chat "再检查一次"
```

**验收**:
```
☐ Agora停服后任务仍可执行（降级模式）
☐ Agora恢复后自动切回
☐ 用户无感知（最多延迟增加）
```

---

## 门禁条件

```
☐ Hermes TaskObject全生命周期自动化（创建→认领→完成→标记）
☐ Memory/Skill已标准化为MCP服务，注册到Agora
☐ Claude Desktop可认领+完成一个UI设计subtask
☐ Codex CLI可认领+完成一个编码subtask
☐ 三Agent协作E2E跑通（一个Task，三Agent各自完成）
☐ Agora降级模式验证通过
```

## TASK_POOL 映射

| ID | Task | Wave | 预估 | 
|----|------|------|------|
| T111 | Hermes TaskObject全流程 | 8.1 | 4天 |
| T112 | Task状态跟踪+进度推送 | 8.1 | 3天 |
| T113 | 子任务完成自动触发 | 8.1 | 3天 |
| T114 | Memory MCP Service | 8.2 | 4天 |
| T115 | Skill MCP Service | 8.2 | 4天 |
| T116 | Agora注册+验证 | 8.2 | 2天 |
| T117 | Claude Desktop接入 | 8.3 | 2天 |
| T118 | Codex CLI接入 | 8.3 | 2天 |
| T119 | 三Agent协作E2E | 8.3 | 3天 |
| T120 | Agora→A2A降级 | 8.4 | 3天 |
| T121 | 混沌测试 | 8.4 | 3天 |

**总计**: 11 Tasks, 6周, ~2000LOC
