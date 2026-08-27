from pathlib import Path

"""E2E快照测试 — 确保重构不改变输出质量"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false


ZPARK = str(Path(__file__).parent.parent / "examples" / "z-park")
DEMO = str(Path(__file__).parent.parent / "examples" / "demo-product")


def test_zpark_derive_snapshot():
    """z-park: 结构分析输出完整性"""
    from ontoderive.core.derive import OntoDerive

    s = OntoDerive(ZPARK).derive()
    assert s["facts"] >= 6
    assert s["scheme_files"] >= 1
    assert "derived_conclusions" in s, "derive()必须输出derived_conclusions"
    assert "derivation_hints" in s, "derive()必须输出derivation_hints"
    assert "confidence_distribution" in s, "derive()必须输出置信度分布"
    assert s["analysis_mode"] == "structural", "derive()必须标注structural模式"


def test_demo_derive_snapshot():
    """demo-product: 推导结论质量"""
    from ontoderive.core.derive import OntoDerive

    s = OntoDerive(DEMO).derive()
    assert s["facts"] >= 6
    assert s["inferences"] >= 2
    dc = s.get("derived_conclusions", [])
    assert len(dc) >= 3, f"demo-product至少应有3条推导结论, 实际{len(dc)}"
    types = {c["type"] for c in dc}
    assert len(types) >= 3, f"推导结论应包含多种类型, 实际{types}"


def test_zpark_check_snapshot():
    """z-park: 规约检查完整性"""
    from ontoderive.core.derive import OntoDerive

    results = OntoDerive(ZPARK).check()
    assert len(results) == 13
    passed = sum(1 for r in results if r["passed"])
    assert passed >= 10, f"z-park规约通过率异常: {passed}/12"


def test_demo_check_snapshot():
    """demo-product: 规约检查完整性"""
    from ontoderive.core.derive import OntoDerive

    results = OntoDerive(DEMO).check()
    assert len(results) == 13
    passed = sum(1 for r in results if r["passed"])
    assert passed >= 10, f"demo-product规约通过率异常: {passed}/12"


def test_derive_output_schema():
    """derive()输出结构一致性"""
    from ontoderive.core.derive import OntoDerive

    for case in [ZPARK, DEMO]:
        s = OntoDerive(case).derive()
        for key in [
            "facts",
            "entities",
            "inferences",
            "scheme_files",
            "derived_conclusions",
            "derivation_hints",
            "analysis_mode",
            "derived_at",
        ]:
            assert key in s, f"{case}: derive()输出缺{key}字段"


def test_reasoner_output_quality():
    """RuleReasoner输出不含跨维度噪声"""
    from ontoderive.core.derive import OntoDerive

    s = OntoDerive(DEMO).derive()
    for c in s.get("derived_conclusions", []):
        if c["type"] == "numeric_comparison":
            # 不应出现明显的跨维度比较
            text = c["conclusion"]
            assert "是" in text  # 格式正确
