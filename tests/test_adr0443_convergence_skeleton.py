"""ADR-0443 骨架三件测试：采集器回放 / pitfall 晋升出口 / ADR 分级校验。"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# --- convergence-pulse 采集器 ------------------------------------------------

CP = _load("bin/gac/convergence-pulse.py", "convergence_pulse")


def test_pulse_escape_clustering_and_missing_dir_tolerance(tmp_path, monkeypatch):
    esc_dir = tmp_path / "swarm-escape"
    esc_dir.mkdir()
    for i in range(3):
        (esc_dir / f"e{i}.json").write_text(
            json.dumps({"ts": "2026-08-30T01:00:00Z", "fingerprint_key": "fp-A"}), encoding="utf-8"
        )
    (esc_dir / "e9.json").write_text(
        json.dumps({"ts": "2026-08-30T02:00:00Z", "fingerprint_key": "fp-B"}), encoding="utf-8"
    )
    (esc_dir / "out.json").write_text(
        json.dumps({"ts": "2026-08-29T02:00:00Z", "fingerprint_key": "fp-OLD"}), encoding="utf-8"
    )
    (esc_dir / "bad.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(CP, "ESCAPE_DIR", esc_dir)
    start = datetime(2026, 8, 30, tzinfo=UTC)
    end = datetime(2026, 8, 31, tzinfo=UTC)
    result = CP.collect_escapes(start, end)
    assert result["available"] is True
    assert result["records"] == 4  # 窗口内 4 条（fp-OLD 出窗、bad 解析失败不计）
    assert result["unique_fingerprints"] == 2
    assert result["top_fingerprints"][0] == {"fingerprint": "fp-A", "count": 3}
    # 目录缺失容错
    monkeypatch.setattr(CP, "ESCAPE_DIR", tmp_path / "missing")
    missing = CP.collect_escapes(start, end)
    assert missing["available"] is False and missing["records"] == 0


def test_pulse_schema_and_week_key():
    pulse = CP.collect_pulse(since=date(2026, 8, 25), until=date(2026, 8, 30))
    assert pulse["schema"] == "governance.convergence-pulse.v1"
    assert pulse["week"] == "2026-W35"
    assert set(pulse["convergence"]) == {"escapes", "history"}
    assert "production" in pulse


# --- error-knowledge 晋升出口 -------------------------------------------------

EK = _load("bin/gac/error-knowledge.py", "error_knowledge_promote")


def test_promote_generates_draft_with_0431_contract_then_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(EK, "RULE_DRAFTS_DIR", tmp_path)
    entry = {
        "id": "PITFALL-SUB-009",
        "times_encountered": 7,
        "discovered_at": "2026-08-25",
        "last_confirmed_at": "2026-08-30",
        "symptom": "empty checkout",
        "prevention": "init before ops",
        "title": "submodule not initialized",
    }
    out = EK._promote_rule_draft(entry)
    assert out is not None and out.name == "CR-PITFALL-SUB-009.json"
    draft = json.loads(out.read_text(encoding="utf-8"))
    rule = draft["draft_rule"]
    assert rule["id"] == "CR-PITFALL-SUB-009"
    assert rule["added_at"] and rule["review_before"]  # 0431 契约字段
    assert "PITFALL-SUB-009" in rule["justification"] and "7" in rule["justification"]  # 证据链
    assert draft["evidence"]["times_encountered"] == 7
    # 幂等：同 pitfall 不重复生成
    assert EK._promote_rule_draft(entry) is None


# --- adr-number-check 分级 ----------------------------------------------------

ANC = _load("bin/ssot/adr-number-check.py", "adr_number_check_443")


def _adr(name: str, decision_body: str) -> Path:
    return name, f"---\nid: ADR\n---\n# t\n\n## Decision\n\n{decision_body}\n\n## Consequences\n\n- x\n"


def test_tier_check_rejects_draft_and_passes_real(tmp_path):
    (tmp_path / "0001-real.md").write_text(
        _adr("r", "Adopt X because Y with Z boundary. Long enough decision body here.")[1], encoding="utf-8"
    )
    (tmp_path / "0002-draft.md").write_text(
        _adr("d", "_Pending human review. Auto-generated draft — do not merge without review._")[1], encoding="utf-8"
    )
    rc = ANC.check_adr_numbers(tmp_path)
    assert rc == 1  # draft 占号被拒
    (tmp_path / "0002-draft.md").unlink()
    rc = ANC.check_adr_numbers(tmp_path)
    assert rc == 0  # 真决策通过
