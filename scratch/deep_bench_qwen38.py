"""Deep benchmark: qwen3.8-27b 三变体全面测评.
Tests: TTFT, TPS, throughput, reasoning quality, tool use, long context.
"""
import json
import time
import httpx

BASE = "http://127.0.0.1:1234"
VARIANTS = [
    "qwen3.8-27b-mlx",
    "qwen3.8-27b-mtplx-optimized-quality",
    "qwen3.8-27b-mtplx-optimized-speed",
]

# Test prompts
PROMPTS = {
    "simple_chinese": "用一句话介绍量子计算。",
    "code_generation": "用 Python 写一个快速排序函数，包含类型注解和 docstring。",
    "reasoning": "一个水池有一个进水管和一个出水管。进水管单独开 6 小时可以注满，出水管单独开 8 小时可以放完。如果同时开两管，几小时能注满？请一步步推理。",
    "tool_use": """你是一个助手，可以调用工具。请调用 get_weather 工具查询北京今天的天气。
请用以下格式响应：
{"tool_call": {"name": "get_weather", "arguments": {"city": "北京"}}}""",
    "long_context": "请总结以下文章的主要观点：\n\n" + "人工智能正在改变世界。" * 100 + "\n\n请用 3 个要点总结。",
    "creative": "写一首关于程序员的五言绝句。",
    "multilingual": "Translate to English, French, and Japanese: 今天天气很好。",
}


def warmup(model_id: str, n: int = 3):
    for _ in range(n):
        try:
            httpx.post(f"{BASE}/v1/chat/completions",
                json={"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1, "temperature": 0},
                timeout=120)
        except Exception:
            pass


def bench_task(model_id: str, prompt_name: str, prompt_text: str, max_tokens: int = 256) -> dict:
    """Run a single benchmark task, measure TTFT + TPS."""
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "stream": True,
    }
    t0 = time.perf_counter()
    ttft = None
    usage = None
    content_parts = []
    try:
        with httpx.stream("POST", f"{BASE}/v1/chat/completions", json=payload, timeout=180) as r:
            if r.status_code != 200:
                return {"ok": False, "error": f"status={r.status_code}"}
            for line in r.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(data)
                        if chunk.get("usage"):
                            usage = chunk["usage"]
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        token_text = delta.get("content") or delta.get("reasoning_content")
                        if token_text:
                            if ttft is None:
                                ttft = time.perf_counter() - t0
                            content_parts.append(token_text)
                    except json.JSONDecodeError:
                        pass
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:100]}
    total = time.perf_counter() - t0
    comp_tokens = usage.get("completion_tokens", 0) if usage else 0
    return {
        "ok": True,
        "ttft_ms": round(ttft * 1000, 1) if ttft else None,
        "total_s": round(total, 2),
        "tokens": comp_tokens,
        "tps": round(comp_tokens / total, 1) if total > 0 and comp_tokens > 0 else 0,
        "chars": len("".join(content_parts)),
        "preview": "".join(content_parts)[:120],
    }


def main():
    all_results = {}
    for vid in VARIANTS:
        print(f"\n{'='*70}")
        print(f"VARIANT: {vid}")
        print(f"{'='*70}")
        print("  warming up (x3)...")
        warmup(vid, n=3)
        variant_results = {}
        for pname, ptext in PROMPTS.items():
            print(f"  [{pname}] ", end="", flush=True)
            r = bench_task(vid, pname, ptext, max_tokens=256)
            variant_results[pname] = r
            if r.get("ok"):
                print(f"TTFT={r['ttft_ms']}ms  TPS={r['tps']}  tokens={r['tokens']}  chars={r['chars']}")
            else:
                print(f"FAILED: {r.get('error')}")
        all_results[vid] = variant_results

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    header = f"{'task':<20s}"
    for vid in VARIANTS:
        short = vid.replace("qwen3.8-27b-", "")
        header += f" {short:>20s}"
    print(header)
    print("-" * 80)
    for pname in PROMPTS:
        row = f"{pname:<20s}"
        for vid in VARIANTS:
            r = all_results[vid].get(pname, {})
            if r.get("ok"):
                row += f" {r['ttft_ms']:>8.0f}ms {r['tps']:>6.1f}tps"
            else:
                row += f" {'FAIL':>15s}"
        print(row)

    # Save raw results
    with open("scratch/qwen38_benchmark_raw.json", "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\nRaw results saved to scratch/qwen38_benchmark_raw.json")


if __name__ == "__main__":
    main()
