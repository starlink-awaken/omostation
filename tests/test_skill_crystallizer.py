"""test_skill_crystallizer.py — SEMA 技能结晶引擎测试 (BET-Y1Q2-T6-06).

验证 skill-crystallizer 的核心契约:
- 2+ 同 Topic 信念 → 结晶 SKILL.md (goal: MOS 信念触发自动萃取)
- 单条 Topic → 不结晶
- 无 beliefs index → 不崩
"""

import importlib.util
from pathlib import Path

import yaml

_BIN_GAC = Path(__file__).resolve().parents[1] / "bin" / "gac"


def _load_crystallizer():
    """skill-crystallizer.py 文件名含连字符, 用 importlib 加载."""
    spec = importlib.util.spec_from_file_location(
        "skill_crystallizer", _BIN_GAC / "skill-crystallizer.py"
    )
    assert spec is not None and spec.loader is not None  # 类型收窄 (Pyright)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SkillCrystallizer


def _write_beliefs(root: Path, beliefs: list[dict]) -> None:
    p = root / ".omo" / "state" / "agent-beliefs"
    p.mkdir(parents=True, exist_ok=True)
    (p / "index.yaml").write_text(
        yaml.safe_dump({"beliefs": beliefs}, allow_unicode=True), encoding="utf-8"
    )


def test_crystallize_2plus_same_topic(tmp_path: Path) -> None:
    """2+ 同 Topic → 结晶 SKILL.md (T6-06 goal 核心契约)."""
    SkillCrystallizer = _load_crystallizer()
    _write_beliefs(
        tmp_path,
        [
            {
                "topic": "fork-bomb",
                "id": "b1",
                "belief_text": "PATH shim 递归",
                "pitfall": "fork bomb",
                "solution": "REAL_GIT 绝对路径",
            },
            {
                "topic": "fork-bomb",
                "id": "b2",
                "belief_text": "settings 污染",
                "pitfall": "Backport 回写",
                "solution": "清 user.json",
            },
        ],
    )
    res = SkillCrystallizer(root=tmp_path).scan_and_crystallize()
    assert res["crystallized_count"] == 1
    skill_file = tmp_path / ".agents" / "skills" / "fork-bomb" / "SKILL.md"
    assert skill_file.exists()
    content = skill_file.read_text(encoding="utf-8")
    assert "fork-bomb" in content
    assert "REAL_GIT" in content  # solution 进 SKILL.md


def test_no_crystallize_single_topic(tmp_path: Path) -> None:
    """单条 Topic (非特殊白名单) → 不结晶."""
    SkillCrystallizer = _load_crystallizer()
    _write_beliefs(tmp_path, [{"topic": "random-topic", "id": "b1"}])
    res = SkillCrystallizer(root=tmp_path).scan_and_crystallize()
    assert res["crystallized_count"] == 0


def test_no_beliefs_file(tmp_path: Path) -> None:
    """无 beliefs index → 不崩, 返回空."""
    SkillCrystallizer = _load_crystallizer()
    res = SkillCrystallizer(root=tmp_path).scan_and_crystallize()
    assert res["crystallized_count"] == 0
    assert res["total_beliefs_scanned"] == 0


def test_idempotent_existing_skill(tmp_path: Path) -> None:
    """SKILL.md 已存在 → 跳过 (不覆盖, skipped)."""
    SkillCrystallizer = _load_crystallizer()
    _write_beliefs(
        tmp_path,
        [
            {"topic": "dup", "id": "b1"},
            {"topic": "dup", "id": "b2"},
        ],
    )
    cr = SkillCrystallizer(root=tmp_path)
    first = cr.scan_and_crystallize()
    assert first["crystallized_count"] == 1
    # 第二次跑: SKILL.md 已存在 → skip
    second = cr.scan_and_crystallize()
    assert second["crystallized_count"] == 0
