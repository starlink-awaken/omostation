"""CR-X2-PROJECT-HEALTH-FRESHNESS: 「判不了」不得洗成「健康」。

缺陷（2026-11-10 实测）：该检查 6 条路径**全部 `return 0`**，而
`FRESHNESS_THRESHOLD_HOURS` 是**死常量** —— `last_updated` 是字符串时直接走
Info 分支返回，时间戳比较从未发生。实测本机的输出恒为
「OK 未发现 system.yaml」：该文件是 gitignored 运行态，干净检出里按构造不存在，
于是「判不了」被洗成「健康」，CI 里那一步永远绿色且零信息。

判据：缺席 ⇒ WARN；陈旧 ⇒ STALE 并给出实际时长；新鲜 ⇒ OK。
退出码按 advisory 约定保持 0（同组 `check-delivery-cadence.py` 亦如此）。
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "check-project-health-freshness.py"


def _load(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("OMOSTATION_STATE_ROOT", raising=False)
    spec = importlib.util.spec_from_file_location("health_freshness_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    return module


def _write_system(tmp_path: Path, *, health_score: int = 80, last_updated: str | None = None) -> None:
    path = tmp_path / ".omo" / "state" / "system.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = f"last_updated: {last_updated}" if last_updated else ""
    path.write_text(f"health_score: {health_score}\n{stamp}\n", encoding="utf-8")


def test_absent_file_is_not_ok(capsys, monkeypatch, tmp_path) -> None:
    module = _load(monkeypatch, tmp_path)

    assert module.main() == 0
    out = capsys.readouterr().out
    assert "WARN" in out and "未发现 system.yaml" in out
    assert not out.startswith("OK"), "文件缺席被洗成通过"


def test_stale_health_score_is_reported(capsys, monkeypatch, tmp_path) -> None:
    stale = (datetime.now(UTC) - timedelta(hours=72)).isoformat()
    _write_system(tmp_path, last_updated=stale)
    module = _load(monkeypatch, tmp_path)

    assert module.main() == 0
    out = capsys.readouterr().out
    assert "STALE" in out, f"72h 未更新却未报 STALE: {out}"
    assert "48" in out, f"未带出阈值: {out}"


def test_fresh_health_score_is_ok(capsys, monkeypatch, tmp_path) -> None:
    fresh = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    _write_system(tmp_path, last_updated=fresh)
    module = _load(monkeypatch, tmp_path)

    assert module.main() == 0
    out = capsys.readouterr().out
    assert out.startswith("OK") and "新鲜度正常" in out


def test_unparseable_timestamp_warns(capsys, monkeypatch, tmp_path) -> None:
    _write_system(tmp_path, last_updated="not-a-date")
    module = _load(monkeypatch, tmp_path)

    assert module.main() == 0
    assert "WARN" in capsys.readouterr().out
