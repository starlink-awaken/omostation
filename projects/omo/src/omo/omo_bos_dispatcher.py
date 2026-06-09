"""P59-W2 omo BOS dispatcher — 同步派发器 + 自测.

P37-W2 era: 原 omo_llm_bos_bridge.py 内含 TOOL_DISPATCHER + _dispatch_sync + _self_test
P59-W2: 抽出到独立 module, 单一职责: 派发 + 自测.

facade (omo_llm_bos_bridge.py) 留: schema + invoke/list 入口 + backward compat re-export.

W3: 集成 omo_bos_metrics — 每次 invoke 自动记录 (uri, status, elapsed_ms).
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any

from omo.omo_llm_bos_bridge import (  # type: ignore[import-not-found]
    bos_uri_tool_schema,
    invoke_bos_uri_tool,
    list_bos_uris_tool,
)


def _dispatch_sync(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """同步派发 (供不支持 async 的 LLM client 用)."""
    if name == "invoke_bos_uri":
        return asyncio.run(invoke_bos_uri_tool(args["uri"], args.get("args")))
    if name == "list_bos_uris":
        return list_bos_uris_tool(args.get("domain"))
    return {"error": f"unknown_tool: {name}"}


def _instrumented_invoke(args: dict[str, Any]) -> dict[str, Any]:
    """W3 instrumented invoke — 包 time_invoke() 自动记录 metrics.

    失败也不抛: 异常被转成 status="error" 入 metric, 然后 re-raise 让上层处理.
    """
    uri = args.get("uri", "")
    try:
        from omo.omo_bos_metrics import time_invoke
    except ImportError:
        # metrics 模块不可用, 退化到无 instrument
        return _dispatch_sync("invoke_bos_uri", args)

    with time_invoke(uri, transport="dispatcher") as timer:
        result = _dispatch_sync("invoke_bos_uri", args)
    # 把 dispatch 内的 status 透传到 metric
    status = result.get("status", "error") if isinstance(result, dict) else "error"
    if status in ("resolved", "agora_unavailable", "invalid_uri",
                  "endpoint_missing", "timeout", "error"):
        timer.set_status(status, error=result.get("error", "") if isinstance(result, dict) else "")
    else:
        timer.set_status("error", error=f"unknown_status: {status}")
    return result


TOOL_DISPATCHER: dict[str, Any] = {
    # P59-W0: lambda 包装 (修复 P37-era _self_test 单 arg 调用 bug)
    "invoke_bos_uri": _instrumented_invoke,
    "list_bos_uris": lambda args: _dispatch_sync("list_bos_uris", args),
}


def _self_test() -> int:
    """快速自测: 验证 schema + 派发器本地闭环."""
    print("=" * 60)
    print("omo.bos_dispatcher 自测")
    print("=" * 60)

    # 1) schema
    schema = bos_uri_tool_schema()
    assert len(schema) == 2, "schema 必须是 2 个工具"
    names = {s["name"] for s in schema}
    assert names == {"invoke_bos_uri", "list_bos_uris"}, f"工具名错: {names}"
    print(f"[OK] schema: 2 tools, names={names}")

    # 2) list
    r = TOOL_DISPATCHER["list_bos_uris"]({"domain": "memory"})
    print(f"[OK] list_bos_uris(memory): count={r.get('count', '?')}")
    assert "count" in r, "list 必须返回 count"

    # 3) invoke (memory/kos/search)
    r = TOOL_DISPATCHER["invoke_bos_uri"](
        {"uri": "bos://memory/kos/search", "args": {"query": "kairon commits"}}
    )
    print(f"[OK] invoke bos://memory/kos/search: status={r.get('status', '?')}")
    assert r.get("status") in ("resolved", "agora_unavailable"), (
        f"invoke 状态错: {r}"
    )

    # 4) invoke (invalid)
    r = TOOL_DISPATCHER["invoke_bos_uri"]({"uri": "bos://bad/foo/bar"})
    print(f"[OK] invoke invalid: status={r.get('status', '?')}")
    assert r.get("status") == "invalid_uri", f"invalid 状态错: {r}"

    # 5) invoke (5 跨域)
    uris = [
        ("bos://memory/kos/search", {"query": "kairon commits"}),
        ("bos://analysis/minerva/research", {"topic": "kairon 提交趋势"}),
        ("bos://analysis/minerva/draft", {"topic": "kairon 提交趋势"}),
        ("bos://analysis/iris/transform", {}),
        ("bos://capability/forge/list-tools", {}),
    ]
    for uri, args in uris:
        r = TOOL_DISPATCHER["invoke_bos_uri"]({"uri": uri, "args": args})
        print(f"  - {uri}: status={r.get('status', '?')}")
    print()
    print("[OK] omo.bos_dispatcher 自测全过")
    return 0


if __name__ == "__main__":
    sys.exit(_self_test())
