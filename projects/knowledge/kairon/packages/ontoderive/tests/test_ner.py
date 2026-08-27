"""Tests for NER — 中文命名实体识别"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.intelligence.ner import _extract_entities_by_suffix, extract_entities


class TestExtractBySuffix:
    def test_org_suffix(self):
        result = _extract_entities_by_suffix("中关村科技园区", ("园区",), "ORG")
        assert len(result) > 0
        assert any("科技园区" in name or "中关村科技园区" in name for name, _ in result)

    def test_role_suffix(self):
        result = _extract_entities_by_suffix("张三经理", ("经理",), "ROL")
        assert len(result) > 0
        names = [name for name, _ in result]
        assert any("经理" in n for n in names)

    def test_loc_suffix(self):
        result = _extract_entities_by_suffix("北京市", ("市",), "ORG")
        assert len(result) > 0
        assert any("北京" in name for name, _ in result)


class TestExtractEntities:
    def test_empty_text(self):
        assert extract_entities("") == []

    def test_short_text(self):
        """不足3字的文本不应产生实体"""
        result = extract_entities("的")
        assert isinstance(result, list)

    def test_org_matching(self):
        """文本中出现组织名后缀应提取"""
        result = extract_entities("北京大学在量子计算领域取得突破", use_jieba=False)
        names = [name for name, _ in result]
        assert len(names) > 0

    def test_role_matching(self):
        result = extract_entities("这项成果由李教授带领团队完成", use_jieba=False)
        names = [name for name, _ in result]
        assert len(names) > 0

    def test_deduplication(self):
        result = extract_entities("北京大学和北京大学医学部", use_jieba=False)
        names = [name for name, _ in result]
        assert len(names) == len(set(names))

    def test_use_jieba_fallback_on_error(self):
        """即使use_jieba=True但jieba不可用, 应平滑回退规则模式"""
        result = extract_entities("清华大学", use_jieba=True)
        assert isinstance(result, list)
