"""omlx-app 侧受控审计: 逐个发请求, 依赖其内存守护自管加载/驱逐.

与 LM Studio 轮的区别: oMLX App 无 per-model unload 命令, 模型加载后由
idle_timeout(1800s) 或内存守护(加载新模型时驱逐旧模型)释放。所以不做
手动 load/unload, 只做: 发请求 → 查内存 → 下一个。任何时刻依赖 oMLX App
自己的 balanced 守护 (soft 85% / hard 95%) 兜底。
"""
import json
import re
import subprocess
import sys
import time

import httpx

OMLX = "http://127.0.0.1:8000"
CONFIG = "/Users/xiamingxing/.config/omlxc/config.toml"

# omlx-app 侧模型显存预估 (权重 GB)
EST_GB = {
    "coding": 24.0,
    "coding-next": 52.0,
    "reasoning": 17.0,
    "embedding": 8.0,
    "vision": 6.0,
    "mythos": 18.0,
    "mistral-medium-128b": 74.0,
    "nemotron-omni": 23.0,
    "ornith-9b": 6.0,
    "ornith-35b": 25.0,
    "embed-bge-m3": 1.0,
    "baai-bge-reranker-v2-m3-mlx-fp16": 3.0,
    "gemma-4-31b-it-mlx-8bit": 32.0,
    "gemma-4-e2b-it-mlx-8bit": 6.0,
    "qwen-3.8-27b": 22.0,
    "coder-precise": 28.0,
}

MIN_FREE_GB = 20.0


def free_gb() -> float:
    out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    free = re.search(r"Pages free:\s+(\d+)", out)
    purge = re.search(r"Pages purgeable:\s+(\d+)", out)
    inact = re.search(r"Pages inactive:\s+(\d+)", out)
    if not free:
        return 0.0
    pages = int(free.group(1))
    if purge:
        pages += int(purge.group(1))
    if inact:
        pages += int(inact.group(1)) * 7 // 10
    return pages * 16384 / 1024**3


def wait_mem(need_gb: float, timeout_s: int = 90) -> bool:
    for _ in range(timeout_s // 5):
        f = free_gb()
        if f >= need_gb:
            return True
        print(f"    [mem-wait] free={f:.1f}GB < {need_gb}GB, 等5s...", flush=True)
        time.sleep(5)
    return free_gb() >= need_gb


def bench(model_id: str) -> dict:
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "用一句话介绍量子计算，直接回答。"}],
        "max_tokens": 80, "temperature": 0.3, "stream": True,
    }
    t0 = time.perf_counter()
    ttft = None
    parts = []
    try:
        with httpx.stream("POST", f"{OMLX}/v1/chat/completions", json=payload, timeout=180) as r:
            if r.status_code != 200:
                return {"ok": False, "error": f"status={r.status_code}"}
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
        return {"ok": False, "error": str(exc)[:120]}
    full = "".join(parts)
    return {"ok": True, "ttft_ms": round(ttft * 1000, 1) if ttft else None, "chars": len(full), "sample": full[:60]}


def is_garbage(s: str) -> bool:
    if not s.strip():
        return True
    ok = sum(1 for c in s if c.isalnum() or c.isspace() or ord(c) > 0x4E00)
    return ok / max(len(s), 1) < 0.6


def load_omlx_placements() -> list[tuple[str, str]]:
    content = open(CONFIG).read()
    blocks = re.split(r"\n(?=\[\[placements\]\])", content)
    out = []
    for b in blocks:
        if not b.strip().startswith("[[placements]]"):
            continue
        bid = re.search(r'backend_id = "([^"]+)"', b)
        if not bid or bid.group(1) != "mbp-m5-max-128g-omlx-app":
            continue
        pid = re.search(r'id = "([^"]+)"', b)
        bmid = re.search(r'backend_model_id = "([^"]+)"', b)
        if not (pid and bmid):
            continue
        if any(k in bmid.group(1).lower() for k in ("embedding", "bge", "reranker")):
            continue
        out.append((pid.group(1), bmid.group(1)))
    return out


def main() -> None:
    placements = load_omlx_placements()
    placements.sort(key=lambda p: EST_GB.get(p[1], 15.0))
    results = []
    print(f"共 {len(placements)} 个 omlx-app placement (依赖其后端内存守护)\n", flush=True)

    for pid, bmid in placements:
        est = EST_GB.get(bmid, 15.0)
        print(f"== {pid} [{bmid}] est={est}GB free={free_gb():.1f}GB", flush=True)

        if not wait_mem(max(est * 1.4, MIN_FREE_GB)):
            results.append((pid, bmid, "SKIP-MEM", None, ""))
            print(f"   SKIP (内存不足)\n", flush=True)
            continue

        r = bench(bmid)
        # 等 oMLX App 释放/平稳 (无手动卸载, 给它时间自平衡)
        time.sleep(5)

        if r.get("ok"):
            status = "GARBAGE" if is_garbage(r.get("sample", "")) else "OK"
        else:
            status = "FAIL"
        results.append((pid, bmid, status, r.get("ttft_ms"), r.get("sample", r.get("error", ""))))
        print(f"   {status} ttft={r.get('ttft_ms')} {r.get('sample', r.get('error',''))!r}\n", flush=True)

    print("=" * 70)
    print(f"{'placement':<42} {'status':<10} {'ttft':<8} note")
    for pid, bmid, st, ttft, note in results:
        print(f"{pid:<42} {st:<10} {str(ttft):<8} {note[:40]}")
    ok = sum(1 for r in results if r[2] == "OK")
    print(f"\nOK={ok} GARBAGE={sum(1 for r in results if r[2]=='GARBAGE')} "
          f"FAIL={sum(1 for r in results if r[2]=='FAIL')} SKIP={sum(1 for r in results if r[2].startswith('SKIP'))}")
    with open("scratch/safe_audit_omlx_results.json", "w") as f:
        json.dump([{"placement": p, "model": m, "status": s, "ttft_ms": t, "note": n}
                   for p, m, s, t, n in results], f, indent=2, ensure_ascii=False)
    sys.exit(1 if any(r[2] == "GARBAGE" for r in results) else 0)


if __name__ == "__main__":
    main()
