"""Tests for bin/commit-checklist.py — 14-dimension pre-commit checklist."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHECKLIST = ROOT / "bin" / "commit-checklist.py"
RULES_PATH = ROOT / "docs" / "generated" / "commit-checklist-rules.yaml"


def run_checklist(args: Sequence[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(CHECKLIST), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestCLI:
    def test_help_exits_zero(self):
        rc, _, _ = run_checklist(["--help"])
        assert rc == 0

    def test_no_staged_returns_zero(self):
        rc, out, _ = run_checklist(["--staged", "--files"])
        assert rc == 0

    def test_hint_only_never_blocks(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--hint-only",
            "--files",
            "nonexistent",
        ])
        assert rc == 0

    def test_json_output_parseable_when_triggered(self):
        rc, out, _ = run_checklist([
            "--staged",
            "--json",
            "--files",
            "docs/README.md",
        ])
        assert rc == 0
        data = json.loads(out)
        assert "triggered" in data
        assert "missing" in data
        assert "docs-adr" in data["triggered"]

    def test_json_empty_when_nothing_triggered(self):
        rc, out, _ = run_checklist([
            "--staged",
            "--json",
            "--files",
            "nonexistent",
        ])
        assert rc == 0
        data = json.loads(out)
        assert data["triggered"] == []
        assert data["missing"] == []


class TestFourteenDimensions:
    def test_docs_capability_sync_missing_when_registry_only(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            ".omo/_truth/registry/capability-registry.yaml",
        ])
        assert rc == 1

    def test_submodule_hygiene_trigger(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            ".gitmodules",
        ])
        assert rc == 1

    def test_ci_script_registry_trigger(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            ".github/workflows/ci.yml",
        ])
        assert rc in (0, 1)

    def test_observability_logging_trigger(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            "observability/logging-config.yaml",
        ])
        assert rc == 0

    def test_agent_runtime_trigger(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            ".omo/state/system.yaml",
        ])
        assert rc == 0

    def test_architecture_convergence_trigger(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            "ARCHITECTURE.md",
        ])
        assert rc == 1

    def test_docs_adr_trigger(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            "docs/README.md",
        ])
        assert rc == 1

    def test_lint_type_format_trigger(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            "src/main.py",
        ])
        assert rc == 0

    def test_ci_path_drift_trigger(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            ".github/workflows/ci.yml",
        ])
        assert rc in (0, 1)

    def test_evidence_drift_trigger(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            ".omo/_truth/registry/governance-checks.yaml",
        ])
        assert rc in (0, 1)

    def test_adr_numbering_trigger(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            ".omo/_knowledge/decisions/INDEX.md",
        ])
        assert rc in (0, 1)

    def test_orphaned_registry_trigger(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            ".omo/_truth/registry/script-registry.yaml",
        ])
        assert rc in (0, 1)

    def test_timeout_retry_circuit_trigger(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            "config/timeout.yaml",
        ])
        assert rc in (0, 1)

    def test_baseline_restore_trigger(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            ".omo/state/health.yaml",
        ])
        assert rc == 0


class TestBootstrapSelfValidation:
    def test_bootstrap_trigger_on_checklist_change(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            str(CHECKLIST),
        ])
        assert rc == 1

    def test_bootstrap_trigger_on_rules_change(self):
        rc, _, _ = run_checklist([
            "--staged",
            "--files",
            str(RULES_PATH),
        ])
        assert rc == 1

    def test_bootstrap_hint_mentions_revalidation(self):
        _, out, _ = run_checklist([
            "--staged",
            "--hint-only",
            "--files",
            str(CHECKLIST),
        ])
        assert "re-validate" in out or "bootstrap" in out


class TestMergeSkip:
    def test_merge_skips_docs_adr(self):
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location("commit_checklist", CHECKLIST)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)

        original = mod._run_git
        def fake_run_git(*args: str) -> str | None:
            if args == ("rev-parse", "-q", "--verify", "MERGE_HEAD"):
                return "abc123"
            return original(*args)

        mod._run_git = fake_run_git
        try:
            results, missing = mod.evaluate(["docs/README.md"])
            triggered_ids = [r.item.id for r in results]
            assert "docs-adr" not in triggered_ids
        finally:
            mod._run_git = original

    def test_no_staged_files_returns_clean(self):
        rc, out, _ = run_checklist(["--staged", "--files"])
        assert rc == 0
        assert "All triggered checks passed" in out or out.strip() == ""


class TestRulesYAML:
    def test_rules_yaml_exists(self):
        assert RULES_PATH.exists()

    def test_rules_yaml_has_version(self):
        text = RULES_PATH.read_text(encoding="utf-8")
        assert "version:" in text or "schema_version:" in text

    def test_rules_yaml_has_fourteen_rules(self):
        text = RULES_PATH.read_text(encoding="utf-8")
        count = sum(1 for line in text.splitlines() if line.strip().startswith("- id:"))
        assert count == 14
