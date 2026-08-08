"""Tests for SEMA skill auto-crystallization engine (BET-Y1Q2-T6-06).

Closed-loop: record_belief (2nd for topic) -> auto-crystallize -> SKILL.md.
"""

from pathlib import Path

from omo.omo_belief import MOSBeliefManager
from omo.omo_crystallizer import (
    CRYSTALLIZATION_THRESHOLD,
    SkillCrystallizer,
    _sanitize_topic_dir,
)


def test_sanitize_topic_dir():
    assert _sanitize_topic_dir("workflow:bet-execution") == "workflow:bet-execution"
    assert _sanitize_topic_dir("my topic") == "my-topic"
    assert _sanitize_topic_dir("a/b/c") == "a-b-c"


def test_crystallizer_below_threshold(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    crystallizer = SkillCrystallizer(skills_dir=skills_dir)

    beliefs = [{"id": "belief-0001", "topic": "test-topic", "belief": "single belief"}]
    result = crystallizer.check_and_crystallize(beliefs=beliefs, topic="test-topic")

    assert result["status"] == "below_threshold"
    assert result["count"] == 1
    assert not (skills_dir / "test-topic").exists()


def test_crystallizer_at_threshold(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    crystallizer = SkillCrystallizer(skills_dir=skills_dir)

    beliefs = [
        {"id": "belief-0001", "topic": "test-topic", "belief": "first"},
        {"id": "belief-0002", "topic": "test-topic", "belief": "second"},
    ]
    result = crystallizer.check_and_crystallize(beliefs=beliefs, topic="test-topic")

    assert result["status"] == "crystallized"
    assert result["count"] == 2
    skill_file = skills_dir / "test-topic" / "SKILL.md"
    assert skill_file.exists()
    content = skill_file.read_text(encoding="utf-8")
    assert "test-topic" in content
    assert "belief-0001" in content
    assert "belief-0002" in content


def test_crystallizer_includes_lessons_and_contexts(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    crystallizer = SkillCrystallizer(skills_dir=skills_dir)

    beliefs = [
        {"id": "b-0001", "topic": "git-shim", "belief": "first"},
        {"id": "b-0002", "topic": "git-shim", "belief": "second"},
    ]
    lessons = [
        {
            "id": "l-0001",
            "belief_id": "b-0001",
            "pitfall": "raw git bypasses shim",
            "solution": "use swarm-git",
            "severity": "critical",
        },
    ]
    contexts = [
        {
            "id": "ctx-0001",
            "belief_id": "b-0001",
            "scope_path": "bin/gac/*",
            "applicable_tags": ["git-shim"],
        },
    ]

    result = crystallizer.check_and_crystallize(
        beliefs=beliefs, lessons=lessons, contexts=contexts, topic="git-shim"
    )

    assert result["status"] == "crystallized"
    assert result["lessons"] == 1
    assert result["contexts"] == 1

    content = (skills_dir / "git-shim" / "SKILL.md").read_text(encoding="utf-8")
    assert "Pitfall" in content
    assert "raw git bypasses shim" in content
    assert "swarm-git" in content
    assert "bin/gac/*" in content


def test_crystallizer_idempotent(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    crystallizer = SkillCrystallizer(skills_dir=skills_dir)

    beliefs = [
        {"id": "b-0001", "topic": "idem", "belief": "first"},
        {"id": "b-0002", "topic": "idem", "belief": "second"},
    ]

    r1 = crystallizer.check_and_crystallize(beliefs=beliefs, topic="idem")
    assert r1["status"] == "crystallized"

    r2 = crystallizer.check_and_crystallize(beliefs=beliefs, topic="idem")
    assert r2["status"] == "already_exists"


def test_crystallizer_batch_scan(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    crystallizer = SkillCrystallizer(skills_dir=skills_dir)

    beliefs = [
        {"id": "b-0001", "topic": "topic-a", "belief": "a1"},
        {"id": "b-0002", "topic": "topic-a", "belief": "a2"},
        {"id": "b-0003", "topic": "topic-b", "belief": "b1"},
    ]

    result = crystallizer.check_and_crystallize(beliefs=beliefs)

    assert result["crystallized_count"] == 1
    topics_crystallized = [s["topic"] for s in result["crystallized"]]
    assert "topic-a" in topics_crystallized
    assert "topic-b" not in topics_crystallized


def test_auto_trigger_on_record_belief(tmp_path: Path):
    """2nd belief for same topic triggers auto-crystallization via MOSBeliefManager."""
    import omo.omo_crystallizer as crystallizer_mod

    original = crystallizer_mod.DEFAULT_SKILLS_DIR
    skills_dir = tmp_path / "auto-skills"
    crystallizer_mod.DEFAULT_SKILLS_DIR = skills_dir

    try:
        mos = MOSBeliefManager(root=tmp_path)
        mos.record_belief(topic="auto-test", belief_text="first belief")

        skill_file = skills_dir / "auto-test" / "SKILL.md"
        assert not skill_file.exists(), "should not crystallize on 1st belief"

        mos.record_belief(topic="auto-test", belief_text="second belief")

        assert skill_file.exists(), "should auto-crystallize on 2nd belief"
        content = skill_file.read_text(encoding="utf-8")
        assert "auto-test" in content
    finally:
        crystallizer_mod.DEFAULT_SKILLS_DIR = original


def test_auto_trigger_no_crystallize_below_threshold(tmp_path: Path):
    """1 belief for a topic should NOT trigger crystallization."""
    import omo.omo_crystallizer as crystallizer_mod

    original = crystallizer_mod.DEFAULT_SKILLS_DIR
    skills_dir = tmp_path / "no-crystal"
    crystallizer_mod.DEFAULT_SKILLS_DIR = skills_dir

    try:
        mos = MOSBeliefManager(root=tmp_path)
        mos.record_belief(topic="lonely-topic", belief_text="only one")

        assert not (skills_dir / "lonely-topic").exists()
    finally:
        crystallizer_mod.DEFAULT_SKILLS_DIR = original


def test_auto_trigger_with_pitfall_and_solution(tmp_path: Path):
    """Beliefs with pitfall+solution should produce richer SKILL.md."""
    import omo.omo_crystallizer as crystallizer_mod

    original = crystallizer_mod.DEFAULT_SKILLS_DIR
    skills_dir = tmp_path / "rich-skills"
    crystallizer_mod.DEFAULT_SKILLS_DIR = skills_dir

    try:
        mos = MOSBeliefManager(root=tmp_path)
        mos.record_belief(
            topic="rich-topic",
            belief_text="first lesson",
            pitfall="forgot to lock",
            solution="always use fcntl_lock",
        )
        mos.record_belief(
            topic="rich-topic",
            belief_text="second lesson",
            pitfall="race condition on write",
            solution="use atomic write",
        )

        skill_file = skills_dir / "rich-topic" / "SKILL.md"
        assert skill_file.exists()
        content = skill_file.read_text(encoding="utf-8")
        assert "forgot to lock" in content
        assert "fcntl_lock" in content
        assert "atomic write" in content
    finally:
        crystallizer_mod.DEFAULT_SKILLS_DIR = original


def test_threshold_constant():
    assert CRYSTALLIZATION_THRESHOLD == 2
