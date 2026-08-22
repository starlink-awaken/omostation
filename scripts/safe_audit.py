#!/usr/bin/env python3
"""内存安全的 lm_studio 系 placement 审计。

方法学: 内存前置检查 -> 受控加载(显式 -c) -> 真实小请求验证 -> 立即卸载。
绝不触碰 GENERATING 状态的模型(硬编码保护)。real_free_gb 低于阈值时自动刹车。
覆盖 MBP 本地 + mac-mini/y7000p 的 SSH 受控通道, 共三个物理节点的 lm_studio backend。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import tomllib

import httpx

# 清理代理环境变量: httpx 继承 shell 的 SOCKS/HTTP 代理变量会导致对内网
# tailscale IP 的请求被错误地经代理转发 (且 SOCKS 需要额外的 socksio 包,
# 未装则直接报错) —— 2026-08-22 实测 mythos--mac-mini 因此假性 FAIL。
for _proxy_var in ("all_proxy", "ALL_PROXY", "http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
    os.environ.pop(_proxy_var, None)

CONFIG_PATH = "/Users/xiamingxing/.config/omlxc/config.toml"
MIN_FREE_GB = 12.0
LMS_LOCAL = "/Users/xiamingxing/.local/bin/lms"


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


def lms_ps(ssh_target: str | None) -> list[dict]:
    if ssh_target:
        argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", ssh_target, "lms ps --json"]
    else:
        argv = [LMS_LOCAL, "ps", "--json"]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=20)
    try:
        return json.loads(result.stdout)
    except Exception:
        return []


def any_generating(ssh_target: str | None) -> bool:
    # omlxc daemon 自己的探测循环(每 probe_interval_seconds 一次)会触发一次
    # 真实短推理, 可能被单次查询误判为"busy"。连续两次(间隔 3s)都 generating
    # 才判定为真忙, 避免撞上探测窗口的假阳性。
    if not any(m.get("status") == "generating" for m in lms_ps(ssh_target)):
        return False
    time.sleep(3)
    return any(m.get("status") == "generating" for m in lms_ps(ssh_target))


def lms_load(ssh_target: str | None, model_id: str, context: int, ttl: int) -> tuple[bool, str]:
    args = f"lms load {model_id!r} -c {context} --parallel 1 --ttl {ttl} -y"
    if ssh_target:
        argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", ssh_target, args]
    else:
        argv = [LMS_LOCAL, "load", model_id, "-c", str(context), "--parallel", "1", "--ttl", str(ttl), "-y"]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=180)
    # 字符串匹配 "loaded successfully" 曾经不可靠: 进度条 spinner 的 ANSI
    # 控制序列有时会把确认文字挤出/打断输出流, 即便模型其实已加载成功
    # (2026-08-22 实测: gemma-4-e2b/ornith-9b/vision 三个都误判 FAIL,
    # 但 lms ps 显示它们其实是 IDLE 已加载)。改为直接查 lms ps 确认真相,
    # 不再信任子进程 stdout 里的文字匹配。
    ok = already_loaded(ssh_target, model_id)
    return ok, (result.stdout[-300:] if result.stdout else result.stderr[-300:])


def lms_unload(ssh_target: str | None, model_id: str) -> None:
    if ssh_target:
        argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", ssh_target, f"lms unload {model_id!r}"]
    else:
        argv = [LMS_LOCAL, "unload", model_id]
    subprocess.run(argv, capture_output=True, text=True, timeout=30)


def already_loaded(ssh_target: str | None, model_id: str) -> bool:
    return any(m.get("identifier") == model_id or m.get("modelKey") == model_id for m in lms_ps(ssh_target))


def chat_probe(base_url: str, model_id: str) -> tuple[str, str]:
    """returns (verdict, detail): OK / GARBAGE / FAIL"""
    try:
        r = httpx.post(
            f"{base_url}/v1/chat/completions",
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": "回复两个字：贯通"}],
                "max_tokens": 200,
                "temperature": 0.3,
                "stream": False,
            },
            timeout=90,
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
    if len(content) > 400 or content.count("�") > 0:
        return "GARBAGE", content[:100]
    return "OK", content[:80]


def main() -> int:
    with open(CONFIG_PATH, "rb") as f:
        cfg = tomllib.load(f)

    backends = {b["id"]: b for b in cfg["backends"]}
    targets = {
        "mbp-m5-max-128g-lm_studio": None,
        "mac-mini-m4-24g-lm_studio": "xiamingxing@100.99.210.78",
        "y7000p-rtx4070-8g-lm_studio": "xia@100.64.43.36",
    }

    placements = [p for p in cfg["placements"] if p["backend_id"] in targets]
    if len(sys.argv) > 1:
        wanted = set(sys.argv[1:])
        placements = [p for p in placements if p["id"] in wanted]
    placements.sort(key=lambda p: p.get("memory_gb", 0))

    results = []
    for p in placements:
        backend_id = p["backend_id"]
        backend = backends[backend_id]
        ssh_target = targets[backend_id]
        base_url = backend["base_url"]
        model_id = p["backend_model_id"]
        placement_id = p["id"]
        mem_gb = p.get("memory_gb", 0)
        ctx = min(p.get("context_limit", 4096), 8192)

        free = real_free_gb()
        print(f"\n[{placement_id}] model={model_id} mem={mem_gb}GB free={free:.1f}GB", flush=True)

        if free < MIN_FREE_GB:
            print(f"  SKIP-MEM: 真实可用 {free:.1f}GB < 安全阈值 {MIN_FREE_GB}GB, 停止后续测试", flush=True)
            results.append((placement_id, "SKIP-MEM", f"free={free:.1f}GB"))
            break

        if any_generating(ssh_target):
            print("  SKIP: 该 backend 有模型正在 GENERATING, 不打扰", flush=True)
            results.append((placement_id, "SKIP-BUSY", "generating in progress"))
            continue

        pre_loaded = already_loaded(ssh_target, model_id)
        if not pre_loaded:
            ok, detail = lms_load(ssh_target, model_id, ctx, ttl=300)
            if not ok:
                print(f"  FAIL(load): {detail}", flush=True)
                results.append((placement_id, "FAIL", f"load failed: {detail}"))
                continue

        verdict, detail = chat_probe(base_url, model_id)
        print(f"  {verdict}: {detail}", flush=True)
        results.append((placement_id, verdict, detail))

        if not pre_loaded:
            lms_unload(ssh_target, model_id)
            time.sleep(1)

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
