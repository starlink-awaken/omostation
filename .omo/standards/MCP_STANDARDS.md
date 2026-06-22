---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
---

# MCP 工具开发规范 (v1.0)

> 状态: merged
> 已合并至 `.omo/standards/mcp-tool-and-transport-standard.md`
> 本文件保留为历史细节来源，不再作为新的 workflow 引用入口。

> 本文档定义所有使用 FastMCP 框架的项目中，`@mcp.tool()` 函数的**统一返回契约**和**合规标准**。
>
> **适用范围**: agora, codeanalyze, iris, kronos, minerva, sophia, SharedBrain/D_Gateway 及其他所有 FastMCP server。
>
> **关联文件**: [tools_template.py 参考模板](#参考模板)

---

## 一、核心契约

### 1.1 返回类型

所有 `@mcp.tool()` 函数必须返回 `dict`，由 FastMCP 框架自动序列化为 JSON-RPC 响应。

```
✅ return dict         → fastmcp 自动序列化
❌ return str          → json.dumps 手动序列化（已废弃）
```

### 1.2 format_version 字段

每个工具函数的返回值 **必须** 包含 `"format_version"` 字段。

**命名规范**:

```
"{project_name}-v{major}"
```

| 项目 | FORMAT_VERSION |
|------|---------------|
| agora | `agora-v1` |
| codeanalyze | `codeanalyze-v1` |
| iris | `iris-v1` |
| kronos | `kronos-v1` |
| minerva | `minerva-v1` |
| sophia | `sophia-v1` |
| SharedBrain D_Gateway | `dgateway-v1` |

### 1.3 辅助函数模式

推荐使用 `_ok()` / `_error()` 辅助函数统一返回格式：

```python
def _ok(data: dict) -> dict:
    return {"status": "ok", **data}

def _error(msg: str) -> dict:
    return {"status": "error", "error": msg, "format_version": FORMAT_VERSION}
```

**注意**: `_ok()` 的 `data` 参数中**不内建** `format_version`，要求每个工具函数**显式传递**（原因见 [AST 静态检测](#三ast-静态检测规则)）。

---

## 二、四种返回模式（按推荐度排序）

| 模式 | 示例 | 合规 | 推荐度 |
|------|------|------|--------|
| A: `_ok()` 辅助函数 | `return _ok({"format_version": FV, ...})` | ✅ | ★★★★★ |
| B: 直接 return dict | `return {"format_version": FV, ...}` | ✅ | ★★★★☆ |
| C: 注入式后 return | `r = {...}; r["format_version"] = FV; return r` | ✅ | ★★★☆☆ |
| D: ~~json.dumps 序列化~~ | `return json.dumps({...})` | ❌ 废弃 | — |

> **模式 A 是推荐标准**，原因：
> 1. 集中管理成功/错误路径格式
> 2. 错误路径自动含 format_version
> 3. 对 AST 静态检测友好（函数体内有字面量）

---

## 三、AST 静态检测规则

SOP 脚本 `scripts/sop_check_format_version.py` 通过 Python `ast` 模块执行静态检查。

### 3.1 什么算通过

工具函数体中找到 `"format_version"` 字符串字面量（在任何表达式中）：

```python
# ✅ 通过 — dict key
return {"format_version": FORMAT_VERSION, ...}

# ✅ 通过 — _ok() 参数
return _ok({"format_version": FORMAT_VERSION, ...})

# ✅ 通过 — Subscript 赋值
result["format_version"] = FORMAT_VERSION

# ✅ 通过 — json.dumps 参数（兼容旧代码）
return json.dumps({"format_version": FORMAT_VERSION, ...})
```

### 3.2 什么算违规

工具函数体内**没有** `"format_version"` 字面量，且也没有通过 `_ok()` / `_error()` 辅助函数委托：

```python
# ❌ 违规 — 返回体中没有 format_version 字面量
return _ok({"data": items})       # _ok() 内建过，但后改为不内建

# ❌ 违规 — 直接返回
return {"status": "ok", "data": items}
```

### 3.3 辅助函数递归检测

当工具函数通过 `return _ok(...)` 返回时，SOP 会额外检查 `_ok` 的定义体。如果 `_ok` 定义体中包含 `format_version`，则视为通过（但会标记为"通过辅助函数委托"）。

> **最佳实践**: 不要依赖辅助函数内建 format_version，而是在每个工具函数中显式传递。这样 SOP 检测更确定，且重构时不会意外丢失。

---

## 四、错误处理规范

### 4.1 try/except 包装

所有可能抛出异常的工具函数应使用 try/except 包装：

```python
@mcp.tool()
def my_tool(...) -> dict:
    try:
        # 核心逻辑
        return _ok({"format_version": FORMAT_VERSION, ...})
    except Exception as e:
        return _error(str(e))
```

### 4.2 错误格式

```python
{"status": "error", "error": "<描述信息>", "format_version": FORMAT_VERSION}
```

### 4.3 成功格式

```python
{"status": "ok", "format_version": FORMAT_VERSION, ...业务字段}
```

> **任何状态码不统一**: 各项目必须统一使用 `"status": "ok"` / `"status": "error"`，不使用其他自定义状态值（如 "done", "warning", "not_initialized" 等）。

### 4.4 返回值顶层键冲突规则

`_ok()` 的展开语义 `{"status": "ok", **data}` 意味着 `data` 中的顶层键会覆盖已有字段。必须遵守：

```python
# ✅ 正确 — 使用 action 字段保留原始语义
return _ok({"format_version": FV, "action": "not_initialized", ...})

# ❌ 违规 — "warning" 与 "ok" 语义冲突
return _ok({"format_version": FV, "warning": "No proxy found"})

# ❌ 违规 — "action" 字段中不应出现 status 级别关键词
return _ok({"format_version": FV, "action": "ok", ...})   # action != status
```

**规则**:
1. `_ok()` 的 `data` 中**不应包含** `"error"`, `"warning"`, `"fail"` 等与 `status: "ok"` 语义冲突的顶层键
2. 需要表达额外语义时使用 `"action"` 字段（见 §4.5）
3. 任何情况下不应在 `_ok()` 中覆盖 `"status"` 字段

### 4.5 Action 字段规范

当工具函数需要表达除成功/失败之外的额外语义时，使用 `action` 字段：

| 情形 | 示例 |
|------|------|
| 资源已注册 | `_ok({"format_version": FV, "action": "registered"})` |
| 任务已开始 | `_ok({"format_version": FV, "action": "started"})` |
| 查询无结果 | `_ok({"format_version": FV, "action": "no_results", "query": q})` |
| 资源不可用 | `_ok({"format_version": FV, "action": "unavailable"})` |

**命名规则**:
- 使用**过去时**动词（`registered`, `started`, `completed`）
- 不使用 `ok` / `error` 作为 action 值（那是 status 的职责）
- 不加前缀（如 `action: "task_completed"` 而不是 `action: "completed"`）

### 4.6 返回值安全规范

```python
# ✅ 安全 — 返回标准化结构化数据
return _ok({"format_version": FV, "summary": result.summary})

# ❌ 不安全 — 直接透传用户输入或异常详情
return _ok({"format_version": FV, "raw": user_input})
return _error(f"Internal error: {traceback.format_exc()}")
```

**规则**:
1. 异常消息如果不含敏感信息可透传，但应使用 FastMCP 的 `mask_error_details=True`
2. 不要将栈追踪 (`traceback.format_exc()`) 直接传入 `_error()`
3. 用户输入不应不加验证地回传

---

## 五、返回值决策树

选择 `_ok()` 的数据组织形式：

```
工具函数需要返回？
├─ 明确的操作结果（增删改查）
│   ├─ 表达额外语义？    → _ok({"format_version": FV, "action": "...", ...})
│   └─ 仅返回数据        → _ok({"format_version": FV, "results": [...], "total": N})
├─ 查询无结果 / 空状态
│   └─ 是否属于错误？
│       ├─ 是（参数无效） → _error("...")
│       └─ 否（合法查询但无匹配） → _ok({"format_version": FV, "action": "no_results"})
└─ 需要标记执行动作
    └─ action 字段优先 → _ok({"format_version": FV, "action": "scheduled", ...})
```

---

## 六、参考模板

每个项目应包含自己的 `tools_template.py`，基于 [codeanalyze 模板](../../projects/agentmesh/packages/gateway/src/hermes/routes.ts) 定制：

```
codeanalyze/src/codeanalyze/tools_template.py   # 通用参考
iris/src/iris/tools_template.py                  # iris 定制版
SharedBrain/organs/D_Gateway/mcp_server/tools_template.py  # D_Gateway 定制版
```

模板包含：
- FastMCP 实例初始化
- FORMAT_VERSION 常量
- `_ok()` / `_error()` 辅助函数
- 同步/异步工具示例
- 边界情况示例
- 入口点

---

## 七、CI 集成

### 7.1 SOP 脚本的 CI 模式

SOP 脚本支持 `--json` 标志，输出 JSON 格式结果供 CI 解析：

```bash
python scripts/sop_check_format_version.py --json
```

### 7.2 文件列表动态发现

SOP 脚本支持从 `gateway/scripts/convergence.yaml` 自动发现 MCP 文件列表：

```yaml
auto_discover:
  scan_pyproject_scripts: true
  scan_mcp_files: true
  prefer_pyproject: true
```

(待收敛配置文件统一后，SOP 将从 convergence.yaml 动态获取文件列表，消除硬编码。)

---

## 八、架构原则

1. **架构一致保持**: 所有项目使用统一的返回模式（dict + _ok/_error）
2. **MCP > REST > CLI subprocess > pip import**: 跨项目通信优先级
3. **每个项目一个明确定义的边界**: 不做功能重复
4. **所有项目必须暴露清晰的外部接口**: CLI / MCP / API 之一
