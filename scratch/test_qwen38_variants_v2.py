"""Warm-up + real-image vision test for qwen3.8-27b variants."""
import json
import time
import base64
import httpx

BASE = "http://127.0.0.1:1234"
VARIANTS = [
    "qwen3.8-27b-mtplx-optimized-quality",
    "qwen3.8-27b-mtplx-optimized-speed",
    "qwen3.8-27b-mlx",
]
PROMPT = "用一句话介绍量子计算。"

# 1x1 red pixel PNG
PNG_1X1_RED = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
    "2mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
)


def warmup(model_id: str):
    """Load model into memory via a tiny chat."""
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1,
        "temperature": 0,
    }
    r = httpx.post(f"{BASE}/v1/chat/completions", json=payload, timeout=120)
    return r.status_code == 200


def test_chat_warm(model_id: str, n: int = 3) -> dict:
    """Test chat after warm-up, average over n runs."""
    latencies = []
    for _ in range(n):
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": 128,
            "temperature": 0.2,
        }
        t0 = time.perf_counter()
        r = httpx.post(f"{BASE}/v1/chat/completions", json=payload, timeout=60)
        elapsed = time.perf_counter() - t0
        if r.status_code == 200:
            latencies.append(elapsed)
    if not latencies:
        return {"ok": False}
    latencies.sort()
    return {
        "ok": True,
        "n": len(latencies),
        "median_s": round(latencies[len(latencies) // 2], 3),
        "min_s": round(latencies[0], 3),
        "max_s": round(latencies[-1], 3),
    }


def test_stream_ttft(model_id: str) -> dict:
    """Measure TTFT on a warm model."""
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 128,
        "temperature": 0.2,
        "stream": True,
    }
    t0 = time.perf_counter()
    ttft = None
    n_tokens = 0
    with httpx.stream("POST", f"{BASE}/v1/chat/completions", json=payload, timeout=60) as r:
        for line in r.iter_lines():
            if line.startswith("data: "):
                data = line[6:]
                if data.strip() == "[DONE]":
                    continue
                try:
                    chunk = json.loads(data)
                    usage = chunk.get("usage")
                    if usage:
                        n_tokens = usage.get("completion_tokens", n_tokens)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    if delta.get("content"):
                        if ttft is None:
                            ttft = time.perf_counter() - t0
                except json.JSONDecodeError:
                    pass
    total = time.perf_counter() - t0
    return {
        "ok": True,
        "ttft_s": round(ttft, 3) if ttft else None,
        "total_s": round(total, 3),
        "tokens": n_tokens,
        "tps": round(n_tokens / total, 1) if total > 0 else 0,
    }


def test_embedding_loaded(model_id: str) -> dict:
    """Test embedding after model is loaded."""
    payload = {"model": model_id, "input": "test embedding"}
    r = httpx.post(f"{BASE}/v1/embeddings", json=payload, timeout=30)
    if r.status_code != 200:
        return {"ok": False, "error": r.text[:200]}
    d = r.json()
    n = len(d.get("data", []))
    dim = len(d["data"][0].get("embedding", [])) if n else 0
    return {"ok": True, "vectors": n, "dim": dim}


def test_vision_real(model_id: str) -> dict:
    """Test vision with the red pixel PNG."""
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{PNG_1X1_RED}"}},
                    {"type": "text", "text": "What color is this image? Reply in 3 words."},
                ],
            }
        ],
        "max_tokens": 32,
        "temperature": 0.1,
    }
    r = httpx.post(f"{BASE}/v1/chat/completions", json=payload, timeout=60)
    if r.status_code != 200:
        return {"ok": False, "error": r.text[:200]}
    content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    return {"ok": True, "preview": content[:200]}


def main():
    for vid in VARIANTS:
        print(f"{'='*60}")
        print(f"VARIANT: {vid}")

        print("\n  [warm-up / load model]")
        ok = warmup(vid)
        print(f"    loaded: {ok}")
        if not ok:
            print("    SKIP (failed to load)")
            continue

        print("\n  [chat warm x3]")
        r = test_chat_warm(vid, n=3)
        print(f"    {json.dumps(r, ensure_ascii=False)}")

        print("\n  [stream TTFT + TPS]")
        r = test_stream_ttft(vid)
        print(f"    {json.dumps(r, ensure_ascii=False)}")

        print("\n  [embedding (model loaded)]")
        r = test_embedding_loaded(vid)
        print(f"    {json.dumps(r, ensure_ascii=False)}")

        print("\n  [vision (red pixel)]")
        r = test_vision_real(vid)
        print(f"    {json.dumps(r, ensure_ascii=False)}")
        print()


if __name__ == "__main__":
    main()
