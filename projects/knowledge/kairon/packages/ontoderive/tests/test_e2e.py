from pathlib import Path

"""E2E集成测试 — 全流程Pipeline+生态+MCP"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false


ZPARK = str(Path(__file__).parent.parent / "examples" / "z-park")


def test_e2e_derive_check_roundtrip():
    """完整推导+检查+报告闭环"""
    from ontoderive.core.derive import OntoDerive

    od = OntoDerive(ZPARK)
    s = od.derive()
    assert s["facts"] >= 2
    assert "confidence_distribution" in s
    results = od.check()
    assert len(results) == 13
    report = od.generate_report()
    assert "事实数" in report


def test_e2e_pipeline_full():
    """Pipeline六阶段全流程"""
    from ontoderive.core.pipeline import DerivePipeline

    pipe = DerivePipeline(ZPARK)
    pipe.set_goal("分析中关村", "科技园区")
    pipe.run()
    result = pipe.to_analysis_result()
    assert result.summary["facts"] >= 2


def test_e2e_toolforge_derive_link():
    """ToolForge匹配→指导→derive"""
    from ontoderive.core.derive import OntoDerive
    from ontoderive.toolforge.matcher import ToolForge

    tf = ToolForge()
    tools = tf.select("中关村科技园区分析")
    assert len(tools) >= 1
    guide = tf.to_inference_guide("中关村科技园区分析")
    assert "推荐" in guide
    od = OntoDerive(ZPARK)
    s = od.derive()
    assert s["facts"] >= 2


def test_e2e_mcp_pipeline_status():
    """MCP bridge routes to the FastMCP-native tool surface."""
    from ontoderive.mcp_server import handle_mcp_request

    result = handle_mcp_request(
        {"id": 99, "method": "tools/call", "params": {"name": "pipeline_status", "arguments": {}}}
    )
    assert "result" in result
    assert result["result"]["server"] == "ontoderive-mcp"


def test_e2e_typesystem_pipeline():
    """TypeValidator→check→C-07闭环"""
    from ontoderive.core.derive import OntoDerive
    from ontoderive.foundation.typesystem import TypeValidator

    tv = TypeValidator()
    r = tv.check_id("D-F1")
    assert r.is_valid
    od = OntoDerive("examples/z-park")
    results = od.check()
    c07 = [r for r in results if r["protocol_id"] == "C-07"]
    assert len(c07) == 1
    assert c07[0]["passed"]
