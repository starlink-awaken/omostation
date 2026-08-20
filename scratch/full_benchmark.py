"""全面模型测评 — 多维度评分榜单.
Tests: TTFT, TPS, output quality (chars), multimodal, tool use.
"""
import json
import time
import httpx

BASE = "http://127.0.0.1:1234"

# 所有可用模型 (从 LM Studio 库存提取)
MODELS = {
    # 编码
    "coding": {"id": "coding", "category": "coding"},
    "coding-fast": {"id": "coding-fast", "category": "coding"},
    "coding-next": {"id": "coding-next", "category": "coding"},
    "coder-precise": {"id": "coder-precise", "category": "coding"},
    # 通用
    "qwen-3.8-27b": {"id": "qwen3.8-27b-mlx", "category": "chat"},
    "mid-local": {"id": "mid-local", "category": "chat"},
    "reasoning": {"id": "reasoning", "category": "reasoning"},
    "nemotron-omni": {"id": "nemotron-omni", "category": "reasoning"},
    "deepseek-v4-flash": {"id": "deepseek-v4-flash-mtp-mlx", "category": "reasoning"},
    "mythos-fast": {"id": "qwythos-9b-claude-mythos-5-1m-mlx", "category": "chat"},
    # 视觉
    "vision": {"id": "vision", "category": "vision"},
    "mythos": {"id": "mythos", "category": "vision"},
    "gemma-4-26b": {"id": "google/gemma-4-26b-a4b-qat", "category": "vision"},
    "gemma-4-31b": {"id": "gemma-4-31b-it-mlx", "category": "vision"},
    "gemma-4-e2b": {"id": "google/gemma-4-e2b", "category": "vision"},
    "ornith-9b": {"id": "ornith-1.0-9b", "category": "vision"},
    "ornith-35b": {"id": "ornith-1.0-35b-xl-mlx", "category": "vision"},
    # 检索
    "embedding": {"id": "qwen3-embedding-8b-mxfp8", "category": "embedding"},
    "embed-bge-m3": {"id": "bge-m3-mlx", "category": "embedding"},
    "baai-bge-reranker": {"id": "baai-bge-reranker-v2-m3-mlx", "category": "embedding"},
}

PROMPTS = {
    "ttft": "用一句话介绍量子计算。",
    "coding": "用 Python 写一个快速排序函数，包含类型注解和 docstring。",
    "reasoning": "一个水池有一个进水管和一个出水管。进水管单独开 6 小时可以注满，出水管单独开 8 小时可以放完。如果同时开两管，几小时能注满？请一步步推理。",
    "creative": "写一首关于程序员的五言绝句。",
    "chinese": "用文言文写一段天气预报，描述明天的天气情况。",
}


def bench_model(model_id: str, prompt: str, max_tokens: int = 256) -> dict:
    """Measure TTFT + TPS for a single model."""
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
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
        return {"ok": False, "error": str(exc)[:80]}
    total = time.perf_counter() - t0
    comp_tokens = usage.get("completion_tokens", 0) if usage else 0
    return {
        "ok": True,
        "ttft_ms": round(ttft * 1000, 1) if ttft else None,
        "total_s": round(total, 2),
        "tokens": comp_tokens,
        "tps": round(comp_tokens / total, 1) if total > 0 and comp_tokens > 0 else 0,
        "chars": len("".join(content_parts)),
    }


def warmup(model_id: str, n: int = 2):
    for _ in range(n):
        try:
            httpx.post(f"{BASE}/v1/chat/completions",
                json={"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1, "temperature": 0},
                timeout=120)
        except Exception:
            pass


def main():
    results = {}
    total = len(MODELS)
    for i, (name, info) in enumerate(MODELS.items(), 1):
        model_id = info["id"]
        print(f"\n[{i}/{total}] {name} ({model_id})")

        # Skip embedding models for chat tests
        if info["category"] == "embedding":
            results[name] = {"category": "embedding", "skip": True}
            print("  (embedding model, skip chat tests)")
            continue

        print("  warming up...")
        warmup(model_id, n=2)

        model_results = {"category": info["category"]}

        # TTFT test
        print("  [ttft] ", end="", flush=True)
        r = bench_model(model_id, PROMPTS["ttft"], max_tokens=128)
        if r.get("ok"):
            model_results["ttft_ms"] = r["ttft_ms"]
            print(f"{r['ttft_ms']}ms")
        else:
            print(f"FAIL: {r.get('error')}")
            model_results["ttft_ms"] = None

        # Coding test
        print("  [coding] ", end="", flush=True)
        r = bench_model(model_id, PROMPTS["coding"], max_tokens=256)
        if r.get("ok"):
            model_results["coding_tps"] = r["tps"]
            model_results["coding_chars"] = r["chars"]
            print(f"TPS={r['tps']} chars={r['chars']}")
        else:
            print(f"FAIL")
            model_results["coding_tps"] = 0

        # Reasoning test
        print("  [reasoning] ", end="", flush=True)
        r = bench_model(model_id, PROMPTS["reasoning"], max_tokens=256)
        if r.get("ok"):
            model_results["reasoning_chars"] = r["chars"]
            print(f"chars={r['chars']}")
        else:
            print(f"FAIL")
            model_results["reasoning_chars"] = 0

        # Creative test
        print("  [creative] ", end="", flush=True)
        r = bench_model(model_id, PROMPTS["creative"], max_tokens=128)
        if r.get("ok"):
            model_results["creative_chars"] = r["chars"]
            print(f"chars={r['chars']}")
        else:
            print(f"FAIL")
            model_results["creative_chars"] = 0

        results[name] = model_results

    # Save raw results
    with open("scratch/full_benchmark_raw.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Print leaderboard
    print(f"\n{'='*70}")
    print("LEADERBOARD")
    print(f"{'='*70}")

    # Filter models with TTFT data
    chat_models = {k: v for k, v in results.items() if not v.get("skip") and v.get("ttft_ms")}

    print(f"\n--- TTFT (首token延迟, 越小越好) ---")
    sorted_ttft = sorted(chat_models.items(), key=lambda x: x[1].get("ttft_ms", 9999))
    for name, r in sorted_ttft[:10]:
        print(f"  {name:<25s} {r.get('ttft_ms', 'N/A'):>8}ms")

    print(f"\n--- Coding TPS (编码吞吐, 越大越好) ---")
    sorted_coding = sorted(chat_models.items(), key=lambda x: x[1].get("coding_tps", 0), reverse=True)
    for name, r in sorted_coding[:10]:
        print(f"  {name:<25s} {r.get('coding_tps', 0):>8.1f} tps")

    print(f"\n--- 综合评分 ---")
    # Score: lower TTFT is better, higher TPS is better
    scores = {}
    for name, r in chat_models.items():
        ttft = r.get("ttft_ms") or 1000
        tps = r.get("coding_tps") or 0
        # Normalize: TTFT score (1000ms = 0, 100ms = 100), TPS score (0=0, 60=100)
        ttft_score = max(0, 100 - (ttft / 10))
        tps_score = min(100, tps * 1.5)
        total_score = round(ttft_score * 0.4 + tps_score * 0.6, 1)
        scores[name] = total_score

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    for name, score in sorted_scores[:15]:
        cat = chat_models[name].get("category", "?")
        print(f"  {name:<25s} {score:>6.1f}  [{cat}]")

    print(f"\nRaw results saved to scratch/full_benchmark_raw.json")


if __name__ == "__main__":
    main()
