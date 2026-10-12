import plistlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / ".omo/cron/registry.yaml"
SERVICES = ROOT / ".omo/_truth/registry/services.yaml"
PLIST = ROOT / "runtime/cron/com.omostation.agent-cell-semantic-smoke.plist"
SERVICE_ID = "omostation.agent-cell-semantic-smoke"


def _job() -> dict:
    jobs = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["jobs"]
    return next(job for job in jobs if job["name"] == "agent-cell-semantic-smoke")


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


def test_semantic_canary_is_registered_as_low_frequency_launchd_job() -> None:
    job = _job()
    command = "PYTHONDONTWRITEBYTECODE=1 " + " ".join(_declared_program(_service()))
    assert job["schedule"] == "17 */6 * * *"
    assert job["planes"] == ["launchd"]
    assert job["status"] == "active"
    assert job["reality"] == "installed"
    assert job["command"] == command
    assert "--state-dir" in job["command"]
    assert "claims_authority" not in job["command"]


def test_semantic_canary_plist_targets_canonical_runtime_without_external_effects() -> None:
    service = _service()
    declared = _declared_program(service)
    root = _repo_root(service)
    state_dir = declared[declared.index("--state-dir") + 1]
    payload = plistlib.loads(PLIST.read_bytes())
    assert payload["Label"] == "com.omostation.agent-cell-semantic-smoke"
    assert payload["StartInterval"] == 21600
    assert payload["RunAtLoad"] is False
    assert payload["ProgramArguments"] == declared
    assert payload["WorkingDirectory"] == str(root)
    variables = payload["EnvironmentVariables"]
    assert variables["AGENT_CELL_ROOT"] == str(root)
    assert variables["AGENT_CELL_STATE_DIR"] == state_dir
    assert variables["PYTHONPATH"] == str(root / "projects/omo/src")
    assert state_dir == str(root / ".omo/state/agent-cell/semantic")
