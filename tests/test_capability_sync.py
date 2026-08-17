"""Test capability-sync.py — 四源扫描生成器测试"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "bin" / "capability-sync.py"


def _load_module() -> object:
    """加载 capability-sync 模块（带连字符，用 importlib）"""
    spec = importlib.util.spec_from_loader("capability_sync", loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__dict__["__file__"] = str(SCRIPT_PATH)
    exec(
        compile(SCRIPT_PATH.read_text(encoding="utf-8"), str(SCRIPT_PATH), "exec"),
        module.__dict__,
    )
    return module


@pytest.fixture(scope="session")
def cap_sync() -> object:
    """缓存加载的模块"""
    return _load_module()


@pytest.fixture
def temp_skill_dir(tmp_path: Path) -> Generator[Path]:
    """临时 skills 目录 fixture"""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    yield skills_dir


def test_scan_skill_frontmatter_valid(cap_sync, temp_skill_dir: Path) -> None:
    """测试扫描有效 SKILL.md frontmatter"""
    # 写入测试 skill
    skill1 = temp_skill_dir / "test-skill" / "SKILL.md"
    skill1.parent.mkdir(parents=True, exist_ok=True)
    skill1.write_text(
        "---\nname: test-skill\ndescription: 这是个测试 skill\n---\ncontent here",
        encoding="utf-8",
    )

    capabilities = cap_sync.scan_skill_frontmatter(temp_skill_dir, "test-source")
    assert len(capabilities) == 1
    assert capabilities[0].name == "test-skill"
    assert capabilities[0].source == "test-source"
    assert "测试 skill" in capabilities[0].description
    assert capabilities[0].invoke == "Skill 工具 /test-skill"


def test_scan_skill_frontmatter_multiple(cap_sync, temp_skill_dir: Path) -> None:
    """测试扫描多个 skills"""
    # 写入多个 skills
    for i in range(3):
        skill = temp_skill_dir / f"skill-{i}" / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(
            f"---\nname: skill-{i}\ndescription: 描述 {i}\n---\n",
            encoding="utf-8",
        )

    capabilities = cap_sync.scan_skill_frontmatter(temp_skill_dir, "test")
    assert len(capabilities) == 3
    names = {c.name for c in capabilities}
    assert names == {"skill-0", "skill-1", "skill-2"}


def test_scan_skill_frontmatter_malformed(cap_sync, temp_skill_dir: Path) -> None:
    """测试容忍坏 frontmatter 文件不崩"""
    # 正常 skill
    good_skill = temp_skill_dir / "good" / "SKILL.md"
    good_skill.parent.mkdir(parents=True, exist_ok=True)
    good_skill.write_text("---\nname: good\n---\n", encoding="utf-8")

    # 坏 skill（无 frontmatter）
    bad_skill1 = temp_skill_dir / "bad1" / "SKILL.md"
    bad_skill1.parent.mkdir(parents=True, exist_ok=True)
    bad_skill1.write_text("no frontmatter here", encoding="utf-8")

    # 坏 skill（只有开头的 ---）
    bad_skill2 = temp_skill_dir / "bad2" / "SKILL.md"
    bad_skill2.parent.mkdir(parents=True, exist_ok=True)
    bad_skill2.write_text("---\nonly start", encoding="utf-8")

    capabilities = cap_sync.scan_skill_frontmatter(temp_skill_dir, "test")
    assert len(capabilities) == 1
    assert capabilities[0].name == "good"


def test_scan_skill_frontmatter_empty_name(cap_sync, temp_skill_dir: Path) -> None:
    """测试跳过空 name 的 skill"""
    skill = temp_skill_dir / "empty" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("---\nname: \ndescription: desc\n---\n", encoding="utf-8")

    capabilities = cap_sync.scan_skill_frontmatter(temp_skill_dir, "test")
    assert len(capabilities) == 0


def test_scan_skill_frontmatter_description_truncate(cap_sync, temp_skill_dir: Path) -> None:
    """测试描述截断（MAX_DESC_LEN=120）"""
    long_desc = "x" * 200
    skill = temp_skill_dir / "long" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        f"---\nname: long\ndescription: {long_desc}\n---\n",
        encoding="utf-8",
    )

    capabilities = cap_sync.scan_skill_frontmatter(temp_skill_dir, "test")
    assert len(capabilities) == 1
    assert len(capabilities[0].description) == 120  # MAX_DESC_LEN
    assert capabilities[0].description.endswith("...")


def test_scan_skill_frontmatter_missing_dir(cap_sync, tmp_path: Path) -> None:
    """测试不存在的目录返回空列表"""
    missing = tmp_path / "nonexistent"
    capabilities = cap_sync.scan_skill_frontmatter(missing, "test")
    assert capabilities == []


def test_capability_truncate(cap_sync) -> None:
    """测试 Capability._truncate 方法"""
    cap_class = cap_sync.Capability

    # 短文本不截断
    cap = cap_class(source="test", name="test", description="short", invoke="invoke")
    assert cap.description == "short"

    # 长文本截断
    long_text = "x" * 200
    cap = cap_class(source="test", name="test", description=long_text, invoke="invoke")
    assert len(cap.description) == 120  # MAX_DESC_LEN
    assert cap.description.endswith("...")


def test_capability_as_dict(cap_sync) -> None:
    """测试 Capability.as_dict 方法"""
    cap_class = cap_sync.Capability
    cap = cap_class(
        source="test-source",
        name="Test Skill",
        description="测试描述",
        invoke="Skill 工具 /test",
    )

    result = cap.as_dict()
    assert result["source"] == "test-source"
    assert result["name"] == "Test Skill"
    assert result["description"] == "测试描述"
    assert result["invoke"] == "Skill 工具 /test"
    assert "id" in result
    assert result["id"] == "test-source:test-skill"


def test_find_capabilities_case_insensitive(cap_sync, tmp_path: Path) -> None:
    """测试 find 大小写不敏感"""
    # 写入临时 registry
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(
        "# GENERATED\n"
        "generated_at:\n"
        '  "2026-08-15T00:00:00+00:00"\n'
        "generator:\n"
        "  capability-sync/v1\n"
        "capabilities:\n"
        '  - id: "test:Test-Skill"\n'
        "    source: test\n"
        '    name: "Test-Skill"\n'
        '    description: "测试 Skill 大小写"\n'
        '    invoke: "invoke"\n'
        '  - id: "test:another"\n'
        "    source: test\n"
        '    name: "another"\n'
        '    description: "另一个"\n'
        '    invoke: "invoke"\n',
        encoding="utf-8",
    )

    # 测试大写查询
    results = cap_sync.find_capabilities(cap_sync.load_registry(registry_path), "TEST")
    assert len(results) == 1
    assert results[0].name == "Test-Skill"

    # 测试小写查询
    results = cap_sync.find_capabilities(cap_sync.load_registry(registry_path), "skill")
    assert len(results) == 1
    assert results[0].name == "Test-Skill"


def test_find_capabilities_query_both_name_and_description(cap_sync, tmp_path: Path) -> None:
    """测试查询匹配 name 和 description"""
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(
        "# GENERATED\n"
        "generated_at:\n"
        '  "2026-08-15T00:00:00+00:00"\n'
        "generator:\n"
        "  capability-sync/v1\n"
        "capabilities:\n"
        '  - id: "test:name-match"\n'
        "    source: test\n"
        '    name: "name-match"\n'
        '    description: "desc"\n'
        '    invoke: "invoke"\n'
        '  - id: "test:desc-match"\n'
        "    source: test\n"
        '    name: "desc-match"\n'
        '    description: "keyword in description"\n'
        '    invoke: "invoke"\n',
        encoding="utf-8",
    )

    results = cap_sync.find_capabilities(cap_sync.load_registry(registry_path), "keyword")
    assert len(results) == 1
    assert results[0].name == "desc-match"


def test_find_capabilities_no_results(cap_sync, tmp_path: Path) -> None:
    """测试无结果返回空列表"""
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(
        "# GENERATED\n"
        "generated_at:\n"
        '  "2026-08-15T00:00:00+00:00"\n'
        "generator:\n"
        "  capability-sync/v1\n"
        "capabilities:\n"
        '  - id: "test:skill"\n'
        "    source: test\n"
        '    name: "skill"\n'
        '    description: "desc"\n'
        '    invoke: "invoke"\n',
        encoding="utf-8",
    )

    results = cap_sync.find_capabilities(cap_sync.load_registry(registry_path), "nonexistent")
    assert results == []


def test_check_drift_no_change(cap_sync) -> None:
    """测试无漂移返回 False"""
    cap1 = cap_sync.Capability(source="test", name="skill", description="desc", invoke="invoke")
    assert cap_sync.check_drift([cap1], [cap1]) is False


def test_check_drift_added(cap_sync) -> None:
    """测试新增 capability 返回 True（漂移）"""
    cap1 = cap_sync.Capability(source="test", name="skill", description="desc", invoke="invoke")
    cap2 = cap_sync.Capability(source="test", name="new", description="new", invoke="invoke")
    assert cap_sync.check_drift([cap1], [cap1, cap2]) is True


def test_check_drift_removed(cap_sync) -> None:
    """测试删除 capability 返回 True（漂移）"""
    cap1 = cap_sync.Capability(source="test", name="skill", description="desc", invoke="invoke")
    cap2 = cap_sync.Capability(source="test", name="old", description="old", invoke="invoke")
    assert cap_sync.check_drift([cap1, cap2], [cap1]) is True


def test_check_drift_description_changed(cap_sync) -> None:
    """测试描述变化返回 True（漂移）"""
    cap1_old = cap_sync.Capability(source="test", name="skill", description="old desc", invoke="invoke")
    cap1_new = cap_sync.Capability(source="test", name="skill", description="new desc", invoke="invoke")
    assert cap_sync.check_drift([cap1_old], [cap1_new]) is True


def test_check_drift_invoke_changed(cap_sync) -> None:
    """测试 invoke 变化返回 True（漂移）"""
    cap1_old = cap_sync.Capability(source="test", name="skill", description="desc", invoke="old invoke")
    cap1_new = cap_sync.Capability(source="test", name="skill", description="desc", invoke="new invoke")
    assert cap_sync.check_drift([cap1_old], [cap1_new]) is True


def test_scan_all_sources_dedup(cap_sync, tmp_path: Path) -> None:
    """测试四源合并去重（按 source:name）"""
    # 创建临时 skills
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill = skills_dir / "test" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("---\nname: test\n---\n", encoding="utf-8")

    capabilities = cap_sync.scan_all_sources(tmp_path)

    # 去重检查（同一个 name 不应重复）
    names = [f"{c.source}:{c.name}" for c in capabilities]
    assert len(names) == len(set(names))


def test_load_registry_empty_file(cap_sync, tmp_path: Path) -> None:
    """测试加载空文件返回空列表"""
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("", encoding="utf-8")
    assert cap_sync.load_registry(empty_file) == []


def test_load_registry_missing_file(cap_sync, tmp_path: Path) -> None:
    """测试加载不存在的文件返回空列表"""
    missing = tmp_path / "nonexistent.yaml"
    assert cap_sync.load_registry(missing) == []
