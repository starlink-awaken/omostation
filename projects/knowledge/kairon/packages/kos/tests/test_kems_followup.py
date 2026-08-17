"""Contract tests for KEMS P1/P2/P3 follow-up capabilities."""

from pathlib import Path

import pytest
from kos.kems import (
    ImportPolicy,
    analyze_ai_survey,
    analyze_policy_document,
    analyze_reconsideration,
    analyze_tri_medical_minutes,
    create_run_record,
    enrich_policy,
    evaluate_policy_fixture,
    import_document,
)

POLICY = """# 关于推进基层医疗信息化建设的通知
发布单位：省卫生健康委
文号：卫办〔2026〕12号
各地应当在2026年8月15日前完成数据摸底。
"""


def test_import_policy_enforces_workspace_boundary_and_preserves_hash(tmp_path: Path):
    source = tmp_path / "inbox" / "policy.md"
    source.parent.mkdir()
    source.write_text(POLICY, encoding="utf-8")

    imported = import_document(source, ImportPolicy(tmp_path))

    assert imported.source_name == "policy.md"
    assert imported.source_format == "md"
    assert len(imported.source_sha256) == 64
    with pytest.raises(PermissionError):
        import_document(tmp_path.parent / "outside.md", ImportPolicy(tmp_path))


def test_run_record_requires_evidence_for_completed_run():
    with pytest.raises(ValueError):
        create_run_record(
            scenario_id="policy-document-processing",
            request_id="req-1",
            request_mode="fixture-backed",
            source_sha256=None,
            output_schema="kems.policy-analysis.v1",
            evidence_refs=(),
            verification_refs=("test_kems_followup.py",),
        )

    record = create_run_record(
        scenario_id="policy-document-processing",
        request_id="req-2",
        request_mode="low-risk-live",
        source_sha256="a" * 64,
        output_schema="kems.policy-analysis.v1",
        evidence_refs=("source:policy.md#L1",),
        verification_refs=("test_kems_followup.py",),
    )
    assert record.to_dict()["schema_version"] == "kems.run-record.v1"


def test_reconsideration_analysis_aggregates_dimensions_and_risk_evidence():
    result = analyze_reconsideration("地区,状态,风险\n甲市,已办结,低\n乙市,办理中,高\n")

    assert result.metrics["total"] == 2
    assert result.metrics["regions"] == {"甲市": 1, "乙市": 1}
    assert result.metrics["high_risk_count"] == 1
    assert result.evidence[0].kind == "high_risk"


def test_ai_survey_analysis_does_not_hide_incomplete_responses():
    result = analyze_ai_survey("单位,状态,联系人\n甲医院,已报送,张三\n乙医院,未报送,\n")

    assert result.metrics["response_count"] == 2
    assert result.metrics["missing_row_count"] == 1
    assert "incomplete_responses" in result.review_flags


def test_tri_medical_minutes_extracts_tasks_and_flags_missing_accountability():
    result = analyze_tri_medical_minutes(
        "任务：完成药品目录核对；责任人：李四；截止：8月15日\n任务：汇总医保数据；责任人：王五\n"
    )

    assert result.metrics["task_count"] == 2
    assert result.metrics["missing_due_count"] == 1
    assert "missing_due_date" in result.review_flags
    assert len(result.evidence) == 2


def test_model_enrichment_rejects_uncited_claim_and_falls_back():
    baseline = analyze_policy_document(POLICY, source_name="policy.md")

    result = enrich_policy(
        baseline,
        lambda _: {"summary": "未经证据的摘要", "claims": [{"text": "无来源结论", "evidence_indexes": []}]},  # type: ignore[reportArgumentType]
        model_id="test-model",
    )

    assert result.fallback_used is True
    assert result.summary == baseline.summary
    assert "model_output_rejected" in result.review_flags


def test_model_enrichment_accepts_claims_with_valid_evidence():
    baseline = analyze_policy_document(POLICY, source_name="policy.md")
    result = enrich_policy(
        baseline,
        lambda _: {"summary": "有证据摘要", "claims": [{"text": "这是可复核结论", "evidence_indexes": [0]}]},  # type: ignore[reportArgumentType]
        model_id="test-model",
    )

    assert result.fallback_used is False
    assert result.claims[0].evidence_indexes == (0,)


def test_policy_evaluation_is_explicit_about_fixture_status():
    result = analyze_policy_document(POLICY, source_name="policy.md")
    report = evaluate_policy_fixture(
        result,
        {
            "title": result.title,
            "document_type": "通知",
            "issuer": "省卫生健康委",
            "document_number": "卫办〔2026〕12号",
        },
    )

    assert report.status == "pass"
    assert report.accuracy == 1.0
    assert report.to_dict()["schema_version"] == "kems.policy-evaluation.v1"
