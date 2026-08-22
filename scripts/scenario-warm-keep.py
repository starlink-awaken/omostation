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
    # (backend_model_id, 逻辑用途, memory_gb, role) — role 决定探测/保活
    # 走 chat 端点还是 embeddings 端点(2026-08-22 实测: embedding 角色
    # 模型打 /v1/chat/completions 会 400 "not an LLM/chat model")。
    ("embedding", "embedding 场景默认模型, 已 resident, 复核用", 8.0, "embedding"),
    ("vision", "vision 场景默认模型, 体积小, 低风险高频", 6.0, "chat"),
    ("coding", "coding 场景默认模型, 已验证响应正常且稳定", 24.0, "chat"),
    ("qwen-3.8-27b", "chat 场景默认模型, 已验证响应正常", 24.0, "chat"),
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


def _probe(model_id: str, role: str, timeout: float) -> int | None:
    """返回 HTTP 状态码, 网络层失败返回 None。role 决定走哪个端点
    (2026-08-22 实测: embedding 角色打 chat 端点会 400)。"""
    try:
        if role == "embedding":
            r = httpx.post(f"{BASE_URL}/v1/embeddings", json={"model": model_id, "input": "hi"}, timeout=timeout)
        else:
            r = httpx.post(
                f"{BASE_URL}/v1/chat/completions",
                json={"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                timeout=timeout,
            )
        return r.status_code
    except httpx.TimeoutException:
        return None
    except Exception:
        return None


def is_warm(model_id: str, role: str) -> bool:
    # oMLX App 没有 lms ps 那样的"已加载"状态查询, 用一次极短超时的探测
    # 请求判断是否已温着(冷启动会显著更慢, 这里只关心"能否快速响应",
    # 不消耗额外资源去验证生成内容本身)。
    return _probe(model_id, role, timeout=3.0) == 200


def main() -> int:
    if lms_generating_locally():
        print("SKIP-BUSY: LM Studio 本地有模型正在 GENERATING, 让路")
        return 0

    # 按体积从小到大尝试, 每个目标独立用"此刻实时可用内存"判断 —— 避免
    # 一个大模型的内存需求把排在它前面、原本能轻松预热的小模型也一起
    # 卡死。每次真正触发加载后重新测量内存, 因为 omlx-app 的加载会实时
    # 占用内存, 后续目标的判断必须基于最新状态。
    for model_id, note, mem_gb, role in sorted(WARM_TARGETS, key=lambda t: t[2]):
        # 先确认是否已温着 —— 这一步只是个短超时探测, 几乎不占内存,
        # 必须排在内存预算检查之前。否则"已加载但此刻空闲内存偏紧"的
        # 模型会被误判为需要新触发加载而 SKIP, 白白浪费一次已有的热身。
        if is_warm(model_id, role):
            print(f"OK: {model_id} 已温着 ({note})")
            continue

        free = real_free_gb()
        if free < MIN_FREE_GB or free < mem_gb + 8:
            print(f"SKIP-MEM: {model_id} 未温着, 需要 ~{mem_gb}GB 触发新加载, 可用 {free:.1f}GB 不足, 跳过")
            continue

        status = _probe(model_id, role, timeout=90.0)
        print(f"{'WARMED' if status == 200 else 'FAIL'}: {model_id} status={status}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
