"""事实提取器测试"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.extractor import ContextExtractor


def test_extractor_init():
    ext = ContextExtractor()
    assert ext.facts == []
    assert ext.fact_counter == 1


def test_extractor_from_text():
    ext = ContextExtractor()
    ext.extract_from_text("公司有240名员工，年营收5000万，成立于2018年")
    assert len(ext.facts) >= 1


def test_extractor_from_file(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("园区占地面积150亩，入驻企业120家，年税收1.2亿")
    ext = ContextExtractor()
    ext.extract_from_file(str(f))
    assert len(ext.facts) >= 1


def test_extractor_to_markdown():
    ext = ContextExtractor()
    ext.extract_from_text("产品月活用户200万，付费转化率8.5%")
    md = ext.to_markdown()
    assert "D-F" in md


def test_extractor_save(tmp_path):
    ext = ContextExtractor()
    ext.extract_from_text("平台日处理订单30万笔，99.9%可用性")
    output = tmp_path / "facts" / "data.md"
    ext.save(output)
    assert output.exists()
    content = output.read_text()
    assert "D-F" in content
