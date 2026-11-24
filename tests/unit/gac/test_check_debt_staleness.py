"""Tests for check-debt-staleness git-failure honesty and default self-test."""

from __future__ import annotations

import datetime
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "check-debt-staleness.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_debt_staleness", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_commits_since_returns_sentinel_when_not_a_git_repo(tmp_path: Path) -> None:
    mod = _load_module()
    ts = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    assert mod._commits_since(tmp_path, "any.py", ts) == -1


def test_collect_and_render_do_not_fake_green_without_git(tmp_path: Path) -> None:
    mod = _load_module()
    items = tmp_path / "items"
    items.mkdir()
    (items / "one.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "ITEM-1",
                "lifecycle_state": "identified",
                "affected_roots": ["bin/foo.py"],
                "last_reviewed_at": "2026-01-01",
            }
        ),
        encoding="utf-8",
    )

    report = mod.collect(items, root=tmp_path)
    rendered = mod._render(report)

    assert report["git_ok"] is False
    assert report["identified"] == 1
    assert report["candidates"] == 1
    assert report["stale_count"] is None
    assert "无法取证 (git 不可读)" in rendered
    assert "✅ 无" not in rendered


def test_collect_handles_real_git_repo_commits_accurately(tmp_path: Path) -> None:
    mod = _load_module()
    subprocess.run(["git", "init", "-q", "-b", "main", "."], cwd=tmp_path, check=True)
    (tmp_path / "a.txt").write_text("v1\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("v1\n", encoding="utf-8")
    old_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=10)).isoformat()
    env = {**__import__("os").environ, "GIT_AUTHOR_DATE": old_date, "GIT_COMMITTER_DATE": old_date}
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", "base"],
        cwd=tmp_path,
        check=True,
        env=env,
    )
    reviewed = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)).isoformat()
    items = tmp_path / "items"
    items.mkdir()
    (items / "stale.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "STALE-1",
                "lifecycle_state": "identified",
                "affected_roots": ["a.txt"],
                "last_reviewed_at": reviewed,
            }
        ),
        encoding="utf-8",
    )
    (items / "fresh.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FRESH-1",
                "lifecycle_state": "identified",
                "affected_roots": ["b.txt"],
                "last_reviewed_at": reviewed,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "a.txt").write_text("v2\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", "update"],
        cwd=tmp_path,
        check=True,
    )

    report = mod.collect(items, root=tmp_path)
    assert report["git_ok"] is True
    assert report["stale_count"] == 1
    assert [row["id"] for row in report["stale"]] == ["STALE-1"]
    rendered = mod._render(report)
    assert "疑似陈旧=1" in rendered


def test_main_runs_self_test_by_default_and_emits_clean_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    mod = _load_module()
    calls: list[bool] = []
    real_self_test = mod.self_test
    real_collect = mod.collect

    def wrapped_self_test(*, quiet: bool = False) -> int:
        calls.append(quiet)
        return real_self_test(quiet=quiet)

    def fake_collect(items_dir=mod.ITEMS_DIR, *, root=mod.ROOT):
        if root != mod.ROOT:
            return real_collect(items_dir, root=root)
        return {
            "git_ok": True,
            "identified": 1,
            "candidates": 0,
            "stale_count": 0,
            "stale": [],
        }

    monkeypatch.setattr(mod, "self_test", wrapped_self_test)
    monkeypatch.setattr(mod, "collect", fake_collect)

    rc = mod.main(["--json"])
    assert rc == 0
    assert calls == [True]
    payload = json.loads(capsys.readouterr().out)
    assert payload["self_test_ok"] is True
    assert payload["git_ok"] is True


def test_main_fails_when_inline_self_test_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_module()
    monkeypatch.setattr(mod, "self_test", lambda *, quiet=False: 1)
    monkeypatch.setattr(
        mod,
        "collect",
        lambda *a, **k: {
            "git_ok": True,
            "identified": 0,
            "candidates": 0,
            "stale_count": 0,
            "stale": [],
        },
    )

    assert mod.main([]) == 1
