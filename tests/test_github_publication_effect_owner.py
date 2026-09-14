"""Wave B4: prove four GitHub workflows cannot publish refs/PRs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATHS = (
    ROOT / ".github" / "workflows" / "omo-autopilot.yml",
    ROOT / ".github" / "workflows" / "reusable-submodule-bump-pr.yml",
    ROOT / ".github" / "workflows" / "submodule-autobump.yml",
    ROOT / ".github" / "workflows" / "submodule-freshness-gatekeeper.yml",
)

FORBIDDEN_PUBLICATION_PATTERNS = (
    re.compile(r"\bgit\s+commit\b"),
    re.compile(r"\bgit\s+push\b"),
    re.compile(r"\bgh\s+pr\s+create\b"),
    re.compile(r"peter-evans/create-pull-request"),
    re.compile(r"/git/refs"),
    re.compile(r"\bcreateRef\b"),
    re.compile(r"\bupdateRef\b"),
    re.compile(r"\bgit\s+update-ref\b"),
    re.compile(r"\bgit\s+push\b[^\n]*--force\b"),
)

WRITE_CAPABLE_TOKEN_RE = re.compile(
    r"token\s*:\s*\$\{\{\s*secrets\.(CROSS_REPO_TOKEN|bot_token|[A-Z0-9_]*TOKEN)\s*\}\}"
)

PROPOSAL_KEY_GROUPS = (
    ("base_sha", "base_ref", "base"),
    ("head_sha", "head_ref", "head", "proposed_sha", "target_sha"),
    ("proposed_ref", "base_ref", "ref"),
    ("remediation", "managed_remediation_entrypoint", "instruction"),
)


def _load_workflow(path: Path) -> tuple[str, dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert isinstance(data, dict), f"{path} did not parse to a mapping"
    return text, data


def _walk_permissions(node: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        perms = node.get("permissions")
        if isinstance(perms, dict):
            found.append(perms)
        for value in node.values():
            found.extend(_walk_permissions(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_walk_permissions(item))
    return found


def _checkout_steps(node: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        uses = str(node.get("uses") or "")
        if uses.startswith("actions/checkout@"):
            found.append(node)
        for value in node.values():
            found.extend(_checkout_steps(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_checkout_steps(item))
    return found


def _upload_artifact_steps(node: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        uses = str(node.get("uses") or "")
        if uses.startswith("actions/upload-artifact@"):
            found.append(node)
        for value in node.values():
            found.extend(_upload_artifact_steps(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_upload_artifact_steps(item))
    return found


@pytest.mark.parametrize("path", WORKFLOW_PATHS, ids=lambda p: p.name)
def test_workflow_yaml_parses(path: Path) -> None:
    assert path.is_file(), f"missing workflow: {path}"
    _load_workflow(path)


@pytest.mark.parametrize("path", WORKFLOW_PATHS, ids=lambda p: p.name)
def test_no_contents_write_permission(path: Path) -> None:
    _text, data = _load_workflow(path)
    for perms in _walk_permissions(data):
        contents = perms.get("contents")
        assert contents != "write", f"{path.name} grants contents: write ({perms})"


@pytest.mark.parametrize("path", WORKFLOW_PATHS, ids=lambda p: p.name)
def test_no_write_capable_checkout_token(path: Path) -> None:
    text, data = _load_workflow(path)
    for step in _checkout_steps(data):
        with_block = step.get("with") or {}
        assert isinstance(with_block, dict)
        token = with_block.get("token")
        assert token is None, f"{path.name} checkout uses write-capable token: {token}"
    assert WRITE_CAPABLE_TOKEN_RE.search(text) is None, (
        f"{path.name} still references a write-capable checkout token"
    )


@pytest.mark.parametrize("path", WORKFLOW_PATHS, ids=lambda p: p.name)
def test_no_publication_writers(path: Path) -> None:
    text, _data = _load_workflow(path)
    for pattern in FORBIDDEN_PUBLICATION_PATTERNS:
        match = pattern.search(text)
        assert match is None, (
            f"{path.name} contains forbidden publication effect {pattern.pattern!r}: "
            f"{match.group(0)!r}"
        )


@pytest.mark.parametrize("path", WORKFLOW_PATHS, ids=lambda p: p.name)
def test_named_proposal_artifact_contract(path: Path) -> None:
    text, data = _load_workflow(path)
    uploads = _upload_artifact_steps(data)
    assert uploads, f"{path.name} missing actions/upload-artifact step"

    named = []
    for step in uploads:
        with_block = step.get("with") or {}
        assert isinstance(with_block, dict)
        name = with_block.get("name")
        artifact_path = with_block.get("path")
        assert isinstance(name, str) and name.strip(), f"{path.name} artifact missing name"
        assert isinstance(artifact_path, str) and artifact_path.strip(), (
            f"{path.name} artifact missing path"
        )
        assert "proposal" in name.lower(), (
            f"{path.name} artifact name must identify a proposal: {name}"
        )
        named.append(name)

    assert named, f"{path.name} has no named proposal artifact"

    for group in PROPOSAL_KEY_GROUPS:
        assert any(key in text for key in group), (
            f"{path.name} proposal generation missing one of {group}"
        )

    assert "PUBLICATION_OWNER_REQUIRED" in text or "managed_remediation_entrypoint" in text, (
        f"{path.name} missing remediation metadata"
    )
    assert "publication-proposal.json" in text or "proposal-artifact" in text, (
        f"{path.name} missing proposal artifact file path"
    )


def test_all_four_workflows_have_zero_ref_or_pr_write_effects() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in WORKFLOW_PATHS)
    for pattern in FORBIDDEN_PUBLICATION_PATTERNS:
        match = pattern.search(combined)
        assert match is None, f"combined workflows still contain {match.group(0)!r}"
    assert "contents: write" not in combined
    assert "peter-evans/create-pull-request" not in combined
    assert WRITE_CAPABLE_TOKEN_RE.search(combined) is None
