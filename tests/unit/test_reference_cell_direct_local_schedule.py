import importlib.util
import plistlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SERVICES = ROOT / ".omo/_truth/registry/services.yaml"
SERVICE_ID = "omostation.reference-cell-direct-local-smoke"
HOME = Path.home()


def _jobs():
    return yaml.safe_load((ROOT / ".omo/cron/registry.yaml").read_text(encoding="utf-8"))["jobs"]


def _service() -> dict:
    """Absolute paths belong to the registry, never to this test file."""
    for doc in yaml.safe_load_all(SERVICES.read_text(encoding="utf-8")):
        for entry in (doc or {}).get("services", []):
            if entry.get("id") == SERVICE_ID:
                return entry
    raise AssertionError(f"{SERVICE_ID} is not declared in services.yaml")


def _declared_program(service: dict) -> list[str]:
    program = service["program"]
    return [program["interpreter"], program["entrypoint"], *program["args"]]


def _repo_root(service: dict) -> Path:
    # outputs.stdout == <root>/runtime/cron/<name>.log
    return Path(service["outputs"]["stdout"]).parents[2]


def test_reference_cell_smoke_is_registered_twelve_hour_launchd_job() -> None:
    job = next(job for job in _jobs() if job["name"] == "reference-cell-direct-local-smoke")
    command = "PYTHONDONTWRITEBYTECODE=1 " + " ".join(_declared_program(_service()))
    assert job["schedule"] == "0 */12 * * *"
    assert job["planes"] == ["launchd"]
    assert job["reality"] == "installed"
    assert job["status"] == "active"
    assert job["sfop_slot"] == "S"
    assert job["command"] == command


def test_reference_cell_smoke_plist_uses_fresh_main_and_attempt_evidence() -> None:
    service = _service()
    declared = _declared_program(service)
    root = _repo_root(service)
    payload = plistlib.loads(
        (ROOT / "runtime/cron/com.omostation.reference-cell-direct-local-smoke.plist").read_bytes()
    )
    arguments = payload["ProgramArguments"]
    variables = payload["EnvironmentVariables"]
    assert payload["StartInterval"] == 43200
    assert payload["RunAtLoad"] is False
    assert arguments == declared
    assert arguments[-1] == "--json"
    assert payload["WorkingDirectory"] == arguments[arguments.index("--code-root") + 1]
    assert arguments[arguments.index("--code-root") + 1] == str(HOME / ".local/share/zhixing-dashboard/code-main")
    assert arguments[arguments.index("--attempts-root") + 1] == str(HOME / "agents/codex-agent-os-reference-cell/attempts")
    assert arguments[arguments.index("--omo-src") + 1] == str(root / "projects/omo/src")
    assert str(HOME / ".local/bin") in variables["PATH"].split(":")


def test_smoke_module_exposes_safe_schema() -> None:
    spec = importlib.util.spec_from_file_location(
        "reference_cell_direct_local_smoke_test",
        ROOT / "bin/ssot/reference-cell-direct-local-smoke.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.SCHEMA == "direct-local-reference-cell-r0-canary/v1"
    assert "attempt-local" in module.__doc__
