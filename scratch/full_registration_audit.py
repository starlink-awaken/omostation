"""全面注册验证：每个已注册模型跑一次真实生成，检测乱码/空输出/超时."""
import json
import time
import httpx

BASE = "http://127.0.0.1:1234"
OMLX = "http://127.0.0.1:8000"

# (omlxc model_id, lm_studio backend_model_id, omlx_app backend_model_id_or_None)
MODELS = [
    ("coding", None, "coding"),
    ("coding-fast", "qwen3-coder-next", None),
    ("coding-next", "qwen3-coder-next", "coding-next"),
    ("coder-precise", "qwopus3.6-27b-coder-mlx", "coder-precise"),
    ("reasoning", "zai-org/glm-4.7-flash", "reasoning"),
    ("nemotron-omni", "nemotron-cascade-2-30b-a3b", "nemotron-omni"),
    ("vision", "qwen3-vl-8b-instruct-mlx", "vision"),
    ("mythos", "qwythos-9b-claude-mythos-5-1m-mlx", "mythos"),
    ("mythos-fast", "qwythos-9b-claude-mythos-5-1m-mlx", None),
    ("mistral-medium-128b", "mistral-medium-3.5-128b", "mistral-medium-128b"),
    ("ornith-9b", "ornith-1.0-9b", "ornith-9b"),
    ("ornith-35b", "ornith-1.5-35b-a3b-mlx", "ornith-35b"),
    ("gemma-4-31b-it-mlx-8bit", "gemma-4-31b-it-mlx", "gemma-4-31b-it-mlx-8bit"),
    ("gemma-4-e2b-it-mlx-8bit", "google/gemma-4-e2b", "gemma-4-e2b-it-mlx-8bit"),
    ("qwen-3.8-27b", "qwen3.8-27b-mlx", "qwen-3.8-27b"),
]

PROMPT = "用一句话介绍量子计算，直接回答不要客套。"


def bench(base, model_id, max_tokens=150):
    payload = {"model": model_id, "messages": [{"role": "user", "content": PROMPT}],
               "max_tokens": max_tokens, "temperature": 0.3, "stream": True}
    t0 = time.perf_counter()
    ttft = None
    parts = []
    try:
        with httpx.stream("POST", f"{base}/v1/chat/completions", json=payload, timeout=60) as r:
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


def is_garbage(sample: str) -> bool:
    if not sample.strip():
        return True
    printable_cjk_latin = sum(1 for c in sample if c.isalnum() or c.isspace() or ord(c) > 0x4e00)
    return printable_cjk_latin / max(len(sample), 1) < 0.6


def main():
    print(f"{'model_id':<28} {'backend':<10} {'status':<10} {'ttft':<10} sample")
    for model_id, lm_id, omlx_id in MODELS:
        if lm_id:
            r = bench(BASE, lm_id)
            status = "OK" if r.get("ok") and not is_garbage(r.get("sample", "")) else ("GARBAGE" if r.get("ok") else "FAIL")
            print(f"{model_id:<28} {'lm_studio':<10} {status:<10} {str(r.get('ttft_ms')):<10} {r.get('sample', r.get('error',''))!r}")
        if omlx_id:
            r = bench(OMLX, omlx_id)
            status = "OK" if r.get("ok") and not is_garbage(r.get("sample", "")) else ("GARBAGE" if r.get("ok") else "FAIL")
            print(f"{model_id:<28} {'omlx-app':<10} {status:<10} {str(r.get('ttft_ms')):<10} {r.get('sample', r.get('error',''))!r}")


if __name__ == "__main__":
    main()
