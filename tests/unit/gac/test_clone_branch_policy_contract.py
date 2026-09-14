"""Cross-component contract for managed clone branch admission."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
AGENT_CLONE_PATH = ROOT / "bin" / "gac" / "agent-clone.py"
BRANCH_CHECK_PATH = ROOT / "bin" / "gac" / "check-branch-naming.py"
POLICY_PATH = ROOT / ".omo" / "_truth" / "registry" / "branch-prefix-policy.yaml"

_GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "contract-test",
    "GIT_AUTHOR_EMAIL": "contract-test@example.invalid",
    "GIT_COMMITTER_NAME": "contract-test",
    "GIT_COMMITTER_EMAIL": "contract-test@example.invalid",
}
_ASCII_ID_PROBES = tuple(chr(code) for code in range(33, 127) if chr(code) != "/")
_ID_LENGTH_SCAN_LIMIT = 256


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


agent_clone = _load_module("agent_clone_branch_contract", AGENT_CLONE_PATH)
branch_checker = _load_module("branch_naming_contract", BRANCH_CHECK_PATH)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(_GIT_ENV)
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result


def _git_accepts_branch(branch: str) -> bool:
    return (
        subprocess.run(
            ["git", "check-ref-format", "--branch", branch],
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        == 0
    )


def _producer_accepts(actor: str, attempt: str) -> bool:
    branch = f"agent/{actor}--{attempt}"
    return bool(
        agent_clone.AGENT_ID_RE.fullmatch(actor)
        and agent_clone.AGENT_ID_RE.fullmatch(attempt)
        and _git_accepts_branch(branch)
    )


def _identity(actor: str, attempt: str) -> dict:
    return {
        "schema": agent_clone.SCHEMA_IDENTITY_ATTEMPT,
        "agent_id": actor,
        "actor_id": actor,
        "delivery_attempt_id": attempt,
        "working_branch": f"agent/{actor}--{attempt}",
    }


@pytest.fixture()
def produced_clone_identity(tmp_path: Path) -> dict:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "--bare", "-b", "main")

    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init", "-b", "main")
    (seed / "README.md").write_text("branch contract\n", encoding="utf-8")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-m", "seed")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "origin", "main")

    attempt_root = tmp_path / "attempt"
    attempt_root.mkdir()
    clone = attempt_root / "ws"
    env = os.environ.copy()
    env.update(_GIT_ENV)
    result = subprocess.run(
        [
            sys.executable,
            str(AGENT_CLONE_PATH),
            "create",
            "--json",
            "--agent-id",
            "Agent.Core_1",
            "--delivery-attempt-id",
            "Attempt_1.2",
            "--source",
            str(remote),
            "--destination",
            str(clone),
            "--no-submodules",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    identity = json.loads((clone / ".git" / "agent-clone-identity.json").read_text())
    assert agent_clone.AGENT_ID_RE.fullmatch(identity["actor_id"])
    assert agent_clone.AGENT_ID_RE.fullmatch(identity["delivery_attempt_id"])
    return agent_clone.validate_clone_identity(identity)


def test_production_v2_clone_branch_is_accepted_by_policy(
    produced_clone_identity: dict,
) -> None:
    policy = branch_checker.load_policy(str(POLICY_PATH))
    branch = produced_clone_identity["working_branch"]

    ok, matched_prefix, _info = branch_checker.check_branch(branch, policy)

    assert ok, f"production-valid clone branch rejected by policy: {branch!r}"
    assert matched_prefix == "agent"


def test_agent_policy_aliases_cannot_drift() -> None:
    policy = branch_checker.load_policy(str(POLICY_PATH))

    assert policy["naming"]["agent"] == policy["prefixes"]["agent"]["pattern"]


def test_existing_worktree_namespace_remains_accepted() -> None:
    policy = branch_checker.load_policy(str(POLICY_PATH))

    ok, matched_prefix, _info = branch_checker.check_branch("agent/test-agent/test-session", policy)

    assert ok
    assert matched_prefix == "agent"


def test_agent_policy_is_fully_anchored() -> None:
    policy = branch_checker.load_policy(str(POLICY_PATH))

    ok, _matched_prefix, _info = branch_checker.check_branch("agent/test-agent/test-session\n", policy)

    assert not ok


def test_policy_acceptance_does_not_replace_clone_identity_validation(
    produced_clone_identity: dict,
) -> None:
    policy = branch_checker.load_policy(str(POLICY_PATH))
    policy_valid_but_identity_wrong = {
        **produced_clone_identity,
        "working_branch": "agent/test-agent/test-session",
    }
    accepted, matched_prefix, _info = branch_checker.check_branch(
        policy_valid_but_identity_wrong["working_branch"], policy
    )

    assert accepted
    assert matched_prefix == "agent"
    with pytest.raises(agent_clone.ToolError) as error:
        agent_clone.validate_clone_identity(policy_valid_but_identity_wrong)
    assert error.value.reason == "identity_invalid"


@pytest.mark.parametrize(
    ("actor", "attempt"),
    [
        ("actor.lock", "attempt"),
        ("actor--part", "attempt"),
        ("actor", "attempt--part"),
    ],
)
def test_independent_clone_policy_accepts_git_valid_identity_edges(
    actor: str,
    attempt: str,
) -> None:
    identity = agent_clone.validate_clone_identity(_identity(actor, attempt))
    branch = identity["working_branch"]
    assert _git_accepts_branch(branch)

    policy = branch_checker.load_policy(str(POLICY_PATH))
    ok, matched_prefix, _info = branch_checker.check_branch(branch, policy)
    assert ok
    assert matched_prefix == "agent"


def test_ambiguous_separator_is_policy_valid_but_identity_bound() -> None:
    first_identity = agent_clone.validate_clone_identity(_identity("a", "b--c"))
    second_identity = agent_clone.validate_clone_identity(_identity("a--b", "c"))
    branch = first_identity["working_branch"]
    assert branch == second_identity["working_branch"]

    policy = branch_checker.load_policy(str(POLICY_PATH))
    ok, matched_prefix, _info = branch_checker.check_branch(branch, policy)
    assert ok
    assert matched_prefix == "agent"

    mismatched_identity = {**first_identity, "agent_id": "other"}
    with pytest.raises(agent_clone.ToolError) as error:
        agent_clone.validate_clone_identity(mismatched_identity)
    assert error.value.reason == "identity_invalid"


@pytest.mark.parametrize(
    "branch",
    [
        "agent/actor..name--attempt",
        "agent/actor--attempt.",
        "agent/actor--attempt.lock",
        "agent/actor--attempt\n",
    ],
)
def test_independent_clone_policy_rejects_git_invalid_refs(branch: str) -> None:
    assert not _git_accepts_branch(branch), branch

    policy = branch_checker.load_policy(str(POLICY_PATH))
    ok, _matched_prefix, _info = branch_checker.check_branch(branch, policy)
    assert not ok


def test_agent_policy_tracks_current_producer_id_boundaries() -> None:
    policy = branch_checker.load_policy(str(POLICY_PATH))
    singleton_ids = [char for char in _ASCII_ID_PROBES if agent_clone.AGENT_ID_RE.fullmatch(char)]
    assert singleton_ids, "AGENT_ID_RE no longer has an ASCII singleton seed"
    seed = singleton_ids[0]

    accepted_lengths = [
        length for length in range(1, _ID_LENGTH_SCAN_LIMIT + 1) if agent_clone.AGENT_ID_RE.fullmatch(seed * length)
    ]
    assert accepted_lengths
    assert accepted_lengths == list(range(1, accepted_lengths[-1] + 1))
    assert accepted_lengths[-1] < _ID_LENGTH_SCAN_LIMIT
    maximum = accepted_lengths[-1]

    candidate_ids = {
        "",
        " ",
        "\t",
        "\n",
        "\x7f",
        "中",
        seed * maximum,
        seed * (maximum + 1),
    }
    candidate_ids.update(_ASCII_ID_PROBES)
    candidate_ids.update(seed + char for char in _ASCII_ID_PROBES)

    for candidate in sorted(candidate_ids):
        for actor, attempt in ((candidate, seed), (seed, candidate)):
            branch = f"agent/{actor}--{attempt}"
            expected = _producer_accepts(actor, attempt)
            actual, matched_prefix, _info = branch_checker.check_branch(branch, policy)

            assert actual is expected, (
                f"producer/policy drift for actor={actor!r}, attempt={attempt!r}, branch={branch!r}"
            )
            if actual:
                assert matched_prefix == "agent"
