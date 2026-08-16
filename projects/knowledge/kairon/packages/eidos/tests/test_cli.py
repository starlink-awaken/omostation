# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false
from __future__ import annotations

import json

from eidos import cli


def test_validate_recognizes_concrete_knowledge_card_type(tmp_path, capsys):
    payload = {
        "id": "kc-1",
        "title": "Test Card",
        "content": "Valid content",
        "source": "unit-test",
        "source_type": "test",
        "schema_type": "KnowledgeCard",
    }
    path = tmp_path / "card.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = cli.main(["validate", "--type", "KnowledgeCard", str(path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert '"is_valid": true' in out
    assert "Unknown schema type" not in out


def test_list_includes_concrete_types(capsys):
    exit_code = cli.main(["list"])

    out = capsys.readouterr().out.splitlines()
    assert exit_code == 0
    assert "KnowledgeCard" in out
    assert "Fact" in out
    assert "OntologyNode" in out


def test_define_help_exposes_interactive_flag(capsys):
    try:
        cli.main(["define", "--help"])
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    assert "--interactive" in out


def test_define_interactive_writes_schema_file(tmp_path, monkeypatch, capsys):
    answers = iter(
        [
            "title",
            "str",
            "y",
            "Card title",
            "",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    output = tmp_path / "schema.json"

    exit_code = cli.main(["define", "MySchema", "--interactive", "--output", str(output)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["name"] == "MySchema"
    assert "title" in payload["fields"]
    assert "defined successfully" in out
