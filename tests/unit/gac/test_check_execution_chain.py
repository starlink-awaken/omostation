"""Drive the shipped execution-chain coverage checker."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "check-execution-chain.py"


def _load_mod():
    spec = importlib.util.spec_from_file_location("check_execution_chain", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_script_registry(directory: Path, item_id: str, triggers: list[str] | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    trig = triggers or []
    if trig:
        trig_yaml = "\n".join(["triggers:"] + [f"  - {t}" for t in trig])
    else:
        trig_yaml = "triggers: []"
    body = (
        "schema: script-registry/v1\n"
        f"id: {item_id}\n"
        "name: Fixture\n"
        "category: governance\n"
        f"{trig_yaml}\n"
    )
    (directory / "fixture.yaml").write_text(body, encoding="utf-8")


def _write_ci_surfaces(path: Path, tool: str, *, gate: bool = False, workflow: str = "(none)") -> None:
    path.write_text(
        "\n".join(
            [
                "version: 1",
                "surfaces:",
                f"- id: fixture-{Path(tool).stem}",
                f"  tool: {tool}",
                f"  workflow: {workflow}",
                f"  gate: {str(gate).lower()}",
                "  triggers:",
                "  - manual",
                "  status: active",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_cron(path: Path, command: str) -> None:
    path.write_text(
        "\n".join(
            [
                "version: 1",
                "jobs:",
                "  - name: fixture-job",
                "    schedule: '0 9 * * *'",
                f"    command: {command!r}",
                "",
            ]
        ),
        encoding="utf-8",
    )


class TestShippedCheckFunction:
    def test_item_in_script_registry_is_not_fail_closed(self, tmp_path: Path) -> None:
        scripts = tmp_path / "scripts"
        _write_script_registry(scripts, "bin/gac/known.py", triggers=["manual"])
        ci = tmp_path / "ci.yaml"
        ci.write_text("version: 1\nsurfaces: []\n", encoding="utf-8")
        cron = tmp_path / "cron.yaml"
        cron.write_text("version: 1\njobs: []\n", encoding="utf-8")
        hooks = tmp_path / "hooks"
        hooks.mkdir()
        mod = _load_mod()
        result = mod.check(
            script_registry_dir=scripts,
            ci_surfaces_path=ci,
            cron_registry_path=cron,
            hooks_dir=hooks,
        )
        assert result["ok"] is True
        assert result["errors"] == []
        assert result["inventories"]["script_registry"] >= 1
        ids = [i["id"] for i in result["items"]]
        assert "bin/gac/known.py" in ids

    def test_orphan_extra_active_fails_closed(self, tmp_path: Path) -> None:
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        ci = tmp_path / "ci.yaml"
        ci.write_text("version: 1\nsurfaces: []\n", encoding="utf-8")
        cron = tmp_path / "cron.yaml"
        cron.write_text("version: 1\njobs: []\n", encoding="utf-8")
        hooks = tmp_path / "hooks"
        hooks.mkdir()
        mod = _load_mod()
        result = mod.check(
            script_registry_dir=scripts,
            ci_surfaces_path=ci,
            cron_registry_path=cron,
            hooks_dir=hooks,
            extra_active=["bin/gac/ghost-orphan.py"],
        )
        assert result["ok"] is False
        assert any("CR-EXEC-CHAIN-01" in err for err in result["errors"])
        assert any("ghost-orphan.py" in err for err in result["errors"])

    def test_ci_surface_counts_as_trigger_not_error(self, tmp_path: Path) -> None:
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        ci = tmp_path / "ci.yaml"
        _write_ci_surfaces(ci, "bin/gac/wired.py", gate=True, workflow="gac-gate.yml")
        cron = tmp_path / "cron.yaml"
        cron.write_text("version: 1\njobs: []\n", encoding="utf-8")
        hooks = tmp_path / "hooks"
        hooks.mkdir()
        mod = _load_mod()
        result = mod.check(
            script_registry_dir=scripts,
            ci_surfaces_path=ci,
            cron_registry_path=cron,
            hooks_dir=hooks,
            extra_active=["bin/gac/wired.py"],
        )
        assert result["ok"] is True
        wired = next(i for i in result["items"] if i["id"] == "bin/gac/wired.py")
        assert "hook" in wired["triggers"] or "CI" in wired["triggers"] or "manual" in wired["triggers"]


class TestGateInventory:
    def test_execution_chain_is_blocking_not_soft(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "gac_local_gate_exec_chain",
            REPO_ROOT / "bin" / "gac" / "gac-local-gate.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        ids = {name for name, _cmd in module.CHECKS}
        assert "execution-chain" in ids
        assert "execution-chain" not in module.SOFT_CHECKS
        assert "execution-chain" not in module.CI_ONLY_CHECKS
        assert "execution-chain" not in module.OPS_ONLY_CHECKS
        selected = module.gate_checks(
            "files", ["bin/gac/check-execution-chain.py"], "", False
        )
        selected_ids = {name for name, _cmd in selected}
        assert "execution-chain" in selected_ids
        command = dict(selected)["execution-chain"]
        assert command[:2] == ["bin/gac/check-execution-chain.py", "--json"]


class TestShippedCli:
    def test_live_json_ok(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout
        data = json.loads(proc.stdout)
        assert data["ok"] is True
        assert data["errors"] == []
        inv = data["inventories"]
        assert inv["script_registry"] > 0
        assert inv["ci_surfaces"] > 0
        assert inv["cron_jobs"] > 0
        assert data["examined"] > 0
        assert isinstance(data.get("warnings"), list)
