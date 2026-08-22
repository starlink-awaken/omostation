#!/usr/bin/env python3
"""内存安全的 oMLX App placement 审计。

omlx_app backend 没有 per-model 卸载 CLI (靠 idle_ttl=1800s 自动释放),
所以策略与 lm_studio 系不同: 直接发 chat 请求触发按需加载, 不做卸载,
只做内存前置检查 + 安全刹车。>35GB 的巨型模型默认 SKIP-MEM(沿用
2026-08-22 早前审计的先例), 除非显式传入 --allow-huge。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib

import httpx

for _proxy_var in ("all_proxy", "ALL_PROXY", "http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
    os.environ.pop(_proxy_var, None)

CONFIG_PATH = "/Users/xiamingxing/.config/omlxc/config.toml"
MIN_FREE_GB = 12.0
HUGE_THRESHOLD_GB = 35.0
BASE_URL = "http://127.0.0.1:8000"


def real_free_gb() -> float:
    out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=10).stdout
    vals: dict[str, int] = {}
    for line in out.splitlines():
        for key in ("Pages free", "Pages purgeable", "Pages inactive"):
            if line.startswith(key):
                vals[key] = int(line.split(":")[1].strip().rstrip(".").replace(",", ""))
    free = vals.get("Pages free", 0)
    purg = vals.get("Pages purgeable", 0)
    inact = vals.get("Pages inactive", 0)
    return (free + purg + inact * 0.7) * 16384 / 1024**3


def lms_generating_locally() -> bool:
    result = subprocess.run(
        ["/Users/xiamingxing/.local/bin/lms", "ps", "--json"], capture_output=True, text=True, timeout=15
    )
    try:
        import json

        rows = json.loads(result.stdout)
    except Exception:
        return False
    return any(r.get("status") == "generating" for r in rows)


def embedding_probe(model_id: str) -> tuple[str, str]:
    try:
        r = httpx.post(
            f"{BASE_URL}/v1/embeddings",
            json={"model": model_id, "input": "贯通测试"},
            timeout=60,
        )
    except Exception as e:
        return "FAIL", str(e)[:150]
    if r.status_code != 200:
        return "FAIL", f"HTTP {r.status_code}: {r.text[:150]}"
    try:
        vec = r.json()["data"][0]["embedding"]
    except Exception as e:
        return "FAIL", f"parse error: {e}"
    if not vec or len(vec) == 0:
        return "GARBAGE", "empty vector"
    return "OK", f"dim={len(vec)}"


def chat_probe(model_id: str, max_tokens: int = 300) -> tuple[str, str]:
    try:
        r = httpx.post(
            f"{BASE_URL}/v1/chat/completions",
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": "回复两个字：贯通"}],
                "max_tokens": max_tokens,
                "temperature": 0.3,
                "stream": False,
            },
            timeout=120,
        )
    except Exception as e:
        return "FAIL", str(e)[:150]
    if r.status_code != 200:
        return "FAIL", f"HTTP {r.status_code}: {r.text[:150]}"
    try:
        content = r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return "FAIL", f"parse error: {e}"
    if not content:
        return "GARBAGE", "empty content"
    if content.count("�") > 0:
        return "GARBAGE", content[:100]
    return "OK", content[:80]


def main() -> int:
    allow_huge = "--allow-huge" in sys.argv
    wanted = {a for a in sys.argv[1:] if a != "--allow-huge"}

    with open(CONFIG_PATH, "rb") as f:
        cfg = tomllib.load(f)

    role_by_model = {m["id"]: m.get("role", "chat") for m in cfg["models"]}
    placements = [p for p in cfg["placements"] if p["backend_id"] == "mbp-m5-max-128g-omlx-app"]
    if wanted:
        placements = [p for p in placements if p["id"] in wanted]
    placements.sort(key=lambda p: p.get("memory_gb", 0))

    results = []
    for p in placements:
        model_id = p["backend_model_id"]
        placement_id = p["id"]
        mem_gb = p.get("memory_gb", 0)

        free = real_free_gb()
        print(f"\n[{placement_id}] model={model_id} mem={mem_gb}GB free={free:.1f}GB", flush=True)

        if mem_gb > HUGE_THRESHOLD_GB and not allow_huge:
            print(f"  SKIP-HUGE: {mem_gb}GB 超过 {HUGE_THRESHOLD_GB}GB 阈值, 默认不测(传 --allow-huge 覆盖)", flush=True)
            results.append((placement_id, "SKIP-HUGE", f"{mem_gb}GB"))
            continue

        if free < MIN_FREE_GB or free < mem_gb + 8:
            print(f"  SKIP-MEM: 可用 {free:.1f}GB 不足以安全承载 {mem_gb}GB 模型, 停止后续测试", flush=True)
            results.append((placement_id, "SKIP-MEM", f"free={free:.1f}GB need={mem_gb}GB"))
            break

        if lms_generating_locally():
            print("  SKIP-BUSY: LM Studio 本地有模型正在 GENERATING, 让路", flush=True)
            results.append((placement_id, "SKIP-BUSY", "lm studio generating"))
            continue

        role = role_by_model.get(p["model_id"], "chat")
        if role == "embedding":
            verdict, detail = embedding_probe(model_id)
        else:
            verdict, detail = chat_probe(model_id)
        print(f"  {verdict}: {detail}", flush=True)
        results.append((placement_id, verdict, detail))

    print("\n" + "=" * 70)
    print("汇总:")
    by_verdict: dict[str, int] = {}
    for pid, verdict, detail in results:
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
        print(f"  {verdict:10s} {pid:55s} {detail[:60]}")
    print("\n" + " / ".join(f"{k}={v}" for k, v in by_verdict.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
