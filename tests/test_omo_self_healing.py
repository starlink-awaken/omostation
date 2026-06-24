from __future__ import annotations

from pathlib import Path

from omo.omo_self_healing import load_rules


def test_load_rules_accepts_multi_document_yaml(tmp_path: Path) -> None:
    rules_path = tmp_path / "healing-rules.yaml"
    rules_path.write_text(
        "---\n- name: heal-a\n  event_types: [runtime.error]\n  threshold: 2\n---\n"
        "- name: heal-b\n  event_types: [runtime.warn]\n  threshold: 3\n",
        encoding="utf-8",
    )

    rules = load_rules(rules_path)

    assert [rule.name for rule in rules] == ["heal-a", "heal-b"]
    assert rules[0].threshold == 2
    assert rules[1].threshold == 3
