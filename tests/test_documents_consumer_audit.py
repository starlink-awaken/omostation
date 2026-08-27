from __future__ import annotations

import json
import plistlib
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPT = Path(__file__).parents[1] / "bin" / "gac" / "documents-consumer-audit.py"


def _registry(path: Path) -> Path:
    path.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "workspace.omostation/v1",
                "kind": "DocumentsContentPlaneMigrations",
                "owner": "governance-team",
                "candidate_kinds": ["runtime", "cache"],
                "major_surfaces": [],
                "families": [
                    {
                        "id": "public-runtime",
                        "source_globs": ["@公共/_runtime/**"],
                    },
                    {
                        "id": "learning-runtime",
                        "source_globs": ["@学习进化/_control/**"],
                    },
                ],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--json"],
        check=False,
        capture_output=True,
        text=True,
    )


def test_audit_detects_active_sources_and_ignores_comment_only_lines(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()
    crontab = tmp_path / "crontab"
    crontab.write_text(
        '* * * * * /usr/bin/python3 "$HOME/Documents/@公共/_runtime/watch-dispatch.py"\n'
        '# * * * * * /usr/bin/python3 "$HOME/Documents/@公共/_runtime/old.py"\n',
        encoding="utf-8",
    )
    launch = tmp_path / "LaunchAgents"
    launch.mkdir()
    (launch / "com.example.plist").write_bytes(
        plistlib.dumps(
            {
                "Label": "com.example",
                "ProgramArguments": ["/bin/bash", str(documents / "@学习进化/_control/run.sh")],
            }
        )
    )
    scheduled = tmp_path / "Scheduled"
    scheduled.mkdir()
    (scheduled / "health" / "SKILL.md").parent.mkdir()
    (scheduled / "health" / "SKILL.md").write_text(
        f"run `python3 {documents}/@公共/_runtime/health.py`\n", encoding="utf-8"
    )

    result = _run(
        "--documents-root",
        str(documents),
        "--registry",
        str(_registry(tmp_path / "migrations.yaml")),
        "--crontab",
        str(crontab),
        "--launch-agents-root",
        str(launch),
        "--scheduled-root",
        str(scheduled),
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["schema"] == "documents.consumer-audit.v1"
    assert payload["summary"]["active"] == 3
    assert all(item["active"] is True for item in payload["consumers"])
    assert {item["family"] for item in payload["consumers"]} == {"public-runtime", "learning-runtime"}
    assert payload["consumer_ids"] == sorted(payload["consumer_ids"])


def test_unknown_active_consumer_fails_closed(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()
    crontab = tmp_path / "crontab"
    crontab.write_text(
        '* * * * * python3 "$HOME/Documents/@未知/_runtime/unknown.py"\n',
        encoding="utf-8",
    )
    (tmp_path / "missing-launch").mkdir()
    (tmp_path / "missing-scheduled").mkdir()

    result = _run(
        "--documents-root",
        str(documents),
        "--registry",
        str(_registry(tmp_path / "migrations.yaml")),
        "--crontab",
        str(crontab),
        "--launch-agents-root",
        str(tmp_path / "missing-launch"),
        "--scheduled-root",
        str(tmp_path / "missing-scheduled"),
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["status"] == "violations"
    assert any("unmatched migration family" in error for error in payload["errors"])


def test_evidence_writes_only_to_explicit_workspace_path(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()
    crontab = tmp_path / "crontab"
    crontab.write_text("# no active consumer\n", encoding="utf-8")
    evidence = tmp_path / "workspace" / "evidence.json"
    (tmp_path / "missing-launch").mkdir()
    (tmp_path / "missing-scheduled").mkdir()

    result = _run(
        "--documents-root",
        str(documents),
        "--registry",
        str(_registry(tmp_path / "migrations.yaml")),
        "--crontab",
        str(crontab),
        "--launch-agents-root",
        str(tmp_path / "missing-launch"),
        "--scheduled-root",
        str(tmp_path / "missing-scheduled"),
        "--evidence",
        str(evidence),
        "--workspace-root",
        str(tmp_path / "workspace"),
    )

    assert result.returncode == 0
    assert evidence.is_file()
    assert json.loads(evidence.read_text(encoding="utf-8"))["schema"] == "documents.consumer-audit.v1"
    assert not list(documents.rglob("*"))
