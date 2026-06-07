"""LLM 工具调用 BOS URI 桥接 — P37-W2 跨域+LLM 实战.

LLM (Claude/GPT) 通过 tool_use 调 BOS URI 跨域串联.

P37-W2 目标: 把 BOS URI 抽象暴露成 LLM 可理解的 tool 工具集,
让 LLM 通过 tool_use 协议直接 invoke 知识工程/治理/分析域的 URI.

设计:
- 工具 1: ``invoke_bos_uri(uri, args)``  - 调单个 BOS URI
- 工具 2: ``list_bos_uris(domain?)``     - 列已注册 URI (供 LLM 上下文)
- 派发: ``TOOL_DISPATCHER``  - LLM 调用的同步派发表

POC 模式: 不依赖 anthropic/openai 包, 仅做工具 schema + 派发器,
真实场景由 demo 脚本 + LLM API 串联 (mock 模式可纯本地跑通).

P32 收官约束: 不改 agora 核心, 不重启 omo daemon, 0 破坏性操作.
本模块纯加法, 只读 BOS URI 注册表, 不写.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# ── BOS URI 验证/解析 ──────────────────────────────────────
# 复用 omo.omo_bos 北星验证, 避免重复实现 URI 解析逻辑
try:
    from omo.omo_bos import validate_bos_uri, parse_bos_uri, load_registry
except ImportError:  # pragma: no cover - 路径旁路场景
    # 允许脱离 PYTHONPATH 单测, 加 src 兜底
    _OMO_SRC = Path(__file__).resolve().parents[0]
    if str(_OMO_SRC) not in sys.path:
        sys.path.insert(0, str(_OMO_SRC))
    from omo.omo_bos import validate_bos_uri, parse_bos_uri, load_registry  # type: ignore[no-redef]


# ── 工具 schema (Anthropic tool_use 格式) ────────────────────


def bos_uri_tool_schema() -> list[dict[str, Any]]:
    """返回 LLM tool_use 工具的 schema (Anthropic 格式).

    LLM 看到这个 schema 后, 会决定在对话中调
    ``invoke_bos_uri`` 或 ``list_bos_uris`` 工具.

    OpenAI function-calling 格式: 把 ``input_schema`` 改成 ``parameters``
    并补 ``"strict": True``, 字段相同.
    """
    return [
        {
            "name": "invoke_bos_uri",
            "description": (
                "调用 BOS (Banyan Object Service) URI 执行知识工程/治理/分析/能力操作. "
                "BOS URI 格式: bos://<domain>/<package>/<action>. "
                "5 个 domain: memory (知识存储/摄取), governance (治理/门控), "
                "analysis (推演/分析), persona (数字人/桥接), capability (工具/能力). "
                "可先用 list_bos_uris 查可用 URI."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "uri": {
                        "type": "string",
                        "description": (
                            "BOS URI, 格式 bos://<domain>/<package>/<action>. "
                            "domain ∈ memory|governance|analysis|persona|capability. "
                            "package/action 是 kebab-case 小写."
                        ),
                        "pattern": (
                            r"^bos://(memory|governance|analysis|persona|capability)"
                            r"/[a-z][a-z0-9-]*[a-z0-9]?/[a-z][a-z0-9-]*[a-z0-9]?$"
                        ),
                    },
                    "args": {
                        "type": "object",
                        "description": (
                            "URI 调用参数 (如 query, topic, path, source 等). "
                            "schema 因 URI 而异, 优先读 list_bos_uris 的 description."
                        ),
                    },
                },
                "required": ["uri"],
            },
        },
        {
            "name": "list_bos_uris",
            "description": (
                "列出已注册的 BOS URI, 可按 domain 过滤. "
                "返回: 每条含 uri/domain/package/action/description. "
                "用来给 LLM 选可用 URI."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "enum": [
                            "memory",
                            "governance",
                            "analysis",
                            "persona",
                            "capability",
                        ],
                        "description": "可选, 按 domain 过滤",
                    },
                },
            },
        },
    ]


# ── 工具实现 (派发器 target) ────────────────────────────────


async def invoke_bos_uri_tool(uri: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """LLM 调 BOS URI 工具入口.

    返回: 标准 dict (JSON 序列化友好), 供 LLM 二次 round 解析.

    失败语义: 永不抛异常, 总是 dict (LLM 不会崩溃).
    """
    args = args or {}

    # 1) 北星验证
    valid, err = validate_bos_uri(uri)
    if not valid:
        return {"error": err, "uri": uri, "status": "invalid_uri"}

    # 2) 解析
    try:
        parsed = parse_bos_uri(uri)
    except ValueError as exc:  # pragma: no cover - validate 已守
        return {"error": str(exc), "uri": uri, "status": "parse_failed"}

    # 3) agora 接管 (走 MCP 跨进程, P32 上线的统一入口)
    # P32 架构: agora 独立 venv 跨进程通信, 不 in-process import
    # (因 agora 依赖链含 websockets/aiohttp, 拉进 omo 进程会污染 omo 依赖面)
    sub_result = await _resolve_via_agora_subprocess(uri, args)
    if sub_result is not None:
        return {
            "uri": uri,
            "domain": parsed["domain"],
            "package": parsed["package"],
            "action": parsed["action"],
            "status": "resolved",
            "transport": "agora_subprocess",
            "result": sub_result,
        }

    # subprocess 全失败 (agora venv 不可用 / URI 不在 11 POC registry)
    return {
        "uri": uri,
        "domain": parsed["domain"],
        "package": parsed["package"],
        "action": parsed["action"],
        "status": "agora_unavailable",
        "note": "agora subprocess 派发失败 (URI 不在 11 POC registry 或 venv 不可用)",
    }


async def _resolve_via_agora_subprocess(uri: str, args: dict[str, Any]) -> dict[str, Any] | None:
    """Subprocess 调 agora venv 跑 resolve_bos_uri (P32 跨进程架构, P42-W2 落地).

    设计理由:
      - agora 是独立 venv, 含 websockets/aiohttp 等重依赖
      - omo 进程不 import agora (避免污染 omo 依赖面, 也避免 agora→omo 循环依赖)
      - 每次调用 spawn 一次 subprocess (POC 阶段够用; 后续 P43+ 可改长驻进程池)

    返回:
      - dict: agora resolve_bos_uri 的 result 字段
      - None: subprocess 失败 (uv/venv 不可用, URI 不在 registry, JSON parse 失败)
    """
    try:
        from omo.omo_paths import PROJECTS_DIR

        _AGORA_PROJECT = PROJECTS_DIR / "agora"
    except Exception:
        return None

    if not (_AGORA_PROJECT / "pyproject.toml").exists():
        return None

    # 内联 Python: import resolve_bos_uri, run, dump JSON to stdout
    # args 通过临时文件传 (避免命令行转义)
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump({"uri": uri, "args": args}, f, ensure_ascii=False)
        args_file = f.name

    inline_py = (
        "import asyncio, json, sys; "
        f"from agora.mcp.bos_resolver import resolve_bos_uri; "
        f"p = {args_file!r}; "
        "data = json.load(open(p)); "
        "r = asyncio.run(resolve_bos_uri(data['uri'], **data.get('args') or {})); "
        "sys.stdout.write(json.dumps(r, ensure_ascii=False))"
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            "uv",
            "run",
            "--project",
            str(_AGORA_PROJECT),
            "python",
            "-c",
            inline_py,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except (subprocess.SubprocessError, asyncio.TimeoutError, OSError) as exc:
        return {"_subprocess_error": f"{type(exc).__name__}: {exc}"}
    finally:
        try:
            Path(args_file).unlink(missing_ok=True)
        except OSError:
            pass

    if proc.returncode != 0:
        return {"_subprocess_error": stderr.decode("utf-8", errors="replace")}

    try:
        return json.loads(stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def list_bos_uris_tool(domain: str | None = None) -> dict[str, Any]:
    """列出已注册 URI (走本地 bos-registry.json via load_registry)."""
    try:
        regs = load_registry()
    except Exception as exc:
        return {"error": f"registry_load_failed: {exc}", "count": 0, "uris": []}

    if domain:
        regs = [r for r in regs if r.get("domain") == domain]

    # 压缩字段供 LLM 读
    compact = [
        {
            "uri": r.get("uri"),
            "domain": r.get("domain"),
            "package": r.get("package"),
            "action": r.get("action"),
            "description": r.get("description", ""),
        }
        for r in regs
    ]
    return {"count": len(compact), "uris": compact}


# ── 派发器 (供 demo + 真 API 模式共用) ──────────────────────


def _dispatch_sync(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """同步派发 (供不支持 async 的 LLM client 用)."""
    if name == "invoke_bos_uri":
        return asyncio.run(invoke_bos_uri_tool(args["uri"], args.get("args")))
    if name == "list_bos_uris":
        return list_bos_uris_tool(args.get("domain"))
    return {"error": f"unknown_tool: {name}"}


TOOL_DISPATCHER: dict[str, Any] = {
    "invoke_bos_uri": _dispatch_sync,  # 闭包内调 asyncio.run
    "list_bos_uris": _dispatch_sync,
}


# ── 自测 (直接 python omo_llm_bos_bridge.py) ───────────────


def _self_test() -> int:
    """快速自测: 验证 schema + 派发器本地闭环."""
    print("=" * 60)
    print("omo.llm_bos_bridge 自测")
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
    print("[OK] omo.llm_bos_bridge 自测全过")
    return 0


if __name__ == "__main__":
    sys.exit(_self_test())
