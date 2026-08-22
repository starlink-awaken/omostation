#!/usr/bin/env python3
"""agent-clone.py - independent agent clone topology (BET-Y1Q1-T1-05 D1 pilot).

Python 3 stdlib-only CLI for the first production slice of the
independent-agent-clone topology.  Subcommands:

  create     --agent-id ID --source URL_OR_PATH --destination PATH
             [--revision REF] [--no-submodules]
  manifest   --clone PATH --output PATH
  verify     --clone PATH --manifest PATH
  changeset  --clone PATH --baseline PATH --output PATH
  verify-changeset --clone PATH --baseline PATH --changeset PATH --agent-id ID
  guard      --workspace PATH [--integration-root PATH]

Exit contract: 0 = success, 1 = policy/verification failure,
2 = usage/tool/environment error.

This tool never mutates source repositories, never runs destructive git
commands (rm / reset --hard / clean / stash / force push), and never
emits objects/info/alternates.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit, urlunsplit

SCHEMA_MANIFEST = "agent-clone-manifest/v1"
SCHEMA_MANIFEST_ATTEMPT = "agent-clone-manifest/v2"
SCHEMA_CHANGESET = "cross-repo-changeset/v1"
SCHEMA_CHANGESET_CLAIMS = "cross-repo-changeset/v2"
SCHEMA_CHANGESET_ATTEMPT = "cross-repo-changeset/v3"
SCHEMA_CLAIM_SNAPSHOT = "agent-workflow-claim-snapshot/v1"
SCHEMA_IDENTITY = "agent-clone-identity/v1"
SCHEMA_IDENTITY_ATTEMPT = "agent-clone-identity/v2"
SCHEMA_READINESS = "clone-readiness/v1"
SCHEMA_READINESS_ATTEMPT = "clone-readiness/v2"
SCHEMA_SUBMODULE_PROFILE = "clone-submodule-profile/v1"
SCHEMA_PROVENANCE = "clone-provenance/v1"
SCHEMA_PROVENANCE_ATTEMPT = "clone-provenance/v2"
IDENTITY_FILENAME = "agent-clone-identity.json"
READINESS_FILENAME = "agent-clone-readiness.json"
PROVENANCE_FILENAME = "agent-clone-provenance.json"
CLAIMS_AUTHORITY_POLICY = ".omo/_truth/registry/swarm-coordination.yaml"
ACCOUNT_WORKSPACE_ROOT = Path(pwd.getpwuid(os.getuid()).pw_dir) / "Workspace"
AGENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
GOVERNANCE_SUBMODULES = (
    "projects/agora",
    "projects/cockpit",
    "projects/cockpit-ui",
    "projects/ecos",
    "projects/omo",
)
SUBMODULE_PROFILES = ("root-only", "governance", "full")
READINESS_PROFILES = (*SUBMODULE_PROFILES, "custom")
GITHUB_COMPONENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
AUTHOR_OVERRIDE_ENV = (
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
)
GIT_REPOSITORY_SCOPE_ENV = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_DIR",
    "GIT_GRAFT_FILE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
)

EXIT_OK = 0
EXIT_POLICY = 1
EXIT_USAGE = 2


class ToolError(Exception):
    """A structured failure with a stable reason and exit code."""

    def __init__(
        self,
        reason: str,
        message: str,
        exit_code: int = EXIT_POLICY,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.exit_code = exit_code
        self.details = details or {}


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------


def git(cwd: str | None, *args: str) -> subprocess.CompletedProcess:
    """Run git with an argv list (never a shell string)."""
    cmd = ["git"]
    if cwd is not None:
        cmd += ["-C", cwd]
    cmd += list(args)
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise ToolError("git_unavailable", f"cannot execute git: {exc}", EXIT_USAGE) from exc


def git_isolated(cwd: str, *args: str) -> subprocess.CompletedProcess:
    """Run an on-disk repository probe without caller repository scope.

    Git hooks export values such as a relative ``GIT_INDEX_FILE`` for the
    superproject.  Letting those values leak into ``git -C <submodule>`` makes
    Git resolve the superproject's scope inside the child repository.  Config
    and index command-line overrides can similarly spoof provenance probes.
    Preserve ordinary process policy (for example global/system config
    selection and author variables), but remove only repository-scoped state.
    """
    env = os.environ.copy()
    for key in GIT_REPOSITORY_SCOPE_ENV:
        env.pop(key, None)
    try:
        return subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except OSError as exc:
        raise ToolError("git_unavailable", f"cannot execute git: {exc}", EXIT_USAGE) from exc


def canonical(path: str) -> str:
    """Absolute, symlink-resolved canonical path."""
    return os.path.realpath(path)


def git_common_dir(repo_root: str) -> str:
    """Absolute path of the clone's Git common dir."""
    proc = git(repo_root, "rev-parse", "--git-common-dir")
    if proc.returncode != 0:
        raise ToolError(
            "not_a_repository",
            f"{repo_root} is not inside a git repository: {proc.stderr.strip()}",
            EXIT_POLICY,
        )
    out = proc.stdout.strip()
    if not os.path.isabs(out):
        out = os.path.join(repo_root, out)
    return canonical(out)


def root_head(repo_root: str) -> str:
    """Current HEAD SHA of a repository."""
    proc = git(repo_root, "rev-parse", "HEAD")
    if proc.returncode != 0:
        raise ToolError(
            "not_a_repository",
            f"{repo_root} is not a git repository: {proc.stderr.strip()}",
            EXIT_POLICY,
        )
    return proc.stdout.strip()


def branch_state(repo_root: str) -> tuple[str | None, bool]:
    """Return (branch_name, detached)."""
    proc = git(repo_root, "symbolic-ref", "--short", "-q", "HEAD")
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip(), False
    return None, True


def gitlinks(repo_root: str) -> dict[str, str]:
    """Map of gitlink path -> pinned SHA from the root index."""
    proc = git(repo_root, "ls-files", "--stage")
    if proc.returncode != 0:
        raise ToolError("git_failed", proc.stderr.strip(), EXIT_USAGE)
    links: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "\t" not in line:
            continue
        meta, path = line.split("\t", 1)
        parts = meta.split()
        if len(parts) == 3 and parts[0] == "160000":
            links[path] = parts[1]
    return links


def submodule_state(repo_root: str, rel_path: str) -> tuple[bool, str | None, str | None, bool]:
    """Return (initialized, child_head, child_origin, clean) for a submodule."""
    sub = os.path.join(repo_root, rel_path)
    # git clone leaves an empty placeholder dir for uninitialized submodules;
    # an initialized one always carries its own .git marker at the root.
    if not os.path.exists(os.path.join(sub, ".git")):
        return False, None, None, True
    probe = git_isolated(sub, "rev-parse", "--show-toplevel")
    if probe.returncode != 0 or canonical(probe.stdout.strip()) != canonical(sub):
        return False, None, None, True
    head_proc = git_isolated(sub, "rev-parse", "HEAD")
    head = head_proc.stdout.strip() if head_proc.returncode == 0 else None
    origin_proc = git_isolated(sub, "config", "--get", "remote.origin.url")
    origin = origin_proc.stdout.strip() if origin_proc.returncode == 0 else None
    status_proc = git_isolated(sub, "status", "--porcelain")
    clean = status_proc.returncode == 0 and status_proc.stdout.strip() == ""
    return True, head, origin, clean


def resolve_submodule_profile(profile: str, links: dict[str, str]) -> list[str]:
    """Resolve a named profile to an exact set of root gitlinks."""
    if profile == "root-only":
        return []
    if profile == "full":
        return sorted(links)
    if profile != "governance":
        raise ToolError(
            "profile_unknown",
            f"unknown clone submodule profile {profile!r}",
            EXIT_USAGE,
        )
    missing = sorted(set(GOVERNANCE_SUBMODULES) - set(links))
    if missing:
        raise ToolError(
            "profile_gitlink_missing",
            f"governance profile requires missing root gitlinks: {missing}",
            EXIT_POLICY,
            {"profile": profile, "missing_gitlinks": missing},
        )
    return list(GOVERNANCE_SUBMODULES)


def expected_submodule_origins(repo_root: str) -> dict[str, str]:
    """Read path-to-origin bindings from the tracked .gitmodules file."""
    proc = git_isolated(
        repo_root,
        "config",
        "--file",
        ".gitmodules",
        "--get-regexp",
        r"^submodule\..*\.(path|url)$",
    )
    if proc.returncode != 0:
        return {}
    sections: dict[str, dict[str, str]] = {}
    for line in proc.stdout.splitlines():
        key, separator, value = line.partition(" ")
        if not separator or not key.startswith("submodule."):
            continue
        section, field = key[len("submodule.") :].rsplit(".", 1)
        sections.setdefault(section, {})[field] = value.strip()
    origins: dict[str, str] = {}
    for section, fields in sections.items():
        if not fields.get("path") or not fields.get("url"):
            continue
        # `git submodule init/update` resolves relative .gitmodules URLs using
        # the superproject remote and stores the result in local config.  Use
        # Git's resolved value rather than reimplementing those URL semantics.
        configured = git_isolated(repo_root, "config", "--get", f"submodule.{section}.url")
        origins[fields["path"]] = (
            configured.stdout.strip()
            if configured.returncode == 0 and configured.stdout.strip()
            else fields["url"]
        )
    return origins


def redact_remote(remote: str | None) -> str | None:
    """Remove embedded URL credentials before a remote enters a portable receipt."""
    if remote is None:
        return None
    parsed = urlsplit(remote)
    if parsed.scheme and parsed.hostname:
        host = parsed.hostname
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path, "", ""))
    if "@" in remote and ":" in remote.split("@", 1)[1]:
        return remote.split("@", 1)[1]
    return remote


def canonical_repository_name(repository: str) -> str:
    """Normalize one explicit GitHub owner/repository authority."""
    value = repository.strip().removeprefix("github.com/").rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    parts = value.split("/")
    if len(parts) != 2 or not all(GITHUB_COMPONENT_RE.fullmatch(part) for part in parts):
        raise ToolError(
            "repository_provenance_invalid",
            "expected repository must be an exact GitHub owner/repository name",
            EXIT_POLICY,
        )
    return f"github.com/{parts[0].lower()}/{parts[1].lower()}"


def canonical_remote_descriptor(remote: str) -> dict[str, str]:
    """Return a credential-free, transport-aware GitHub remote identity."""
    value = remote.strip()
    transport: str
    owner: str
    repository: str
    scp = re.fullmatch(
        r"git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?",
        value,
        flags=re.IGNORECASE,
    )
    if scp:
        transport = "ssh"
        owner, repository = scp.groups()
    else:
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError as exc:
            raise ToolError(
                "repository_provenance_invalid",
                "remote URL contains an invalid port",
                EXIT_POLICY,
            ) from exc
        if parsed.query or parsed.fragment or "%" in parsed.path:
            raise ToolError(
                "repository_provenance_invalid",
                "remote URL query, fragment, and encoded path forms are not admitted",
                EXIT_POLICY,
            )
        if parsed.hostname is None or parsed.hostname.lower() != "github.com":
            raise ToolError(
                "repository_provenance_invalid",
                "root repository must use an exact github.com remote",
                EXIT_POLICY,
            )
        if parsed.scheme == "https":
            if parsed.username is not None or parsed.password is not None or port is not None:
                raise ToolError(
                    "repository_provenance_invalid",
                    "HTTPS root remotes cannot embed credentials or an explicit port",
                    EXIT_POLICY,
                )
            transport = "https"
        elif parsed.scheme == "ssh":
            if parsed.username != "git" or parsed.password is not None or port not in (None, 22):
                raise ToolError(
                    "repository_provenance_invalid",
                    "SSH root remotes must use git@github.com and the standard port",
                    EXIT_POLICY,
                )
            transport = "ssh"
        else:
            raise ToolError(
                "repository_provenance_invalid",
                "root repository remote must use HTTPS or SSH",
                EXIT_POLICY,
            )
        path = parsed.path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        parts = path.split("/")
        if len(parts) != 2 or not all(GITHUB_COMPONENT_RE.fullmatch(part) for part in parts):
            raise ToolError(
                "repository_provenance_invalid",
                "root repository remote must contain one owner and repository",
                EXIT_POLICY,
            )
        owner, repository = parts
    descriptor = {
        "canonical_repository": f"github.com/{owner.lower()}/{repository.lower()}",
        "transport": transport,
    }
    descriptor["remote_digest"] = hashlib.sha256(
        json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return descriptor


def remote_urls(repo_root: str, *, push: bool) -> list[str]:
    args = ["remote", "get-url"]
    if push:
        args.append("--push")
    args.extend(["--all", "origin"])
    proc = git_isolated(repo_root, *args)
    values = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if proc.returncode != 0 or len(values) != 1:
        direction = "push" if push else "fetch"
        raise ToolError(
            "repository_provenance_invalid",
            f"origin must expose exactly one {direction} URL",
            EXIT_POLICY,
        )
    return values


def repository_provenance(repo_root: str, expected_repository: str) -> dict[str, str]:
    """Bind fetch and push transports to one explicit canonical repository."""
    expected = canonical_repository_name(expected_repository)
    fetch = canonical_remote_descriptor(remote_urls(repo_root, push=False)[0])
    push = canonical_remote_descriptor(remote_urls(repo_root, push=True)[0])
    if (
        fetch["canonical_repository"] != expected
        or push["canonical_repository"] != expected
    ):
        raise ToolError(
            "repository_provenance_mismatch",
            "origin fetch/push repositories do not match the expected canonical root",
            EXIT_POLICY,
        )
    return {
        "canonical_repository": expected,
        "fetch_transport": fetch["transport"],
        "push_transport": push["transport"],
        "fetch_url_digest": fetch["remote_digest"],
        "push_url_digest": push["remote_digest"],
    }


def author_identity_digest(name: str, email: str) -> str:
    payload = {"email": email, "name": name}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def parse_git_ident(value: str) -> tuple[str, str]:
    match = re.fullmatch(r"(.+) <([^<>]+)> [0-9]+ [+-][0-9]{4}", value.strip())
    if not match:
        raise ToolError(
            "author_identity_invalid",
            "Git did not expose a parseable author or committer identity",
            EXIT_POLICY,
        )
    return match.group(1), match.group(2)


def git_local_value(repo_root: str, key: str) -> str | None:
    proc = git(repo_root, "config", "--local", "--get", key)
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else None


def bind_author_identity(repo_root: str) -> dict[str, str | bool]:
    """Pin the current effective Git identity into clone-local config."""
    overrides = sorted(key for key in AUTHOR_OVERRIDE_ENV if key in os.environ)
    if overrides:
        raise ToolError(
            "author_identity_override",
            "author provenance cannot be bound while Git author/committer overrides are present",
            EXIT_POLICY,
            {"override_keys": overrides},
        )
    values: dict[str, str] = {}
    for key in ("user.name", "user.email"):
        proc = git(repo_root, "config", "--get", key)
        if proc.returncode != 0 or not proc.stdout.strip():
            raise ToolError(
                "author_identity_missing",
                f"Git {key} must be configured before provenance binding",
                EXIT_POLICY,
            )
        values[key] = proc.stdout.strip()
        configured = git(repo_root, "config", "--local", key, values[key])
        if configured.returncode != 0:
            raise ToolError("author_identity_write_failed", configured.stderr.strip(), EXIT_POLICY)
    configured = git(repo_root, "config", "--local", "user.useConfigOnly", "true")
    if configured.returncode != 0:
        raise ToolError("author_identity_write_failed", configured.stderr.strip(), EXIT_POLICY)
    return live_author_identity(repo_root)


def live_author_identity(repo_root: str) -> dict[str, str | bool]:
    """Read clone-local and effective author/committer identity without exposing PII."""
    name = git_local_value(repo_root, "user.name")
    email = git_local_value(repo_root, "user.email")
    use_config_only = git_local_value(repo_root, "user.useConfigOnly")
    if not name or not email or (use_config_only or "").lower() != "true":
        raise ToolError(
            "author_identity_missing",
            "clone-local user.name, user.email, and user.useConfigOnly=true are required",
            EXIT_POLICY,
        )
    author_proc = git(repo_root, "var", "GIT_AUTHOR_IDENT")
    committer_proc = git(repo_root, "var", "GIT_COMMITTER_IDENT")
    if author_proc.returncode != 0 or committer_proc.returncode != 0:
        raise ToolError("author_identity_invalid", "Git identity probe failed", EXIT_POLICY)
    author = parse_git_ident(author_proc.stdout)
    committer = parse_git_ident(committer_proc.stdout)
    if author != (name, email) or committer != (name, email):
        raise ToolError(
            "author_identity_mismatch",
            "effective Git author/committer differs from clone-local identity",
            EXIT_POLICY,
        )
    return {
        "identity_digest": author_identity_digest(name, email),
        "name_digest": hashlib.sha256(name.encode("utf-8")).hexdigest(),
        "email_digest": hashlib.sha256(email.encode("utf-8")).hexdigest(),
        "source": "clone-local",
        "use_config_only": True,
    }


def extract_uv_path_dependencies(repo_root: str) -> list[str]:
    """Extract local path dependencies from [tool.uv.sources].

    Returns a list of package names that have path dependencies (e.g., ['ecos', 'agora']).
    Returns empty list if pyproject.toml doesn't exist or has no [tool.uv.sources].
    """
    pyproject = os.path.join(repo_root, "pyproject.toml")
    if not os.path.isfile(pyproject):
        return []

    try:
        with open(pyproject, encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return []

    # Simple text parsing: find [tool.uv.sources] section and extract package names
    # Format: package_name = { path = "../xxx", editable = true }
    in_uv_section = False
    packages: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "[tool.uv.sources]":
            in_uv_section = True
            continue
        if in_uv_section:
            # Exit section when we hit another section header
            if stripped.startswith("[") and stripped != "[tool.uv.sources]":
                break
            # Extract package name: format is "name = { path = ... }"
            match = re.match(r"^([A-Za-z0-9_-]+)\s*=\s*\{", line)
            if match:
                packages.append(match.group(1))

    return packages


def reinstall_path_dependencies(clone_root: str) -> tuple[bool, str]:
    """Reinstall all uv path dependencies to avoid cache staleness (E8 fix).

    E8: 子仓版本号未动但文件变了时 uv 不重装 (2026-08-15 实证),
    clone 后强制 reinstall 每个 path 依赖.

    Returns (success, message). Never raises -- this is best-effort.
    """
    packages = extract_uv_path_dependencies(clone_root)
    if not packages:
        return True, "no uv path dependencies found"

    # 检查 uv 是否可用
    try:
        proc = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            check=False,
            cwd=clone_root,
        )
        if proc.returncode != 0:
            return False, f"uv not available (exit {proc.returncode})"
    except FileNotFoundError:
        return False, "uv command not found"

    # 逐个 reinstall
    failed = []
    for pkg in packages:
        proc = subprocess.run(
            ["uv", "sync", "--reinstall-package", pkg],
            capture_output=True,
            text=True,
            check=False,
            cwd=clone_root,
        )
        if proc.returncode != 0:
            failed.append((pkg, proc.stderr.strip() or proc.stdout.strip()))

    if failed:
        msg = f"uv sync --reinstall-package failed for: {[p for p, _ in failed]}"
        for pkg, err in failed:
            msg += f"\n  {pkg}: {err[:100]}"
        return False, msg

    return (
        True,
        f"reinstalled {len(packages)} uv path dependencies: {', '.join(packages)}",
    )


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------


def identity_path(repo_root: str) -> str:
    return os.path.join(git_common_dir(repo_root), IDENTITY_FILENAME)


def readiness_path(repo_root: str) -> str:
    return os.path.join(git_common_dir(repo_root), READINESS_FILENAME)


def provenance_path(repo_root: str) -> str:
    return os.path.join(git_common_dir(repo_root), PROVENANCE_FILENAME)


def read_identity(repo_root: str, required: bool = True) -> dict | None:
    path = identity_path(repo_root)
    if not os.path.isfile(path):
        if required:
            raise ToolError(
                "identity_missing",
                f"clone identity not found at {path}",
                EXIT_POLICY,
            )
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError("identity_invalid", f"cannot read clone identity {path}: {exc}", EXIT_POLICY) from exc
    if data.get("schema") not in {SCHEMA_IDENTITY, SCHEMA_IDENTITY_ATTEMPT}:
        raise ToolError(
            "identity_invalid",
            f"unexpected identity schema {data.get('schema')!r}",
            EXIT_POLICY,
        )
    if data.get("schema") == SCHEMA_IDENTITY_ATTEMPT:
        actor_id = data.get("actor_id")
        attempt_id = data.get("delivery_attempt_id")
        expected_branch = f"agent/{actor_id}--{attempt_id}"
        if (
            not isinstance(actor_id, str)
            or not AGENT_ID_RE.fullmatch(actor_id)
            or data.get("agent_id") != actor_id
            or not isinstance(attempt_id, str)
            or not AGENT_ID_RE.fullmatch(attempt_id)
            or data.get("working_branch") != expected_branch
        ):
            raise ToolError(
                "identity_invalid",
                "attempt-qualified clone identity fields are missing or inconsistent",
                EXIT_POLICY,
            )
    return data


def attempt_binding(identity: dict) -> dict[str, str]:
    """Return digest-bound actor/attempt fields for a v2 clone identity."""
    if identity.get("schema") != SCHEMA_IDENTITY_ATTEMPT:
        return {}
    return {
        "actor_id": identity["actor_id"],
        "delivery_attempt_id": identity["delivery_attempt_id"],
    }


def expected_artifact_schema(identity: dict, legacy: str, attempt: str) -> str:
    return attempt if identity.get("schema") == SCHEMA_IDENTITY_ATTEMPT else legacy


def write_identity(repo_root: str, identity: dict) -> str:
    path = identity_path(repo_root)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(identity, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
    return path


def write_json_replace(path: str, payload: dict) -> None:
    """Atomically replace one clone-internal JSON projection."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# canonical JSON / digests
# ---------------------------------------------------------------------------


def canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_digest(obj: dict, exclude_field: str | None = None) -> str:
    if exclude_field is not None:
        obj = {k: v for k, v in obj.items() if k != exclude_field}
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def normalize_source(source: str) -> str:
    """Canonicalized source descriptor: realpath for local paths, else as-is."""
    if os.path.isdir(source):
        return canonical(source)
    return source


def normalize_local_upstream(source_root: str, upstream: str) -> str:
    """Resolve local relative remotes in the source repository's namespace."""
    if "://" in upstream or re.match(r"^(?:[^/@:]+@)?[^/:]+:.+", upstream):
        return upstream
    expanded = os.path.expanduser(upstream)
    if os.path.isabs(expanded):
        return canonical(expanded)
    return canonical(os.path.join(source_root, expanded))


def canonical_upstream(source_root: str, upstream: str) -> str:
    """Follow local working-clone origins to their final upstream endpoint."""
    current = normalize_local_upstream(source_root, upstream)
    visited = {canonical(source_root)}
    while os.path.isdir(current):
        repo_root = canonical(current)
        if repo_root in visited:
            raise ToolError(
                "origin_cycle",
                f"local origin chain cycles at {repo_root}",
                EXIT_POLICY,
            )
        visited.add(repo_root)
        probe = git(repo_root, "rev-parse", "--git-dir")
        if probe.returncode != 0:
            break
        next_origin = git(repo_root, "remote", "get-url", "origin")
        if next_origin.returncode != 0 or not next_origin.stdout.strip():
            break
        current = normalize_local_upstream(repo_root, next_origin.stdout.strip())
    return current


def origin_branch_name(revision: str) -> str | None:
    """Return the branch portion of an origin remote-tracking ref."""
    prefixes = ("origin/", "refs/remotes/origin/")
    for prefix in prefixes:
        if not revision.startswith(prefix):
            continue
        branch = revision[len(prefix) :]
        check = git(None, "check-ref-format", f"refs/heads/{branch}")
        return branch if branch and check.returncode == 0 else None
    return None


def resolve_upstream_branch(source_url: str, branch: str) -> tuple[str, str]:
    """Resolve one canonical upstream branch without mutating the source clone."""
    ref = f"refs/heads/{branch}"
    resolved = git(None, "ls-remote", "--exit-code", source_url, ref)
    if resolved.returncode != 0:
        raise ToolError(
            "revision_checkout_failed",
            f"cannot resolve {ref} from canonical upstream: {resolved.stderr.strip()}",
            EXIT_POLICY,
        )
    matches = []
    for line in resolved.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2 and parts[1] == ref and re.fullmatch(r"[0-9a-fA-F]{40,64}", parts[0]):
            matches.append(parts[0].lower())
    if len(matches) != 1:
        raise ToolError(
            "revision_checkout_failed",
            f"canonical upstream returned {len(matches)} exact matches for {ref}",
            EXIT_POLICY,
        )
    return matches[0], ref


def atomic_publish_no_replace(source: str, destination: str) -> None:
    """Atomically publish a directory without replacing a concurrent path."""
    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    if sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        rename_exclusive = 0x00000004
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(source_bytes, destination_bytes, rename_exclusive)
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        at_fdcwd = -100
        rename_no_replace = 1
        rename = libc.renameat2
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(
            at_fdcwd,
            source_bytes,
            at_fdcwd,
            destination_bytes,
            rename_no_replace,
        )
    else:
        raise ToolError(
            "atomic_publish_unsupported",
            "this platform does not expose an atomic no-replace directory rename",
            EXIT_POLICY,
        )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise ToolError(
            "destination_collision",
            f"destination {destination} appeared during clone; refusing publication",
            EXIT_POLICY,
        )
    raise ToolError(
        "atomic_publish_failed",
        f"cannot atomically publish clone: {os.strerror(error_number)}",
        EXIT_POLICY,
    )


def write_json_exclusive(output_path: str, payload: dict, failure_reason: str) -> None:
    """Publish one generated JSON artifact without overwriting a racing writer."""
    fd: int | None = None
    created = False
    try:
        fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fd = None
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
    except FileExistsError as exc:
        raise ToolError(
            "output_collision",
            f"output {output_path} already exists; refusing overwrite",
            EXIT_POLICY,
        ) from exc
    except OSError as exc:
        if fd is not None:
            os.close(fd)
        if created:
            try:
                os.unlink(output_path)
            except OSError:
                pass
        raise ToolError(
            failure_reason,
            f"cannot write {output_path}: {exc}",
            EXIT_USAGE,
        ) from exc


def write_json_exclusive_or_match(output_path: str, payload: dict, failure_reason: str) -> None:
    """Publish once, or accept an identical artifact left by an interrupted retry."""
    try:
        write_json_exclusive(output_path, payload, failure_reason)
        return
    except ToolError as exc:
        if exc.reason != "output_collision":
            raise
    try:
        with open(output_path, encoding="utf-8") as fh:
            existing = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "output_collision",
            f"output {output_path} exists but is not a matching resumable receipt: {exc}",
            EXIT_POLICY,
        ) from exc
    if existing != payload:
        raise ToolError(
            "output_collision",
            f"output {output_path} exists with different content; refusing overwrite",
            EXIT_POLICY,
        )


def commit_identities_match(repo_root: str, frozen_sha: str, expected_digest: str) -> bool:
    commits = git(repo_root, "rev-list", f"{frozen_sha}..HEAD")
    if commits.returncode != 0:
        return False
    for commit_sha in (line.strip() for line in commits.stdout.splitlines() if line.strip()):
        ident = git(
            repo_root,
            "show",
            "-s",
            "--format=%an%x00%ae%x00%cn%x00%ce",
            commit_sha,
        )
        if ident.returncode != 0:
            return False
        fields = ident.stdout.rstrip("\n").split("\x00")
        if len(fields) != 4:
            return False
        author_digest = author_identity_digest(fields[0], fields[1])
        committer_digest = author_identity_digest(fields[2], fields[3])
        if author_digest != expected_digest or committer_digest != expected_digest:
            return False
    return True


def verify_clone_provenance(repo_root: str, identity: dict) -> dict:
    """Live-revalidate a bound root repository and Git author identity."""
    try:
        with open(provenance_path(repo_root), encoding="utf-8") as fh:
            receipt = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "clone_provenance_missing",
            "clone provenance receipt is missing or unreadable",
            EXIT_POLICY,
        ) from exc
    digest = canonical_digest(receipt, exclude_field="receipt_digest")
    repository = receipt.get("repository") or {}
    author = receipt.get("author") or {}
    expected_schema = expected_artifact_schema(
        identity,
        SCHEMA_PROVENANCE,
        SCHEMA_PROVENANCE_ATTEMPT,
    )
    binding = attempt_binding(identity)
    if (
        receipt.get("schema") != expected_schema
        or receipt.get("receipt_digest") != digest
        or identity.get("provenance_receipt_digest") != digest
        or identity.get("provenance_status") != "ready"
        or receipt.get("status") != "ready"
        or receipt.get("agent_id") != identity.get("agent_id")
        or receipt.get("clone_root") != canonical(repo_root)
        or receipt.get("working_branch") != identity.get("working_branch")
        or receipt.get("frozen_root_sha") != identity.get("frozen_root_sha")
        or any(receipt.get(key) != value for key, value in binding.items())
        or not repository.get("canonical_repository")
        or not author.get("identity_digest")
    ):
        raise ToolError(
            "clone_provenance_mismatch",
            "clone provenance receipt does not match the clone identity",
            EXIT_POLICY,
        )
    try:
        live_repository = repository_provenance(
            repo_root,
            repository["canonical_repository"],
        )
        live_author = live_author_identity(repo_root)
    except ToolError as exc:
        raise ToolError(
            "clone_provenance_mismatch",
            "live repository or author provenance no longer matches",
            EXIT_POLICY,
            {"cause": exc.reason},
        ) from exc
    ancestor = git(
        repo_root,
        "merge-base",
        "--is-ancestor",
        identity["frozen_root_sha"],
        "HEAD",
    )
    if (
        live_repository != repository
        or live_author != author
        or ancestor.returncode != 0
        or not commit_identities_match(
            repo_root,
            identity["frozen_root_sha"],
            author["identity_digest"],
        )
    ):
        raise ToolError(
            "clone_provenance_mismatch",
            "live repository, author, or commit provenance no longer matches",
            EXIT_POLICY,
        )
    return receipt


def cmd_provenance(args: argparse.Namespace) -> dict:
    """Bind one untouched clone to an explicit repository and author identity."""
    identity = read_identity(args.clone)
    if root_head(args.clone) != identity.get("frozen_root_sha"):
        raise ToolError(
            "provenance_late_binding",
            "provenance must be bound before the clone creates new commits",
            EXIT_POLICY,
        )
    branch, detached = branch_state(args.clone)
    if detached or branch != identity.get("working_branch"):
        raise ToolError(
            "provenance_branch_mismatch",
            "provenance must be bound on the clone identity branch",
            EXIT_POLICY,
        )
    repository = repository_provenance(args.clone, args.expected_repository)
    author = bind_author_identity(args.clone)
    receipt = {
        "schema": expected_artifact_schema(
            identity,
            SCHEMA_PROVENANCE,
            SCHEMA_PROVENANCE_ATTEMPT,
        ),
        "agent_id": identity["agent_id"],
        "clone_root": canonical(args.clone),
        "repository": repository,
        "author": author,
        "frozen_root_sha": identity["frozen_root_sha"],
        "working_branch": identity["working_branch"],
        "status": "ready",
        "generated_at": identity.get("created_at"),
    }
    receipt.update(attempt_binding(identity))
    receipt["receipt_digest"] = canonical_digest(receipt, exclude_field="receipt_digest")
    write_json_exclusive_or_match(args.output, receipt, "provenance_write_failed")
    write_json_replace(provenance_path(args.clone), receipt)
    identity["source_url"] = remote_urls(args.clone, push=False)[0]
    identity["provenance_required"] = True
    identity["provenance_status"] = "ready"
    identity["provenance_receipt_digest"] = receipt["receipt_digest"]
    write_identity(args.clone, identity)
    return {
        "ok": True,
        "reason": "provenance_bound",
        "clone_root": canonical(args.clone),
        "canonical_repository": repository["canonical_repository"],
        "status": "ready",
        "provenance_path": args.output,
        "receipt_digest": receipt["receipt_digest"],
    }


def cmd_create(args: argparse.Namespace) -> dict:
    agent_id = args.agent_id
    if not agent_id or not AGENT_ID_RE.match(agent_id):
        raise ToolError(
            "agent_id_invalid",
            f"agent id {agent_id!r} must match {AGENT_ID_RE.pattern}",
            EXIT_USAGE,
        )
    delivery_attempt_id = getattr(args, "delivery_attempt_id", None)
    if not delivery_attempt_id:
        raise ToolError(
            "delivery_attempt_id_required",
            "new clones require a delivery attempt; v1 identities are compatibility-only",
            EXIT_USAGE,
        )
    if not AGENT_ID_RE.fullmatch(delivery_attempt_id):
        raise ToolError(
            "delivery_attempt_id_invalid",
            f"delivery attempt id {delivery_attempt_id!r} must match {AGENT_ID_RE.pattern}",
            EXIT_USAGE,
        )
    working_branch = f"agent/{agent_id}--{delivery_attempt_id}"
    branch_check = git(None, "check-ref-format", "--branch", working_branch)
    if branch_check.returncode != 0:
        raise ToolError(
            "agent_id_invalid",
            f"agent id {agent_id!r} does not form a valid Git branch",
            EXIT_USAGE,
        )

    dest = args.destination
    if os.path.lexists(dest):
        raise ToolError(
            "destination_collision",
            f"destination {dest} already exists; refusing every pre-existing path",
            EXIT_POLICY,
        )

    source = args.source
    source_url = normalize_source(source)
    revision = args.revision
    source_revision_ref = revision
    revision_fetch_url = source
    if os.path.isdir(source):
        upstream = git(source, "remote", "get-url", "origin")
        if upstream.returncode == 0 and upstream.stdout.strip():
            source_url = canonical_upstream(source, upstream.stdout.strip())
        if revision:
            remote_branch = origin_branch_name(revision)
            if remote_branch is not None:
                revision, source_revision_ref = resolve_upstream_branch(source_url, remote_branch)
                revision_fetch_url = source_url
            else:
                resolved = git(source, "rev-parse", "--verify", f"{revision}^{{commit}}")
                if resolved.returncode != 0:
                    raise ToolError(
                        "revision_checkout_failed",
                        f"cannot resolve revision {revision} in source: {resolved.stderr.strip()}",
                        EXIT_POLICY,
                    )
                revision = resolved.stdout.strip()
                symbolic = git(source, "rev-parse", "--symbolic-full-name", source_revision_ref)
                if symbolic.returncode == 0 and symbolic.stdout.strip():
                    source_revision_ref = symbolic.stdout.strip()

    remote_ref = f"refs/heads/{working_branch}"
    attempt_probe = git(
        None,
        "ls-remote",
        "--exit-code",
        "--heads",
        source_url,
        remote_ref,
    )
    if attempt_probe.returncode == 0:
        raise ToolError(
            "delivery_attempt_reused",
            f"delivery attempt branch already exists: {remote_ref}",
            EXIT_POLICY,
        )
    if attempt_probe.returncode != 2:
        raise ToolError(
            "delivery_attempt_lookup_failed",
            f"cannot prove delivery attempt uniqueness: {attempt_probe.stderr.strip()}",
            EXIT_POLICY,
        )

    destination_parent = os.path.dirname(os.path.abspath(dest)) or os.curdir
    if not os.path.isdir(destination_parent):
        raise ToolError(
            "destination_parent_missing",
            f"destination parent does not exist: {destination_parent}",
            EXIT_POLICY,
        )
    staging_root = tempfile.mkdtemp(prefix=f".{os.path.basename(dest)}.agent-clone-", dir=destination_parent)
    staging_clone = os.path.join(staging_root, "workspace")
    published = False

    clone_args = ["clone"]
    if os.path.isdir(source):
        # Force a full copy: no hardlinks, no alternates, no dependence on the
        # human Workspace as a persistent Git alternate.
        clone_args.append("--no-local")
    clone_args += [source, staging_clone]
    failure = None
    cleanup_failure = None
    try:
        proc = git(None, *clone_args)
        if proc.returncode != 0:
            raise ToolError(
                "clone_failed",
                f"git clone failed (exit {proc.returncode}): {proc.stderr.strip()}",
                EXIT_POLICY,
            )

        # Fail closed if a clone still emitted an alternates pointer.
        alt = os.path.join(git_common_dir(staging_clone), "objects", "info", "alternates")
        if os.path.exists(alt) and os.path.getsize(alt) > 0:
            raise ToolError(
                "alternates_emitted",
                f"clone emitted persistent alternates at {alt}",
                EXIT_POLICY,
            )

        if revision:
            object_probe = git(staging_clone, "cat-file", "-e", f"{revision}^{{commit}}")
            if object_probe.returncode != 0 and os.path.isdir(source):
                fetch = git(
                    staging_clone,
                    "fetch",
                    "--no-tags",
                    revision_fetch_url,
                    source_revision_ref,
                )
                if fetch.returncode != 0:
                    raise ToolError(
                        "revision_checkout_failed",
                        f"cannot fetch source revision {source_revision_ref}: {fetch.stderr.strip()}",
                        EXIT_POLICY,
                    )
            proc = git(staging_clone, "checkout", revision)
            if proc.returncode != 0:
                raise ToolError(
                    "revision_checkout_failed",
                    f"cannot checkout revision {revision}: {proc.stderr.strip()}",
                    EXIT_POLICY,
                )

        proc = git(staging_clone, "switch", "-c", working_branch)
        if proc.returncode != 0:
            raise ToolError(
                "agent_branch_failed",
                f"cannot create private branch {working_branch}: {proc.stderr.strip()}",
                EXIT_POLICY,
            )

        if source_url != normalize_source(source):
            proc = git(staging_clone, "remote", "set-url", "origin", source_url)
            if proc.returncode != 0:
                raise ToolError(
                    "origin_rebind_failed",
                    f"cannot bind clone origin to source upstream: {proc.stderr.strip()}",
                    EXIT_POLICY,
                )

        requested_submodules = sorted(set(getattr(args, "submodule", None) or []))
        requested_profile = getattr(args, "profile", None)
        identity_profile = requested_profile or ("custom" if requested_submodules else None)
        all_gitlinks = gitlinks(staging_clone)
        unknown_submodules = sorted(set(requested_submodules) - set(all_gitlinks))
        if unknown_submodules:
            raise ToolError(
                "submodule_unknown",
                f"requested paths are not root gitlinks: {unknown_submodules}",
                EXIT_POLICY,
            )
        if requested_profile:
            initialize_paths = resolve_submodule_profile(requested_profile, all_gitlinks)
        elif requested_submodules:
            initialize_paths = requested_submodules
        elif args.no_submodules:
            initialize_paths = []
        else:
            initialize_paths = sorted(all_gitlinks)

        if initialize_paths:
            # Initialize only the selected root gitlinks. Do not recurse
            # into nested workspace mirrors: a submodule may itself contain the
            # entire project graph, causing scripts/scripts/... expansion.
            proc = git(
                staging_clone,
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "update",
                "--init",
                "--",
                *initialize_paths,
            )
            if proc.returncode != 0:
                raise ToolError(
                    "submodule_init_failed",
                    f"submodule init failed: {proc.stderr.strip()}",
                    EXIT_POLICY,
                )
            for path in initialize_paths:
                pinned_sha = all_gitlinks[path]
                initialized, child_head, _origin, clean = submodule_state(staging_clone, path)
                if not initialized or child_head != pinned_sha or not clean:
                    raise ToolError(
                        "submodule_init_incomplete",
                        f"submodule {path} did not reach a clean pinned checkout",
                        EXIT_POLICY,
                    )
        for path in sorted(set(all_gitlinks) - set(initialize_paths)):
            initialized, _child_head, _origin, _clean = submodule_state(staging_clone, path)
            if initialized:
                raise ToolError(
                    "submodule_init_unrequested",
                    f"submodule {path} initialized outside the requested set",
                    EXIT_POLICY,
                )
        submodules_initialized = len(initialize_paths) == len(all_gitlinks)

        # Clone-local hook activation must succeed before the clone is declared ready.
        if os.path.isfile(os.path.join(staging_clone, ".githooks", "pre-commit")):
            proc = git(staging_clone, "config", "core.hooksPath", ".githooks")
            if proc.returncode != 0:
                raise ToolError(
                    "hook_activation_failed",
                    f"cannot set core.hooksPath: {proc.stderr.strip()}",
                    EXIT_POLICY,
                )

        frozen_sha = root_head(staging_clone)
        reinstall_ok, reinstall_msg = reinstall_path_dependencies(staging_clone)
        if not reinstall_ok:
            warnings.warn(f"uv sync --reinstall-package warning: {reinstall_msg}")
        identity = {
            "schema": SCHEMA_IDENTITY_ATTEMPT if delivery_attempt_id else SCHEMA_IDENTITY,
            "agent_id": agent_id,
            "canonical_root": canonical(dest),
            "source_url": source_url,
            "frozen_root_sha": frozen_sha,
            "working_branch": working_branch,
            "ready": True,
            "requested_revision": source_revision_ref,
            "dependency_reinstall_status": "pass" if reinstall_ok else "degraded",
            "dependency_reinstall_message": reinstall_msg,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if delivery_attempt_id is not None:
            identity["actor_id"] = agent_id
            identity["delivery_attempt_id"] = delivery_attempt_id
        if identity_profile:
            identity["profile"] = identity_profile
            identity["required_submodules"] = initialize_paths
        if identity_profile in {"governance", "full"}:
            identity["provenance_required"] = True
            identity["provenance_status"] = "unbound"
        write_identity(staging_clone, identity)
        atomic_publish_no_replace(staging_clone, dest)
        published = True
    except ToolError as exc:
        failure = exc
    except Exception as exc:
        failure = ToolError(
            "internal_error",
            f"{type(exc).__name__}: {exc}",
            EXIT_USAGE,
        )
    finally:
        try:
            shutil.rmtree(staging_root)
        except OSError as exc:
            cleanup_failure = exc

    if failure is not None:
        if cleanup_failure is not None:
            failure.details.update(
                {
                    "cleanup_reason": type(cleanup_failure).__name__,
                    "residual_resources": [canonical(staging_root)],
                }
            )
        raise failure
    if cleanup_failure is not None:
        raise ToolError(
            "staging_cleanup_failed",
            f"clone was published but staging cleanup failed: {cleanup_failure}",
            EXIT_POLICY,
            {
                "cleanup_reason": type(cleanup_failure).__name__,
                "publication_state": "published_cleanup_unconfirmed",
                "published_resource": canonical(dest),
                "residual_resources": [canonical(staging_root)],
            },
        )

    if not published:
        raise ToolError("clone_failed", "clone was not published", EXIT_POLICY)
    identity_file = identity_path(dest)

    result = {
        "ok": True,
        "reason": "clone_created",
        "agent_id": agent_id,
        "clone_root": canonical(dest),
        "source_url": identity["source_url"],
        "frozen_root_sha": frozen_sha,
        "working_branch": working_branch,
        "profile": identity_profile,
        "submodules_initialized": submodules_initialized,
        "initialized_submodules": initialize_paths,
        "identity_file": identity_file,
        "reinstall_status": "ok" if reinstall_ok else "warning",
        "reinstall_message": reinstall_msg,
    }
    if delivery_attempt_id is not None:
        result["actor_id"] = agent_id
        result["delivery_attempt_id"] = delivery_attempt_id
    return result


def managed_python_probe(repo_root: str, profile: str) -> tuple[dict, dict | None]:
    """Run the tracked managed-Python probe and return a receipt-safe check."""
    runner = os.path.join(repo_root, "bin", "gac", "managed-python")
    if not os.path.isfile(runner) or not os.access(runner, os.X_OK):
        return (
            {
                "status": "degraded",
                "required": True,
                "detail": "tracked managed-python runner is missing or not executable",
            },
            None,
        )
    try:
        proc = subprocess.run(
            [runner, "probe", "--profile", profile, "--json"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ({"status": "degraded", "required": True, "detail": str(exc)[:240]}, None)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
        return ({"status": "degraded", "required": True, "detail": detail[:240]}, None)
    try:
        receipt = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return (
            {
                "status": "degraded",
                "required": True,
                "detail": "managed-python emitted invalid JSON",
            },
            None,
        )
    if receipt.get("schema") != "managed-python-runtime-receipt/v1":
        return (
            {
                "status": "degraded",
                "required": True,
                "detail": "managed-python receipt schema mismatch",
            },
            None,
        )
    return ({"status": "pass", "required": True}, receipt)


def workflow_entrypoint_check(repo_root: str) -> dict:
    """Execute the workflow status seam without mutating workflow state."""
    runner = os.path.join(repo_root, "bin", "gac", "managed-python")
    entrypoint = os.path.join(repo_root, "bin", "agent-workflow.py")
    try:
        proc = subprocess.run(
            [runner, "run", "--profile", "pyyaml", "--", entrypoint, "status", "--json"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "degraded", "required": True, "detail": str(exc)[:240]}
    if proc.returncode == 0:
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = {}
        if payload.get("ok") is True:
            return {"status": "pass", "required": True}
        return {
            "status": "degraded",
            "required": True,
            "detail": "workflow status did not emit an ok JSON receipt",
        }
    detail = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
    return {"status": "degraded", "required": True, "detail": detail[:240]}


def cmd_readiness(args: argparse.Namespace) -> dict:
    """Verify a named-profile clone and publish a canonical readiness receipt."""
    cmd_verify(argparse.Namespace(clone=args.clone, manifest=args.manifest))
    identity = read_identity(args.clone)
    profile = identity.get("profile")
    if profile not in READINESS_PROFILES:
        raise ToolError(
            "readiness_profile_missing",
            "clone identity does not bind a named submodule profile",
            EXIT_POLICY,
        )
    try:
        with open(args.manifest, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError("manifest_unreadable", str(exc), EXIT_POLICY) from exc

    links = {entry["path"]: entry["pinned_sha"] for entry in manifest["repositories"]}
    if profile == "custom":
        required_paths = sorted(identity.get("required_submodules") or [])
        missing = sorted(set(required_paths) - set(links))
        if not required_paths or missing:
            raise ToolError(
                "readiness_profile_missing",
                f"custom profile has invalid required submodules: {missing or required_paths}",
                EXIT_POLICY,
            )
    else:
        required_paths = resolve_submodule_profile(profile, links)
    by_path = {entry["path"]: entry for entry in manifest["repositories"]}
    configured_origins = expected_submodule_origins(args.clone)
    required_submodules = []
    for path in required_paths:
        entry = by_path[path]
        expected_origin = configured_origins.get(path)
        if expected_origin is None or normalize_source(entry.get("origin") or "") != normalize_source(
            expected_origin
        ):
            raise ToolError(
                "profile_origin_mismatch",
                f"submodule {path} origin does not match tracked .gitmodules",
                EXIT_POLICY,
                {
                    "path": path,
                    "expected_origin": redact_remote(expected_origin),
                    "actual_origin": redact_remote(entry.get("origin")),
                },
            )
        required_submodules.append(
            {
                **entry,
                "origin": redact_remote(entry.get("origin")),
                "expected_origin": redact_remote(expected_origin),
            }
        )
    initialized_submodules = sorted(
        entry["path"] for entry in manifest["repositories"] if entry.get("initialized")
    )
    if initialized_submodules != required_paths:
        raise ToolError(
            "profile_initialization_mismatch",
            f"profile {profile} requires {required_paths}, initialized {initialized_submodules}",
            EXIT_POLICY,
        )

    provenance_receipt = None
    if identity.get("provenance_required") is True:
        provenance_receipt = verify_clone_provenance(args.clone, identity)

    checks: dict[str, dict] = {
        "root_repository": {"status": "pass", "required": True},
        "profile_submodules": {"status": "pass", "required": True},
        "manifest": {"status": "pass", "required": True},
        "hooks": {
            "status": "pass" if manifest.get("hooks_path") == ".githooks" else "degraded",
            "required": True,
        },
        "dependencies": {
            "status": identity.get("dependency_reinstall_status", "degraded"),
            "required": True,
            "detail": identity.get("dependency_reinstall_message", "dependency status missing"),
        },
    }
    if provenance_receipt is not None:
        checks["clone_provenance"] = {
            "status": "pass",
            "required": True,
            "receipt_digest": provenance_receipt["receipt_digest"],
        }
    managed_python: dict[str, dict] = {}
    stdlib_check, stdlib_receipt = managed_python_probe(args.clone, "stdlib")
    checks["managed_python_stdlib"] = stdlib_check
    if stdlib_receipt is not None:
        managed_python["stdlib"] = stdlib_receipt

    if profile in {"governance", "full"}:
        pyyaml_check, pyyaml_receipt = managed_python_probe(args.clone, "pyyaml")
        checks["managed_python_pyyaml"] = pyyaml_check
        if pyyaml_receipt is not None:
            managed_python["pyyaml"] = pyyaml_receipt
        checks["workflow_entrypoint"] = workflow_entrypoint_check(args.clone)
    else:
        checks["writer_admission"] = {
            "status": "degraded",
            "required": True,
            "detail": f"{profile} profile is intentionally read-only and cannot admit a writer",
        }

    degraded = sorted(
        check_id
        for check_id, check in checks.items()
        if check.get("required") and check.get("status") != "pass"
    )
    status = "ready" if not degraded else "degraded"
    receipt = {
        "schema": expected_artifact_schema(
            identity,
            SCHEMA_READINESS,
            SCHEMA_READINESS_ATTEMPT,
        ),
        "profile_schema": SCHEMA_SUBMODULE_PROFILE,
        "profile_version": 1,
        "profile": profile,
        "agent_id": identity["agent_id"],
        "clone_root": canonical(args.clone),
        "source_url": redact_remote(identity["source_url"]),
        "requested_revision": identity.get("requested_revision"),
        "root_head_sha": manifest["root_head_sha"],
        "working_branch": identity["working_branch"],
        "required_submodules": required_submodules,
        "initialized_submodules": initialized_submodules,
        "managed_python": managed_python,
        "checks": checks,
        "degraded_checks": degraded,
        "status": status,
        "generated_at": identity["created_at"],
    }
    receipt.update(attempt_binding(identity))
    receipt["receipt_digest"] = canonical_digest(receipt, exclude_field="receipt_digest")
    write_json_exclusive_or_match(args.output, receipt, "readiness_write_failed")
    write_json_replace(readiness_path(args.clone), receipt)
    identity["readiness_profile"] = profile
    identity["readiness_status"] = status
    identity["readiness_receipt_digest"] = receipt["receipt_digest"]
    identity["ready"] = status == "ready"
    write_identity(args.clone, identity)
    return {
        "ok": True,
        "reason": "readiness_generated",
        "clone_root": canonical(args.clone),
        "profile": profile,
        "status": status,
        "degraded_checks": degraded,
        "readiness_path": args.output,
        "receipt_digest": receipt["receipt_digest"],
    }


# ---------------------------------------------------------------------------
# manifest / verify
# ---------------------------------------------------------------------------


def build_manifest(repo_root: str) -> dict:
    identity = read_identity(repo_root)
    if identity.get("ready") is not True:
        raise ToolError(
            "identity_not_ready",
            "clone identity is not ready; refusing manifest generation",
            EXIT_POLICY,
        )
    expected_root = canonical(repo_root)
    if identity["canonical_root"] != expected_root:
        raise ToolError(
            "identity_root_mismatch",
            f"clone moved: identity root {identity['canonical_root']} != {expected_root}",
            EXIT_POLICY,
        )

    links = gitlinks(repo_root)
    entries = []
    for path in sorted(links):
        initialized, head, origin, clean = submodule_state(repo_root, path)
        if initialized and not clean:
            raise ToolError(
                "child_dirty",
                f"initialized submodule {path} is dirty",
                EXIT_POLICY,
            )
        entries.append(
            {
                "path": path,
                "pinned_sha": links[path],
                "initialized": initialized,
                "child_head": head,
                "origin": origin,
                "clean": clean,
            }
        )
    root_status = git(repo_root, "status", "--porcelain")
    if root_status.returncode != 0:
        raise ToolError("not_a_repository", root_status.stderr.strip(), EXIT_POLICY)

    # root_dirty 忽略 untracked 的孤儿仓库目录 (?? dir/, 主仓未登记 gitlink 的
    # 独立仓库如 c2g/gbrain/kairon), 但 untracked 单文件 (?? file.txt) 仍视为
    # dirty — 那是意外残留, 不是合法拓扑 (BET-Y1Q3-T1-07).
    tracked_changes = [
        line
        for line in root_status.stdout.splitlines()
        if line.strip() and not (line.startswith("?? ") and line.rstrip().endswith("/"))
    ]
    if tracked_changes:
        raise ToolError("root_dirty", "root repository has uncommitted changes", EXIT_POLICY)

    branch, detached = branch_state(repo_root)
    hooks_proc = git(repo_root, "config", "--get", "core.hooksPath")
    hooks_path = hooks_proc.stdout.strip() if hooks_proc.returncode == 0 else None
    manifest = {
        "schema": expected_artifact_schema(
            identity,
            SCHEMA_MANIFEST,
            SCHEMA_MANIFEST_ATTEMPT,
        ),
        "agent_id": identity["agent_id"],
        "canonical_root": expected_root,
        "origin_url": identity["source_url"],
        "root_head_sha": root_head(repo_root),
        "branch": branch,
        "detached": detached,
        "hooks_path": hooks_path,
        "repositories": entries,
    }
    manifest.update(attempt_binding(identity))
    manifest["manifest_digest"] = canonical_digest(manifest, exclude_field="manifest_digest")
    return manifest


def cmd_manifest(args: argparse.Namespace) -> dict:
    manifest = build_manifest(args.clone)
    write_json_exclusive(args.output, manifest, "manifest_write_failed")
    return {
        "ok": True,
        "reason": "manifest_generated",
        "clone_root": canonical(args.clone),
        "manifest_path": args.output,
        "manifest_digest": manifest["manifest_digest"],
        "root_head_sha": manifest["root_head_sha"],
    }


def cmd_verify(args: argparse.Namespace) -> dict:
    try:
        with open(args.manifest, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "manifest_unreadable",
            f"cannot read manifest {args.manifest}: {exc}",
            EXIT_POLICY,
        ) from exc
    if manifest.get("schema") not in {SCHEMA_MANIFEST, SCHEMA_MANIFEST_ATTEMPT}:
        raise ToolError(
            "manifest_schema_mismatch",
            f"unexpected manifest schema {manifest.get('schema')!r}",
            EXIT_POLICY,
        )
    stored = manifest.get("manifest_digest")
    recomputed = canonical_digest(manifest, exclude_field="manifest_digest")
    if stored != recomputed:
        raise ToolError(
            "manifest_digest_mismatch",
            f"manifest digest mismatch: stored {stored} != recomputed {recomputed}",
            EXIT_POLICY,
        )

    identity = read_identity(args.clone)
    expected_manifest_schema = expected_artifact_schema(
        identity,
        SCHEMA_MANIFEST,
        SCHEMA_MANIFEST_ATTEMPT,
    )
    if identity.get("ready") is not True:
        raise ToolError("identity_mismatch", "stored identity is not marked ready", EXIT_POLICY)
    if manifest.get("schema") != expected_manifest_schema or any(
        manifest.get(key) != value for key, value in attempt_binding(identity).items()
    ):
        raise ToolError(
            "identity_mismatch",
            "manifest delivery attempt does not match clone identity",
            EXIT_POLICY,
        )
    if identity["agent_id"] != manifest.get("agent_id"):
        raise ToolError(
            "identity_mismatch",
            "identity agent_id does not match manifest",
            EXIT_POLICY,
        )
    if identity["canonical_root"] != manifest.get("canonical_root"):
        raise ToolError(
            "identity_mismatch",
            "identity canonical_root does not match manifest",
            EXIT_POLICY,
        )
    if identity["source_url"] != manifest.get("origin_url"):
        raise ToolError(
            "identity_mismatch",
            "identity source_url does not match manifest origin_url",
            EXIT_POLICY,
        )
    if identity.get("working_branch") != manifest.get("branch"):
        raise ToolError(
            "identity_mismatch",
            "identity working_branch does not match manifest branch",
            EXIT_POLICY,
        )
    origin_proc = git(args.clone, "config", "--get", "remote.origin.url")
    live_origin = origin_proc.stdout.strip() if origin_proc.returncode == 0 else None
    if live_origin is None or normalize_source(live_origin) != manifest.get("origin_url"):
        raise ToolError(
            "origin_drift",
            f"live origin {live_origin!r} != manifest {manifest.get('origin_url')!r}",
            EXIT_POLICY,
        )
    if canonical(args.clone) != manifest.get("canonical_root"):
        raise ToolError(
            "root_moved",
            f"clone root moved: {canonical(args.clone)} != {manifest.get('canonical_root')}",
            EXIT_POLICY,
        )

    head = root_head(args.clone)
    if head != manifest["root_head_sha"]:
        raise ToolError(
            "root_sha_mismatch",
            f"root HEAD {head} != manifest {manifest['root_head_sha']}",
            EXIT_POLICY,
        )

    root_status = git(args.clone, "status", "--porcelain")
    if root_status.returncode != 0:
        raise ToolError("root_dirty", "cannot check root cleanliness", EXIT_POLICY)
    # 忽略 untracked 孤儿仓库目录 (?? dir/), 文件型 untracked 仍拒绝 (BET-Y1Q3-T1-07).
    tracked_changes = [
        line
        for line in root_status.stdout.splitlines()
        if line.strip() and not (line.startswith("?? ") and line.rstrip().endswith("/"))
    ]
    if tracked_changes:
        raise ToolError("root_dirty", "root repository is dirty", EXIT_POLICY)

    hooks_proc = git(args.clone, "config", "--get", "core.hooksPath")
    live_hooks = hooks_proc.stdout.strip() if hooks_proc.returncode == 0 else None
    expected_hooks = manifest.get("hooks_path")
    if live_hooks != expected_hooks:
        raise ToolError(
            "hooks_path_drift",
            f"core.hooksPath {live_hooks} != manifest {expected_hooks}",
            EXIT_POLICY,
        )
    if expected_hooks:
        hook_file = os.path.join(args.clone, expected_hooks, "pre-commit")
        if not os.path.isfile(hook_file):
            raise ToolError(
                "hooks_path_drift",
                f"hook file {hook_file} is missing",
                EXIT_POLICY,
            )

    links = gitlinks(args.clone)
    expected = {e["path"]: e["pinned_sha"] for e in manifest.get("repositories", [])}
    if links != expected:
        raise ToolError(
            "gitlink_drift",
            f"gitlinks differ: current {links} != manifest {expected}",
            EXIT_POLICY,
        )

    checks = [
        {"check": "root_sha", "pass": True},
        {"check": "root_clean", "pass": True},
    ]
    for entry in manifest.get("repositories", []):
        path = entry["path"]
        initialized, child_head, child_origin, clean = submodule_state(args.clone, path)
        if entry.get("initialized"):
            if not initialized:
                raise ToolError(
                    "child_initialization_drift",
                    f"submodule {path} expected initialized",
                    EXIT_POLICY,
                )
            if child_head != entry.get("child_head"):
                raise ToolError(
                    "child_head_drift",
                    f"submodule {path} HEAD {child_head} != manifest {entry.get('child_head')}",
                    EXIT_POLICY,
                )
            if child_origin != entry.get("origin"):
                raise ToolError(
                    "child_origin_drift",
                    f"submodule {path} origin {child_origin!r} != manifest {entry.get('origin')!r}",
                    EXIT_POLICY,
                )
            if not clean:
                raise ToolError("child_dirty", f"submodule {path} is dirty", EXIT_POLICY)
            checks.append({"check": "child_head", "path": path, "pass": True})
        elif initialized:
            raise ToolError(
                "child_initialization_drift",
                f"submodule {path} expected uninitialized",
                EXIT_POLICY,
            )

    return {
        "ok": True,
        "reason": "verified",
        "clone_root": canonical(args.clone),
        "root_head_sha": head,
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# changeset
# ---------------------------------------------------------------------------


def load_baseline(baseline_path: str) -> dict:
    try:
        with open(baseline_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "baseline_unreadable",
            f"cannot read baseline manifest {baseline_path}: {exc}",
            EXIT_POLICY,
        ) from exc
    if manifest.get("schema") not in {SCHEMA_MANIFEST, SCHEMA_MANIFEST_ATTEMPT}:
        raise ToolError(
            "baseline_schema_mismatch",
            f"unexpected baseline schema {manifest.get('schema')!r}",
            EXIT_POLICY,
        )
    recomputed = canonical_digest(manifest, exclude_field="manifest_digest")
    if manifest.get("manifest_digest") != recomputed:
        raise ToolError(
            "baseline_digest_mismatch",
            "baseline manifest digest validation failed",
            EXIT_POLICY,
        )
    return manifest


def is_ancestor(repo_root: str, ancestor: str, descendant: str) -> bool:
    proc = git(repo_root, "merge-base", "--is-ancestor", ancestor, descendant)
    return proc.returncode == 0


def root_changed_paths(repo_root: str, base: str, candidate: str) -> list[str]:
    """Return ordinary root paths changed between two commits, rename-expanded."""
    proc = git(
        repo_root,
        "diff",
        "--name-status",
        "-z",
        "--no-renames",
        base,
        candidate,
        "--",
    )
    if proc.returncode != 0:
        raise ToolError(
            "root_diff_failed",
            f"cannot enumerate root changes: {proc.stderr.strip()}",
            EXIT_POLICY,
        )
    fields = [item for item in proc.stdout.split("\0") if item]
    if len(fields) % 2 != 0:
        raise ToolError(
            "root_diff_malformed",
            "root diff emitted an incomplete name-status record",
            EXIT_POLICY,
        )
    paths: list[str] = []
    for status, path in zip(fields[::2], fields[1::2]):
        if not status or status[0] not in {"A", "C", "D", "M", "T", "U", "X", "B"}:
            raise ToolError(
                "root_diff_malformed",
                f"root diff emitted unsupported status {status!r}",
                EXIT_POLICY,
            )
        paths.append(path)
    return sorted(paths)


def object_at_path(repo_root: str, revision: str, path: str) -> str | None:
    proc = git(repo_root, "rev-parse", "--verify", f"{revision}:{path}")
    return proc.stdout.strip() if proc.returncode == 0 else None


def trusted_claims_authority(
    repo_root: str,
    baseline_revision: str,
    claims_root: str,
) -> dict[str, str]:
    """Resolve authority from the OS-account integration workspace, never the writer clone."""
    try:
        import yaml
    except ImportError as exc:
        raise ToolError("claim_verification_unavailable", "PyYAML is required") from exc
    expected = canonical(str(ACCOUNT_WORKSPACE_ROOT))
    actual = canonical(claims_root)
    if actual != expected:
        raise ToolError(
            "claims_authority_mismatch",
            f"claims root {actual} is not the OS-account integration workspace {expected}",
        )
    source = git(actual, "remote", "get-url", "origin")
    if source.returncode != 0 or not source.stdout.strip():
        raise ToolError(
            "claims_authority_remote_unreadable",
            "cannot resolve origin from the OS-account integration workspace",
        )
    policy_ref = "refs/heads/main"
    remote = git(actual, "ls-remote", "--exit-code", source.stdout.strip(), policy_ref)
    rows = [line.split() for line in remote.stdout.splitlines() if line.strip()]
    if (
        remote.returncode != 0
        or len(rows) != 1
        or len(rows[0]) != 2
        or rows[0][1] != policy_ref
        or re.fullmatch(r"[0-9a-f]{40}", rows[0][0]) is None
    ):
        raise ToolError(
            "claims_authority_revision_unavailable",
            f"cannot resolve exact {policy_ref} from the integration workspace origin",
        )
    policy_revision = rows[0][0]
    present = git(repo_root, "cat-file", "-e", f"{policy_revision}^{{commit}}")
    if present.returncode != 0:
        raise ToolError(
            "claims_authority_revision_unavailable",
            f"trusted main revision {policy_revision} is not present in the writer clone; fetch before retrying",
        )
    if not is_ancestor(repo_root, baseline_revision, policy_revision):
        raise ToolError(
            "claims_authority_baseline_untrusted",
            "baseline revision is not an ancestor of the integration workspace origin/main",
        )
    policy = git(repo_root, "show", f"{policy_revision}:{CLAIMS_AUTHORITY_POLICY}")
    if policy.returncode != 0:
        raise ToolError(
            "claims_authority_policy_unreadable",
            f"cannot read {CLAIMS_AUTHORITY_POLICY} at baseline {policy_revision}",
        )
    try:
        documents = list(yaml.safe_load_all(policy.stdout))
    except yaml.YAMLError as exc:
        raise ToolError("claims_authority_policy_invalid", f"invalid authority policy: {exc}") from exc
    data = next((doc for doc in documents if isinstance(doc, dict)), None)
    topology = data.get("topology_migration") if isinstance(data, dict) else None
    configured = topology.get("integration_root") if isinstance(topology, dict) else None
    if not isinstance(configured, str) or not configured:
        raise ToolError(
            "claims_authority_policy_invalid",
            "topology_migration.integration_root is required",
        )
    account_home = pwd.getpwuid(os.getuid()).pw_dir
    if configured == "~":
        configured_path = account_home
    elif configured.startswith("~/"):
        configured_path = os.path.join(account_home, configured[2:])
    elif os.path.isabs(configured):
        configured_path = configured
    else:
        raise ToolError(
            "claims_authority_policy_invalid",
            "integration_root must be absolute or account-home-relative",
        )
    policy_root = canonical(configured_path)
    if actual != policy_root:
        raise ToolError(
            "claims_authority_mismatch",
            f"claims root {actual} is not the policy-bound integration workspace {policy_root}",
        )
    policy_blob = object_at_path(repo_root, policy_revision, CLAIMS_AUTHORITY_POLICY)
    if not policy_blob:
        raise ToolError("claims_authority_policy_unreadable", "cannot resolve authority policy blob")
    return {
        "policy_path": CLAIMS_AUTHORITY_POLICY,
        "policy_ref": policy_ref,
        "policy_source_url": source.stdout.strip(),
        "policy_revision": policy_revision,
        "policy_blob_sha": policy_blob,
        "baseline_revision": baseline_revision,
        "claims_root": actual,
    }


def _safe_claim_path(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ToolError("claims_snapshot_invalid", "claim path must be a non-empty string")
    normalized = raw.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ToolError("claims_snapshot_invalid", f"unsafe claim path: {raw!r}")
    return path.as_posix()


def _path_covered_by_claim(claimed: list[str], changed: str) -> bool:
    changed = _safe_claim_path(changed)
    for claim in claimed:
        if claim.endswith("/**"):
            if changed.startswith(claim[:-2]):
                return True
        elif changed == claim or changed.startswith(claim.rstrip("/") + "/"):
            return True
    return False


def _build_claim_snapshot(claims_root: str, agent_id: str) -> dict[str, Any]:
    """Read the complete authoritative active-run plane into a replayable receipt."""
    try:
        import yaml
    except ImportError as exc:
        raise ToolError("claim_verification_unavailable", "PyYAML is required") from exc

    root = Path(canonical(claims_root))
    if not root.is_dir():
        raise ToolError("claims_root_unreadable", f"claims root is not a directory: {root}")
    source = root / ".omo" / "_delivery" / "agent-workflows" / "runs"
    if not source.is_dir():
        raise ToolError("claims_source_unreadable", f"authoritative runs directory is absent: {source}")
    source_real = source.resolve(strict=True)
    try:
        source_real.relative_to(root)
    except ValueError as exc:
        raise ToolError("claims_source_escape", "authoritative runs directory escapes claims root") from exc

    participating_runs: list[dict[str, Any]] = []
    all_claimed: list[str] = []
    for run_path in sorted(source.glob("*.yaml"), key=lambda item: item.name):
        try:
            run_real = run_path.resolve(strict=True)
            relative_path = run_real.relative_to(source_real).as_posix()
        except (OSError, ValueError) as exc:
            raise ToolError("claims_run_escape", f"run path escapes authority: {run_path}") from exc
        if "/" in relative_path:
            raise ToolError("claims_run_escape", f"unexpected nested run path: {run_path}")
        try:
            payload = run_real.read_bytes()
            documents = list(yaml.safe_load_all(payload.decode("utf-8")))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            raise ToolError("claims_run_unreadable", f"cannot parse {run_path}: {exc}") from exc
        data = next((doc for doc in documents if isinstance(doc, dict)), None)
        if data is None:
            raise ToolError("claims_run_invalid", f"run is not a mapping: {run_path}")
        if data.get("status") != "active":
            continue
        run_id = data.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ToolError("claims_run_invalid", f"active run lacks run_id: {run_path}")
        updated_at = data.get("updated_at")
        if not isinstance(updated_at, str) or not updated_at:
            raise ToolError("claims_run_invalid", f"active run lacks updated_at: {run_path}")
        claims = data.get("claims", [])
        if not isinstance(claims, list):
            raise ToolError("claims_run_invalid", f"active run claims are not a list: {run_path}")
        matching_claims: list[dict[str, Any]] = []
        for claim in claims:
            if not isinstance(claim, dict):
                raise ToolError("claims_run_invalid", f"active run contains malformed claim: {run_path}")
            if claim.get("actor") != agent_id:
                continue
            paths = claim.get("paths")
            if not isinstance(paths, list):
                raise ToolError("claims_run_invalid", f"agent claim paths are not a list: {run_path}")
            claimed_at = claim.get("claimed_at")
            if not isinstance(claimed_at, str) or not claimed_at:
                raise ToolError("claims_run_invalid", f"agent claim lacks claimed_at: {run_path}")
            normalized_paths = sorted({_safe_claim_path(path) for path in paths})
            if not normalized_paths:
                continue
            matching_claims.append(
                {
                    "actor": agent_id,
                    "claimed_at": claimed_at,
                    "paths": normalized_paths,
                }
            )
            all_claimed.extend(normalized_paths)
        if matching_claims:
            matching_claims.sort(key=lambda item: canonical_json(item))
            participating_runs.append(
                {
                    "run_id": run_id,
                    "relative_path": relative_path,
                    "file_sha256": hashlib.sha256(payload).hexdigest(),
                    "status": "active",
                    "updated_at": updated_at,
                    "run_actor": data.get("actor"),
                    "matching_claims": matching_claims,
                }
            )
    participating_runs.sort(key=lambda item: (item["run_id"], item["relative_path"]))
    snapshot: dict[str, Any] = {
        "schema": SCHEMA_CLAIM_SNAPSHOT,
        "claims_root": str(root),
        "source_root": str(source_real),
        "agent_id": agent_id,
        "runs": participating_runs,
        "claimed_paths": sorted(set(all_claimed)),
    }
    snapshot["snapshot_digest"] = f"sha256:{canonical_digest(snapshot)}"
    return snapshot


def _verify_changeset_claims(
    claims_root: str, agent_id: str, changes: list[dict[str, Any]]
) -> dict[str, Any]:
    first = _build_claim_snapshot(claims_root, agent_id)
    second = _build_claim_snapshot(claims_root, agent_id)
    if first != second:
        raise ToolError("claims_snapshot_raced", "authoritative claims changed while snapshotting")
    checked = [_safe_claim_path(change.get("path")) for change in changes]
    claimed = first["claimed_paths"]
    violations = [path for path in checked if not _path_covered_by_claim(claimed, path)]
    return {
        "enabled": True,
        "claimed_paths": claimed,
        "checked": checked,
        "violations": violations,
        "all_covered": not violations,
        "snapshot": first,
    }


def cmd_changeset(args: argparse.Namespace) -> dict:
    baseline = load_baseline(args.baseline)

    root_status = git(args.clone, "status", "--porcelain")
    if root_status.returncode != 0:
        raise ToolError("candidate_not_a_repository", root_status.stderr.strip(), EXIT_POLICY)
    # 忽略 untracked 孤儿仓库目录 (?? dir/), 文件型 untracked 仍视为 dirty (BET-Y1Q3-T1-07).
    tracked_changes = [
        line
        for line in root_status.stdout.splitlines()
        if line.strip() and not (line.startswith("?? ") and line.rstrip().endswith("/"))
    ]
    if tracked_changes:
        raise ToolError("candidate_dirty", "candidate clone root is dirty", EXIT_POLICY)
    links = gitlinks(args.clone)
    for path in links:
        initialized, _head, _origin, clean = submodule_state(args.clone, path)
        if initialized and not clean:
            raise ToolError("candidate_dirty", f"candidate submodule {path} is dirty", EXIT_POLICY)

    root_base = baseline["root_head_sha"]
    root_candidate = root_head(args.clone)
    if not is_ancestor(args.clone, root_base, root_candidate):
        raise ToolError(
            "root_rewind_or_diverged",
            f"candidate root {root_candidate} does not descend from baseline root {root_base}",
            EXIT_POLICY,
        )

    baseline_entries = {e["path"]: e for e in baseline.get("repositories", [])}
    gitlink_paths = set(baseline_entries) | set(links)
    changes = [
        {
            "kind": "root_file",
            "path": path,
            "base_sha": object_at_path(args.clone, root_base, path),
            "candidate_sha": object_at_path(args.clone, root_candidate, path),
            "ancestry_proven": True,
        }
        for path in root_changed_paths(args.clone, root_base, root_candidate)
        if path not in gitlink_paths
    ]
    for path in sorted(set(baseline_entries) | set(links)):
        base_sha = baseline_entries[path]["pinned_sha"] if path in baseline_entries else None
        cand_sha = links.get(path, None)
        if base_sha == cand_sha:
            continue
        initialized, _head, _origin, _clean = submodule_state(args.clone, path)
        if not initialized:
            raise ToolError(
                "child_uninitialized",
                f"submodule {path} changed but is not initialized in the candidate",
                EXIT_POLICY,
            )
        if base_sha is None or cand_sha is None:
            raise ToolError(
                "child_set_drift",
                f"submodule {path} was added or removed; split the topology change",
                EXIT_POLICY,
            )
        child_root = os.path.join(args.clone, path)
        child_head = root_head(child_root)
        if child_head != cand_sha:
            raise ToolError(
                "child_head_gitlink_mismatch",
                f"submodule {path} HEAD {child_head} != candidate gitlink {cand_sha}",
                EXIT_POLICY,
            )
        if not is_ancestor(child_root, base_sha, cand_sha):
            raise ToolError(
                "child_rewind_or_diverged",
                f"submodule {path} does not descend from baseline {base_sha}",
                EXIT_POLICY,
            )
        changes.append(
            {
                "kind": "gitlink",
                "path": path,
                "base_sha": base_sha,
                "candidate_sha": cand_sha,
                "ancestry_proven": True,
            }
        )

    identity = None
    try:
        identity = read_identity(args.clone, required=False)
    except ToolError:
        identity = None

    # D3 升级: 跨仓变更审计 — 校验变更路径在 agent claim 范围内
    claim_verification = None
    if getattr(args, "verify_claims", False):
        claims_root = getattr(args, "claims_root", None)
        if not claims_root:
            raise ToolError("claims_root_required", "--verify-claims requires explicit --claims-root")
        if not identity or identity.get("ready") is not True:
            raise ToolError("clone_identity_required", "claim verification requires a ready clone identity")
        authority_binding = trusted_claims_authority(
            args.clone, root_base, claims_root
        )
        claim_actor_id = identity.get("actor_id", identity["agent_id"])
        claim_verification = _verify_changeset_claims(
            authority_binding["claims_root"], claim_actor_id, changes
        )
        claim_verification["authority_binding"] = authority_binding
        claim_verification["consistency"] = {
            "mode": "best-effort-double-read",
            "atomic_with_push": False,
        }

    no_change = root_base == root_candidate and not changes
    attempt_identity = attempt_binding(identity) if identity else {}
    changeset = {
        "schema": (
            SCHEMA_CHANGESET_ATTEMPT
            if attempt_identity
            else SCHEMA_CHANGESET_CLAIMS
            if claim_verification is not None
            else SCHEMA_CHANGESET
        ),
        "agent_id": identity["agent_id"] if identity else None,
        "clone_root": canonical(args.clone),
        "baseline_manifest_digest": baseline["manifest_digest"],
        "root_base_sha": root_base,
        "root_candidate_sha": root_candidate,
        "changes": changes,
        "no_change": no_change,
        "claim_verification": claim_verification,
    }
    changeset.update(attempt_identity)
    changeset["change_id"] = canonical_digest(changeset, exclude_field="change_id")

    write_json_exclusive(args.output, changeset, "changeset_write_failed")
    if claim_verification is not None:
        violations = claim_verification.get("violations", [])
        if violations:
            raise ToolError(
                "claim_scope_violation",
                f"changeset contains unclaimed paths: {violations}",
                EXIT_POLICY,
                {"output_path": args.output, "violations": violations},
            )
        if claim_verification.get("all_covered") is not True:
            raise ToolError(
                "claim_verification_incomplete",
                "claim verification did not prove complete coverage",
                EXIT_POLICY,
                {"output_path": args.output},
            )
    return {
        "ok": True,
        "reason": "changeset_generated",
        "clone_root": canonical(args.clone),
        "output_path": args.output,
        "change_id": changeset["change_id"],
        "no_change": no_change,
        "changes_count": len(changes),
    }


def cmd_verify_changeset(args: argparse.Namespace) -> dict:
    """Rebuild and compare a claim-verified changeset against current clone state."""
    try:
        with open(args.changeset, encoding="utf-8") as fh:
            stored = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "changeset_unreadable",
            f"cannot read changeset {args.changeset}: {exc}",
            EXIT_POLICY,
        ) from exc
    if stored.get("schema") not in {
        SCHEMA_CHANGESET_CLAIMS,
        SCHEMA_CHANGESET_ATTEMPT,
    }:
        raise ToolError(
            "changeset_schema_mismatch",
            f"unexpected changeset schema {stored.get('schema')!r}",
            EXIT_POLICY,
        )
    stored_digest = stored.get("change_id")
    recomputed_digest = canonical_digest(stored, exclude_field="change_id")
    if stored_digest != recomputed_digest:
        raise ToolError(
            "changeset_digest_mismatch",
            "changeset digest validation failed",
            EXIT_POLICY,
        )
    claims = stored.get("claim_verification")
    if not isinstance(claims, dict) or claims.get("enabled") is not True:
        raise ToolError(
            "changeset_claims_unverified",
            "changeset was not created with successful --verify-claims",
            EXIT_POLICY,
        )
    if claims.get("all_covered") is not True or claims.get("violations"):
        raise ToolError(
            "changeset_claim_scope_violation",
            "changeset contains unclaimed paths",
            EXIT_POLICY,
        )
    claims_root = getattr(args, "claims_root", None)
    if not claims_root:
        raise ToolError("claims_root_required", "verify-changeset requires explicit --claims-root")
    claims_root = canonical(claims_root)
    snapshot = claims.get("snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("claims_root") != claims_root:
        raise ToolError("claims_root_mismatch", "changeset was generated from a different claims root")
    clone_root = canonical(args.clone)
    identity = read_identity(args.clone)
    binding = attempt_binding(identity)
    requested_attempt = getattr(args, "delivery_attempt_id", None)
    if requested_attempt is not None and requested_attempt != binding.get(
        "delivery_attempt_id"
    ):
        raise ToolError(
            "changeset_attempt_mismatch",
            "requested delivery attempt does not match clone identity",
            EXIT_POLICY,
        )
    if (
        identity.get("ready") is not True
        or identity.get("canonical_root") != clone_root
        or identity.get("agent_id") != args.agent_id
    ):
        raise ToolError(
            "changeset_agent_mismatch",
            "ready clone identity does not match requested clone and agent",
            EXIT_POLICY,
        )
    expected_changeset_schema = (
        SCHEMA_CHANGESET_ATTEMPT if binding else SCHEMA_CHANGESET_CLAIMS
    )
    if stored.get("schema") != expected_changeset_schema or any(
        stored.get(key) != value for key, value in binding.items()
    ):
        raise ToolError(
            "changeset_attempt_mismatch",
            "changeset delivery attempt does not match clone identity",
            EXIT_POLICY,
        )
    baseline = load_baseline(args.baseline)
    if (
        baseline.get("agent_id") != args.agent_id
        or baseline.get("canonical_root") != clone_root
        or any(baseline.get(key) != value for key, value in binding.items())
    ):
        raise ToolError(
            "changeset_baseline_mismatch",
            "baseline is not bound to this clone and agent",
            EXIT_POLICY,
        )
    authority_binding = trusted_claims_authority(
        args.clone,
        baseline["root_head_sha"],
        claims_root,
    )
    if claims.get("authority_binding") != authority_binding:
        raise ToolError(
            "claims_authority_binding_mismatch",
            "changeset authority binding does not match baseline topology policy",
            EXIT_POLICY,
        )
    if (
        stored.get("agent_id") != args.agent_id
        or stored.get("clone_root") != clone_root
        or any(stored.get(key) != value for key, value in binding.items())
    ):
        raise ToolError(
            "changeset_clone_mismatch",
            "changeset is not bound to this clone and agent",
            EXIT_POLICY,
        )

    with tempfile.TemporaryDirectory(prefix="agent-clone-verify-") as tmp:
        output = os.path.join(tmp, "current-changeset.json")
        cmd_changeset(
            argparse.Namespace(
                clone=args.clone,
                baseline=args.baseline,
                output=output,
                verify_claims=True,
                claims_root=claims_root,
            )
        )
        with open(output, encoding="utf-8") as fh:
            current = json.load(fh)
    if stored != current:
        raise ToolError(
            "changeset_stale",
            "changeset does not match current baseline, HEAD, paths, objects, or claims",
            EXIT_POLICY,
            {
                "stored_head": stored.get("root_candidate_sha"),
                "current_head": current.get("root_candidate_sha"),
                "stored_change_id": stored_digest,
                "current_change_id": current.get("change_id"),
            },
        )
    return {
        "ok": True,
        "reason": "changeset_verified",
        "clone_root": clone_root,
        "baseline_manifest_digest": stored["baseline_manifest_digest"],
        "root_head_sha": stored["root_candidate_sha"],
        "changed_paths": [change["path"] for change in stored.get("changes", [])],
        "change_id": stored_digest,
        "no_change": stored.get("no_change", False),
    }


# ---------------------------------------------------------------------------
# guard
# ---------------------------------------------------------------------------


def path_within(path: str, root: str) -> bool:
    """True when path equals or is contained within root (canonicalized)."""
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def cmd_guard(args: argparse.Namespace) -> dict:
    ws = canonical(args.workspace)
    integration_root = args.integration_root
    if integration_root is None:
        integration_root = os.environ.get("INTEGRATION_WORKSPACE")
    if integration_root is None:
        integration_root = os.path.expanduser("~/Workspace")
    ir = canonical(integration_root)
    agent_id = os.environ.get("AGENT_ID")

    result = {
        "ok": True,
        "workspace": ws,
        "integration_root": ir,
        "agent_id": agent_id,
    }
    if agent_id is None:
        result["state"] = "human"
        result["reason"] = "human_operation_allowed"
        return result
    if ws == ir or path_within(ws, ir):
        raise ToolError(
            "agent_on_integration_root",
            f"agent {agent_id} operating on or inside integration root {ir}",
            EXIT_POLICY,
        )
    identity = None
    try:
        identity = read_identity(ws, required=False)
    except ToolError:
        identity = None
    if identity is None:
        if args.require_clone:
            raise ToolError(
                "clone_identity_required",
                f"agent {agent_id} must operate from an independent agent clone",
                EXIT_POLICY,
            )
        result["state"] = "legacy_isolated_worktree"
        result["reason"] = "legacy_isolated_worktree_allowed"
        return result
    if identity.get("provenance_required") is True:
        verify_clone_provenance(ws, identity)
    if identity.get("profile") is not None:
        profile = identity.get("profile")
        if profile not in {"governance", "full"}:
            raise ToolError(
                "clone_readiness_mismatch",
                f"profile {profile!r} is not eligible for writer admission",
                EXIT_POLICY,
            )
        receipt_file = readiness_path(ws)
        try:
            with open(receipt_file, encoding="utf-8") as fh:
                receipt = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise ToolError(
                "clone_readiness_missing",
                f"named-profile clone has no valid readiness receipt: {exc}",
                EXIT_POLICY,
            ) from exc
        receipt_digest = canonical_digest(receipt, exclude_field="receipt_digest")
        frozen_ancestor = git(
            ws,
            "merge-base",
            "--is-ancestor",
            identity.get("frozen_root_sha", ""),
            "HEAD",
        )
        if (
            receipt.get("schema")
            != expected_artifact_schema(
                identity,
                SCHEMA_READINESS,
                SCHEMA_READINESS_ATTEMPT,
            )
            or receipt.get("receipt_digest") != receipt_digest
            or identity.get("readiness_receipt_digest") != receipt_digest
            or identity.get("readiness_status") != "ready"
            or receipt.get("status") != "ready"
            or receipt.get("profile") != profile
            or receipt.get("agent_id") != identity.get("agent_id")
            or receipt.get("clone_root") != ws
            or receipt.get("source_url") != redact_remote(identity.get("source_url"))
            or receipt.get("root_head_sha") != identity.get("frozen_root_sha")
            or receipt.get("working_branch") != identity.get("working_branch")
            or any(
                receipt.get(key) != value
                for key, value in attempt_binding(identity).items()
            )
            or frozen_ancestor.returncode != 0
        ):
            raise ToolError(
                "clone_readiness_mismatch",
                "named-profile clone readiness is missing, degraded, or digest-mismatched",
                EXIT_POLICY,
            )
        live_links = gitlinks(ws)
        required_paths = resolve_submodule_profile(profile, live_links)
        receipt_paths = [entry.get("path") for entry in receipt.get("required_submodules", [])]
        configured_origins = expected_submodule_origins(ws)
        if receipt_paths != required_paths:
            raise ToolError(
                "clone_readiness_mismatch",
                "readiness receipt required submodules do not match the named profile",
                EXIT_POLICY,
            )
        for path in required_paths:
            initialized, child_head, child_origin, clean = submodule_state(ws, path)
            if (
                not initialized
                or child_head != live_links[path]
                or not clean
                or normalize_source(child_origin or "")
                != normalize_source(configured_origins.get(path, ""))
            ):
                child_status = git_isolated(os.path.join(ws, path), "status", "--porcelain")
                raise ToolError(
                    "clone_readiness_mismatch",
                    f"live submodule {path} no longer satisfies the named profile",
                    EXIT_POLICY,
                    {
                        "path": path,
                        "initialized": initialized,
                        "pinned_sha": live_links[path],
                        "child_head": child_head,
                        "clean": clean,
                        "expected_origin": redact_remote(configured_origins.get(path)),
                        "actual_origin": redact_remote(child_origin),
                        "status_returncode": child_status.returncode,
                        "status_sample": child_status.stdout.splitlines()[:5],
                        "status_error": child_status.stderr.strip()[:240],
                        "git_index_file": os.environ.get("GIT_INDEX_FILE"),
                        "git_dir_env": os.environ.get("GIT_DIR"),
                        "git_work_tree_env": os.environ.get("GIT_WORK_TREE"),
                    },
                )
    hooks_proc = git(ws, "config", "--get", "core.hooksPath")
    hooks_path = hooks_proc.stdout.strip() if hooks_proc.returncode == 0 else None
    if (
        identity.get("ready") is True
        and identity["agent_id"] == agent_id
        and identity["canonical_root"] == ws
        and branch_state(ws) == (identity.get("working_branch"), False)
        and hooks_path == ".githooks"
        and os.path.isfile(os.path.join(ws, ".githooks", "pre-commit"))
    ):
        result["state"] = "verified_clone"
        result["reason"] = "clone_identity_matched"
        result["clone_root"] = identity["canonical_root"]
        result.update(attempt_binding(identity))
        return result
    raise ToolError(
        "clone_identity_mismatch",
        f"identity agent {identity['agent_id']} or root {identity['canonical_root']} "
        f"does not match agent {agent_id} at {ws}",
        EXIT_POLICY,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-clone",
        description="Independent agent clone topology (BET-Y1Q1-T1-05 D1 pilot)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--json", action="store_true", help="emit JSON output")

    p = sub.add_parser("create")
    add_common(p)
    p.add_argument("--agent-id", required=True)
    p.add_argument(
        "--delivery-attempt-id",
        required=True,
        help="single delivery-attempt identity; creates agent/<actor>--<attempt>",
    )
    p.add_argument("--source", required=True)
    p.add_argument("--destination", required=True)
    p.add_argument("--revision")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--no-submodules", action="store_true")
    group.add_argument("--profile", choices=SUBMODULE_PROFILES)
    group.add_argument(
        "--submodule",
        action="append",
        default=[],
        help="initialize only this root gitlink; repeat for multiple paths",
    )
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("provenance")
    add_common(p)
    p.add_argument("--clone", required=True)
    p.add_argument("--expected-repository", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_provenance)

    p = sub.add_parser("readiness")
    add_common(p)
    p.add_argument("--clone", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_readiness)

    p = sub.add_parser("manifest")
    add_common(p)
    p.add_argument("--clone", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_manifest)

    p = sub.add_parser("verify")
    add_common(p)
    p.add_argument("--clone", required=True)
    p.add_argument("--manifest", required=True)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("changeset")
    add_common(p)
    p.add_argument("--clone", required=True)
    p.add_argument("--baseline", required=True)
    p.add_argument("--output", required=True)
    p.add_argument(
        "--verify-claims",
        action="store_true",
        help="D3 跨仓变更审计: 校验变更路径在 agent claim 范围内",
    )
    p.add_argument("--claims-root", help="authoritative workspace containing workflow runs")
    p.set_defaults(func=cmd_changeset)

    p = sub.add_parser("verify-changeset")
    add_common(p)
    p.add_argument("--clone", required=True)
    p.add_argument("--baseline", required=True)
    p.add_argument("--changeset", required=True)
    p.add_argument("--agent-id", required=True)
    p.add_argument("--delivery-attempt-id")
    p.add_argument("--claims-root", help="same authoritative claims root used to generate changeset")
    p.set_defaults(func=cmd_verify_changeset)

    p = sub.add_parser("guard")
    add_common(p)
    p.add_argument("--workspace", required=True)
    p.add_argument("--integration-root")
    p.add_argument(
        "--require-clone",
        action="store_true",
        help="reject agent workspaces without a verified independent-clone identity",
    )
    p.set_defaults(func=cmd_guard)
    return parser


def humanize(result: dict) -> str:
    lines = []
    for key, value in result.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, sort_keys=True)
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def emit(result: dict, pretty: bool) -> None:
    """Write one JSON document to stdout and a summary to stderr."""
    if pretty:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print(humanize(result), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except ToolError as exc:
        error = {"ok": False, "reason": exc.reason, "message": exc.message}
        error.update(exc.details)
        emit(
            error,
            getattr(args, "json", False),
        )
        return exc.exit_code
    except Exception as exc:
        out = {
            "ok": False,
            "reason": "internal_error",
            "message": f"{type(exc).__name__}: {exc}",
        }
        emit(out, getattr(args, "json", False))
        return EXIT_USAGE
    emit(result, getattr(args, "json", False))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
