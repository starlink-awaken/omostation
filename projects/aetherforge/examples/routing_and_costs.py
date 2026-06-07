"""Example 3: 智能路由 + 限流 + 成本追踪。"""

from llm_gateway.policies import RouterPipeline, OnlineFilter, CostScore, SpeedScore
from llm_gateway.rate_limiter import RateLimiter
from llm_gateway.types import ModelDescriptor, ModelRequest
from compute_mesh.pool import CostTracker
from compute_mesh.topology import NodeRegistry

# 1. 构建自定义路由 pipeline
pipeline = RouterPipeline()
pipeline.add_filter(OnlineFilter())     # 只看在线模型
pipeline.add_score(CostScore())         # 便宜优先
pipeline.add_score(SpeedScore())        # 快速优先

# 2. 创建测试模型数据
models = [
    ModelDescriptor(id="gpt-4", provider="openai", capabilities=["chat"],
                    is_available=True, cost_per_1k_tokens={"input": 0.03, "output": 0.06},
                    avg_latency_ms=1200, context_window=8192),
    ModelDescriptor(id="claude-3", provider="anthropic", capabilities=["chat"],
                    is_available=True, cost_per_1k_tokens={"input": 0.015, "output": 0.075},
                    avg_latency_ms=800, context_window=100000),
    ModelDescriptor(id="local-llama", provider="ollama", capabilities=["chat"],
                    is_available=True, cost_per_1k_tokens=None,
                    avg_latency_ms=200, context_window=4096),
]

request = ModelRequest(task="写一篇短文章", required_capabilities=["chat"])

# 3. 执行调度
ranked = pipeline.select(models, request)
print("📊 调度排名:")
for i, sm in enumerate(ranked, 1):
    cost = sm.model.cost_per_1k_tokens or {"input": 0, "output": 0}
    print(f"  #{i} {sm.model.id:20s} score={sm.score:.2f} "
          f"cost=(${cost['input']}+${cost['output']})/1K")

# 4. 限流演示
limiter = RateLimiter()
limiter.set_limit("gpt-4", tpm=100_000, rpm=30)
can_pass = limiter.acquire("gpt-4", tokens=500)
print(f"\n🔒 限流检查: {'通过 ✅' if can_pass else '限流 ❌'}")

# 5. 成本追踪
tracker = CostTracker(NodeRegistry())
tracker.record("gpt-4", prompt_tokens=500, completion_tokens=200, model="gpt-4")
tracker.record("local-llama", prompt_tokens=1000, completion_tokens=500, model="llama3")
report = tracker.get_report()
print(f"\n💰 成本报告:")
print(f"  会话总计: ${report['session']['total_cost']:.4f}")
print(f"  累计总计: ${report['all_time']['total_cost']:.4f}")
