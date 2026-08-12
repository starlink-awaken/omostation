"""Behavior tests for the read-only agent-pool observation preflight."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

TOOL = Path(__file__).resolve().parents[3] / "bin" / "gac" / "agent-pool-observe.py"
SPEC = importlib.util.spec_from_file_location("agent_pool_observe", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


class Runner:
    def __init__(self, responses: dict[tuple[str, ...], object]):
        self.responses = responses
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv: list[str], timeout: float):
        key = tuple(argv)
        self.calls.append(key)
        response = self.responses.get(key)
        if isinstance(response, BaseException):
            raise response
        if response is None:
            raise FileNotFoundError(argv[0])
        return response


def completed(argv: list[str], stdout: str = "", rc: int = 0):
    return subprocess.CompletedProcess(argv, rc, stdout=stdout, stderr="failure" if rc else "")


def write_registry(tmp_path: Path, *, probe: list[str] | None = None, quota: bool = True) -> tuple[Path, Path]:
    providers = tmp_path / "providers.yaml"
    workers = tmp_path / "workers.yaml"
    provider: dict = {
        "id": "codex",
        "launch_argv": ["codex", "exec"],
        "version_probe_argv": probe if probe is not None else ["codex", "--version"],
    }
    if quota:
        provider["quota_observation"] = {"source": "codexbar", "provider": "codex"}
    providers.write_text(
        yaml.safe_dump(
            {
                "observation_contract": {
                    "version_probe_timeout_seconds": 5,
                    "quota_probe_timeout_seconds": 5,
                },
                "quota_observer": {"executable": "codexbar", "argv_prefix": ["codexbar", "usage"]},
                "compute_plane": {
                    "route_uri": "bos://compute/aetherforge/infer",
                    "health_probe_argv": ["omlxc", "status", "--json"],
                },
                "providers": [provider],
            }
        ),
        encoding="utf-8",
    )
    workers.write_text(
        yaml.safe_dump(
            {
                "workers": [
                    {
                        "id": "codex",
                        "class": "external_agent_cli",
                        "provider_ref": "codex",
                        "enabled": False,
                        "admission_state": "declared",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return providers, workers


def quota_payload(*, timestamp: datetime = NOW, email: str = "private@example.test") -> str:
    return json.dumps(
        [
            {
                "provider": "codex",
                "accountEmail": email,
                "identity": {"id": "secret"},
                "usage": {
                    "updatedAt": timestamp.isoformat().replace("+00:00", "Z"),
                    "dataConfidence": "high",
                    "primary": {"usedPercent": 25, "resetsAt": "2026-08-13T15:00:00Z"},
                    "secondary": {"usedPercent": 10, "resetsAt": "2026-08-20T00:00:00Z"},
                },
            }
        ]
    )


def healthy_responses() -> dict[tuple[str, ...], object]:
    return {
        ("codex", "--version"): completed(["codex", "--version"], "codex 1.2.3\n"),
        (
            "codexbar", "usage", "--provider", "codex", "--format", "json", "--status", "--no-credits", "--no-color",
        ): completed(["codexbar"], quota_payload()),
        ("omlxc", "status", "--json"): completed(["omlxc"], '{"status":"ready","identity":"do-not-leak"}'),
    }


def observe(tmp_path: Path, runner: Runner):
    providers, workers = write_registry(tmp_path)
    return MODULE.observe_pool(providers, workers, runner=runner, clock=lambda: NOW)


def test_observation_is_read_only_sanitized_and_digest_verifiable(tmp_path):
    result = observe(tmp_path, Runner(healthy_responses()))

    assert result["mode"] == "observation_only"
    assert result["dispatch"] == "forbidden"
    assert result["agents"][0]["probe"]["state"] == "observed"
    assert result["agents"][0]["admission_state"] == "declared"
    assert result["agents"][0]["quota"]["state"] == "observed"
    encoded = json.dumps(result, sort_keys=True)
    assert "private@example.test" not in encoded
    assert "secret" not in encoded
    assert "do-not-leak" not in encoded
    assert MODULE.verify_manifest(result) == []


@pytest.mark.parametrize(
    ("response", "expected_state", "expected_reason"),
    [
        (None, "unavailable", "command_missing"),
        (completed(["codex"], rc=7), "unavailable", "probe_nonzero"),
        (subprocess.TimeoutExpired(["codex", "--version"], 5), "error", "probe_timeout"),
    ],
)
def test_missing_nonzero_and_timeout_are_not_admitted(tmp_path, response, expected_state, expected_reason):
    replies = healthy_responses()
    replies[("codex", "--version")] = response
    result = observe(tmp_path, Runner(replies))

    agent = result["agents"][0]
    assert agent["probe"]["state"] == expected_state
    assert agent["probe"]["reason"] == expected_reason
    assert agent["admission_state"] == "declared"


def test_unsafe_registry_argv_is_rejected_without_execution(tmp_path):
    providers, workers = write_registry(tmp_path, probe=["codex;rm", "--version"], quota=False)
    runner = Runner({("omlxc", "status", "--json"): completed(["omlxc"], '{"status":"ready"}')})
    result = MODULE.observe_pool(providers, workers, runner=runner, clock=lambda: NOW)

    assert result["agents"][0]["probe"] == {"state": "error", "reason": "unsafe_argv"}
    assert ("codex;rm", "--version") not in runner.calls


@pytest.mark.parametrize(
    ("usage", "reason"),
    [
        ("not-json", "malformed"),
        (quota_payload(timestamp=NOW - timedelta(hours=2)), "stale"),
    ],
)
def test_malformed_or_stale_quota_is_unknown(tmp_path, usage, reason):
    replies = healthy_responses()
    quota_argv = ("codexbar", "usage", "--provider", "codex", "--format", "json", "--status", "--no-credits", "--no-color")
    replies[quota_argv] = completed(["codexbar"], usage)
    result = observe(tmp_path, Runner(replies))

    assert result["agents"][0]["quota"] == {"state": "unknown", "reason": reason}


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda payload: payload[0]["usage"].pop("updatedAt"), "timestamp_missing"),
        (lambda payload: payload[0]["usage"].__setitem__("dataConfidence", "unknown"), "confidence_unknown"),
    ],
)
def test_quota_without_timestamp_or_with_unknown_confidence_is_unknown(tmp_path, mutate, reason):
    payload = json.loads(quota_payload())
    mutate(payload)
    replies = healthy_responses()
    quota_argv = ("codexbar", "usage", "--provider", "codex", "--format", "json", "--status", "--no-credits", "--no-color")
    replies[quota_argv] = completed(["codexbar"], json.dumps(payload))
    result = observe(tmp_path, Runner(replies))

    assert result["agents"][0]["quota"] == {"state": "unknown", "reason": reason}


@pytest.mark.parametrize(
    ("response", "state", "reason"),
    [
        (completed(["omlxc"], '{"status":"degraded"}'), "degraded", "reported_degraded"),
        (completed(["omlxc"], "not-json"), "error", "malformed"),
    ],
)
def test_compute_health_is_independent_and_never_provider_quota(tmp_path, response, state, reason):
    replies = healthy_responses()
    replies[("omlxc", "status", "--json")] = response
    result = observe(tmp_path, Runner(replies))

    assert result["compute"] == {
        "route_ref": "bos://compute/aetherforge/infer",
        "state": state,
        "reason": reason,
    }
    assert "compute" not in result["agents"][0]["quota"]


def test_tampered_manifest_fails_independent_verify(tmp_path):
    result = observe(tmp_path, Runner(healthy_responses()))
    result["agents"][0]["probe"]["state"] = "admitted"

    errors = MODULE.verify_manifest(result)
    assert "manifest_digest_mismatch" in errors


def test_external_expected_digest_detects_recomputed_tampering(tmp_path):
    result = observe(tmp_path, Runner(healthy_responses()))
    expected_digest = result["manifest_digest"]
    result["agents"][0]["probe"]["state"] = "admitted"
    result["manifest_digest"] = MODULE.manifest_digest(result)

    assert MODULE.verify_manifest(result) == []
    assert MODULE.verify_manifest(result, expected_digest=expected_digest) == ["expected_digest_mismatch"]


def test_verify_cli_requires_fixed_expected_checksum_when_supplied(tmp_path):
    result = observe(tmp_path, Runner(healthy_responses()))
    expected_digest = result["manifest_digest"]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(result), encoding="utf-8")
    command = [sys.executable, str(TOOL), "verify", "--manifest", str(manifest_path), "--expected-digest", expected_digest, "--json"]

    valid = subprocess.run(command, capture_output=True, text=True, check=False)
    assert valid.returncode == 0
    assert json.loads(valid.stdout)["checksum"] == expected_digest
    result["agents"][0]["probe"]["state"] = "admitted"
    result["manifest_digest"] = MODULE.manifest_digest(result)
    manifest_path.write_text(json.dumps(result), encoding="utf-8")
    tampered = subprocess.run(command, capture_output=True, text=True, check=False)
    assert tampered.returncode == 1
    assert json.loads(tampered.stdout)["errors"] == ["expected_digest_mismatch"]


def test_sensitive_nested_quota_window_is_not_projected(tmp_path):
    payload = json.loads(quota_payload())
    payload[0]["usage"]["primary"]["identity"] = {"token": "do-not-project"}
    replies = healthy_responses()
    quota_argv = ("codexbar", "usage", "--provider", "codex", "--format", "json", "--status", "--no-credits", "--no-color")
    replies[quota_argv] = completed(["codexbar"], json.dumps(payload))
    result = observe(tmp_path, Runner(replies))

    quota = result["agents"][0]["quota"]
    assert quota["state"] == "observed"
    assert "primary" not in quota["windows"]
    assert "secondary" in quota["windows"]
    assert "do-not-project" not in json.dumps(quota)


def test_each_candidate_version_probe_runs_once_without_retries(tmp_path):
    runner = Runner(healthy_responses())
    observe(tmp_path, runner)

    assert runner.calls.count(("codex", "--version")) == 1


def test_real_registry_only_uses_observation_contract_and_never_admits_candidates():
    root = TOOL.parents[2]
    providers_path = root / ".omo/_truth/registry/capability-providers.yaml"
    workers_path = root / ".omo/_truth/registry/workers.yaml"
    providers_document = yaml.safe_load(providers_path.read_text(encoding="utf-8"))
    workers_document = list(yaml.safe_load_all(workers_path.read_text(encoding="utf-8")))[-1]
    providers = {provider["id"]: provider for provider in providers_document["providers"]}
    external_workers = [worker for worker in workers_document["workers"] if worker["class"] == "external_agent_cli"]

    class RegistryRunner:
        def __init__(self):
            self.calls: list[tuple[str, ...]] = []

        def __call__(self, argv: list[str], timeout: float):
            self.calls.append(tuple(argv))
            if argv == ["omlxc", "status", "--json"]:
                return completed(argv, '{"status":"ready"}')
            if argv[:2] == ["codexbar", "usage"]:
                provider = argv[3]
                return completed(
                    argv,
                    json.dumps(
                        [{"provider": provider, "usage": {"updatedAt": "2026-08-13T12:00:00Z", "dataConfidence": "high", "primary": {"usedPercent": 1}}}]
                    ),
                )
            return completed(argv, f"{argv[0]} 1.0\n")

    runner = RegistryRunner()
    result = MODULE.observe_pool(providers_path, workers_path, runner=runner, clock=lambda: NOW)

    assert len(result["agents"]) == 12
    assert {agent["provider_id"] for agent in result["agents"]} <= providers.keys()
    expected_version_calls = [tuple(providers[worker["provider_ref"]]["version_probe_argv"]) for worker in external_workers]
    for argv in expected_version_calls:
        assert runner.calls.count(argv) == 1

    expected_quota_calls = {
        (
            "codexbar",
            "usage",
            "--provider",
            provider["quota_observation"]["provider"],
            "--format",
            "json",
            "--status",
            "--no-credits",
            "--no-color",
        )
        for provider in providers.values()
        if provider.get("quota_observation", {}).get("source") == "codexbar"
        and provider["id"] in {worker["provider_ref"] for worker in external_workers}
    }
    allowed_calls = set(expected_version_calls) | expected_quota_calls | {("omlxc", "status", "--json")}
    assert set(runner.calls) <= allowed_calls
    assert not any(call == tuple(provider["launch_argv"]) for call in runner.calls for provider in providers.values())
    declared = [worker for worker in external_workers if worker["enabled"] is False]
    declared_ids = {worker["id"] for worker in declared}
    assert all(agent["admission_state"] == "declared" for agent in result["agents"] if agent["worker_id"] in declared_ids)
    assert next(agent for agent in result["agents"] if agent["worker_id"] == "kilo")["admission_state"] == "declared"
