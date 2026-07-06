# MCPTOOL M1 实例 Adder Guide (Round 5b)

> **配套 ADR-0147** (Round 5b, 2026-07-06)
> **状态**: M4 Health 100/100 时代, 单工具 MCPTOOL 节点的增量添加守门文档
> **目的**: 让开发者 5 分钟内正确添加 1 个 new single-tool MCPTOOL yaml

---

## 0. TL;DR

本文档描述如何**正确**新加 1 个 single-tool MCPTOOL 节点 (与 collection
MCPTOOL 区分,见 ADR-0145)。Adder pipeline:

1. 写 yaml
2. 复核对齐 3 个 schema (m3.yaml MCPTool / m2 type MCPTool / m1 yaml)
3. 跑 `bin/mcp-tool-data-complete.py` 守护
4. 跑 `bin/mof-bootstrap.py all` + `bin/m4-health-score.py` 验证
5. commit + push

**no-op 守门**: `bin/mcp-tool-data-complete.py` 自动跳过 collection yaml,
不误报 single-tool 不合规情况。

---

## 1. 何时创建 single-tool MCPTOOL yaml

### 1.1 单工具 vs 集合

| 模式 | 判定 | yaml 示例 | 处理 |
|------|------|----------|------|
| **Single-tool** | 1 yaml 表示 1 个 MCP tool endpoint | MCPTOOL-COCKPIT-cards_check.yaml | **应当** + mof-validate 校验 |
| **Collection** | 1 yaml 表示 1 个 MCP server (含 N 个 tools) | MCPTOOL-C2G.yaml + `tool_count: 7` | **跳过校验** (ADR-0145) |

### 1.2 判定标准

文件**有**以下任一特征 → **collection** (skip):
- `tool_count: N` 字段 (N > 1)
- `tools: [name1, name2, ...]` 列表字段

否则 → **single-tool** (must pass validation):

---

## 2. Single-tool MCPTOOL yaml 形状

### 2.1 标准 13 字段

```yaml
id: MCPTOOL-{SERVER}-{tool_name}        # PascalCase ID
type: MCPTool                           # m2 type enum
m3_parent: StructuralElement.Component  # m3 anchor (fixed)
name: {短描述}                          # e.g. "cards_check"
description: |
  {工具描述, 一个自然段}
tool_name: {tool_name}                  # 端点名 (e.g. cards_check)
server: {server}                        # MCP server 名 (e.g. cockpit)
project: {server}                        # 项目名 (e.g. cockpit)
component: COMP-WS-{server}             # 组件 ID
transport: stdio                        # stdio / sse / http
status: active                          # active / deprecated / archived
created: '2026-07-06T08:00:00'           # ISO-8601 datetime
```

### 2.2 字段语义

| 字段 | 含义 | 派生规则 |
|------|------|----------|
| `id` | MCPTOOL 全局唯一 ID | PascalCase: `MCPTOOL-{SERVER_UPPER}-{tool_name}` |
| `type: MCPTool` | 强制 | m2 schema 固定 |
| `m3_parent` | m3 anchor, "StructuralElement.Component" 固定 | 不要改 |
| `name` | 短人类可读名 | 推荐与 `tool_name` 同 |
| `description` | 1 段描述 | min 20 字 |
| `tool_name` | MCP 工具端点名 | MCP protocol method_name |
| `server` | MCP server 名 | protocol server name |
| `project` | 项目仓名 (等同 `server`) | |
| `component` | COMP-WS-{server} 引用 | |
| `transport` | stdio / sse / http | 按实际 |
| `status` | active 默认 | |
| `created` | ISO-8601 datetime | 工具首次入仓时刻 |

### 2.3 可选字段

- `model_driven_refs: [{source_file, ...}]` — 反向追溯
- `relations: [{provided_by: ...}]` — M3 relation
- `state_history: [{state, timestamp, reason}]` — lifecycle 审计

---

## 3. 模板生成 (copilot 用)

```bash
TOOL=my_tool
SERVER=cockpit
PROJECT_DIR=projects/$SERVER

cat > projects/ecos/src/ecos/ssot/mof/m1/mcptool/MCPTOOL-${SERVER^^}-$TOOL.yaml <<YAML
id: MCPTOOL-${SERVER^^}-$TOOL
type: MCPTool
m3_parent: StructuralElement.Component
name: $TOOL
description: |
  Brief description of what $TOOL does (≥ 20 chars).
  Mention use case and operator-facing expectation.
tool_name: $TOOL
server: $SERVER
project: $SERVER
component: COMP-WS-$SERVER
transport: stdio
status: active
created: '$(date -u +%Y-%m-%dT%H:%M:%S)'

model_driven_refs:
  source_file: $PROJECT_DIR/src/$SERVER/mcp_server.py
YAML
```

---

## 4. 自检步骤 (5 分钟内)

```bash
# 1. 验证 yaml 符合 M3/M2/M1 三层 schema
uv run --with pyyaml python bin/mof-bootstrap.py all
# 期望: 5-check strict 全 0 err

# 2. 验证 tool_name + server 字段完整性
uv run --with pyyaml python bin/mcp-tool-data-complete.py
# 期望: "✅ 所有 MCPTOOL 节点 tool_name 和 server 均有值"
#       或 "{new-tool}: tool_name: ..., server: ..."
```

如果 mcp-tool-data-complete **没**列出 new-tool, 它**跳过了**:
- 检查 new-tool yaml 是否有 `tool_count: 1` 或 `tools: [...]` 字段误带
- 如果是, 改为真正的 single-tool yaml (删除这两个字段)

如果 mof-bootstrap check_2 **报 new-tool 缺字段**:
- 检查 m3_parent 写错 (应为 "StructuralElement.Component")
- 检查 type 不是 "MCPTool"

---

## 5. 提交格式

```bash
# 1. 加文件
git add projects/ecos/src/ecos/ssot/mof/m1/mcptool/MCPTOOL-${SERVER^^}-$TOOL.yaml

# 2. 子模块内 commit
cd projects/ecos
git commit -m "feat(mcptool): add {server}::{tool_name} ({short desc})"
cd ../..

# 3. 根仓 bump 子模块指针
git add projects/ecos
git commit -m "chore(m4): bump projects/ecos — add MCPTOOL-{server}::{tool}"

# 4. 跑全套验证
uv run --with pyyaml python tests/integration/m4_metamodel/run_all.py
uv run --with pyyaml python bin/m4-health-score.py --emit

# 5. push (经过 PR review)
git push origin work/{branch}
```

**不要**: 在 main 上直接 add + push (需要 PR review)。

---

## 6. 常见错误

### 6.1 误把 single-tool 写成 collection

**症状**: `bin/mof-bootstrap.py check_2` 报 `tool_name 缺` 报错,
但 yaml 看起来有 `tool_name: xxx`。

**根因**: yaml 含 `tool_count: 1` 或 `tools: [xxx]` 误带,触发 ADR-0145
skip 逻辑,**所有校验都跳过**, yaml 看似"valid" 但实际是 collection 模式。

**修法**:
- 删除 `tool_count: 1` (single-tool 不需要)
- 删除 `tools: [xxx]` 列表 (single-tool 不需要)

### 6.2 server 字段错

**症状**: mcp-tool-data-complete 报 `server: 'old_value'` 应改为
`server: 'cockpit'`。

**根因**: yaml 复制时漏改 server。

**修法**: 改 yaml `server:` 字段为正确 MCP server 名。

### 6.3 m3_parent 写成 ComponentClassName

**症状**: `bin/mof-bootstrap.py check_3` 报
`m3_parent 'Component.XYZ' 中 'Component' 不在 m3.yaml Element 集`。

**根因**: 误以为 m3_parent 完整路径。

**修法**: m3_parent 写 `StructuralElement.Component` (m3.yaml root 类目)。

---

## 7. 关联

- ADR-0145 (MCPTOOL 集合占位识别) — 本指南基础
- ADR-0140 (M4 Health Score) — adder 后的健康度验证
- projects/ecos/src/ecos/ssot/mof/m2/mcptool.yaml (m2 schema)
- projects/ecos/src/ecos/ssot/mof/m3.yaml::MCPTool (m3 schema)
- [docs/M4-DECISIONS-INDEX.md](./M4-DECISIONS-INDEX.md) (R0..R5 速查)
