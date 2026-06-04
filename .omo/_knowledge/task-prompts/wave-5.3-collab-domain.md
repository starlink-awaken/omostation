# Task Prompt: Wave 5.3 — L3 Collab Domain

> 类型: P9 → P8 Task Prompt | 状态: backlog | 预估: 180min
> Phase: 5 → 5.3 | 负责人: prometheus | 日期: Day 4
> 前置: Wave 5.2 (L4 Self Domain) 已完成

## 一、目标

实现共享工作平面(TaskObject)：KOS SQLite中创建表、CRUD操作、并发控制(行锁)、6个MCP工具。

## 二、文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `kos/collab/__init__.py` | 新建 | 模块声明 |
| `kos/collab/api.py` | 新建 | CRUD + claim_subtask(行锁) + complete_subtask(进度计算) |
| `kos/collab/mcp.py` | 新建 | 6个MCP工具: create_task, get_task, list_tasks, update_task, claim_subtask, add_artifact |
| `kos/mcp/server.py` | 修改 | import + dispatch注册collab.*路由 |

## 三、验收标准

```
☐ python3 -c "from kos.collab.api import create_task; t=create_task('测试','验证','user:老王'); assert t['status']=='active'"
☐ 并发test: 两个Agent同时claim同一个subtask → 只有一个成功
☐ 依赖test: claim依赖未满足的subtask → 返回DEPENDENCY_NOT_MET
☐ KOS MCP Server list_tools 显示 collab.* 6个工具
```

## 四、关键实现

见09-架构Review与机制设计.md第3节完整代码。核心逻辑:
- `create_task()`: 生成task-id, 插入kos_collab_tasks表
- `claim_subtask()`: BEGIN IMMEDIATE行锁 → 检查依赖 → 更新状态
- `complete_subtask()`: BEGIN IMMEDIATE → 验证assignee → 计算progress% → 满100自动complete
- 所有handler返回统一格式: `{"status": "...", "task": {...}}` 或 `{"error": "...", "code": "..."}`

## 五、→ 下一个Wave

完成后触发 **Wave 5.4.A (Consensus Domain)**。
