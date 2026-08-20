"""Robust benchmark handling reasoning_content and model switching."""
import json
import time
import httpx

BASE = "http://127.0.0.1:1234"
VARIANTS = [
    "qwen3.8-27b-optimized-quality",
    "qwen3.8-27b-optimized-speed",
    "qwen3.8-27b-mlx",
]
PROMPT = "用一句话介绍量子计算。"


def warmup(model_id: str, n: int = 2):
    for _ in range(n):
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1,
            "temperature": 0,
        }
        try:
            httpx.post(f"{BASE}/v1/chat/completions", json=payload, timeout=120)
        except Exception:
            pass


def bench_stream(model_id: str, n: int = 5) -> dict:
    """Measure TTFT and TPS, handling reasoning_content."""
    ttfts = []
    tps_list = []
    errors = []
    for i in range(n):
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": 128,
            "temperature": 0.2,
            "stream": True,
        }
        t0 = time.perf_counter()
        ttft = None
        usage = None
        served_model = None
        try:
            with httpx.stream("POST", f"{BASE}/v1/chat/completions", json=payload, timeout=120) as r:
                if r.status_code != 200:
                    errors.append(f"status={r.status_code}")
                    continue
                for line in r.iter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            continue
                        try:
                            chunk = json.loads(data)
                            if not served_model:
                                served_model = chunk.get("model")
                            if chunk.get("usage"):
                                usage = chunk["usage"]
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            # Count both content and reasoning_content as output tokens
                            token_text = delta.get("content") or delta.get("reasoning_content")
                            if token_text and ttft is None:
                                ttft = time.perf_counter() - t0
                        except json.JSONDecodeError:
                            pass
        except Exception as exc:
            errors.append(str(exc))
            continue
        total = time.perf_counter() - t0
        if ttft is not None:
            ttfts.append(ttft)
        comp_tokens = usage.get("completion_tokens", 0) if usage else 0
        if total > 0 and comp_tokens > 0:
            tps_list.append(comp_tokens / total)
    if not ttfts:
        return {"ok": False, "errors": errors[:3]}
    ttfts.sort()
    tps_list.sort()
    return {
        "ok": True,
        "n": len(ttfts),
        "served_model": served_model,
        "ttft_median_ms": round(ttfts[len(ttfts) // 2] * 1000, 1),
        "ttft_min_ms": round(ttfts[0] * 1000, 1),
        "ttft_max_ms": round(ttfts[-1] * 1000, 1),
        "tps_median": round(tps_list[len(tps_list) // 2], 1) if tps_list else 0,
        "tps_min": round(tps_list[0], 1) if tps_list else 0,
        "tps_max": round(tps_list[-1], 1) if tps_list else 0,
    }


def main():
    results = {}
    for vid in VARIANTS:
        print(f"\n{'='*60}")
        print(f"BENCHMARK: {vid}")
        print(f"{'='*60}")

        print("  warming up (x2)...")
        warmup(vid, n=2)

        print("  measuring (x5)...")
        r = bench_stream(vid, n=5)
        results[vid] = r
        if r.get("ok"):
            print(f"  served by: {r.get('served_model')}")
            print(f"  TTFT median: {r['ttft_median_ms']}ms  (min={r['ttft_min_ms']}, max={r['ttft_max_ms']})")
            print(f"  TPS   median: {r['tps_median']}    (min={r['tps_min']}, max={r['tps_max']})")
        else:
            print(f"  FAILED: {r.get('errors', [])}")

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"{'requested':<42s} {'served':<30s} {'TTFT_ms':>10s} {'TPS':>8s}")
    print("-" * 92)
    for vid in VARIANTS:
        r = results.get(vid, {})
        if r.get("ok"):
            print(f"{vid:<42s} {r.get('served_model',''):<30s} {r['ttft_median_ms']:>10.1f} {r['tps_median']:>8.1f}")
        else:
            print(f"{vid:<42s} {'FAILED':<30s}")


if __name__ == "__main__":
    main()
