from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGES_ROOT = REPO_ROOT / "projects" / "kairon" / "packages"


def test_kairon_packages_production_code_has_no_user_absolute_paths() -> None:
    offenders: list[str] = []

    for path in PACKAGES_ROOT.rglob("*.py"):
        if not path.is_file():
            continue
        rel_path = path.relative_to(REPO_ROOT)
        rel_str = rel_path.as_posix()
        if "/tests/" in rel_str or "/docs/" in rel_str or "/site-packages/" in rel_str:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "/Users/" in text:
            offenders.append(rel_str)

    assert offenders == []
