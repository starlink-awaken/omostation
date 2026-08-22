"""受控内存审计: LM Studio 侧全部 placement, 逐个显式加载→测→卸载.

护栏设计 (2026-08-22 多次内存事故后):
- 每步检查 vm_stat, free < 阈值就等待/中止
- 显式 lms load -c 8192 锁死上下文, 绝不让 JIT 用模型最大值
- 单模型 max_tokens=80 的小请求
- 测完立刻 lms unload, 确认内存回落再继续
- 大模型需要 free > size*1.5 才测, 否则 SKIP
- omlx-app 侧本轮跳过 (内存优先, LM Studio 覆盖主力模型)
"""
import json
import re
import subprocess
import sys
import time

import httpx

LMS = "http://127.0.0.1:1234"
CONFIG = "/Users/xiamingxing/.config/omlxc/config.toml"

# 预估权重 GB (8K 上下文下额外 KV 可忽略), 用于加载前的内存闸门
EST_GB = {
    "qwopus3.6-27b-coder-mlx": 29.0,
    "qwen3-coder-next": 55.0,
    "qwythos-9b-claude-mythos-5-1m-mlx": 19.0,
    "qwen3.8-27b-mlx": 23.0,
    "gemma-4-31b-it-mlx": 32.0,
    "google/gemma-4-e2b": 8.0,
    "zai-org/glm-4.7-flash": 17.0,
    "nemotron-cascade-2-30b-a3b": 21.0,
    "qwen3-vl-8b-instruct-mlx": 8.0,
    "qwen/qwen3.6-27b": 16.0,
    "ornith-1.5-35b-a3b-mlx": 20.0,
    "ornith-1.5-9b-mlx": 18.0,
    "ornith-1.0-9b": 6.0,
    "ornith-1.0-35b-xl-mlx": 20.0,
    "mistral-medium-3.5-128b": 75.0,
    "qwen3-embedding-8b-mxfp8": 8.0,   # embedding, 不发 chat
    "bge-m3-mlx": 2.0,                  # embedding
}

MIN_FREE_GB = 18.0   # 低于此值暂停等待
ABORT_FREE_GB = 12.0  # 低于此值直接中止


def free_gb() -> float:
    """真实可用内存: free + purgeable + 70% inactive (macOS 有压力时会回收 inactive)."""
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


def wait_mem(need_gb: float, timeout_s: int = 60) -> bool:
    """等待 free 恢复到 need_gb 以上."""
    for _ in range(timeout_s // 5):
        f = free_gb()
        if f >= need_gb:
            return True
        if f < ABORT_FREE_GB:
            return False
        print(f"    [mem-wait] free={f:.1f}GB < {need_gb}GB, 等5s...", flush=True)
        time.sleep(5)
    return free_gb() >= need_gb


def lms(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/Users/xiamingxing/.local/bin/lms", *args],
        capture_output=True, text=True, timeout=180,
    )


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
        with httpx.stream("POST", f"{LMS}/v1/chat/completions", json=payload, timeout=120) as r:
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


def load_lm_placements() -> list[tuple[str, str]]:
    content = open(CONFIG).read()
    blocks = re.split(r"\n(?=\[\[placements\]\])", content)
    out = []
    for b in blocks:
        if not b.strip().startswith("[[placements]]"):
            continue
        bid = re.search(r'backend_id = "([^"]+)"', b)
        if not bid or bid.group(1) != "mbp-m5-max-128g-lm_studio":
            continue
        pid = re.search(r'id = "([^"]+)"', b)
        bmid = re.search(r'backend_model_id = "([^"]+)"', b)
        if not (pid and bmid):
            continue
        # embedding/rerank 模型没有 lm_head, 不支持 /chat/completions, 跳过
        if any(k in bmid.group(1).lower() for k in ("embedding", "bge", "reranker")):
            continue
        out.append((pid.group(1), bmid.group(1)))
    return out


def main() -> None:
    placements = load_lm_placements()
    # 按预估体积升序: 小的先测, 大的内存不够自然 SKIP
    placements.sort(key=lambda p: EST_GB.get(p[1], 15.0))
    results = []
    print(f"共 {len(placements)} 个 LM Studio placement (受控模式, omlx-app 本轮跳过)\n", flush=True)

    for pid, bmid in placements:
        est = EST_GB.get(bmid, 15.0)
        print(f"== {pid} [{bmid}] est={est}GB free={free_gb():.1f}GB", flush=True)

        need = est * 1.5
        if not wait_mem(need):
            results.append((pid, bmid, "SKIP-MEM", None, ""))
            print(f"   SKIP (内存不足, 需~{need:.0f}GB)\n", flush=True)
            continue

        ld = lms("load", bmid, "-c", "8192", "--parallel", "1", "--ttl", "120", "-y")
        if "successfully" not in (ld.stdout + ld.stderr):
            err = (ld.stderr or ld.stdout).strip().splitlines()[-1][:80] if (ld.stderr or ld.stdout) else "unknown"
            results.append((pid, bmid, "LOAD-FAIL", None, err))
            print(f"   LOAD-FAIL: {err}\n", flush=True)
            continue

        r = bench(bmid)
        lms("unload", bmid)
        # 等内存回落
        for _ in range(6):
            if free_gb() >= need - 2:
                break
            time.sleep(3)

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
    with open("scratch/safe_audit_results.json", "w") as f:
        json.dump([{"placement": p, "model": m, "status": s, "ttft_ms": t, "note": n}
                   for p, m, s, t, n in results], f, indent=2, ensure_ascii=False)
    sys.exit(1 if any(r[2] == "GARBAGE" for r in results) else 0)


if __name__ == "__main__":
    main()
