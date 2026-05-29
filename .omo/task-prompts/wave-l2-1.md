# Wave L2-1: Resource Accounting

**目标**: 在 Agora 中实现 MCP 调用资源计量 (token/cost追踪)

## Task L2-1.1: 数据模型
- 文件: `~/Workspace/agora/src/agora/accounting.py`
- ResourceAccounting 模块: `CallRecord` dataclass
  - caller_id, service_name, tool_name, input_tokens, output_tokens, cost_usd, billed_to, timestamp
- SQLite 持久化 (WAL模式)
- 验证: `python3 -c "from agora.accounting import CallRecord; print('OK')"`

## Task L2-1.2: MCP 调用拦截中间件
- 文件: `~/Workspace/agora/src/agora/router.py` 或新 middleware
- 每次 MCP 调用经过时记录: caller, service, tokens, cost
- token 从 LLM 响应中提取 (usage.total_tokens)
- cost 估算: input*rate + output*rate (参考 openrouter pricing)
- 验证: 模拟一次MCP调用, 检查DB中有记录

## Task L2-1.3: CLI 查询命令
- 文件: `~/Workspace/agora/src/agora/cli.py`
- 新增 `accounting` 命令组:
  - `agora accounting top --period day` — 按caller排序
  - `agora accounting report --period week` — 汇总报告
  - `agora accounting quota --caller hermes` — 剩余配额
- 验证: `agora accounting top --period day` 返回非空

## Task L2-1.4: 测试
- 文件: `~/Workspace/agora/tests/test_accounting.py`
- 模拟3次MCP调用 → 验证记录
- 验证: `pytest tests/test_accounting.py -q`
