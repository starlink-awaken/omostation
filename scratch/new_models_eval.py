"""评估新下载模型 + 复查可疑 MTP 配置项."""
import json
import time
import httpx

BASE = "http://127.0.0.1:1234"

MODELS = {
    "ornith-1.5-35b (new)": "ornith-1.5-35b-a3b-mlx",
    "ornith-1.0-35b (current)": "ornith-1.0-35b-xl-mlx",
    "qwen3.6-35b-a3b-mtp (registered)": "qwen3.6-35b-a3b-qwable-holo3-qwopus-oq6-mtp",
}

PROMPTS = {
    "ttft": "用一句话介绍量子计算。",
    "coding": "用 Python 写一个快速排序函数，包含类型注解和 docstring。",
    "reasoning": "一个水池有一个进水管和一个出水管。进水管单独开 6 小时可以注满，出水管单独开 8 小时可以放完。如果同时开两管，几小时能注满？请一步步推理。",
    "creative": "写一首关于程序员的五言绝句。",
}


def bench(model_id: str, prompt: str, max_tokens: int = 256) -> dict:
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "stream": True,
    }
    t0 = time.perf_counter()
    ttft = None
    content_parts = []
    try:
        with httpx.stream("POST", f"{BASE}/v1/chat/completions", json=payload, timeout=180) as r:
            if r.status_code != 200:
                body = r.read()[:200]
                return {"ok": False, "error": f"status={r.status_code} body={body}"}
            for line in r.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        token_text = delta.get("content") or delta.get("reasoning_content")
                        if token_text:
                            if ttft is None:
                                ttft = time.perf_counter() - t0
                            content_parts.append(token_text)
                    except json.JSONDecodeError:
                        pass
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:150]}
    total = time.perf_counter() - t0
    full = "".join(content_parts)
    return {
        "ok": True,
        "ttft_ms": round(ttft * 1000, 1) if ttft else None,
        "total_s": round(total, 2),
        "chars": len(full),
        "sample": full[:80].replace("\n", " "),
    }


def main():
    for label, model_id in MODELS.items():
        print(f"\n=== {label} ({model_id}) ===")
        for pname, prompt in PROMPTS.items():
            r = bench(model_id, prompt, max_tokens=200 if pname != "ttft" else 128)
            if r.get("ok"):
                print(f"  [{pname}] ttft={r['ttft_ms']}ms chars={r['chars']} sample='{r['sample']}'")
            else:
                print(f"  [{pname}] FAIL: {r.get('error')}")


if __name__ == "__main__":
    main()
