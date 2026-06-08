# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""Council 多智能体审议 — @Sage/@Devil/@Builder 辩论解决冲突。"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[6]
DB_PATH = str(PROJECT_ROOT / "data" / "db" / "organs" / "memory" / "fact_graph.db")
REPORT_DIR = PROJECT_ROOT / "data" / "scenario2"


LMSTUDIO_URL = "http://localhost:1234/v1/chat/completions"
LMSTUDIO_MODEL = "qwen/qwen3.6-27b"

# ---------------------------------------------------------------------------
# LLM provider — try kairon engine_llm, fall back to httpx direct
# ---------------------------------------------------------------------------
_HAS_KAIRON_LLM = False
try:
    from runtime.executor.engine_llm import CompletionOptions
    from runtime.executor.engine_llm import ProviderManager as KaironProviderManager
    _HAS_KAIRON_LLM = True
except ImportError:
    pass


def _call_lmstudio(prompt: str, timeout: int = 180) -> str | None:
    """直接调 LMStudio API（OpenAI 兼容格式），空响应自动重试一次。"""
    try:
        import time as _time

        import httpx

        payload = {
            "model": LMSTUDIO_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 8192,
            "reasoning_effort": "none",
        }
        for attempt in range(2):
            resp = httpx.post(LMSTUDIO_URL, json=payload, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                msg = data.get("choices", [{}])[0].get("message", {})
                content = msg.get("content", "")
                # 空 content 时尝试从 reasoning_content 尾部提取 JSON（推理吃光token预算）
                if (not content or not content.strip()) and msg.get("reasoning_content"):
                    content = msg.get("reasoning_content", "")
                if content and content.strip():
                    return content
            if attempt == 0:
                _time.sleep(2)
        return None
    except (ImportError, ValueError, httpx.HTTPError):
        return None


async def _call_kairon_llm(prompt: str) -> str | None:
    """尝试通过 kairon engine_llm ProviderManager 调用 LLM。"""
    if not _HAS_KAIRON_LLM:
        return None
    try:
        pm = KaironProviderManager()
        try:
            provider = pm.get()
        except ValueError:
            # No provider registered — fall through to direct httpx
            return None
        options = CompletionOptions(temperature=0.7, max_tokens=8192)
        result = await provider.complete(prompt, options)
        if result and result.content and result.content.strip():
            return result.content
    except Exception:
        pass
    return None


async def run_llm_council(conflict: dict) -> dict[str, Any]:
    """运行三角色辩论 — LMStudio → kairon LLM → 确定性 fallback。"""
    sub = conflict["sub"]
    pred = conflict["pred"]
    facts = conflict["facts"]

    prompt_lines = [
        f"冲突检测: 实体 '{sub}' 在谓词 '{pred}' 上有 {len(facts)} 个不同断言。",
        "",
    ]
    for i, f in enumerate(facts, 1):
        prompt_lines.append(f"  断言 {i}: \"{f['obj']}\" (来源: {f['source']}, 置信度: {f['confidence']})")
    prompt_lines.extend([
        "",
        "请综合评估两个断言的可信度和适用范围，给出每个断言的合理权重（0-1，合计1.0）。",
        "权重应基于来源可靠性和内容合理性。",
        "",
        "以JSON格式回复: {\"resolution\": \"...\", \"weights\": {\"断言1\": 0.0, \"断言2\": 0.0}, \"rationale\": \"...\"}",
    ])

    prompt = "\n".join(prompt_lines)

    # 1. 先试 LMStudio 直连
    content = _call_lmstudio(prompt)

    # 2. 如果 LMStudio 没响应，试 kairon ProviderManager
    if not content or "[MOCK]" in content:
        content = await _call_kairon_llm(prompt)

    # 3. 如果都失败，返回 None 让上层 fallback
    if not content or "[MOCK]" in content:
        return None  # type: ignore[return-value]

    # 尝试从回复中提取 JSON
    import re
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if json_match:
        try:
            result = json.loads(json_match.group())
            return {
                "sub": sub,
                "pred": pred,
                "method": "llm_council",
                "resolution": result.get("resolution", content[:300]),
                "weights": result.get("weights", {}),
                "rationale": result.get("rationale", ""),
            }
        except json.JSONDecodeError:
            pass

    return {
        "sub": sub, "pred": pred, "method": "llm_council",
        "resolution": content[:300], "weights": {}, "rationale": content[:200],
    }


def run_deterministic_council(conflict: dict) -> dict[str, Any]:
    """确定性规则裁决 — 基于置信度的 fallback。"""
    facts = conflict["facts"]
    total_confidence = sum(f.get("confidence", 0.5) for f in facts)

    weights: dict[str, float] = {}
    for i, f in enumerate(facts):
        label = f"断言{i+1}"
        weights[label] = round(f.get("confidence", 0.5) / total_confidence, 3)

    best = max(facts, key=lambda x: x.get("confidence", 0))

    confidence_details = ", ".join(
        f'{f["source"]}={f["confidence"]}' for f in facts
    )
    return {
        "sub": conflict["sub"], "pred": conflict["pred"],
        "method": "deterministic_fallback",
        "resolution": f"基于置信度加权: 最高权重断言为「{best['obj'][:50]}」(来源: {best['source']})",
        "weights": weights,
        "rationale": f"置信度: {confidence_details}。最高置信度来源优先。",
    }


async def deliberate_conflicts(conflicts: list[dict]) -> list[dict[str, Any]]:
    results = []
    for conflict in conflicts:
        print(f"\n📋 审议冲突: {conflict['sub']} — {conflict['pred']}")
        result = None
        try:
            result = await run_llm_council(conflict)
        except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
            print(f"  ⚠️  LLM 异常: {exc}")

        if result is None:
            print("  ⚠️  LLM 未返回有效结果，回退到确定性裁决")
            result = run_deterministic_council(conflict)
            print("  ✅ 确定性裁决完成")
        else:
            print("  ✅ LLM Council 完成")
        results.append(result)
    return results


def generate_report(results: list[dict[str, Any]]) -> str:
    timestamp = datetime.now(UTC).isoformat()
    lines = [
        "# @Council 审议报告: 个人知识冲突",
        "",
        f"**时间:** {timestamp}",
        f"**决议数:** {len(results)}",
        "",
        "---",
        "",
    ]

    for i, r in enumerate(results, 1):
        lines.extend([
            f"## 决议 {i}: {r['sub']} — {r['pred']}",
            "",
            f"**方法:** {r['method']}",
            f"**决议:** {r['resolution']}",
            "",
            "**权重分配:**",
        ])
        for label, weight in r.get("weights", {}).items():
            lines.append(f"- {label}: **{weight}**")
        lines.append("")
        if r.get("rationale"):
            lines.append(f"**推理过程:** {r['rationale']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


async def main() -> None:
    import sys as _sys
    _sys.path.insert(0, str(PROJECT_ROOT))

    from runtime.executor.workflows.scenario2.detect_conflicts import get_conflict_via_definitions

    mode = _sys.argv[1] if len(_sys.argv) > 1 else "scenario"

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if mode == "scenario":
        conflicts = get_conflict_via_definitions(conn)
    else:
        from runtime.executor.workflows.scenario2.detect_conflicts import get_all_conflicts
        conflicts = get_all_conflicts(conn)

    conn.close()

    if not conflicts:
        print("✅ 无冲突需要审议。")
        return

    print(f"发现 {len(conflicts)} 个冲突，开始审议...")
    results = await deliberate_conflicts(conflicts)
    report = generate_report(results)

    report_path = REPORT_DIR / "council_deliberation_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"\n📄 审议报告已保存: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
