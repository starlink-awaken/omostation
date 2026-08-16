"""
测试 foundation/rule_loader.py - 规则加载器
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import json

import pytest
from ontoderive.foundation.rule_loader import RuleLoader  # type: ignore[import-not-found]


class TestRuleLoader:
    """RuleLoader - 从 YAML/JSON 加载推理规则"""

    def test_load_json_rules(self, tmp_path):
        """能从 JSON 文件加载规则列表"""
        rules = [
            {"id": "R1", "name": "rule_a", "type": "deduction", "confidence": 0.9},
            {"id": "R2", "name": "rule_b", "type": "induction", "confidence": 0.8},
        ]
        fp = tmp_path / "rules.json"
        fp.write_text(json.dumps(rules))

        loader = RuleLoader()
        loaded = loader.load_json(str(fp))
        assert len(loaded) == 2
        assert loaded[0]["id"] == "R1"
        assert loaded[1]["id"] == "R2"

    def test_load_json_single_object(self, tmp_path):
        """JSON 中单个对象也会被包装为列表"""
        fp = tmp_path / "single.json"
        fp.write_text(json.dumps({"id": "R1", "name": "x", "type": "deduction"}))

        loader = RuleLoader()
        loaded = loader.load_json(str(fp))
        assert len(loaded) == 1
        assert loaded[0]["id"] == "R1"

    def test_load_yaml_with_pyyaml(self, tmp_path):
        """使用 pyyaml 加载 YAML 规则 (如果 pyyaml 可用)"""
        try:
            import yaml  # noqa
        except ImportError:
            pytest.skip("pyyaml not available")

        yaml_text = """
- id: R1
  name: numeric_comparison
  type: numeric_comparison
  category: deduction
  confidence: 0.95
"""

        fp = tmp_path / "rules.yaml"
        fp.write_text(yaml_text)

        loader = RuleLoader()
        loaded = loader.load_yaml(str(fp))
        assert len(loaded) == 1
        assert loaded[0]["id"] == "R1"
        assert loaded[0]["type"] == "numeric_comparison"

    def test_load_yaml_simple_fallback(self, tmp_path):
        """简易 YAML 解析器也能处理基本 YAML 规则"""
        yaml_text = """id: R1
name: numeric_comparison
type: numeric_comparison
category: deduction
confidence: 0.9
"""
        fp = tmp_path / "rules.yaml"
        fp.write_text(yaml_text)

        loader = RuleLoader()
        loaded = loader._load_yaml_simple(str(fp))
        assert len(loaded) == 1
        assert loaded[0]["id"] == "R1"
        assert loaded[0]["type"] == "numeric_comparison"

    def test_validate_filters_invalid_rules(self):
        """_validate 应过滤掉缺少必要字段的规则"""
        loader = RuleLoader()
        rules = [
            {"id": "R1", "name": "a", "type": "deduction"},
            {"id": "R2", "name": "b"},  # missing type
            {"name": "c", "type": "deduction"},  # missing id
        ]
        valid = loader._validate(rules)
        assert len(valid) == 1
        assert valid[0]["id"] == "R1"

    def test_get_by_type(self):
        loader = RuleLoader()
        loader.rules = [
            {"id": "R1", "name": "a", "type": "deduction"},
            {"id": "R2", "name": "b", "type": "induction"},
            {"id": "R3", "name": "c", "type": "deduction"},
        ]
        deducted = loader.get_by_type("deduction")
        assert len(deducted) == 2
        assert deducted[0]["id"] == "R1"
        assert deducted[1]["id"] == "R3"

    def test_get_by_category(self):
        loader = RuleLoader()
        loader.rules = [
            {"id": "R1", "name": "a", "type": "x", "category": "analytics"},
            {"id": "R2", "name": "b", "type": "y", "category": "deduction"},
        ]
        result = loader.get_by_category("analytics")
        assert len(result) == 1
        assert result[0]["id"] == "R1"

    def test_to_conclusion_with_kwargs(self):
        """to_conclusion 应替换模板变量并返回结论字典"""
        rule = {
            "id": "R5",
            "name": "threshold_alert",
            "type": "threshold_alert",
            "conclusion_template": "{metric}达到{value}",
            "confidence": 0.9,
        }
        result = RuleLoader.to_conclusion(rule, metric="温度", value="100")
        assert result is not None
        assert result["conclusion"] == "温度达到100"
        assert result["confidence"] == 0.9
        assert result["method"] == "rule_loader"

    def test_to_conclusion_missing_kwargs_returns_none(self):
        """缺少模板所需变量时返回 None"""
        rule = {
            "id": "R5",
            "name": "threshold_alert",
            "type": "threshold_alert",
            "conclusion_template": "{metric}达到{value}",
            "confidence": 0.9,
        }
        result = RuleLoader.to_conclusion(rule, metric="温度")
        assert result is None

    def test_to_conclusion_fallback_to_name(self):
        """无 conclusion_template 时用 name 作为结论"""
        rule = {
            "id": "R1",
            "name": "simple_rule",
            "type": "basic",
        }
        result = RuleLoader.to_conclusion(rule)
        assert result is not None
        assert result["conclusion"] == "simple_rule"

    def test_loaded_rules_accumulate(self, tmp_path):
        """多次 load 应累积所有规则"""
        r1 = [{"id": "R1", "name": "a", "type": "x"}]
        r2 = [{"id": "R2", "name": "b", "type": "y"}]
        f1 = tmp_path / "r1.json"
        f2 = tmp_path / "r2.json"
        f1.write_text(json.dumps(r1))
        f2.write_text(json.dumps(r2))

        loader = RuleLoader()
        loader.load_json(str(f1))
        loader.load_json(str(f2))
        assert len(loader.rules) == 2
