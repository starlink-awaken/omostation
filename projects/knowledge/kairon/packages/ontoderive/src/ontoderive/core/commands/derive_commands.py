"""命令: derive/analyze/check/rounds/generate — 推导与分析命令"""

import json
from pathlib import Path
from typing import Any

from ontoderive.core.derive import OntoDerive


def _run_toolforge(project: str, goal: str, tool_context: str) -> None:
    from ontoderive.toolforge import ToolForge

    tf = ToolForge()
    print(f"\n{'━' * 50}")
    print("  🧰 ToolForge 前置匹配")
    print(f"     目标: {goal or '(未指定)'}")
    print(f"{'━' * 50}")
    guide = tf.to_inference_guide(goal, tool_context)
    guide_path = Path(project) / "inferences" / "_toolforge_guide.md"
    guide_path.parent.mkdir(parents=True, exist_ok=True)
    guide_path.write_text(guide)
    top = tf.select(goal, tool_context, top_n=3)
    if top:
        for t in top:
            print(f"      {t['id']} {t['name']} (匹配度:{t['score']})")


def cmd_derive(
    project: Any, auto: Any, with_tools: Any, goal: Any, tool_context: Any, pipeline_input: Any, pipeline_output: Any
) -> None:
    """正向推导 (pipeline:json 感知)"""
    od = OntoDerive(project)

    # Pipeline 输入: 读取上游 JSON, 提取 data/目标
    if pipeline_input:
        raw = json.loads(Path(pipeline_input).read_text(encoding="utf-8"))
        data = raw.get("data", raw)
        if not goal and isinstance(data, dict):
            goal = data.get("goal") or data.get("query") or goal
        print(f"[derive] pipeline-input: {pipeline_input}, goal: {goal}")

    # ToolForge 前置
    if with_tools:
        _run_toolforge(project, goal, tool_context)

    if auto:
        print("[derive] --auto: 自动检测LLM并执行全量分析...")
        od.analyze()
    elif pipeline_output:
        import datetime

        result = {"derived": True, "count": 0, "items": []}
        pipeline_result = {
            "pipeline": {
                "version": "1.1",
                "tool": "ontoderive",
                "action": "derive",
                "timestamp": datetime.datetime.now().isoformat(),
            },
            "meta_type": "INFERENCE",
            "data": result,
            "provenance": {
                "source": f"pipeline://{pipeline_input}" if pipeline_input else "cli:derive",
                "confidence": 0.0,
                "pipeline_input": pipeline_input,
            },
        }
        Path(pipeline_output).write_text(json.dumps(pipeline_result, ensure_ascii=False, indent=2))
        print(f"Output -> {pipeline_output}")
        return
    else:
        od.derive()


def cmd_analyze(project: Any, force: Any) -> None:
    """全量分析: 推导+LLM洞察(自动检测)"""
    print("[analyze] 全量分析: 结构推导 + LLM洞察(自动检测LLM)...")
    from ontoderive.intelligence.llm import get_enhancer

    od = OntoDerive(project)
    enhancer = get_enhancer(force)
    if enhancer.available:
        print(f"[analyze] ✅ LLM后端: {enhancer.backend}, 模型: {enhancer.model}")
    else:
        print("[analyze] ⚠️ LLM不可用, 仅执行结构分析")
    od.analyze()


def cmd_check(project: Any) -> None:
    """规约检查"""
    od = OntoDerive(project)
    od.check()


def cmd_rounds(project: Any, n: Any) -> None:
    """多轮迭代"""
    od = OntoDerive(project)
    od.run_rounds(n)


def cmd_generate(project: Any, export: Any) -> None:
    """生成推导报告"""
    from ontoderive.core.derive import OntoDerive

    od = OntoDerive(project)
    if export:
        r = od.derive()
        try:
            if export == "html":
                from ontoderive.core.export import to_html

                output = to_html(r, project)
                Path(project + "/export.html").write_text(output)
            elif export == "json":
                import json

                Path(project + "/export.json").write_text(json.dumps(r, ensure_ascii=False))
            else:
                print(f"[export] 格式 {export} 暂不支持")
        except Exception as e:
            print(f"[export] ❌ {e}")
    else:
        od.generate_report()
