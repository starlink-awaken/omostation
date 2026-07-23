# Codebase Memory — Agent 知识图谱用法

> **状态**: active  
> **工具**: MCP server `codebase-memory-mcp` + skill `codebase-memory`  
> **本地产物**: `.codebase-memory/`（**gitignore**，本机生成，不进仓）  
> **用途**: 用结构图回答「谁调用谁 / 影响面 / 死代码」，替代大范围 grep。

---

## 1. 何时用

| 问题 | 优先工具 |
|------|----------|
| 谁调用了 X？ | `trace_path(direction=inbound)` |
| X 调用了谁？ | `trace_path(direction=outbound)` |
| 按名字找函数/类 | `search_graph(name_pattern=…)` 或 `query=…` |
| 全文 + 结构排序 | `search_code(pattern=…)` |
| 本次 diff 影响谁 | `detect_changes(project=…, base_branch=main)` |
| 包/入口/热点总览 | `get_architecture(project=…)` |
| 跨服务 HTTP 边 | `query_graph` + Cypher（`HTTP_CALLS`） |

**不要**用它替代：治理 SSOT 读数、BOS 注册表、测试执行。那些仍走 `AGENTS.md` / `omo` / `bos-services.yaml`。

---

## 2. 本工作区项目 ID

索引后用 **project 名**（不是路径）调工具。先 `list_projects` 核对。

| 范围 | 典型 project 名 | 说明 |
|------|-----------------|------|
| **全仓 monorepo** | `Users-xiamingxing-Workspace` | 根路径 `Workspace/`，moderate 索引 |
| 单仓 cockpit | `Users-xiamingxing-Workspace-projects-cockpit` | 可选；全仓已含 cockpit 源码 |
| 单仓 cockpit-ui | `Users-xiamingxing-Workspace-projects-cockpit-ui` | UI 独立索引 |

> 名称由本机路径派生，不同机器前缀可能不同。**以 `list_projects` 返回为准**，勿在文档硬编码节点/边数量。

---

## 3. 冷启动 / 重建索引

```text
1. list_projects          → 是否已有 Users-xiamingxing-Workspace
2. 若无 / 过旧:
   index_repository(
     repo_path="/Users/xiamingxing/Workspace",
     mode="moderate",      # 全仓推荐；full 更重
     persistence=true      # 写 .codebase-memory/graph.db.zst（本地）
   )
3. index_status(project=…) → status=ready
4. get_architecture / search_graph / trace_path …
```

**mode 选择**

| mode | 用途 |
|------|------|
| `moderate` | **全仓默认**：过滤噪声目录 + 相似/语义边 |
| `fast` | 只要调用结构、尽快 |
| `full` | 尽量全文件（慢、更大） |

**moderate 常排除**：`.git`、`.venv`、`bin/`、`docs/`、`scripts/`、部分 runtime 缓存等。若目标在这些目录，对子路径单独 `index_repository` 或改用 `full`/单项目索引。

**更新时机**（建议，非闸门）

- 大合并进 main 后
- 跨多子模块重构前
- `detect_changes` 结果明显与现状不符时

---

## 4. Agent 操作约定

1. **先 `list_projects`**，确认 project 名与 `status=ready`。  
2. **`trace_path` 前先 `search_graph`** 拿到准确 `name` / `qualified_name`。  
3. **读源码**：`get_code_snippet(qualified_name=…, project=…)`（先 search 再读）。  
4. **影响分析**：改代码前可 `detect_changes`；合 PR 后必要时重索引。  
5. **与 graphify 区分**：`graphify-out/` 是另一套本地图产物（已 gitignore）；codebase-memory 走 MCP，产物在 `.codebase-memory/`。

### Skill / MCP

- Skill：`codebase-memory`（`~/.agents/skills/codebase-memory/SKILL.md`）
- MCP：`codebase-memory-mcp`（工具名带 server 前缀，如 `codebase-memory-mcp__search_graph`）

---

## 5. 产物与 Git 策略

| 路径 | 策略 | 原因 |
|------|------|------|
| `.codebase-memory/graph.db.zst` | **gitignore** | 压缩后仍数十 MB 级，可本机重算 |
| `.codebase-memory/artifact.json` | **gitignore**（随目录） | 含 commit/节点数快照，易漂移 |
| `.codebase-memory/.gitattributes` | **gitignore**（随目录） | 仅服务本地 merge 策略 |

**不进仓**：避免 PR 体积膨胀、避免多机 `nodes/edges` 数字 SSOT 漂移。  
**团队共享**：各自 `index_repository`；可选把 zst 放到内网制品库（非本仓）。

---

## 6. 快速自检

```text
list_projects
# 期望含 Workspace 全仓 project 且 nodes/edges > 0

search_graph(project=<workspace>, query="cmd_import", limit=5)
trace_path(project=<workspace>, function_name="cmd_import", direction="both", depth=2)
```

失败时：确认 MCP 已连接 → 重跑 `index_repository` → 再 `index_status`。

---

## 7. 相关入口

| 文档 | 角色 |
|------|------|
| [`AGENTS.md`](../../AGENTS.md) | 操作总则（含本能力指针） |
| [`CLAUDE.md`](../../CLAUDE.md) | 会话启动路由 |
| [`docs/SYSTEM-INDEX.md`](../SYSTEM-INDEX.md) | 导航枢纽 |
| Skill `codebase-memory` | 工具决策矩阵与 Cypher 示例 |
