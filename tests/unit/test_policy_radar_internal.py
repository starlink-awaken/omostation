"""晨报: 空解析不覆盖有效缓存 + 内部信号(督办台账/邮件简报)。"""

from __future__ import annotations

import importlib.util as iu
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _radar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = iu.spec_from_file_location("pr", ROOT / "bin/bc-os/policy_radar.py")
    pr = iu.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "bin/bc-os"))
    spec.loader.exec_module(pr)
    monkeypatch.setattr(pr, "STATE_DIR", tmp_path)
    return pr


def test_empty_parse_keeps_cache_and_degrades(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pr = _radar(tmp_path, monkeypatch)
    (tmp_path).mkdir(parents=True, exist_ok=True)
    good = {"sources": {"nhsa": {"items": [{"title": "医保重要政策", "score": 5, "tags": ["政策"]}], "fetched_at": "x"}}}
    (tmp_path / "cache.json").write_text(json.dumps(good), encoding="utf-8")
    monkeypatch.setattr(pr, "_fetch", lambda url: "<html>页面改版没标题</html>")
    brief = pr.collect()
    nhsa = next(i for i in brief["items"] if i["source_id"] == "nhsa")
    assert "医保重要政策" in nhsa["title"]  # 缓存条目保留
    assert "nhsa" in brief["degraded_sources"]
    cache_now = json.loads((tmp_path / "cache.json").read_text(encoding="utf-8"))
    assert cache_now["sources"]["nhsa"]["items"]  # 没被空结果覆盖


def test_internal_signals_from_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pr = _radar(tmp_path, monkeypatch)
    monkeypatch.setattr(pr, "_fetch", lambda url: (_ for _ in ()).throw(pr.urllib.error.URLError("down")))
    led = tmp_path / "ledger.json"
    led.write_text(json.dumps([
        {"subject": "数据安全自查", "deadline": "2000-01-01", "status": "pending", "owner": "张磊"},
        {"subject": "未来事项", "deadline": "2099-01-01", "status": "pending"},
    ]), encoding="utf-8")
    monkeypatch.setenv("OMO_TRACKED_TASKS", str(led))
    brief = pr.collect()
    assert brief["internal"]["overdue"][0]["subject"] == "数据安全自查"
    md = pr.render_markdown(brief)
    assert "数据安全自查" in md and "已超期" in md
