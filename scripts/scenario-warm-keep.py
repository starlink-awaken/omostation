#!/usr/bin/env python3
"""高频场景模型保活: 定期对指定的 omlx-app placement 发一个轻量请求,
触发 ensure_loaded(未加载则加载) 并因最近访问而不被 idle_ttl 淘汰。

背景 (2026-08-22): placement.resident=True 这个字段虽然在类型系统里
"活着"(PlacementTarget 引用它), 但真正执行"周期性检查+ensure_loaded"
的 reconcile 循环从未被 daemon 组装流程(composition.py)实例化启动 ——
和 remote_resident 是同一类"写好了但没接入"的模式。omlx-app 没有显式
卸载 CLI, 无法像 lm_studio 系那样用 --ttl 精确控制, 只能靠"定期戳一下"
的保活模式让高频模型不因 idle_ttl(1800s) 过期而冷启动。

刻意只覆盖 coding 这一个最高频的开发场景模型, 不做大范围预热 ——
多个大模型同时驻留是今天已实测过的真实风险(qwen3-coder-next+qwythos
同时驻留曾把内存打到 510MB), 保活的价值必须和内存压力仔细权衡。
"""

from __future__ import annotations

import os
import subprocess
import sys

import httpx

for _proxy_var in ("all_proxy", "ALL_PROXY", "http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
    os.environ.pop(_proxy_var, None)

BASE_URL = "http://127.0.0.1:8000"
MIN_FREE_GB = 20.0  # 比常规 12GB 红线更保守: 这是主动预热, 不是响应真实请求
WARM_TARGETS = [
    # (backend_model_id, 逻辑用途)
    ("coding", "coding 场景默认模型, 已验证响应正常且稳定"),
]


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
    import json

    result = subprocess.run(
        ["/Users/xiamingxing/.local/bin/lms", "ps", "--json"], capture_output=True, text=True, timeout=15
    )
    try:
        rows = json.loads(result.stdout)
    except Exception:
        return False
    return any(r.get("status") == "generating" for r in rows)


def is_warm(model_id: str) -> bool:
    try:
        r = httpx.get(f"{BASE_URL}/v1/models", timeout=8)
    except Exception:
        return False
    if r.status_code != 200:
        return False
    # oMLX App 没有 lms ps 那样的"已加载"状态查询, 用一次极短的探测请求
    # 判断是否已温着(冷启动会显著更慢, 但这里只关心"能否快速拿到首个
    # token", 用短超时区分冷/热而不消耗额外资源去真的验证)。
    try:
        r = httpx.post(
            f"{BASE_URL}/v1/chat/completions",
            json={"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
            timeout=3.0,
        )
        return r.status_code == 200
    except httpx.TimeoutException:
        return False
    except Exception:
        return False


def main() -> int:
    free = real_free_gb()
    if free < MIN_FREE_GB:
        print(f"SKIP-MEM: 可用 {free:.1f}GB < 保守阈值 {MIN_FREE_GB}GB, 本轮不预热")
        return 0

    if lms_generating_locally():
        print("SKIP-BUSY: LM Studio 本地有模型正在 GENERATING, 让路")
        return 0

    for model_id, note in WARM_TARGETS:
        if is_warm(model_id):
            print(f"OK: {model_id} 已温着 ({note})")
            continue
        try:
            r = httpx.post(
                f"{BASE_URL}/v1/chat/completions",
                json={"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                timeout=90,
            )
            print(f"{'WARMED' if r.status_code == 200 else 'FAIL'}: {model_id} status={r.status_code}")
        except Exception as e:
            print(f"FAIL: {model_id} {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
