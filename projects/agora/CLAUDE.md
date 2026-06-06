# CLAUDE.md — Agora I0 Service Mesh

> AI Agent 操作指南。修改此项目前请先阅读。

## 核心概念

Agora 是 eCOS v5 架构中的 **I0 织层** — 所有跨服务通信的 MCP 动态反向代理枢纽。

- **Hub-Spoke**: 服务只认识 Agora，Agora 认识所有服务
- **工具代理**: 所有下游 MCP 工具通过 Agora 透明代理
- **智能路由**: SmartRouter 支持 direct/recommend/auto 三种策略
- **联邦路由**: FederationRouter 跨节点路由

## 关键模式

### 返回格式
```python
def _ok(data: dict) -> dict:    # 成功: {"ok": True, ...data}
def _error(msg: str) -> dict:   # 失败: {"ok": False, "error": msg}
```

### MCP 工具注册
工具在 `server/mcp.py` 中用 `@mcp.tool()` 装饰器注册，无需额外配置。

### 导入约定
- 包内: `from agora.xxx import ...`
- 禁止裸 `except:` (全部指定异常类型)
- 使用 `hmac.compare_digest()` 防时序攻击

## 文件职责

| 文件 | 职责 | 风险 |
|------|------|------|
| `server/mcp.py` | MCP 入口 + 工具注册 + 代理管理 | God Module — 勿再添加代码 |
| `mcp_proxy/client.py` | Stdio/HTTP MCP 客户端 | 稳定 |
| `core/router.py` | 服务路由决策 | 稳定 |
| `federation/federation_router.py` | 跨节点联邦路由 | SSRF 已修复 |
| `adapters/node_adapter.py` | 外部节点适配器 | SSRF 已修复 |
| `ssrf_guard.py` | URL 安全验证 | 新增 |
| `auth/` | 认证授权 (9 files) | 密钥敏感 |
| `mcp_registry/` | 服务发现 + 生命周期 | Phase 2 新增 |

## 测试规范

- 测试文件: `tests/` 下按 `test_*.py` 命名
- 网络测试用 `@pytest.mark.network` 标记
- conftest.py 自动清理 `AGORA_*`, `OPENAI_*`, `ANTHROPIC_*` 环境变量
- 修改 `server/mcp.py` 时要警惕 — 这是 God Module，牵一发而动全身

## 已知技术债务

1. **server/mcp.py God Module** (1,757行) — 需拆分为 proxy/repo/a2a 三个模块
2. **_ok/_error 重复** — 在 `mcp/tools_template.py` 和 `server/mcp.py` 中重复定义
3. **ecos/omo 依赖声明但无静态 import** — pyproject.toml 有声明但实际通过 subprocess
4. **缺少 mypy 配置** — pyproject.toml 无 `[tool.mypy]`

## 安全检查清单

修改涉及网络请求/端点/认证的代码时：
- [ ] 调用 `validate_external_url()` 进行 SSRF 防护
- [ ] 使用 `hmac.compare_digest()` 而非 `==` 比较密钥
- [ ] 所有密钥通过 `os.environ.get()` 读取，无硬编码
- [ ] 无 `eval()` / `exec()` / `pickle.load()`
