# L4 Kernel MCP Server · 完整实现

**2026-06-08 · 42 tools · 19域 · 多协议 · 插件扩展**

---

## 一、项目结构 (新增文件)

```
projects/l4-kernel/
├── src/l4_kernel/
│   ├── registry.py          ✅ 19域注册
│   ├── domain_types.py      ✅ 7种类型
│   ├── kems.py              ✅ KEMS六面
│   ├── templates.py         ✅ 模板+校验
│   ├── health.py            ✅ 健康聚合
│   ├── signals.py           ✅ 信号总线
│   ├── claude_injector.py   ✅ Schema注入
│   │
│   ├── config.py            🔜 配置模型
│   ├── governance.py        🔜 治理引擎
│   ├── scheduler.py         🔜 定时调度
│   ├── mof_constraints.py   🔜 M2约束
│   ├── sync.py              🔜 双向同步
│   │
│   ├── lifecycle.py         🔜 域生命周期
│   ├── plugins.py           🔜 插件扩展框架
│   ├── workflows.py         🔜 工作流引擎
│   ├── confirm.py           🔜 确认/回滚
│   │
│   ├── mcp_server.py        🔜 MCP Server (42 tools)
│   ├── http_server.py       🔜 HTTP API (FastAPI)
│   └── cli.py               ✅→🔜 扩展 CLI
│
├── plugins/                 🔜 业务插件目录
│   ├── __init__.py
│   ├── document_kems.py     🔜 DocumentDomain KEMS 操作
│   ├── config_schema.py     🔜 ConfigDomain Schema 校验
│   ├── tool_registry.py     🔜 ToolDomain 脚本管理
│   └── engine_monitor.py    🔜 EngineDomain 进程监控
│
└── tests/
    ├── test_lifecycle.py     🔜
    ├── test_workflows.py     🔜
    ├── test_mcp_server.py    🔜
    └── test_plugins.py       🔜
