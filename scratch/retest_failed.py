"""对首轮失败的 placement 做干净复测：内存已释放，逐个跑 + 间隔，避免级联崩溃."""
import json
import time
import httpx

BASE = "http://127.0.0.1:1234"
OMLX = "http://127.0.0.1:8000"
PROMPT = "用一句话介绍量子计算，直接回答不要客套。"

FAILED = [
    ("coding-fast", BASE, "qwen3-coder-next"),
    ("coding-next", BASE, "qwen3-coder-next"),
    ("coding-next", OMLX, "coding-next"),
    ("coder-precise", BASE, "qwopus3.6-27b-coder-mlx"),
    ("coder-precise", OMLX, "coder-precise"),
    ("reasoning", OMLX, "reasoning"),
    ("nemotron-omni", OMLX, "nemotron-omni"),
    ("vision", OMLX, "vision"),
    ("mythos", OMLX, "mythos"),
    ("mistral-medium-128b", BASE, "mistral-medium-3.5-128b"),
    ("mistral-medium-128b", OMLX, "mistral-medium-128b"),
    ("ornith-9b", OMLX, "ornith-9b"),
    ("ornith-35b", OMLX, "ornith-35b"),
    ("gemma-4-31b-it-mlx-8bit", OMLX, "gemma-4-31b-it-mlx-8bit"),
    ("gemma-4-e2b-it-mlx-8bit", OMLX, "gemma-4-e2b-it-mlx-8bit"),
    ("qwen-3.8-27b", OMLX, "qwen-3.8-27b"),
]


def bench(base, model_id, max_tokens=120, timeout=90):
    payload = {"model": model_id, "messages": [{"role": "user", "content": PROMPT}],
               "max_tokens": max_tokens, "temperature": 0.3, "stream": True}
    t0 = time.perf_counter()
    ttft = None
    parts = []
    try:
        with httpx.stream("POST", f"{base}/v1/chat/completions", json=payload, timeout=timeout) as r:
            if r.status_code != 200:
                return {"ok": False, "error": f"status={r.status_code} {r.read()[:150]}"}
            for line in r.iter_lines():
                if line.startswith("data: "):
                    d = line[6:]
                    if d.strip() == "[DONE]":
                        continue
                    try:
                        c = json.loads(d)
                        delta = c.get("choices", [{}])[0].get("delta", {})
                        t = delta.get("content") or delta.get("reasoning_content")
                        if t:
                            if ttft is None:
                                ttft = time.perf_counter() - t0
                            parts.append(t)
                    except json.JSONDecodeError:
                        pass
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:150]}
    full = "".join(parts)
    return {"ok": True, "ttft_ms": round(ttft * 1000, 1) if ttft else None, "chars": len(full), "sample": full[:60]}


def main():
    for model_id, base, backend_id in FAILED:
        backend_name = "lm_studio" if base == BASE else "omlx-app"
        r = bench(base, backend_id)
        status = "OK" if r.get("ok") else "FAIL"
        print(f"{model_id:<28} {backend_name:<10} {status:<6} ttft={r.get('ttft_ms')} {r.get('sample', r.get('error',''))!r}", flush=True)
        time.sleep(3)


if __name__ == "__main__":
    main()
