"""
测试 intelligence/prompts.py - 提示词模板系统
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import json

from ontoderive.intelligence.prompts import (  # type: ignore[import-not-found]
    CHECK_CONTRADICTION,
    DERIVE_INSIGHTS,
    DOMAIN_PRESETS,
    JUDGE_QUALITY,
    RECOMMEND_TOOLS,
    PromptTemplate,
    auto_detect_domain,
    export_all_templates,
    get_template,
)


class TestPromptTemplate:
    """PromptTemplate - 提示词模板数据类"""

    def test_render_replaces_variables(self):
        """render 应替换 {var} 占位符"""
        tmpl = PromptTemplate(
            name="test",
            version="1.0",
            purpose="测试",
            domain="general",
            system_prompt="你是一个助手",
            user_prompt_template="分析: {goal} under {condition}",
            variables=["goal", "condition"],
            output_format="text",
            temperature=0.0,
            max_tokens=100,
            chain_of_thought=False,
            fallback="none",
        )
        result = tmpl.render(goal="growth", condition="risk")
        assert result == "分析: growth under risk"

    def test_render_missing_variable_uses_empty_string(self):
        """render 中缺失的变量应替换为空字符串"""
        tmpl = PromptTemplate(
            name="test",
            version="1.0",
            purpose="测试",
            domain="general",
            system_prompt="test",
            user_prompt_template="a={a}, b={b}",
            variables=["a", "b"],
            output_format="text",
            temperature=0.0,
            max_tokens=100,
            chain_of_thought=False,
            fallback="none",
        )
        result = tmpl.render(a="1")  # b not provided
        assert result == "a=1, b="


class TestPredefinedTemplates:
    """预定义提示词模板完整性"""

    def test_derive_insights_has_required_fields(self):
        assert DERIVE_INSIGHTS.name == "derive_insights"
        assert DERIVE_INSIGHTS.version == "1.0.0"
        assert "facts_summary" in DERIVE_INSIGHTS.variables
        assert "inferences_summary" in DERIVE_INSIGHTS.variables
        assert DERIVE_INSIGHTS.output_format == "json"
        assert DERIVE_INSIGHTS.fallback != ""

    def test_judge_quality_has_required_fields(self):
        assert JUDGE_QUALITY.name == "judge_quality"
        assert JUDGE_QUALITY.version == "1.0.0"
        assert "context" in JUDGE_QUALITY.variables
        assert JUDGE_QUALITY.output_format == "json"

    def test_check_contradiction_has_all_variables(self):
        expected = {"inf_a_title", "inf_a_text", "inf_b_title", "inf_b_text", "shared_facts"}
        assert set(CHECK_CONTRADICTION.variables) == expected

    def test_recommend_tools_has_low_temperature(self):
        assert RECOMMEND_TOOLS.temperature == 0.1
        assert RECOMMEND_TOOLS.chain_of_thought is False

    def test_all_templates_have_fallback(self):
        for tmpl in [DERIVE_INSIGHTS, JUDGE_QUALITY, CHECK_CONTRADICTION, RECOMMEND_TOOLS]:
            assert tmpl.fallback, f"{tmpl.name} missing fallback"


class TestDomainPresets:
    """领域预设配置"""

    def test_known_domains(self):
        assert set(DOMAIN_PRESETS.keys()) == {"policy", "business", "academic", "tech"}

    def test_each_preset_has_required_keys(self):
        for name, preset in DOMAIN_PRESETS.items():
            assert "description" in preset
            assert "system_addon" in preset
            assert "keywords" in preset
            assert len(preset["keywords"]) >= 1

    def test_auto_detect_domain_by_keywords(self):
        domain = auto_detect_domain(
            facts_summary="这是一项市场策略分析 关注营收增长",
            inferences_summary="竞争格局",
        )
        assert domain == "business"

    def test_auto_detect_general_when_no_match(self):
        domain = auto_detect_domain(
            facts_summary="普通描述 不含关键词",
            inferences_summary="",
        )
        assert domain == "general"


class TestGetTemplate:
    """get_template - 模板获取与领域定制"""

    def test_get_known_template(self):
        tmpl = get_template("derive_insights")
        assert tmpl is not None
        assert tmpl.name == "derive_insights"

    def test_get_unknown_template_returns_none(self):
        tmpl = get_template("nonexistent")
        assert tmpl is None

    def test_domain_preset_appends_system_prompt(self):
        """指定 domain 时应在 system_prompt 后追加领域 addon"""
        tmpl = get_template("derive_insights", domain="policy")
        assert tmpl is not None
        # 检查 system_prompt 是否包含政策领域 preset 的 addon 关键词
        assert "政策体系" in tmpl.system_prompt
        assert "利益相关者" in tmpl.system_prompt

    def test_unknown_domain_falls_back_to_general(self):
        tmpl = get_template("derive_insights", domain="unknown")
        assert tmpl is not None
        # 应保持原始 system_prompt
        assert tmpl.system_prompt == DERIVE_INSIGHTS.system_prompt


class TestExportAllTemplates:
    """export_all_templates - 导出为 JSON"""

    def test_returns_valid_json(self):
        result = export_all_templates()
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_contains_all_templates(self):
        data = json.loads(export_all_templates())
        assert "derive_insights" in data
        assert "judge_quality" in data
        assert "check_contradiction" in data
        assert "recommend_tools" in data
        assert "domain_presets" in data

    def test_each_template_has_required_export_fields(self):
        data = json.loads(export_all_templates())
        for name in ["derive_insights", "judge_quality", "check_contradiction", "recommend_tools"]:
            tmpl = data[name]
            assert "version" in tmpl
            assert "purpose" in tmpl
            assert "variables" in tmpl
            assert "temperature" in tmpl
            assert "output_format" in tmpl
