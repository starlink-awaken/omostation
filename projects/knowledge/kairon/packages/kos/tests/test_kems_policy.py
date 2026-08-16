"""Contract tests for the first KEMS policy-document vertical slice."""

from kos.kems import analyze_policy_document, analyze_policy_file

FIXTURE = """# 关于推进基层医疗信息化建设的通知
发布单位：省卫生健康委
文号：卫办〔2026〕12号
发布日期：2026年7月30日

各地应当在2026年8月15日前完成基层医疗机构数据摸底，建立统一台账。
各地须于2026年8月20日前报送信息化建设进展，不得迟报、漏报。
本通知聚焦医疗、医保、药品和数据治理，推动三医协同和人工智能应用。
"""


def test_policy_analysis_returns_reviewable_fields_and_evidence():
    result = analyze_policy_document(FIXTURE, source_name="policy.md")

    assert result.schema_version == "kems.policy-analysis.v1"
    assert result.title == "关于推进基层医疗信息化建设的通知"
    assert result.document_type == "通知"
    assert result.issuer == "省卫生健康委"
    assert result.document_number == "卫办〔2026〕12号"
    assert "信息化" in result.topics
    assert len(result.actions) == 3
    assert {item.kind for item in result.evidence} >= {"title", "issuer", "action"}
    assert result.review_flags == ()


def test_policy_analysis_flags_missing_fields_instead_of_inventing_them():
    result = analyze_policy_document("一段没有来源和责任要求的政策说明。", source_name="brief.txt")

    assert result.issuer is None
    assert result.document_number is None
    assert "issuer_not_detected" in result.review_flags
    assert "document_number_not_detected" in result.review_flags
    assert "action_items_not_detected" in result.review_flags


def test_policy_file_uses_kos_handler_and_preserves_source_digest(tmp_path):
    source = tmp_path / "政策通知.md"
    source.write_text(FIXTURE, encoding="utf-8")

    result = analyze_policy_file(source)

    assert result.source_name == source.name
    assert len(result.source_sha256 or "") == 64
    assert result.title == "关于推进基层医疗信息化建设的通知"
