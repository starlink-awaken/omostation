# 架构细化Review与机制设计

> 基于: 09-个人AI操作系统-最终架构方案.md + 09-实施方案-细化方案.md
> 类型: **架构Review + 详细机制设计**
> 日期: 2026-05-25

---

## 目录

1. [架构Review：6个剩余缺口](#1-架构review6个剩余缺口)
2. [机制设计：KOS MCP Server组织方式](#2-机制设计kos-mcp-server组织方式)
3. [机制设计：TaskObject持久化与并发控制](#3-机制设计taskobject持久化与并发控制)
4. [机制设计：Consensus分级验证](#4-机制设计consensus分级验证)
5. [机制设计：Self Context自动注入](#5-机制设计self-context自动注入)
6. [机制设计：Agora集成契约](#6-机制设计agora集成契约)
7. [状态机与流程图](#7-状态机与流程图)
8. [错误处理矩阵](#8-错误处理矩阵)
9. [数据库Schema总表](#9-数据库schema总表)

---

## 1. 架构Review：6个剩余缺口

对09-实施方案-细化方案的审查看出6个缺口：

| # | 缺口 | 细化方案的状态 | 影响 |
|---|------|--------------|------|
| G1 | **KOS MCP Server组织** — 13个新工具往哪里放？单文件还是分模块？ | 未定义 | 代码组织混乱，维护困难 |
| G2 | **TaskObject存储** — 具体存在哪个库哪个表？并发控制怎么做？ | 说"使用现有机制" | 无法实现 |
| G3 | **Consensus验证** — "用户+Agent联合验证"的代码语义是什么？谁有权限？ | 未定义 | 共识系统无法工作 |
| G4 | **Self Context自动注入** — "Agent自动加载L4"的具体实现是什么？ | 未定义 | L4是纸上谈兵 |
| G5 | **Agora集成方式** — 新工具需要启动新服务还是在现有服务中扩展？ | 模糊 | 可能多启动一个多余的进程 |
| G6 | **错误和边界** — 冷启动/并发冲突/服务重启怎么处理？ | 未定义 | 生产不可用 |

以下各节逐个给出机制设计。

---

## 2. 机制设计：KOS MCP Server组织方式

### 决策

**维持单进程+模块化拆分**。不启动新进程。

### 原理

```
启动 → server.py (路由器)
         │
         ├── import kos.self.mcp     → SELF_TOOLS + self_handlers
         ├── import kos.collab.mcp   → COLLAB_TOOLS + collab_handlers
         └── import kos.consensus.mcp → CONSENSUS_TOOLS + consensus_handlers
         │
         ├── TOOLS = {**EXISTING, **SELF, **COLLAB, **CONSENSUS}
         ├── 收到MCP请求 → dispatch(tool_name, args)
         └── dispatch → self_handlers | collab_handlers | consensus_handlers | existing
```

### 模块契约

每个新domain的mcp.py模块必须导出：

```python
# kos/self/mcp.py 示例

# 1. TOOLS dict — 工具注册信息
SELF_TOOLS = {
    "self.get_profile": {
        "description": "获取完整自我画像",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    "self.get_current_role": {
        "description": "根据当前时间判断活跃角色",
        "inputSchema": {
            "type": "object",
            "properties": {
                "context_hint": {"type": "string"}
            },
            "required": [],
        },
    },
    "self.get_vision_summary": {
        "description": "获取愿景摘要（供Agent prompt注入）",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
}

# 2. handlers dict — 函数映射
SELF_HANDLERS = {
    "self.get_profile": handle_get_profile,
    "self.get_current_role": handle_get_current_role,
    "self.get_vision_summary": handle_get_vision_summary,
}

# 3. 每个handler必须返回dict（不能抛异常）
def handle_get_profile(**kwargs) -> dict:
    try:
        from kos.self.api import get_profile
        return get_profile()
    except Exception as e:
        return {"error": str(e), "code": "SELF_ERROR"}
```

### server.py修改点

```python
# 在run_stdio的TOOLS定义处：
from kos.self.mcp import SELF_TOOLS, SELF_HANDLERS
from kos.collab.mcp import COLLAB_TOOLS, COLLAB_HANDLERS
from kos.consensus.mcp import CONSENSUS_TOOLS, CONSENSUS_HANDLERS

# 合并TOOLS
TOOLS = {
    **EXISTING_TOOLS,      # 原有13个工具
    **SELF_TOOLS,          # self.*
    **COLLAB_TOOLS,        # collab.*
    **CONSENSUS_TOOLS,     # consensus.*
}

# 合并handlers
HANDLERS = {}
HANDLERS.update(SELF_HANDLERS)
HANDLERS.update(COLLAB_HANDLERS)
HANDLERS.update(CONSENSUS_HANDLERS)
# 原有handler也在HANDLERS中

# dispatch修改
def dispatch_tool(tool_name: str, args: dict) -> dict:
    handler = HANDLERS.get(tool_name)
    if handler:
        return handler(**args)
    return {"error": f"Unknown tool: {tool_name}", "code": "TOOL_NOT_FOUND"}
```

### 现有handler迁移

当前server.py中handler是内联函数（`tool_search_knowledge`等）。
为了统一，保持内联不动，只把新domain做成模块化。
原有工具不需要迁移——保持兼容。

---

## 3. 机制设计：TaskObject持久化与并发控制

### 存储位置

利用KOS现有的SQLite检索库（`retrievalDatabase`），新增一张表。

### 数据库Schema

```sql
-- 在 KOS 检索库中新增的表
CREATE TABLE IF NOT EXISTS kos_collab_tasks (
    task_id     TEXT PRIMARY KEY,
    data        TEXT NOT NULL,           -- 完整TaskObject JSON
    status      TEXT NOT NULL DEFAULT 'active',  -- active|completed|cancelled|blocked
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    visibility  TEXT DEFAULT 'private'    -- private|team|org|public
);

CREATE INDEX IF NOT EXISTS idx_collab_status ON kos_collab_tasks(status);
CREATE INDEX IF NOT EXISTS idx_collab_visibility ON kos_collab_tasks(visibility);
CREATE INDEX IF NOT EXISTS idx_collab_updated ON kos_collab_tasks(updated_at);
```

### CRUD操作

#### create_task

```python
def create_task(title: str, goal: str, creator_id: str, **kwargs) -> dict:
    import uuid, json
    from datetime import datetime
    
    task_id = f"task-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    
    task = {
        "id": task_id,
        "title": title,
        "goal": goal,
        "creator": {"id": creator_id, "role": kwargs.get("creator_role", "")},
        "visibility_scope": kwargs.get("visibility", "private"),
        "subtasks": kwargs.get("subtasks", []),
        "artifacts": [],
        "progress": 0,
        "status": "active",
        "timeline": [],
        "resource_usage": {"total_tokens": 0, "total_cost_usd": 0, "org_billing": kwargs.get("org", "")},
    }
    
    db_path = get_artifact_path("retrievalDatabase")
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO kos_collab_tasks (task_id, data, status, created_at, updated_at, visibility) VALUES (?,?,?,?,?,?)",
        (task_id, json.dumps(task), "active", datetime.now().isoformat(), datetime.now().isoformat(), task["visibility_scope"])
    )
    conn.commit()
    conn.close()
    return task
```

#### claim_subtask（含并发控制）

```python
def claim_subtask(task_id: str, subtask_id: str, agent_id: str) -> dict:
    """原子操作：认领子任务。使用事务+行锁防止并发冲突。"""
    from datetime import datetime
    db_path = get_artifact_path("retrievalDatabase")
    conn = sqlite3.connect(str(db_path))
    
    try:
        # BEGIN IMMEDIATE = 获取数据库写锁
        conn.execute("BEGIN IMMEDIATE")
        
        row = conn.execute(
            "SELECT data FROM kos_collab_tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        
        if not row:
            conn.rollback()
            return {"error": "Task not found", "code": "TASK_NOT_FOUND"}
        
        task = json.loads(row[0])
        
        # 检查依赖是否满足
        for st in task.get("subtasks", []):
            if st["id"] != subtask_id:
                continue
            if st["status"] != "pending":
                conn.rollback()
                return {"error": f"Subtask status is not pending: {st['status']}", "code": "SUBTASK_NOT_AVAILABLE"}
            
            # 检查依赖
            deps = st.get("depends_on", [])
            dep_statuses = {d["id"]: d["status"] for d in task["subtasks"]}
            for dep in deps:
                if dep_statuses.get(dep) != "completed":
                    conn.rollback()
                    return {"error": f"Dependency not met: {dep}", "code": "DEPENDENCY_NOT_MET"}
            
            # 认领
            st["status"] = "in_progress"
            st["assignee"] = agent_id
            st["claimed_at"] = datetime.now().isoformat()
            
            task["timeline"].append({
                "at": datetime.now().isoformat(),
                "event": "subtask.claimed",
                "by": agent_id,
                "detail": subtask_id,
            })
            
            # 写回
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE kos_collab_tasks SET data=?, updated_at=? WHERE task_id=?",
                (json.dumps(task), now, task_id)
            )
            conn.commit()
            return {"status": "claimed", "subtask": st, "task": task}
        
        conn.rollback()
        return {"error": f"Subtask not found: {subtask_id}", "code": "SUBTASK_NOT_FOUND"}
    
    except Exception as e:
        conn.rollback()
        return {"error": str(e), "code": "DB_ERROR"}
    finally:
        conn.close()
```

#### complete_subtask

```python
def complete_subtask(task_id: str, subtask_id: str, agent_id: str, output: str = "") -> dict:
    """原子操作：完成子任务。自动更新任务进度百分比。"""
    from datetime import datetime
    db_path = get_artifact_path("retrievalDatabase")
    conn = sqlite3.connect(str(db_path))
    
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT data FROM kos_collab_tasks WHERE task_id=?", (task_id,)).fetchone()
        task = json.loads(row[0])
        
        completed = 0
        total = len(task.get("subtasks", []))
        
        for st in task["subtasks"]:
            if st["id"] == subtask_id:
                if st.get("assignee") != agent_id:
                    conn.rollback()
                    return {"error": "Not the assignee", "code": "NOT_ASSIGNEE"}
                st["status"] = "completed"
                st["completed_at"] = datetime.now().isoformat()
                if output:
                    st["output"] = output
            
            if st["status"] == "completed":
                completed += 1
        
        task["progress"] = int((completed / total) * 100) if total > 0 else 0
        if task["progress"] == 100:
            task["status"] = "completed"
        
        task["timeline"].append({
            "at": datetime.now().isoformat(),
            "event": "subtask.completed",
            "by": agent_id,
            "detail": subtask_id,
        })
        
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE kos_collab_tasks SET data=?, status=?, updated_at=? WHERE task_id=?",
            (json.dumps(task), task["status"], now, task_id)
        )
        conn.commit()
        return {"status": "completed" if task["status"] == "completed" else "partial", "task": task}
    
    except Exception as e:
        conn.rollback()
        return {"error": str(e), "code": "DB_ERROR"}
    finally:
        conn.close()
```

### 任务进度自动计算

```
progress = (completed_subtasks / total_subtasks) * 100

没有subtasks的任务: progress = 0
部分subtask完成: progress = 3/5 * 100 = 60%
全部完成: progress = 100 → status自动变为"completed"
```

---

## 4. 机制设计：Consensus分级验证

### 三级共识模型

```
L1: Agent标记共识
    创建者: 任何Agent
    有效期: 30天
    用途: "Agent觉得这个验证过了"
    自动续签: 可以（无冲突时）

L2: 用户确认共识
    创建者: 用户("user:*"前缀)
    有效期: 90天
    用途: "用户说OK"
    自动续签: 不可以（需用户再次确认）

L3: 红队验证共识
    创建者: L4角色"red-teamer"
    有效期: 365天
    用途: "经过对抗测试"
    自动续签: 不可以（需重新测试）
```

### 数据库Schema

```sql
CREATE TABLE IF NOT EXISTS kos_consensus (
    consensus_id  TEXT PRIMARY KEY,
    entity_id     TEXT NOT NULL,         -- 所标记的实体ID
    level         INTEGER NOT NULL DEFAULT 1,  -- 1|2|3
    agreed_by     TEXT NOT NULL,         -- JSON array of signers
    agreement     TEXT NOT NULL,         -- 共识内容
    source_session TEXT,                 -- 来源会话ID
    confirmed_at  TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    status        TEXT DEFAULT 'active'  -- active|stale|superseded
);

CREATE INDEX IF NOT EXISTS idx_consensus_entity ON kos_consensus(entity_id);
CREATE INDEX IF NOT EXISTS idx_consensus_status ON kos_consensus(status);
CREATE INDEX IF NOT EXISTS idx_consensus_expires ON kos_consensus(expires_at);
```

### MCP工具

#### consensus.create

```python
def create_consensus(entity_id: str, agreed_by: list, agreement: str,
                     level: int = 1, source_session: str = "") -> dict:
    """创建共识记录。level根据agreed_by中的身份自动确定。"""
    import uuid
    from datetime import datetime, timedelta
    
    # 自动判断level
    has_user = any(s.startswith("user:") for s in agreed_by)
    if has_user and level < 2:
        level = 2  # 有用户参与 → L2
    
    # 有效期
    expiry_map = {1: 30, 2: 90, 3: 365}
    expires_at = (datetime.now() + timedelta(days=expiry_map.get(level, 30))).isoformat()
    
    consensus = {
        "consensus_id": f"csn-{uuid.uuid4().hex[:12]}",
        "entity_id": entity_id,
        "level": level,
        "agreed_by": agreed_by,
        "agreement": agreement,
        "source_session": source_session,
        "confirmed_at": datetime.now().isoformat(),
        "expires_at": expires_at,
        "status": "active",
    }
    
    # 持久化到 kos_consensus 表
    ...
    return consensus
```

#### consensus.get

```python
def get_consensus(entity_id: str) -> dict:
    """获取某个实体的活跃共识。可能有多条，按level降序返回。"""
    rows = conn.execute(
        "SELECT * FROM kos_consensus WHERE entity_id=? AND status='active' ORDER BY level DESC",
        (entity_id,)
    ).fetchall()
    return {"consensus": [dict(r) for r in rows], "count": len(rows)}
```

#### consensus.check_expired (供Cron消费)

```python
def check_expired() -> list:
    """检查所有过期共识。每天由保鲜Cron调用。"""
    now = datetime.now().isoformat()
    rows = conn.execute(
        "SELECT * FROM kos_consensus WHERE expires_at < ? AND status='active'",
        (now,)
    ).fetchall()
    for r in rows:
        # L1自动续签（如果没有冲突）
        if r["level"] == 1:
            renew_consensus(r["consensus_id"])
        else:
            # L2/L3标记为stale，等用户确认
            conn.execute(
                "UPDATE kos_consensus SET status='stale' WHERE consensus_id=?",
                (r["consensus_id"],)
            )
    return [dict(r) for r in rows]
```

---

## 5. 机制设计：Self Context自动注入

### 实现方式（并非"每个Agent启动时硬加载"）

我们用一个更务实的方式：**在Hermes的交互prompt中，在每天第一次交互时注入L4上下文。** 不是每个请求都加——那样浪费token。

### Hermes config扩展

```yaml
# ~/.hermes/config.yaml
context_preload:
  schedule: "daily_first"  # daily_first | every_session | manual
  sources:
    - source: "mcp:self.get_vision_summary"
      inject_at: "system_prompt"  # system_prompt | user_message | tool_result
    
    - source: "mcp:self.get_current_role"
      format: "## 当前角色\n{result}"
    
    - source: "mcp:self.get_profile"
      fields: ["person", "roles"]  # 只取部分字段
      format: "## 用户画像\n{result}"
```

### 注入时机

```
Hermes启动/每天第一次消息
  → 检查是否有 context_preload 配置
  → 调用 sources 中的 MCP 工具
  → 将结果格式化为用户消息的一部分（不是system message）
  → 拼入prompt顶部

后续消息不重复加载（除非schedule=every_session）
```

### 为什么不用system message？

- system message在每个请求都发送，浪费token
- L4内容变化频率低（角色切换最多一天几次）
- MCP工具调用可以按需触发
- Claude Desktop和Codex不支持自定义system message注入

### 对其他Agent

Claude Desktop和Codex不直接支持preload。
解决方案——通过共享工作平面间接获取：

```
Claude Desktop用户: "帮我设计一个监控面板UI"
  → Claude Desktop创建TaskObject → creator.role = "personal-dev"
  → 通过collab.get_task感知：哦，这是老王的个人开发任务
  → Claude Desktop可以调用 self.get_profile 自行查询（如果它愿意）
```

即：不强求所有Agent都自动注入L4，但任何Agent都可以**按需查询**。

---

## 6. 机制设计：Agora集成契约

### 现状

KOS MCP server已经是一个stdio进程：
- 启动方式: `python3 -m kos.mcp.server`
- Agora注册: `agora service register --name kos --command "python3" --args "-m kos.mcp.server"`
- 路由: `kos.*` 前缀映射到该服务

### 新增工具的影响

**不需要启动新进程。** 新工具只是追加到现有server.py中。

Agora在服务重启时自动发现新增的工具（通过list_tools()调用）。

### 路由规则

```
工具名                    →  路由至
search_knowledge         →  kos MCP server (已有)
self.get_profile         →  kos MCP server (新增, 通过"self."前缀路由)
self.get_current_role    →  kos MCP server
collab.create_task       →  kos MCP server (通过"collab."前缀路由)
consensus.create         →  kos MCP server (通过"consensus."前缀路由)
```

Agora的路由配置不需要改——因为已经在同一个process里。

### 启动顺序

```
1. KOS MCP server 启动
2. server.py 加载所有domain的mcp模块
3. server.py 向Agora发送 list_tools 响应（包含所有新工具）
4. Agora 更新路由表
5. 客户端可以调用新工具了
```

无需额外配置步骤。

### 注册命令参考

```bash
# 如果未来需要单独注册某个domain（例如self作为一个独立服务）
agora service register \
  --name "kos-self" \
  --command "python3" \
  --args "-c 'from kos.self.mcp import run_standalone; run_standalone()'"

agora add-route \
  --tool "self.*" \
  --service "kos-self"
```

但当前不推荐这样做——保持单进程更简单。

---

## 7. 状态机与流程图

### 7.1 TaskObject 生命周期

```
                     ┌──────────────┐
                     │   CREATED    │  create_task
                     └──────┬───────┘
                            │ 有subtasks?
                   ┌────────┴────────┐
                   ▼                 ▼
            ┌────────────┐    ┌────────────┐
            │ HAS_TASKS   │    │ EMPTY      │
            └──────┬─────┘    │ (无subtask) │
                   │          └──────┬──────┘
          ┌────────┴────────┐        │
          ▼                 ▼        ▼
   ┌────────────┐   ┌────────────┐  ┌──────────────┐
   │ IN_PROGRESS│   │  BLOCKED   │  │  ACTIVE      │
   │ (至少1个   │   │ (有依赖未   │  │ (直接完成)   │
   │ 进行中)    │   │  满足的)    │  └──────┬───────┘
   └──────┬─────┘   └────────────┘         │
          │ 全部完成              全部完成   │
          └──────────┬─────────────────────┘
                     ▼
              ┌──────────────┐
              │  COMPLETED   │
              └──────────────┘
       还可以从任何状态↓到 CANCELLED
```

### 7.2 子任务状态机

```
          claim_subtask
  ┌────┐ ──────────────→ ┌──────┐
  │PEND│                  │INFLG│  ← in_progress
  └────┘                  └──┬───┘
     ↑                       │ complete_subtask
     │ release_subtask       ▼
     └────────────────────┌────┐
      (取消认领)          │DONE│
                          └────┘
  ┌────┐
  │FAIL│ ← fail_subtask (从任何状态)
  └────┘
```

### 7.3 Consensus 生命周期

```
        create_consensus
        ┌──────────────┐
        │   ACTIVE     │
        └──────┬───────┘
               │
       ┌───────┴────────┐
       ▼                ▼
  ┌─────────┐     ┌────────────┐
  │  STALE  │     │ SUPERSEDED │
  │ (过期)  │     │ (被新共识) │
  └────┬────┘     └────────────┘
       │
       │ renew_consensus
       ▼
  ┌──────────────┐
  │   ACTIVE     │ (续签)
  └──────────────┘
```

### 7.4 完整交互序列：多Agent协作场景

```
User(老王)        Hermes(A)        ClaudeDesktop(B)    KOS MCP Server
   │                 │                  │                   │
   │ 1. "设计监控面板"│                  │                   │
   │────────────────→│                  │                   │
   │                 │ 2. create_task()  │                   │
   │                 │──────────────────│──────────────────→│
   │                 │                  │                   │ 存储task
   │                 │←─────────────────│───────────────────│
   │                 │                  │                   │
   │                 │ 3. event: task.created (EventBus)    │
   │                 │──────────────────│──────────────────→│
   │                 │                  │                   │
   │                 │ 4. claim_subtask │                   │
   │                 │   ("research")   │                   │
   │                 │──────────────────│──────────────────→│
   │                 │←──claimed───────│───────────────────│
   │                 │                  │                   │
   │                 │ 5. 收到事件, 看到有UI设计子任务       │
   │                 │                  │                   │
   │                 │       6. claim_subtask("ui-design")  │
   │                 │←────────────────│───────────────────│
   │                 │                  │←──claimed────────│
   │                 │                  │                   │
   │ 7. "调研完了"   │                  │                   │
   │←───────────────│                  │                   │
   │                 │ 8. complete_subtask("research")      │
   │                 │──────────────────│──────────────────→│
   │                 │                  │                   │
   │ 9. event: research done           │                   │
   │                 │   (EventBus)     │                   │
   │                 │──────────────────│──────────────────→│
   │                 │                  │                   │
   │                 │       10. 感知research完成           │
   │                 │       开始UI设计...                  │
```

---

## 8. 错误处理矩阵

| 错误场景 | 错误码 | 处理方式 | 调用方重试策略 |
|---------|--------|---------|--------------|
| Task不存在 | TASK_NOT_FOUND | 返回error | 检查ID后重试 |
| Subtask状态不可认领 | SUBTASK_NOT_AVAILABLE | 返回error + 当前状态 | 轮询等待或选其他subtask |
| 依赖未满足 | DEPENDENCY_NOT_MET | 返回error + 未满足的依赖ID | 等待依赖完成 |
| 不是认领者试图完成 | NOT_ASSIGNEE | 返回error | 检查assignee |
| 数据库错误 | DB_ERROR | 回滚事务 + 返回error | 指数退避重试 |
| 并发冲突（行锁超时） | DB_LOCK_TIMEOUT | SQLite自动处理，返回error | 100ms后重试 |
| Consensus已过期 | CONSENSUS_EXPIRED | 返回error + 过期时间 | 调用create新的 |
| MCP Server未就绪 | SERVER_NOT_READY | 返回error | 等待后重试 |
| Self Profile为空 | SELF_NOT_INITIALIZED | 返回空profile + 建议初始化 | 触发初始化流程 |
| 创建重复Task | TASK_DUPLICATE | 返回已存在的task | 复用已有task |

### 重试策略

```python
# 在Agent端（Hermes或任何MCP Client）调用时的重试封装

def mcp_call_with_retry(tool_name: str, args: dict, max_retries: int = 3):
    for attempt in range(max_retries):
        result = mcp_call(tool_name, args)
        if "error" not in result:
            return result
        if result.get("code") in ("DB_LOCK_TIMEOUT", "SERVER_NOT_READY"):
            time.sleep(0.1 * (2 ** attempt))  # 指数退避
            continue
        # 其他错误不重试
        break
    return result
```

---

## 9. 数据库Schema总表

### KOS检索库（retrievalDatabase）新增表

| 表名 | 用途 | Key | 说明 |
|------|------|-----|------|
| kos_collab_tasks | TaskObject存储 | task_id (PK) | 完整JSON存data字段 |
| kos_consensus | 共识记录 | consensus_id (PK) | 三级共识模型 |

### KOS本地文件（~/.kos/self/profile.json）

| 路径 | 内容 | 说明 |
|------|------|------|
| ~/.kos/self/profile.json | 完整L4自我画像 | JSON文件，非数据库 |

### KOS本地文件（~/.kos/accounting/usage.db）

| 表名 | 用途 | 说明 |
|------|------|------|
| resource_usage | Resource Accounting日志 | SQLite插入为主，很少查询 |

---

## 总结

| 缺口 | 机制 | 关键设计 |
|------|------|---------|
| G1 KOS MCP组织 | 单进程+模块化拆分 | kos/self/mcp.py等模块按domain隔离 |
| G2 TaskObject存储 | KOS SQLite新增表 | 行锁解决并发冲突 |
| G3 Consensus验证 | 三级模型(L1/L2/L3) | 自动续签L1，L2/L3等用户确认 |
| G4 Self Context注入 | 每日首次注入prompt | 通过Hermes config配置，非硬编码 |
| G5 Agora集成 | 扩展现有进程不改路由 | 追加TOOLS列表即可 |
| G6 错误边界 | 错误码+重试策略 | 指数退避+不重试不可恢复错误 |

**结论**: 6个缺口全部有明确机制设计，可进入代码阶段。
