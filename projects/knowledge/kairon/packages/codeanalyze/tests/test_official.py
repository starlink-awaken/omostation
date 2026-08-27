"""Tests for documents/official.py — policy document analysis."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codeanalyze.documents.official import (
    _extract_doc_number,
    _extract_domain_from_path,
    _guess_level_from_path_or_name,
    analyze_policy_directory,
)


class TestDocNumberExtraction:
    def test_standard_format(self):
        result = _extract_doc_number("京发改〔2026〕287号 通知")
        assert len(result) >= 1

    def test_with_org_prefix(self):
        result = _extract_doc_number("京教科人办发〔2026〕2号")
        assert len(result) >= 1

    def test_empty_filename(self):
        result = _extract_doc_number("通知文件.pdf")
        assert result == []

    def test_no_match(self):
        result = _extract_doc_number("简单的文件名.txt")
        assert result == []

    def test_from_content(self):
        result = _extract_doc_number("文件名.txt", content_hint="根据京发改〔2026〕287号要求")
        assert len(result) >= 1


class TestLevelGuessing:
    def test_national(self):
        assert _guess_level_from_path_or_name("国家发改委文件.pdf") == "国家级"
        assert _guess_level_from_path_or_name("国务院通知") == "国家级"

    def test_beijing(self):
        assert _guess_level_from_path_or_name("北京市通知") == "北京市级"
        assert _guess_level_from_path_or_name("京发改文件") == "北京市级"

    def test_fangshan(self):
        assert _guess_level_from_path_or_name("房山区方案") == "房山区级"

    def test_other(self):
        assert _guess_level_from_path_or_name("其它文件") == "其他"


class TestDomainExtraction:
    def test_zhongshi(self):
        assert _extract_domain_from_path("/path/中小试/x.pdf") == "中试平台"

    def test_gainian(self):
        assert _extract_domain_from_path("/path/概念验证/x.pdf") == "概念验证"

    def test_chengguo(self):
        assert _extract_domain_from_path("/path/成果转化/x.pdf") == "科技成果转化"

    def test_default(self):
        assert _extract_domain_from_path("/path/其他目录/x.pdf") == "通用政策"


class TestAnalyzePolicyDirectory:
    def test_nonexistent_directory(self):
        result = analyze_policy_directory("/nonexistent/path")
        assert result.total_count == 0

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as d:
            result = analyze_policy_directory(d)
            assert result.total_count == 0

    def test_file_counted_by_extension(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "test.pdf").write_text("x")
            result = analyze_policy_directory(d)
            assert result.total_count == 1
