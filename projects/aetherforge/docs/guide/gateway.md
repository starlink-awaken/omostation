# LLM 调用 (Gateway)

Gateway 是 AetherForge 的统一 LLM 入口，支持 9 个 Provider。

## 支持的 Provider

| Provider | 环境变量 | SDK |
|:---------|:---------|:----|
| OpenAI | `OPENAI_API_KEY` | `openai` |
| Anthropic | `ANTHROPIC_API_KEY` | `anthropic` |
| Gemini | `GOOGLE_API_KEY` | `google-generativeai` |
| DeepSeek | `DEEPSEEK_API_KEY` | `openai` |
| Azure OpenAI | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | `openai` |
| AWS Bedrock | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | `boto3` |
| Google Vertex AI | `GOOGLE_CLOUD_PROJECT` | `vertexai` |
| Ollama | 无需配置 (自动检测 `localhost:11434`) | `requests` |
| HITL | 无需配置 (人工介入兜底) | 内置 |

## CLI 用法

```bash
aetherforge gateway list              # 列出可用模型
aetherforge gateway generate "你好"    # 默认模型生成
aetherforge gateway generate -m gpt-4 "写代码"  # 指定模型
```

## Python 用法

```python
from llm_gateway.detection import detect_backends
from llm_gateway.provider import LLMRequest

for p in detect_backends():
    if p.is_available():
        resp = p.complete(LLMRequest(prompt="你好"))
        print(resp.content)
```

## 智能路由

AetherForge 支持两阶段 (Filter → Score) 路由策略：

```python
from llm_gateway.policies import RouterPipeline, OnlineFilter, CostScore

pipeline = RouterPipeline()
pipeline.add_filter(OnlineFilter())   # 仅在线模型
pipeline.add_score(CostScore())       # 便宜优先
ranked = pipeline.select(candidates, request)
```

## 限流

防止账单炸裂：

```python
from llm_gateway.rate_limiter import RateLimiter
limiter = RateLimiter()
limiter.set_limit("gpt-4", tpm=100_000, rpm=30)
if limiter.acquire("gpt-4", tokens=500):
    # 在配额内
    pass
```
