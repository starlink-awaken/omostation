"""Example 1: 基础 LLM 调用 — 最简单的入门方式。"""

from llm_gateway.detection import detect_backends, create_provider
from llm_gateway.provider import LLMRequest

# 1. 自动检测可用的 LLM Provider
providers = detect_backends()
print(f"发现 {len(providers)} 个 Provider:")
for p in providers:
    icon = "🟢" if p.is_available() else "🔴"
    print(f"  {icon} {p.provider_name}: {p.available_models()[:3]}")

# 2. 选择第一个可用的 Provider 并调用
for p in providers:
    if p.is_available():
        print(f"\n使用 {p.provider_name} 生成...")
        resp = p.complete(LLMRequest(prompt="用一句话介绍 AI"))
        print(f"  [{resp.model}] {resp.content}")
        break
else:
    print("\n没有可用的 Provider。")
    print("💡 安装 Ollama: https://ollama.com")
    print("💡 或设置 OPENAI_API_KEY 环境变量")
