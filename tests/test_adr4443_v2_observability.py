"""ADR-0443 v2 批次 1 测试：三桶聚类 / preflight-clean 归因 / pitfall 周期喂食。"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CP = _load("bin/gac/convergence-pulse.py", "cp_v2")
EK = _load("bin/gac/error-knowledge.py", "ek_v2")


def _mk_escapes(directory: Path) -> None:
    for i in range(3):
        (directory / f"e{i}.json").write_text(
            json.dumps(
                {
                    "ts": "2026-08-30T01:00:00Z",
                    "fingerprint_key": "ci-local-fast|gac|deadbeef",
                    "fingerprints": [
                        {
                            "surface": "ci-local-fast",
                            "check_id": "gac",
                            "output_excerpt": "GaC local gate FAIL gac-validate script registry violation",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
    (directory / "clean.json").write_text(
        json.dumps({"ts": "2026-08-30T01:00:00Z", "fingerprint_key": "preflight-clean|skip|none", "fingerprints": []}),
        encoding="utf-8",
    )
    (directory / "old.json").write_text(
        json.dumps({"ts": "2026-08-30T01:00:00Z", "fingerprint_key": "unspecified|unspecified|none", "fingerprints": []}),
        encoding="utf-8",
    )
    (directory / "rare.json").write_text(
        json.dumps(
            {
                "ts": "2026-08-30T01:00:00Z",
                "fingerprint_key": "ci-local-fast|lint|cafe1234",
                "fingerprints": [{"surface": "ci-local-fast", "check_id": "lint", "output_excerpt": "ruff minor"}],
            }
        ),
        encoding="utf-8",
    )


# --- convergence-pulse 三桶 ---------------------------------------------------

def test_pulse_three_bucket_clustering(tmp_path, monkeypatch):
    esc = tmp_path / "esc"
    esc.mkdir()
    _mk_escapes(esc)
    monkeypatch.setattr(CP, "ESCAPE_DIR", esc)
    result = CP.collect_escapes(datetime(2026, 8, 30, tzinfo=timezone.utc), datetime(2026, 8, 31, tzinfo=timezone.utc))
    assert result["records"] == 6
    assert result["unique_fingerprints"] == 2  # gac 指纹 + lint 指纹（正常桶）
    assert result["preflight_clean"] == 1
    assert result["unattributed"] == 1  # 老 unspecified 降级
    assert all(not fp["fingerprint"].startswith("unspecified") for fp in result["top_fingerprints"])


# --- pitfall 周期喂食（隔离 PITFALLS_DIR，杜绝真库污染）-----------------------


def test_feed_escapes_fed_bumped_and_clean_skipped(tmp_path, monkeypatch):
    esc = tmp_path / "esc"
    esc.mkdir()
    _mk_escapes(esc)
    pitfalls = tmp_path / "pitfalls"
    monkeypatch.setattr(EK, "PITFALLS_DIR", pitfalls)
    monkeypatch.setattr(EK, "RULE_DRAFTS_DIR", tmp_path / "drafts")
    monkeypatch.setattr(EK, "ROOT", tmp_path)  # _load_all 若基于 ROOT 也隔离

    counts = EK.feed_from_escapes(esc)
    assert counts["fed"] == 1  # gac 指纹 3 次 ≥ 阈值；lint 1 次不喂；clean/unspecified 跳过
    entries = list(pitfalls.rglob("*.yaml"))
    assert len(entries) == 1
    # 二次喂食（下周同指纹再来）→ fuzzy 去重走 bumped 而非新增
    counts2 = EK.feed_from_escapes(esc)
    assert counts2["fed"] == 0 and counts2["bumped"] == 1
    assert len(list(pitfalls.rglob("*.yaml"))) == 1  # 不新增文件
    # id 命名对齐既有 category[:3] 语义
    name = entries[0].name
    assert name.startswith("PITFALL-GAT-"), name


def test_feed_escapes_promotes_on_threshold(tmp_path, monkeypatch):
    esc = tmp_path / "esc"
    esc.mkdir()
    for i in range(6):  # 6 ≥ ESCALATION_THRESHOLD(5)：首喂直达晋升
        (esc / f"e{i}.json").write_text(
            json.dumps(
                {
                    "ts": "2026-08-30T01:00:00Z",
                    "fingerprint_key": "pointer-drift|sub|f00d",
                    "fingerprints": [{"surface": "pointer-drift", "check_id": "sub", "output_excerpt": "submodule pointer drift detected"}],
                }
            ),
            encoding="utf-8",
        )
    monkeypatch.setattr(EK, "PITFALLS_DIR", tmp_path / "pitfalls")
    monkeypatch.setattr(EK, "RULE_DRAFTS_DIR", tmp_path / "drafts")
    monkeypatch.setattr(EK, "ROOT", tmp_path)
    counts = EK.feed_from_escapes(esc)
    assert counts["fed"] == 1 and counts["promoted"] == 1
    drafts = list((tmp_path / "drafts").glob("*.json"))
    assert len(drafts) == 1  # 喂食即晋升：管道第一车有货
