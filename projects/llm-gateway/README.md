# llm-gateway — LLM Provider 抽象层

> Ollama · OpenAI · Anthropic · Gemini · DeepSeek · HITL
> 原 llm-gateway-kernel 的 `llm_gateway/` 模块

## 功能

- 6 个 LLM Provider (异步/同步/流式)
- ModelRegistry + ModelScheduler (4 策略: cost/speed/capability/balanced)
- CircuitBreaker + Retry
- MCP Server + CLI
- L0 SSOT M1 compute_engine 集成

## CLI

```bash
llm-gateway list              # 列出可用模型
llm-gateway list --ssot       # 从 L0 M1 节点加载
llm-gateway generate "你好"    # 生成
llm-gateway mcp               # 启动 MCP Server
```
