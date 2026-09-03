"""BET-Y1Q4-T10-01 DLP: scan recall, sanitize, quarantine, <2ms budget."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "dlp_broker", ROOT / "projects/ecos/src/ecos/governance/dlp_broker.py"
)
assert spec and spec.loader
DLP = importlib.util.module_from_spec(spec)
sys.modules["dlp_broker"] = DLP
spec.loader.exec_module(DLP)


def test_scan_each_sensitive_type():
    cases = {
        "〔2026〕15号": "classified_doc_number",
        "证件 11010119900307867X": "national_id",
        "电话 13812345678": "mobile_phone",
        "节点 10.1.2.3 维护": "internal_ip",
        "预算 500万元 拨付": "financial_budget",
        "本件属机密级": "classified_mark",
    }
    for text, expected in cases.items():
        found = {f.type for f in DLP.scan(text)}
        assert expected in found, f"{expected} missed in {text}"


def test_scan_adversarial_clean():
    for text in ("GB/T 9704-2012 排版标准", "第3号议题讨论", "user19 会话"):
        assert DLP.scan(text) == [], text


def test_sanitize_partial_keeps_edges():
    text = "电话 13812345678 结束"
    findings = DLP.scan(text)
    out = DLP.sanitize(text, findings)
    assert "13812345678" not in out
    assert out.startswith("电话 1") and "8 结束" in out  # 首尾保留


def test_sanitize_mask_full():
    text = "节点 10.1.2.3 维护"
    out = DLP.sanitize(text, DLP.scan(text))
    assert "10.1.2.3" not in out and "█" in out


def test_quarantine_high_risk_alert():
    text = "国卫办发布〔2026〕15号 预算 3500万元"
    q = DLP.quarantine(text, DLP.scan(text))
    assert q["status"] == "pending_approval"
    assert "机密文号" in q["alert"] and "需夏明星二次确认" in q["alert"]


def test_quarantine_medium_only_no_alert():
    q = DLP.quarantine("电话 13812345678", DLP.scan("电话 13812345678"))
    assert q["status"] == "clean_or_medium" and q["alert"] is None


def test_verify_contract_full():
    report = DLP.test_dlp()
    assert all(report["checks"].values())
    assert report["scan_ms_median"] <= 2.0
