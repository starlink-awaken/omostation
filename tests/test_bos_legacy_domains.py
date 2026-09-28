"""BOS 合法域来源: 遗留域登记在域标准文档, 不再依赖 bos-pending-registrations.yaml; 副本/缓存目录不扫。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "bos_completeness", WORKSPACE / "bin" / "gac" / "check-mcp-bos-uri-completeness.py"
)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_pending_list_is_not_a_domain_source() -> None:
    assert not hasattr(mod, "BOS_PENDING")


@pytest.mark.parametrize("legacy", ["voice", "brain", "scene", "im", "inbox", "execution", "spine", "work"])
def test_legacy_domains_come_from_standard(legacy: str) -> None:
    assert legacy in mod._load_bos_domains_from_standard()


def test_copies_and_caches_are_not_scanned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    std = tmp_path / "standard.md"
    std.write_text("`bos://memory/`\n", encoding="utf-8")
    monkeypatch.setattr(mod, "BOS_STANDARD", std)
    monkeypatch.setattr(mod, "VALID_DOMAINS", {"memory"})
    for part in (
        ".worktrees/x",
        ".codebase-memory",
        "projects/p/.venv/lib/site-packages",
        "runtime/wip-snapshots/t",
        "a/archive",
    ):
        d = tmp_path / part
        d.mkdir(parents=True)
        (d / "copy.md").write_text("bos://zombie/old/uri\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "real.md").write_text("bos://memory/kos/search\n", encoding="utf-8")

    issues, seen = mod.check_bos_uri_standard(tmp_path)
    assert issues == [] and seen == {"memory"}

    (tmp_path / "docs" / "new.md").write_text("bos://zombie/new/uri\n", encoding="utf-8")
    issues, _ = mod.check_bos_uri_standard(tmp_path)
    assert len(issues) == 1 and "zombie" in issues[0]
