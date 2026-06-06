# 架构实施方案 — 细化执行方案

> 基于: 09-个人AI操作系统-最终架构方案.md
> 类型: **审查报告 + 详细实施计划**
> 日期: 2026-05-25

---

## 第一部分：审查发现

### 文档层面的5个缺口

| # | 缺口 | 表现 | 影响 |
|---|------|------|------|
| 1 | **Phase 1太粗糙** | "L4 Self域 → KOS结构化 ~200LOC" —— 没说建什么文件、什么MCP工具、什么schema | 无法执行 |
| 2 | **依赖顺序缺失** | 3个新KOS domain(self/collab/consensus)有依赖关系（共识依赖实体存在），计划里没标 | 可能做了一半发现缺东西 |
| 3 | **KOS现有实体类型不匹配** | _types.py只有 Person/Org/Project/Resource/Event/Standard/Concept，没有 Role/Axiom/Principle/Skill/Consensus | 扩展前先改Eidos |
| 4 | **缺少验收标准** | 没有说"做完什么算Phase1完成" | 无法确认进度 |
| 5 | **回滚方案缺失** | 如果KOS新增domain做砸了怎么回退？Schema改错了怎么恢复？ | 有风险 |

### 代码审查发现的2个具体障碍

| # | 障碍 | 详情 |
|---|------|------|
| 6 | **KOS实体ID前缀** | ENTITY_ID_PREFIXES只有7个（ROL-/ORG-/PRJ-/RES-/EVT-/STD-/CON-），需要新增ROL-、AXI-、PRI-等前缀 |
| 7 | **MCP工具注册模式** | KOS MCP server的tools是硬编码dict（在run_stdio的TOOLS字典里），新增domain需要：写handler函数+加TOOLS条目+处理函数映射 |

---

### 修正方案：依赖关系图

```
Day 1-2:  Eidos Schema 扩展 (基础)
  │
  ├──→ Day 2-4: KOS EntityType + 前缀扩展 (基础设施)
  │     │
  │     ├──→ Day 3-5: L4 Self domain + MCP tools
  │     │     │
  │     │     └──→ Day 4-6: X3 Consensus domain + MCP tools
  │     │           (依赖Self/collab存在)
  │     │
  │     └──→ Day 3-5: L3 TaskObject domain + MCP tools
  │           │
  │           └──→ Day 6-8: 保鲜Cron + Value Stack字段
  │
  └──→ Day 3-5: Resource Accounting (独立,可在agentmesh侧并行)
```

---

## 第二部分：逐日执行方案

### Day 1：Eidos Schema 扩展 (~150LOC)

**目标**：在Eidos中定义新增实体类型的Schema，确保跨项目数据一致性。

#### 文件1: `~/Workspace/eidos/schemas/identity-role.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "eidos:identity-role/v1",
  "title": "Identity Role",
  "description": "用户不同场景下的角色画像",
  "type": "object",
  "required": ["role_id", "name", "priority", "values"],
  "properties": {
    "role_id": { "type": "string", "pattern": "^role:[a-z-]+$" },
    "name": { "type": "string" },
    "priority": { "type": "integer", "minimum": 1, "maximum": 10 },
    "values": { "type": "array", "items": { "type": "string" } },
    "time_window": { "type": "string" },
    "communication_style": { "type": "string" },
    "tags": { "type": "array", "items": { "type": "string" } }
  }
}
```

#### 文件2: `~/Workspace/eidos/schemas/value-principle.schema.json`

```json
{
  "$schema": "...",
  "$id": "eidos:value-principle/v1",
  "title": "Value Principle",
  "description": "决策原则：带权重和来源追溯",
  "type": "object",
  "required": ["name", "weight", "source_axiom"],
  "properties": {
    "name": { "type": "string" },
    "weight": { "type": "number", "minimum": 0, "maximum": 1 },
    "source_axiom": { "type": "string" },
    "conflict_resolution": { "type": "string" },
    "version": { "type": "integer", "default": 1 },
    "status": { "type": "string", "enum": ["active", "superseded", "archived"] }
  }
}
```

#### 文件3: `~/Workspace/eidos/schemas/consensus.schema.json`

```json
{
  "$schema": "...",
  "$id": "eidos:consensus/v1",
  "title": "Consensus",
  "description": "用户+Agent联合验证过的可信标记",
  "type": "object",
  "required": ["entity_id", "agreed_by", "agreement", "confirmed_at", "expires_at"],
  "properties": {
    "entity_id": { "type": "string", "description": "共识所标记的实体ID" },
    "agreed_by": { "type": "array", "items": { "type": "string" } },
    "agreement": { "type": "string" },
    "source_session": { "type": "string" },
    "confirmed_at": { "type": "string", "format": "date-time" },
    "expires_at": { "type": "string", "format": "date-time" },
    "status": { "type": "string", "enum": ["active", "stale", "superseded"] }
  }
}
```

#### 文件4: `~/Workspace/eidos/schemas/task-object.schema.json`

```json
{
  "$schema": "...",
  "$id": "eidos:task-object/v1",
  "title": "TaskObject",
  "description": "多Agent共享工作平面——任务协作实体",
  "type": "object",
  "required": ["id", "title", "goal", "status"],
  "properties": {
    "id": { "type": "string", "pattern": "^task-" },
    "title": { "type": "string" },
    "creator": {
      "type": "object",
      "properties": {
        "id": { "type": "string" },
        "role": { "type": "string" }
      }
    },
    "goal": { "type": "string" },
    "visibility_scope": {
      "type": "string",
      "enum": ["private", "team", "org", "public"]
    },
    "subtasks": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "title", "status"],
        "properties": {
          "id": { "type": "string" },
          "title": { "type": "string" },
          "status": { "type": "string", "enum": ["pending", "in_progress", "completed", "failed", "blocked"] },
          "assignee": { "type": "string" },
          "depends_on": { "type": "array", "items": { "type": "string" } },
          "output": { "type": "string" },
          "value_tier": { "type": "string" },
          "freshness": {
            "type": "object",
            "properties": {
              "last_validated": { "type": "string", "format": "date-time" },
              "next_review": { "type": "string", "format": "date-time" }
            }
          }
        }
      }
    },
    "artifacts": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": { "type": "string" },
          "type": { "type": "string" },
          "created_by": { "type": "string" }
        }
      }
    },
    "progress": { "type": "integer", "minimum": 0, "maximum": 100 },
    "status": { "type": "string", "enum": ["active", "completed", "cancelled", "blocked"] },
    "timeline": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "at": { "type": "string", "format": "date-time" },
          "event": { "type": "string" },
          "by": { "type": "string" }
        }
      }
    },
    "resource_usage": {
      "type": "object",
      "properties": {
        "total_tokens": { "type": "integer" },
        "total_cost_usd": { "type": "number" },
        "org_billing": { "type": "string" }
      }
    }
  }
}
```

#### 文件5: 更新 Eidos 注册表
追加到 `~/Workspace/eidos/schemas/registry.json`:
```json
{
  "schemas": [
    {"$id": "eidos:identity-role/v1", "path": "schemas/identity-role.schema.json"},
    {"$id": "eidos:value-principle/v1", "path": "schemas/value-principle.schema.json"},
    {"$id": "eidos:consensus/v1", "path": "schemas/consensus.schema.json"},
    {"$id": "eidos:task-object/v1", "path": "schemas/task-object.schema.json"}
  ]
}
```

**验收标准**: `workspace contracts validate` 能通过所有新Schema的校验。

---

### Day 2：KOS EntityType扩展 (~100LOC)

**目标**：让KOS的实体系统支持新的类型（Role/Axiom/Principle等）。

#### 修改: `~/Workspace/kos/kos/ontology/_types.py`

```python
class EntityType(str, Enum):
    """统一实体类型枚举 — 扩展后"""
    PERSON = "person"
    ORGANIZATION = "organization"
    PROJECT = "project"
    RESOURCE = "resource"
    EVENT = "event"
    STANDARD = "standard"
    CONCEPT = "concept"
    # ── 新增 ──
    ROLE = "role"            # 角色 (L4 Self)
    AXIOM = "axiom"          # 公理 (L4 Self, 最稳定)
    PRINCIPLE = "principle"  # 原则 (L4 → X3 Value Stack)
    THEORY = "theory"        # 理论 (X3 Value Stack)
    FRAMEWORK = "framework"  # 框架 (X3 Value Stack)
    SKILL = "skill"          # 技能 (X3 Value Stack)
    CONSENSUS = "consensus"  # 共识 (X3)
    TASK = "task"            # 任务 (L3 TaskObject)

ENTITY_ID_PREFIXES = {
    # ── 原有 ──
    "ROL-": EntityType.PERSON,     # 不改，保留兼容
    "ORG-": EntityType.ORGANIZATION,
    "PRJ-": EntityType.PROJECT,
    "RES-": EntityType.RESOURCE,
    "EVT-": EntityType.EVENT,
    "STD-": EntityType.STANDARD,
    "CON-": EntityType.CONCEPT,
    # ── 新增 ──
    "RLX-": EntityType.ROLE,       # 角色
    "AXI-": EntityType.AXIOM,      # 公理
    "PRI-": EntityType.PRINCIPLE,  # 原则
    "THY-": EntityType.THEORY,     # 理论
    "FRW-": EntityType.FRAMEWORK,  # 框架
    "SKL-": EntityType.SKILL,      # 技能
    "CSN-": EntityType.CONSENSUS,  # 共识
    "TSK-": EntityType.TASK,       # 任务
}
```

**验收标准**: `python3 -c "from kos.ontology._types import EntityType; print(list(EntityType))"` 输出15个类型。

---

### Day 3：L4 Self Domain + MCP工具 (~150LOC)

**目标**：在KOS中新增self领域，提供身份画像/愿景/原则/认知框架的CRUD。

#### 文件: `~/Workspace/kos/kos/self/__init__.py`

```python
"""KOS Self Domain — L4 自我层

提供: 
- 身份画像 CRUD (roles)
- 愿景系统 CRUD (vision/okrs)
- 价值原则 CRUD (principles)  
- 认知框架 CRUD (frameworks)
- 配置查询 (get_profile)
"""
```

#### 文件: `~/Workspace/kos/kos/self/api.py`

```python
"""Self Domain API — 所有self数据通过这里读写"""

import json
from datetime import datetime
from pathlib import Path

SELF_DB_PATH = Path.home() / ".kos" / "self" / "profile.json"

def _ensure_db():
    SELF_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SELF_DB_PATH.exists():
        SELF_DB_PATH.write_text(json.dumps({
            "version": "v1",
            "updated_at": datetime.now().isoformat(),
            "person": "",
            "roles": [],
            "vision": {},
            "principles": [],
            "frameworks": {},
        }, indent=2, ensure_ascii=False))

def get_profile():
    _ensure_db()
    return json.loads(SELF_DB_PATH.read_text())

def update_profile(data: dict):
    _ensure_db()
    current = get_profile()
    current.update(data)
    current["updated_at"] = datetime.now().isoformat()
    SELF_DB_PATH.write_text(json.dumps(current, indent=2, ensure_ascii=False))
    return current

def get_current_role(context_hint: str = "") -> dict:
    """根据时间/上下文判断当前角色"""
    profile = get_profile()
    roles = profile.get("roles", [])
    if not roles:
        return {}
    from datetime import datetime
    now = datetime.now()
    # 简单判断: 工作日白天→最高优先级, 晚上/周末→次级
    is_weekday = now.weekday() < 5
    is_work_hours = 9 <= now.hour < 18
    if is_weekday and is_work_hours:
        # 按优先级取
        sorted_roles = sorted(roles, key=lambda r: r.get("priority", 99))
        return sorted_roles[0] if sorted_roles else {}
    # 非工作时间
    for role in roles:
        if "家庭" in role.get("name", "") or role.get("priority", 99) > 2:
            return role
    return roles[-1] if roles else {}

def get_vision_summary() -> str:
    """获取愿景摘要（供Agent注入prompt用）"""
    profile = get_profile()
    vision = profile.get("vision", {})
    parts = []
    if vision.get("long_term"):
        parts.append(f"长期愿景: {vision['long_term']}")
    if vision.get("mid_term"):
        parts.append(f"中期目标: {vision['mid_term']}")
    okrs = vision.get("current_okrs", {})
    for q, krs in okrs.items():
        items = [f"  - {kr.get('kr','')} ({kr.get('progress',0)}%)" for kr in krs]
        parts.append(f"当前OKR ({q}):\n" + "\n".join(items))
    return "\n".join(parts)
```

#### MCP工具（追加到`kos/mcp/server.py`）

新增3个工具：

| 工具名 | handler函数 | 功能 |
|--------|------------|------|
| `self.get_profile` | `tool_self_get_profile` | 获取完整自我画像 |
| `self.get_current_role` | `tool_self_get_current_role` | 获取当前活跃角色 |
| `self.get_vision_summary` | `tool_self_get_vision_summary` | 获取愿景摘要（Agent prompt用） |

在`run_stdio`的`TOOLS`字典中添加：
```python
"self.get_profile": {
    "description": "获取完整自我画像（身份/愿景/原则/认知框架）",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
},
"self.get_current_role": {
    "description": "根据当前时间和上下文判断活跃角色",
    "inputSchema": {
        "type": "object",
        "properties": {
            "context_hint": {"type": "string", "description": "上下文提示词"}
        },
        "required": []
    },
},
"self.get_vision_summary": {
    "description": "获取愿景摘要（供Agent注入prompt用）",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
},
```

**验收标准**: 
- `mcp_call self.get_profile` 返回完整的L4画像
- `mcp_call self.get_current_role` 返回当前活跃角色
- 可在Agora中注册为MCP服务

---

### Day 4：L3 TaskObject Domain (~200LOC)

**目标**：在KOS中新增collab领域，提供TaskObject的CRUD和协作工具。

#### 文件: `~/Workspace/kos/kos/collab/__init__.py`

```python
"""KOS Collab Domain — L3 多Agent协作层

提供共享工作平面(TaskObject):
- create_task / get_task / list_tasks / update_task
- claim_subtask / complete_subtask
- add_artifact
"""
```

#### MCP工具（追加到`kos/mcp/server.py`）

新增6个工具：

| 工具名 | handler函数 | 功能 |
|--------|------------|------|
| `collab.create_task` | `tool_collab_create_task` | 创建TaskObject |
| `collab.get_task` | `tool_collab_get_task` | 获取TaskObject详情 |
| `collab.list_tasks` | `tool_collab_list_tasks` | 列任务（按状态/scope过滤） |
| `collab.update_task` | `tool_collab_update_task` | 更新任务状态/进度 |
| `collab.claim_subtask` | `tool_collab_claim_subtask` | Agent认领子任务 |
| `collab.add_artifact` | `tool_collab_add_artifact` | 添加制品 |

```python
def tool_collab_create_task(title: str, goal: str, creator_id: str,
                            creator_role: str = "", visibility: str = "private",
                            subtasks: list = None) -> dict:
    """创建新的TaskObject"""
    import uuid
    task_id = f"task-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    task = {
        "id": task_id,
        "title": title,
        "goal": goal,
        "creator": {"id": creator_id, "role": creator_role},
        "visibility_scope": visibility,
        "subtasks": subtasks or [],
        "artifacts": [],
        "progress": 0,
        "status": "active",
        "timeline": [{"at": datetime.now().isoformat(), "event": "created", "by": creator_id}],
        "resource_usage": {"total_tokens": 0, "total_cost_usd": 0, "org_billing": ""},
    }
    _save_task(task)
    return task

def tool_collab_claim_subtask(task_id: str, subtask_id: str, agent_id: str) -> dict:
    """Agent认领子任务"""
    task = _load_task(task_id)
    for st in task.get("subtasks", []):
        if st["id"] == subtask_id and st["status"] == "pending":
            # 检查依赖是否满足
            deps = st.get("depends_on", [])
            all_deps_done = all(
                any(d["id"] == dep and d["status"] == "completed" for d in task["subtasks"])
                for dep in deps
            )
            if not all_deps_done:
                return {"error": f"依赖未完成: {deps}", "task": task}
            st["status"] = "in_progress"
            st["assignee"] = agent_id
            task["timeline"].append({
                "at": datetime.now().isoformat(),
                "event": "subtask.claimed",
                "by": agent_id,
                "detail": subtask_id,
            })
            _save_task(task)
            return {"status": "claimed", "subtask": st, "task": task}
    return {"error": f"Subtask {subtask_id} not found or not available"}

# _load_task/_save_task 使用 KOS 现有的持久化机制（SQLite或文件）
```

**验收标准**:
- 创建→认领→完成→查看 整条链路跑通
- 依赖检查正常（依赖未完成时拒接认领）
- Agora注册后可通过MCP调用

---

### Day 5：X3 Consensus Domain + Value Stack字段 (~150LOC)

**目标**：共识系统和价值堆栈字段。

#### 文件: `~/Workspace/kos/kos/consensus/__init__.py`

```python
"""KOS Consensus Domain — X3 共识系统

用户+Agent联合验证的"可信标记"
- create_consensus / get_consensus / list_consensus
- verify_consensus / expire_consensus
"""
```

#### MCP工具（追加到`kos/mcp/server.py`）

| 工具名 | 功能 |
|--------|------|
| `consensus.create` | 创建共识记录（打在每个实体上） |
| `consensus.get` | 查询实体的共识状态 |
| `consensus.list_expired` | 列出过期共识（供X2保鲜Cron消费） |
| `consensus.renew` | 续签共识（用户确认后） |

#### Value Stack字段

在`kos/ontology/_types.py`中为每个Entity类增加：

```python
@dataclass
class Entity:
    # ... 原有字段 ...
    # ── X3 Value Stack 字段 ──
    value_tier: str = ""       # axiom|principle|theory|framework|knowledge|skill|tool
    half_life_days: int = 0    # 半衰期（天）
    freshness_status: str = "unknown"  # fresh|stale|unknown|expired
    last_validated: str = ""   # 最后验证时间
    next_review: str = ""      # 下次review时间
    references: list = field(default_factory=list)  # 上层引用链
```

**验收标准**:
- 在实体上创建共识 → 查询共识 → 标记过期 → 续签，整条链路跑通
- Entity的value_tier字段正确初始化

---

### Day 6：保鲜Cron (~150LOC)

**目标**：根据半衰期自动检查知识新鲜度。

#### 脚本: `~/.hermes/scripts/freshness_check.sh`

```bash
#!/bin/bash
# 抗熵保鲜检查 — 根据半衰期扫描KOS实体
# 由cron调度，no_agent模式（静默输出）

# 检查过期共识
python3 -m kos.consensus check_expired > /tmp/freshness_report.txt

# 检查需要review的知识
python3 -m kos.maintenance freshness_scan \
  --max-age-days 365 \
  --output /tmp/freshness_report.txt

# 如果有需要关注的项目 → 输出报告（cron会投递）
if [ -s /tmp/freshness_report.txt ]; then
    cat /tmp/freshness_report.txt
fi
```

#### Cron Job

```yaml
# cron: 每周一早上8点运行保鲜检查
schedule: "0 8 * * 1"
script: "~/.hermes/scripts/freshness_check.sh"
no_agent: true  # 静默模式，有更新才通知
```

**验收标准**: 
- 脚本能正常执行
- 过期实体能在报告中列出
- 无异常时不输出任何内容（静默）

---

### Day 7-8：自测 + 注册到Agora + 集成验证

**目标**：确保所有新工具在Agora中可用，端到端验证。

#### 1. 在Agora注册新MCP服务

```bash
# 注册self domain
agora service register \
  --name "kos-self" \
  --command "python3" \
  --args "-m kos.mcp.server" \
  --description "KOS Self Domain — L4 自我层"

# 注册collab domain  
agora service register \
  --name "kos-collab" \
  --command "python3" \
  --args "-m kos.mcp.server" \
  --description "KOS Collab Domain — L3 协作层"

# 注册consensus domain
agora service register \
  --name "kos-consensus" \
  --command "python3" \
  --args "-m kos.mcp.server" \
  --description "KOS Consensus Domain — X3 共识系统"
```

> **注意**: 如果KOS MCP server已经是单进程，合并新工具到现有server.py即可，不需额外注册。

#### 2. 端到端验证脚本

```python
"""phase1_e2e_test.py — Phase1 端到端验证"""

def test_l4_self():
    r = mcp_call("self.get_profile")
    assert r["person"] == "老王"
    assert len(r["roles"]) >= 3
    
    r = mcp_call("self.get_current_role")
    assert "role_id" in r

def test_l3_collab():
    r = mcp_call("collab.create_task",
        title="测试任务",
        goal="验证协作层",
        creator_id="user:老王")
    task_id = r["id"]
    
    r = mcp_call("collab.get_task", task_id=task_id)
    assert r["status"] == "active"
    
    r = mcp_call("collab.claim_subtask",
        task_id=task_id,
        subtask_id="test-1",
        agent_id="agent:hermes")
    assert r["status"] == "claimed"

def test_x3_consensus():
    r = mcp_call("consensus.create",
        entity_id="knowledge:how-to-audit",
        agreed_by=["user:老王", "agent:hermes"],
        agreement="先扫全貌→逐层深入→红蓝对抗→清零")
    assert "entity_id" in r

print("Phase1 E2E: ALL PASSED")
```

**验收标准**: 所有端到端测试通过。

---

## 第三部分：Phase 2、Phase 3 细化

### Phase 2：Agent解耦（2-3周）

核心是把Hermes内部的skill和memory提取为独立MCP服务。

| 任务 | 文件 | 工作量 |
|------|------|--------|
| **Skill MCP Service** | `~/.hermes/skills/mcp_server.py` | ~200LOC |
| **Memory MCP Service** | `~/.hermes/memory/mcp_server.py` | ~200LOC |
| **Resource Accounting** | `~/Workspace/agentmesh/packages/model-orchestrator/accounting.py` | ~200LOC |
| **Hermes Adapter改造** | Hermes config中让MCP Client通过Agora连接 | ~100LOC |

#### Skill MCP Service 设计

```python
# ~/.hermes/skills/mcp_server.py
# 将Hermes的skill_manage/skill_view 暴露为MCP服务

tools:
  skill.list      → 列出所有可用skill
  skill.view      → 查看skill详情
  skill.search    → 按关键词搜skill
  skill.match     → 根据任务描述匹配合适的skill

# 注册到Agora后，任何Agent都能查询skill
# Hermes自己的skill机制不需要改——只是多了一个MCP门面
```

#### Memory MCP Service 设计

```python
# ~/.hermes/memory/mcp_server.py
# 将Hermes的memory tool 暴露为MCP服务

tools:
  memory.get      → 查询记忆条目（按关键词/类型）
  memory.set      → 写记忆条目
  memory.search   → 搜索历史记忆
  memory.delete   → 删除记忆

# 注意: 这个和gbrain的关系
# gbrain是Agent持久记忆的存储后端
# Memory MCP Service是gbrain的MCP门面
# 底层数据仍在gbrain中
```

#### Resource Accounting 设计

```python
# ~/Workspace/agentmesh/packages/model-orchestrator/accounting.py

@dataclass
class ResourceUsage:
    call_id: str
    caller: str           # "agent:hermes"
    service: str          # "minerva.research_now"
    tokens_input: int
    tokens_output: int
    cost_usd: float
    org: str              # "starlink-core"
    billed_to: str        # "project:xxx"
    timestamp: str

class ResourceAccounting:
    def __init__(self):
        self.db = Path.home() / ".kos" / "accounting" / "usage.db"
    
    def record(self, usage: ResourceUsage):
        """记录一次调用成本"""
        ...
    
    def get_usage(self, org: str, since: str) -> dict:
        """查询组织在某段时间内的总成本"""
        ...
    
    def check_budget(self, org: str, project: str) -> bool:
        """检查是否超出预算"""
        ...
```

---

### Phase 3：生态适配

| 任务 | 前置条件 | 验证方式 |
|------|---------|---------|
| Claude Desktop接入 | TaskObject就绪 | 让Claude Desktop认领一个UI设计子任务 |
| Codex CLI接入 | TaskObject + Resource Accounting | 让Codex认领编码子任务 |
| 降级模式 | Agora A2A增强 | 停Agora → 检查Agent能否通过A2A直连 |

---

## 第四部分：回滚方案

| 场景 | 回滚操作 |
|------|---------|
| KOS新增EntityType导致现有代码崩溃 | 回退_types.py到修改前版本 |
| 新增MCP工具注册错误 | 回退server.py + 重启MCP server |
| L4 Self数据写入错误 | 删除~/.kos/self/profile.json（自动重建） |
| TaskObject数据错误 | 删除KOS collab domain对应的数据表 |
| Schema定义错误 | 回退Eidos schema + 重新run indexer |

---

## 第五部分：总结

### 总工作量明细

| 天 | 任务 | LOC | 交付物 |
|----|------|-----|--------|
| Day 1 | Eidos Schema扩展 | ~150LOC | 4个新schema文件 + registry更新 |
| Day 2 | KOS EntityType扩展 | ~100LOC | `_types.py`修改（15类型） |
| Day 3 | L4 Self Domain + MCP | ~150LOC | `kos/self/` + 3个MCP工具 |
| Day 4 | L3 TaskObject Domain | ~200LOC | `kos/collab/` + 6个MCP工具 |
| Day 5 | X3 Consensus Domain | ~150LOC | `kos/consensus/` + 4个MCP工具 + Entity字段 |
| Day 6 | 保鲜Cron | ~150LOC | shell脚本 + cron配置 |
| Day 7-8 | 集成验证 | ~100LOC | E2E测试 + Agora注册 |

**总计**: ~850LOC新建 + ~100LOC修改
**与文档估算对比**: 原估~900LOC → 细化后约~950LOC（误差<10%，合理）

**可逆性**: 每天的工作都可以独立回滚，不阻塞整体进度。

---

> 本文档替代Phase 1-3的粗略描述，作为实施时的逐日指南。
> "依次执行，做好验证" 即可。
