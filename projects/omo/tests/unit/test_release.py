"""P34-W3 多仓库统一发布 — 单元测试.

验证:
  1. VERSION 文件存在且非空
  2. CHANGELOG.md 含 [0.1.0] 段
  3. omo.__version__ 等于 VERSION 文件内容
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
VERSION_FILE = WORKSPACE_ROOT / "VERSION"
CHANGELOG = WORKSPACE_ROOT / "CHANGELOG.md"


def test_version_file_exists() -> None:
    """VERSION 文件必须存在且非空."""
    assert VERSION_FILE.exists(), f"missing: {VERSION_FILE}"
    content = VERSION_FILE.read_text().strip()
    assert content, "VERSION file is empty"
    # 必须 X.Y.Z 格式
    assert re.match(r"^\d+\.\d+\.\d+$", content), f"bad format: {content!r}"


def test_changelog_has_001_section() -> None:
    """CHANGELOG.md 必须含 [0.1.0] 段."""
    assert CHANGELOG.exists(), f"missing: {CHANGELOG}"
    text = CHANGELOG.read_text()
    assert "[0.1.0]" in text, "CHANGELOG missing [0.1.0] section"
    # 必须含 "Changed" 或 "Added" 段
    assert "### " in text, "CHANGELOG has no ### subsections"


def test_omo_version_matches_workspace() -> None:
    """omo.__version__ 必须等于 VERSION 文件内容."""
    from omo import __version__

    expected = VERSION_FILE.read_text().strip()
    assert __version__ == expected, (
        f"omo.__version__={__version__!r} != VERSION={expected!r}"
    )


def test_kairon_version_matches_workspace() -> None:
    """kairon.__version__ 必须等于 VERSION 文件内容 (如果可导入)."""
    try:
        from kairon import __version__ as kv  # type: ignore
    except ImportError:
        pytest.skip("kairon not importable in this env")
    expected = VERSION_FILE.read_text().strip()
    assert kv == expected, f"kairon.__version__={kv!r} != VERSION={expected!r}"


def test_release_script_exists() -> None:
    """scripts/release.sh 必须存在且可执行."""
    script = WORKSPACE_ROOT / "scripts" / "release.sh"
    assert script.exists(), f"missing: {script}"
    assert script.stat().st_mode & 0o111, "release.sh not executable"
