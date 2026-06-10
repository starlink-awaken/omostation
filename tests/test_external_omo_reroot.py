from __future__ import annotations

from pathlib import Path


NEW_EXTERNAL_OMO_ROOT = Path("/Users/xiamingxing/Documents/学习进化/2-knowledge/体系/OMO")
LEGACY_EXTERNAL_OMO_ROOT = Path("/Users/xiamingxing/Documents/学习进化/2-knowledge/经验积累/OMO")


def test_new_external_omo_root_exists_with_core_surfaces() -> None:
    for rel_path in [
        "README.md",
        "INDEX.md",
        "_control/STATE.md",
        "_knowledge/02-OMO增长路线图.md",
        "_delivery/INDEX.md",
    ]:
        assert (NEW_EXTERNAL_OMO_ROOT / rel_path).exists(), rel_path


def test_legacy_external_omo_root_is_redirect_shell() -> None:
    for rel_path in ["README.md", "INDEX.md", "AGENT.md", "CLAUDE.md"]:
        path = LEGACY_EXTERNAL_OMO_ROOT / rel_path
        assert path.exists(), rel_path
        text = path.read_text(encoding="utf-8")
        assert "学习进化/2-knowledge/体系/OMO" in text
        assert "canonical" in text or "新 canonical 位置" in text
