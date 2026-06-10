"""P34-W5 真实场景测试 — 5 URI 真实场景串联全 ok.

场景: 'P34-W5 真实场景 5/5 ok' 验证
  1. minerva.research 接收问题
  2. minerva.audit 审计结论
  3. ontoderive.derive 推导事实
  4. minerva.draft 生成草稿
  5. iris.transform 数据转换

P34-W5 目标: 5 URI 全部 ok (W2 报告 2/5 ok, 3 错误: ontoderive 包名 / resolver
未注册 / __main__ 缺失). W5 修复后应 5/5 全 ok.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

AGORA_ROOT = Path("/Users/xiamingxing/Workspace/projects/agora")
KAIRON_ROOT = Path("/Users/xiamingxing/Workspace/projects/kairon")


def _invoke_agora_stdio(uri: str, action: str, args: list | None = None, kwargs: dict | None = None) -> dict:
    """跨进程调 agora stdio invoke (不在 omo 进程 import kairon)."""
    args_str = json.dumps(args or [])
    kwargs_str = json.dumps(kwargs or {})
    code = (
        "import json; "
        "from agora.mcp.bos_resolver import invoke_stdio; "
        f"r = invoke_stdio({json.dumps(uri)}, {json.dumps(action)}, args={args_str}, kwargs={kwargs_str}, timeout=8.0); "
        "print(json.dumps(r, ensure_ascii=False, default=str))"
    )
    r = subprocess.run(
        [
            "uv", "run", "--directory", str(AGORA_ROOT),
            "python", "-c", code,
        ],
        capture_output=True, text=True,
        timeout=30,
    )
    if r.returncode != 0:
        return {"status": "error", "error": f"subprocess_failed: {r.stderr[:200]}"}
    out = r.stdout.strip()
    last_line = [ln for ln in out.splitlines() if ln.startswith("{")][-1]
    return json.loads(last_line)


@pytest.mark.integration
def test_real_scenario_p34w5_5of5():
    """W5 真实场景: 5 URI 串联全 ok.

    期望 (W5 目标): 5/5 全 ok
      1. bos://analysis/minerva/research — research 接收
      2. bos://analysis/minerva/audit — audit 结论
      3. bos://analysis/ontoderive/derive — derive 推导
      4. bos://analysis/minerva/draft — draft 草稿
      5. bos://analysis/iris/transform — transform 转换
    """
    scenario = [
        ("bos://analysis/minerva/research", "research", ["P34-W5 真实场景 5/5 ok"], None),
        ("bos://analysis/minerva/audit", "audit", ["P34-W5 audit"], None),
        ("bos://analysis/ontoderive/derive", "derive", ["P34-W5 derivation"], None),
        ("bos://analysis/minerva/draft", "draft", ["P34-W5 draft"], None),
        ("bos://analysis/iris/transform", "transform", [{"input": "P34-W5", "format": "json"}], None),
    ]

    results = []
    for uri, action, args, kwargs in scenario:
        t0 = time.monotonic()
        r = _invoke_agora_stdio(uri, action, args, kwargs)
        elapsed = time.monotonic() - t0
        results.append({
            "uri": uri,
            "action": action,
            "elapsed_s": round(elapsed, 2),
            "status": r.get("status"),
            "result": r.get("result") if r.get("status") == "ok" else r.get("error"),
        })
        # 不应 timeout (跨进程)
        if r.get("error"):
            assert "timeout" not in r["error"].lower(), f"{uri} timed out: {r['error']}"

    ok_count = sum(1 for r in results if r["status"] == "ok")
    error_count = sum(1 for r in results if r["status"] == "error")

    # 详细打印
    print("\n=== P34-W5 真实场景 5/5 串联结果 ===")
    for r in results:
        marker = "OK" if r["status"] == "ok" else "ERR"
        print(f"  [{marker}] {r['uri']:50s} {r['status']:6s} {r['elapsed_s']}s")
    print(f"\n  ok: {ok_count}/{len(results)}, error: {error_count}/{len(results)}")

    # W5 目标: 5/5 全 ok
    assert ok_count == 5, f"W5 目标 5/5 ok, 实得 {ok_count}/5: {results}"


@pytest.mark.integration
def test_real_scenario_research_echo():
    """W5 anchor: 单条 minerva.research 真活."""
    r = _invoke_agora_stdio(
        "bos://analysis/minerva/research",
        "research",
        ["P34-W5 anchor test"],
    )
    assert r.get("status") == "ok", f"minerva.research not ok: {r}"
    assert r.get("uri") == "bos://analysis/minerva/research"
    assert "result" in r
    msg = r["result"].get("message", "")
    assert "research" in msg, f"Unexpected message: {msg}"


@pytest.mark.integration
def test_real_scenario_spawn_lifecycle():
    """W5: 进程池生命周期 — 同一 URI 多次调用, 进程复用 (P34-W1 持久)."""
    r1 = _invoke_agora_stdio(
        "bos://analysis/minerva/research",
        "research",
        ["first call"],
    )
    r2 = _invoke_agora_stdio(
        "bos://analysis/minerva/research",
        "research",
        ["second call"],
    )
    assert r1.get("status") == "ok", f"First call failed: {r1}"
    assert r2.get("status") == "ok", f"Second call failed: {r2}"
    assert r1.get("request_id") != r2.get("request_id")


# ── 摘要 ─────────────────────────────────────────────

@pytest.mark.integration
def test_p34w5_real_scenario_summary():
    """W5 真实场景摘要 — 5/5 全 ok."""
    scenario = [
        ("bos://analysis/minerva/research", "research", ["scenario"]),
        ("bos://analysis/minerva/audit", "audit", []),
        ("bos://analysis/ontoderive/derive", "derive", []),
        ("bos://analysis/minerva/draft", "draft", []),
        ("bos://analysis/iris/transform", "transform", []),
    ]
    counts = {"ok": 0, "error": 0, "total": 0}
    for uri, action, args in scenario:
        r = _invoke_agora_stdio(uri, action, args)
        counts["total"] += 1
        if r.get("status") == "ok":
            counts["ok"] += 1
        else:
            counts["error"] += 1
    print(f"\nP34-W5 真实场景: {counts}")
    assert counts["ok"] == 5, f"W5 目标 5/5 ok, 实得 {counts}"
