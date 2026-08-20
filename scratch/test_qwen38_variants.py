"""Comprehensive test for LM Studio qwen3.8-27b variants."""
import json
import time
import httpx

BASE = "http://127.0.0.1:1234"
VARIANTS = [
    "qwen3.8-27b-mtplx-optimized-quality",
    "qwen3.8-27b-mtplx-optimized-speed",
    "qwen3.8-27b-mlx",
]
PROMPT = "用一句话介绍量子计算。"


def get_all_models():
    r = httpx.get(f"{BASE}/v1/models", timeout=5)
    return r.json().get("data", [])


def test_chat(model_id: str) -> dict:
    """Test non-streaming chat, measure TTFT and total latency."""
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 128,
        "temperature": 0.2,
    }
    t0 = time.perf_counter()
    r = httpx.post(f"{BASE}/v1/chat/completions", json=payload, timeout=60)
    elapsed = time.perf_counter() - t0
    if not r.status_code == 200:
        return {"ok": False, "error": r.text[:200], "latency_s": elapsed}
    d = r.json()
    usage = d.get("usage", {})
    content = d.get("choices", [{}])[0].get("message", {}).get("content", "")
    return {
        "ok": True,
        "latency_s": round(elapsed, 3),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "tps": round(usage.get("completion_tokens", 0) / elapsed, 1) if elapsed > 0 else 0,
        "preview": content[:150],
    }


def test_stream(model_id: str) -> dict:
    """Test streaming chat, measure TTFT (first token) and total."""
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 128,
        "temperature": 0.2,
        "stream": True,
    }
    t0 = time.perf_counter()
    ttft = None
    content_parts = []
    with httpx.stream("POST", f"{BASE}/v1/chat/completions", json=payload, timeout=60) as r:
        for line in r.iter_lines():
            if line.startswith("data: "):
                data = line[6:]
                if data.strip() == "[DONE]":
                    continue
                try:
                    chunk = json.loads(data)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    c = delta.get("content", "")
                    if c:
                        if ttft is None:
                            ttft = time.perf_counter() - t0
                        content_parts.append(c)
                except json.JSONDecodeError:
                    pass
    total = time.perf_counter() - t0
    return {
        "ok": True,
        "ttft_s": round(ttft, 3) if ttft else None,
        "total_s": round(total, 3),
        "preview": "".join(content_parts)[:150],
    }


def test_embedding(model_id: str) -> dict:
    """Test if model supports /v1/embeddings."""
    payload = {"model": model_id, "input": "test embedding"}
    r = httpx.post(f"{BASE}/v1/embeddings", json=payload, timeout=30)
    if r.status_code != 200:
        return {"ok": False, "error": r.text[:150]}
    d = r.json()
    n = len(d.get("data", []))
    dim = len(d["data"][0].get("embedding", [])) if n else 0
    return {"ok": True, "vectors": n, "dim": dim}


def test_vision(model_id: str) -> dict:
    """Test vision with a tiny 1x1 PNG."""
    png_1x1 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    import base64
    b64 = base64.b64encode(bytes.fromhex(png_1x1.replace("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", ""))).decode() if False else png_1x1
    # Just use the standard base64 directly
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png_1x1}"}},
                    {"type": "text", "text": "What color is this image? Reply in 5 words."},
                ],
            }
        ],
        "max_tokens": 32,
    }
    r = httpx.post(f"{BASE}/v1/chat/completions", json=payload, timeout=60)
    if r.status_code != 200:
        return {"ok": False, "error": r.text[:200]}
    content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    return {"ok": True, "preview": content[:150]}


def main():
    all_models = get_all_models()
    all_ids = {m["id"] for m in all_models}
    print(f"=== LM Studio total models in inventory: {len(all_models)} ===\n")

    for vid in VARIANTS:
        print(f"{'='*60}")
        print(f"VARIANT: {vid}")
        print(f"  in inventory: {vid in all_ids}")

        print("\n  [chat non-stream]")
        r = test_chat(vid)
        print(f"    {json.dumps(r, ensure_ascii=False)}")

        print("\n  [chat stream — TTFT]")
        r = test_stream(vid)
        print(f"    {json.dumps(r, ensure_ascii=False)}")

        print("\n  [embedding]")
        r = test_embedding(vid)
        print(f"    {json.dumps(r, ensure_ascii=False)}")

        print("\n  [vision]")
        r = test_vision(vid)
        print(f"    {json.dumps(r, ensure_ascii=False)}")
        print()


if __name__ == "__main__":
    main()
