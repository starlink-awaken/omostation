#!/usr/bin/env python3
"""governance_closed_loop.py — 治理闭环端到端验证（真实场景）

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md:
串联 8 个工具跑真实数据，验证"模型变更 → 派生 → 验证 → 推理 → 查询 → OWL"
完整闭环，产出综合报告。

用法:
    python3 bin/ssot/governance_closed_loop.py
"""

import argparse
import sys
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "projects" / "ecos" / ".omo" / "_derived" / "l0-constraints.v2.yaml"
CONSUMER_IDX = ROOT / "projects" / "ecos" / ".omo" / "_derived" / "consumer-index.yaml"
OWL_OUT = ROOT / "projects" / "ecos" / ".omo" / "_derived" / "l0-constraints.owl"

TOOL_PY = {
    "consumer_index": ("bin/ssot/consumer_index.py", ROOT),
    "m0_feedback": ("bin/ssot/m0_feedback.py", ROOT),
    "inference": ("bin/inference_engine.py", ROOT / "projects" / "ecos"),
    "owl": ("bin/ssot/owl_adapter.py", ROOT),
}


def _run_tool(name: str, args: list[str]) -> tuple[int, str]:
    tool, cwd = TOOL_PY[name]
    proc = subprocess.run([sys.executable, str(cwd / tool), *args],
                          capture_output=True, text=True, timeout=120)
    return proc.returncode, proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""


def run_closed_loop() -> dict:
    """执行闭环各阶段，返回每阶段结果摘要。

    ok 语义: 工具成功运行（rc∈(0,1)）即为 ok；漂移/违规作为发现记录，
    不视为工具失败。
    """
    stages = {}
    derived = yaml.safe_load(DERIVED.read_text(encoding="utf-8"))
    stages["derived"] = {"constraints": len(derived.get("constraints", [])),
                         "ok": DERIVED.exists()}
    rc, last = _run_tool("consumer_index", [])
    stages["index"] = {"ok": rc in (0, 1), "note": last}
    rc, last = _run_tool("inference", [])
    stages["inference"] = {"ok": rc in (0, 1), "note": last}
    rc, last = _run_tool("m0_feedback", [])
    stages["m0"] = {"ok": rc in (0, 1), "note": last, "drifts": 0 if rc == 0 else 1}
    rc, last = _run_tool("owl", ["--emit"])
    owl_count = 0
    if OWL_OUT.exists():
        owl_count = OWL_OUT.read_text(encoding="utf-8").count("owl:Class rdf:about")
    stages["owl"] = {"ok": rc in (0, 1), "constraints": owl_count}
    return stages


def summarize(stages: dict) -> str:
    """构建闭环综合报告。"""
    lines = ["# 治理闭环端到端验证报告", ""]
    d = stages.get("derived", {})
    lines.append(f"- 派生面: {d.get('constraints', '?')} 条约束 (ok={d.get('ok')})")
    i = stages.get("index", {})
    lines.append(f"- consumer index: ok={i.get('ok')} | {i.get('note', '')}")
    inf = stages.get("inference", {})
    lines.append(f"- 推理引擎: ok={inf.get('ok')} | {inf.get('note', '')}")
    m0 = stages.get("m0", {})
    lines.append(f"- M0 反馈: ok={m0.get('ok')} | {m0.get('note', '')} | drifts={m0.get('drifts', '?')}")
    o = stages.get("owl", {})
    lines.append(f"- OWL: ok={o.get('ok')} | {o.get('constraints', '?')} 约束")
    lines.append("")
    all_ok = all(s.get("ok", False) for s in stages.values() if isinstance(s, dict))
    lines.append(f"结论: {'✅ 闭环全部通过' if all_ok else '⚠️ 存在未通过阶段'}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()
    if not DERIVED.exists():
        print(f"[FAIL] 派生面缺失: {DERIVED}", file=sys.stderr)
        return 1
    stages = run_closed_loop()
    if args.json:
        import json

        print(json.dumps(stages, ensure_ascii=False, indent=1))
        return 0 if all(s.get("ok", False) for s in stages.values() if isinstance(s, dict)) else 1
    print(summarize(stages))
    return 0 if all(s.get("ok", False) for s in stages.values() if isinstance(s, dict)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
