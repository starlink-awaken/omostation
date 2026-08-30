from __future__ import annotations

import json
import plistlib
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPT = Path(__file__).parents[1] / "bin" / "gac" / "documents-domain-owner-job.py"


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
        [sys.executable, str(SCRIPT), "consumer-audit", *args, "--json"],
        check=False,
        capture_output=True,
        text=True,
    )


def _scheduled_result(
    tmp_path: Path,
    command: str,
    *,
    documents_name: str = "Documents",
) -> subprocess.CompletedProcess[str]:
    documents = tmp_path / documents_name
    documents.mkdir()
    crontab = tmp_path / "crontab"
    crontab.write_text("# no active cron consumer\n", encoding="utf-8")
    launch = tmp_path / "LaunchAgents"
    launch.mkdir()
    scheduled = tmp_path / "Scheduled"
    skill = scheduled / "health" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(f"run `{command}`\n", encoding="utf-8")
    return _run(
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


def test_scheduled_home_executor_with_trailing_argv_is_forbidden(tmp_path: Path) -> None:
    result = _scheduled_result(
        tmp_path,
        "bash ~/Documents/@学习进化/_control/l4-kernel.sh all",
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["status"] == "violations"
    assert payload["summary"]["forbidden_executors"] == 1
    assert payload["consumers"][0]["relative_path"] == "@学习进化/_control/l4-kernel.sh"
    assert payload["consumers"][0]["execution_mode"] == "documents-executor"


def test_scheduled_absolute_executor_with_trailing_argv_is_forbidden(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    result = _scheduled_result(
        tmp_path,
        f"python3 {documents}/@学习进化/_control/health.py --verbose",
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["summary"]["forbidden_executors"] == 1
    assert payload["consumers"][0]["relative_path"] == "@学习进化/_control/health.py"


def test_extensionless_control_executor_is_forbidden(tmp_path: Path) -> None:
    result = _scheduled_result(
        tmp_path,
        "~/Documents/@学习进化/_control/executors/kems-mcp --stdio",
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["summary"]["forbidden_executors"] == 1
    assert payload["consumers"][0]["relative_path"] == "@学习进化/_control/executors/kems-mcp"
    assert payload["consumers"][0]["family"] == "learning-runtime"


def test_quoted_absolute_executor_path_preserves_spaces(tmp_path: Path) -> None:
    documents = tmp_path / "Documents Root"
    result = _scheduled_result(
        tmp_path,
        f'python3 "{documents}/@学习进化/_control/job with space.sh" --check',
        documents_name=documents.name,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["summary"]["forbidden_executors"] == 1
    assert payload["consumers"][0]["relative_path"] == "@学习进化/_control/job with space.sh"


def test_quoted_home_executor_path_preserves_spaces(tmp_path: Path) -> None:
    result = _scheduled_result(
        tmp_path,
        'python3 "~/Documents/@学习进化/_control/job with space.sh" --check',
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["summary"]["forbidden_executors"] == 1
    assert payload["consumers"][0]["relative_path"] == "@学习进化/_control/job with space.sh"


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
    assert result.returncode == 1
    assert payload["schema"] == "documents.consumer-audit.v1"
    assert payload["status"] == "violations"
    assert payload["summary"]["active"] == 3
    assert all(item["active"] is True for item in payload["consumers"])
    assert {item["family"] for item in payload["consumers"]} == {"public-runtime", "learning-runtime"}
    assert payload["consumer_ids"] == sorted(payload["consumer_ids"])
    assert all(item["execution_mode"] == "documents-executor" for item in payload["consumers"])
    assert payload["summary"]["forbidden_executors"] == 3
    assert len(payload["errors"]) == 3


def test_workspace_owner_read_is_not_forbidden_executor(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()
    crontab = tmp_path / "crontab"
    crontab.write_text(
        '0 6 * * * cd "$HOME/.local/share/omostation/accepted-20260902" && '
        'uv run --with pyyaml python bin/gac/documents-domain-owner-job.py '
        'controller-preflight --documents-root "$HOME/Documents"\n',
        encoding="utf-8",
    )
    (tmp_path / "launch").mkdir()
    (tmp_path / "scheduled").mkdir()

    result = _run(
        "--documents-root",
        str(documents),
        "--registry",
        str(_registry(tmp_path / "migrations.yaml")),
        "--crontab",
        str(crontab),
        "--launch-agents-root",
        str(tmp_path / "launch"),
        "--scheduled-root",
        str(tmp_path / "scheduled"),
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["summary"]["forbidden_executors"] == 0
    assert payload["summary"]["workspace_read_owners"] == 1
    assert payload["consumers"][0]["execution_mode"] == "workspace-owner-read"
    assert payload["consumers"][0]["writes_documents"] is False
    assert payload["consumers"][0]["forbidden_executor"] is False


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


def test_unmatched_domain_gateway_content_reference_does_not_fail(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    gateway = documents / "@公共" / "_control" / "README.md"
    gateway.parent.mkdir(parents=True)
    gateway.write_text(
        "historical command: `python3 @公共/_control/executors/kems --help`\n",
        encoding="utf-8",
    )
    crontab = tmp_path / "crontab"
    crontab.write_text("# no active consumer\n", encoding="utf-8")
    launch = tmp_path / "launch"
    launch.mkdir()
    scheduled = tmp_path / "scheduled"
    scheduled.mkdir()

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
    assert payload["status"] == "ok"
    assert payload["summary"]["unmatched"] == 0
    assert payload["summary"]["content_references"] == 1
    assert payload["consumers"][0]["execution_mode"] == "content-reference"


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
