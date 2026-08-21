#!/usr/bin/env python3
"""深度注册审计：对 config.toml 里每个模型的每个 placement 发一次真实生成请求，
检测乱码/空输出/加载失败。模型清单从 `omlxc models list --json` 动态读取，
不硬编码，config.toml 增删模型后无需改这个脚本。

比 pipeline-watchdog.sh 贵(真实加载+生成)，不放进 5 分钟一次的快速探测层。
建议时机: 改完 config.toml 之后手动跑一次；或按需定期跑。
"""
import json
import os
import re
import subprocess
import sys
import time

import httpx

CONFIG_PATH = os.path.expanduser("~/.config/omlxc/config.toml")

PROMPT = "用一句话介绍量子计算，直接回答不要客套。"
BACKEND_BASE_URL = {
    "mbp-m5-max-128g-lm_studio": "http://127.0.0.1:1234",
    "mbp-m5-max-128g-omlx-app": "http://127.0.0.1:8000",
    "mac-mini-m4-24g-lm_studio": None,  # 远程节点，跳过(需要 Tailscale 可达)
    "y7000p-rtx4070-8g-lm_studio": None,
}


def get_models() -> list[dict]:
    out = subprocess.run(["omlxc", "models", "list", "--json"], capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    return data["data"]["items"]


def load_placement_backend_model_ids() -> dict[str, str]:
    """config.toml 里 placement_id -> backend_model_id 的映射
    (omlxc CLI 的 JSON 输出不带 backend_model_id，只能读 TOML)。"""
    content = open(CONFIG_PATH).read()
    blocks = re.split(r"\n(?=\[\[placements\]\])", content)
    mapping = {}
    for b in blocks:
        if not b.strip().startswith("[[placements]]"):
            continue
        pid = re.search(r'id = "([^"]+)"', b)
        bmid = re.search(r'backend_model_id = "([^"]+)"', b)
        if pid and bmid:
            mapping[pid.group(1)] = bmid.group(1)
    return mapping


def load_chat_capable_model_ids() -> set[str]:
    """config.toml 里 role != "chat" 的模型(embedding/rerank)不支持 /v1/chat/completions,
    发请求测这些只会拿到 400，不代表模型坏了。"""
    content = open(CONFIG_PATH).read()
    blocks = re.split(r"\n(?=\[\[models\]\])", content)
    ids = set()
    for b in blocks:
        if not b.strip().startswith("[[models]]"):
            continue
        mid = re.search(r'id = "([^"]+)"', b)
        role = re.search(r'role = "([^"]+)"', b)
        if mid and role and role.group(1) == "chat":
            ids.add(mid.group(1))
    return ids


def is_garbage(text: str) -> bool:
    if not text.strip():
        return True
    ok = sum(1 for c in text if c.isalnum() or c.isspace() or ord(c) > 0x4E00)
    return ok / max(len(text), 1) < 0.6


def bench(base: str, model_id: str, max_tokens: int = 120, timeout: float = 90) -> dict:
    payload = {"model": model_id, "messages": [{"role": "user", "content": PROMPT}],
               "max_tokens": max_tokens, "temperature": 0.3, "stream": True}
    t0 = time.perf_counter()
    ttft = None
    parts = []
    try:
        with httpx.stream("POST", f"{base}/v1/chat/completions", json=payload, timeout=timeout) as r:
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
    return {"ok": True, "ttft_ms": round(ttft * 1000, 1) if ttft else None, "sample": full[:60], "garbage": is_garbage(full)}


def main():
    models = get_models()
    backend_model_ids = load_placement_backend_model_ids()
    chat_capable = load_chat_capable_model_ids()
    rows = []
    for m in models:
        if m["id"] not in chat_capable:
            continue
        for p in m.get("placement_states", []):
            backend_id = p["backend_id"]
            base = BACKEND_BASE_URL.get(backend_id)
            if base is None:
                continue
            backend_model_id = backend_model_ids.get(p["placement_id"])
            if not backend_model_id:
                continue
            r = bench(base, backend_model_id)
            if r.get("ok"):
                status = "GARBAGE" if r.get("garbage") else "OK"
            else:
                status = "FAIL"
            rows.append((m["id"], backend_id, status, r.get("ttft_ms"), r.get("sample", r.get("error", ""))))
            print(f"{m['id']:<32} {backend_id:<28} {status:<8} ttft={r.get('ttft_ms')} {r.get('sample', r.get('error',''))!r}", flush=True)
            time.sleep(2)

    bad = [row for row in rows if row[2] in ("GARBAGE", "FAIL")]
    print(f"\n{'='*70}")
    print(f"共测 {len(rows)} 个 placement，{len(bad)} 个异常(GARBAGE/FAIL)")
    for row in bad:
        print(f"  {row[0]} / {row[1]}: {row[2]}")
    sys.exit(1 if any(r[2] == "GARBAGE" for r in rows) else 0)


if __name__ == "__main__":
    main()
