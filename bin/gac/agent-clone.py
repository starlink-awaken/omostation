#!/usr/bin/env python3
"""agent-clone.py - independent agent clone topology (BET-Y1Q1-T1-05 D1 pilot).

Python 3 stdlib-only CLI for the first production slice of the
independent-agent-clone topology.  Subcommands:

  create     --agent-id ID --source URL_OR_PATH --destination PATH
             [--revision REF] [--no-submodules]
  manifest   --clone PATH --output PATH
  verify     --clone PATH --manifest PATH
  changeset  --clone PATH --baseline PATH --output PATH
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
import re
import shutil
import subprocess
import sys
import tempfile

SCHEMA_MANIFEST = "agent-clone-manifest/v1"
SCHEMA_CHANGESET = "cross-repo-changeset/v1"
SCHEMA_IDENTITY = "agent-clone-identity/v1"
IDENTITY_FILENAME = "agent-clone-identity.json"
AGENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

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


def submodule_state(
    repo_root: str, rel_path: str
) -> tuple[bool, str | None, str | None, bool]:
    """Return (initialized, child_head, child_origin, clean) for a submodule."""
    sub = os.path.join(repo_root, rel_path)
    # git clone leaves an empty placeholder dir for uninitialized submodules;
    # an initialized one always carries its own .git marker at the root.
    if not os.path.exists(os.path.join(sub, ".git")):
        return False, None, None, True
    probe = git(sub, "rev-parse", "--show-toplevel")
    if probe.returncode != 0 or canonical(probe.stdout.strip()) != canonical(sub):
        return False, None, None, True
    head_proc = git(sub, "rev-parse", "HEAD")
    head = head_proc.stdout.strip() if head_proc.returncode == 0 else None
    origin_proc = git(sub, "config", "--get", "remote.origin.url")
    origin = origin_proc.stdout.strip() if origin_proc.returncode == 0 else None
    status_proc = git(sub, "status", "--porcelain")
    clean = status_proc.returncode == 0 and status_proc.stdout.strip() == ""
    return True, head, origin, clean


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------


def identity_path(repo_root: str) -> str:
    return os.path.join(git_common_dir(repo_root), IDENTITY_FILENAME)


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
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "identity_invalid", f"cannot read clone identity {path}: {exc}", EXIT_POLICY
        ) from exc
    if data.get("schema") != SCHEMA_IDENTITY:
        raise ToolError(
            "identity_invalid",
            f"unexpected identity schema {data.get('schema')!r}",
            EXIT_POLICY,
        )
    return data


def write_identity(repo_root: str, identity: dict) -> str:
    path = identity_path(repo_root)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(identity, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
    return path


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
        if (
            len(parts) == 2
            and parts[1] == ref
            and re.fullmatch(r"[0-9a-fA-F]{40,64}", parts[0])
        ):
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


def cmd_create(args: argparse.Namespace) -> dict:
    agent_id = args.agent_id
    if not agent_id or not AGENT_ID_RE.match(agent_id):
        raise ToolError(
            "agent_id_invalid",
            f"agent id {agent_id!r} must match {AGENT_ID_RE.pattern}",
            EXIT_USAGE,
        )
    working_branch = f"agent/{agent_id}"
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
                revision, source_revision_ref = resolve_upstream_branch(
                    source_url, remote_branch
                )
                revision_fetch_url = source_url
            else:
                resolved = git(
                    source, "rev-parse", "--verify", f"{revision}^{{commit}}"
                )
                if resolved.returncode != 0:
                    raise ToolError(
                        "revision_checkout_failed",
                        f"cannot resolve revision {revision} in source: "
                        f"{resolved.stderr.strip()}",
                        EXIT_POLICY,
                    )
                revision = resolved.stdout.strip()
                symbolic = git(
                    source, "rev-parse", "--symbolic-full-name", source_revision_ref
                )
                if symbolic.returncode == 0 and symbolic.stdout.strip():
                    source_revision_ref = symbolic.stdout.strip()

    destination_parent = os.path.dirname(os.path.abspath(dest)) or os.curdir
    if not os.path.isdir(destination_parent):
        raise ToolError(
            "destination_parent_missing",
            f"destination parent does not exist: {destination_parent}",
            EXIT_POLICY,
        )
    staging_root = tempfile.mkdtemp(
        prefix=f".{os.path.basename(dest)}.agent-clone-", dir=destination_parent
    )
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
        alt = os.path.join(
            git_common_dir(staging_clone), "objects", "info", "alternates"
        )
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
                        f"cannot fetch source revision {source_revision_ref}: "
                        f"{fetch.stderr.strip()}",
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

        submodules_initialized = False
        if not args.no_submodules:
            # Initialize the superproject's complete gitlink set. Do not recurse
            # into nested workspace mirrors: a submodule may itself contain the
            # entire project graph, causing scripts/scripts/... expansion.
            proc = git(
                staging_clone,
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "update",
                "--init",
            )
            if proc.returncode != 0:
                raise ToolError(
                    "submodule_init_failed",
                    f"submodule init failed: {proc.stderr.strip()}",
                    EXIT_POLICY,
                )
            for path, pinned_sha in gitlinks(staging_clone).items():
                initialized, child_head, _origin, clean = submodule_state(
                    staging_clone, path
                )
                if not initialized or child_head != pinned_sha or not clean:
                    raise ToolError(
                        "submodule_init_incomplete",
                        f"submodule {path} did not reach a clean pinned checkout",
                        EXIT_POLICY,
                    )
            submodules_initialized = True

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
        identity = {
            "schema": SCHEMA_IDENTITY,
            "agent_id": agent_id,
            "canonical_root": canonical(dest),
            "source_url": source_url,
            "frozen_root_sha": frozen_sha,
            "working_branch": working_branch,
            "ready": True,
        }
        write_identity(staging_clone, identity)
        atomic_publish_no_replace(staging_clone, dest)
        published = True
    except ToolError as exc:
        failure = exc
    except Exception as exc:  # noqa: BLE001 - preserve cleanup evidence
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

    return {
        "ok": True,
        "reason": "clone_created",
        "agent_id": agent_id,
        "clone_root": canonical(dest),
        "source_url": identity["source_url"],
        "frozen_root_sha": frozen_sha,
        "working_branch": working_branch,
        "submodules_initialized": submodules_initialized,
        "identity_file": identity_file,
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

    root_status = git(repo_root, "status", "--porcelain")
    if root_status.returncode != 0:
        raise ToolError(
            "not_a_repository", root_status.stderr.strip(), EXIT_POLICY
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
    if root_status.stdout.strip():
        raise ToolError(
            "root_dirty", "root repository has uncommitted changes", EXIT_POLICY
        )

    branch, detached = branch_state(repo_root)
    hooks_proc = git(repo_root, "config", "--get", "core.hooksPath")
    hooks_path = hooks_proc.stdout.strip() if hooks_proc.returncode == 0 else None
    manifest = {
        "schema": SCHEMA_MANIFEST,
        "agent_id": identity["agent_id"],
        "canonical_root": expected_root,
        "origin_url": identity["source_url"],
        "root_head_sha": root_head(repo_root),
        "branch": branch,
        "detached": detached,
        "hooks_path": hooks_path,
        "repositories": entries,
    }
    manifest["manifest_digest"] = canonical_digest(
        manifest, exclude_field="manifest_digest"
    )
    return manifest


def cmd_manifest(args: argparse.Namespace) -> dict:
    manifest = build_manifest(args.clone)
    try:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except OSError as exc:
        raise ToolError(
            "manifest_write_failed",
            f"cannot write manifest {args.output}: {exc}",
            EXIT_USAGE,
        ) from exc
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
        with open(args.manifest, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "manifest_unreadable",
            f"cannot read manifest {args.manifest}: {exc}",
            EXIT_POLICY,
        ) from exc
    if manifest.get("schema") != SCHEMA_MANIFEST:
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
    if identity.get("ready") is not True:
        raise ToolError(
            "identity_mismatch", "stored identity is not marked ready", EXIT_POLICY
        )
    if identity["agent_id"] != manifest.get("agent_id"):
        raise ToolError(
            "identity_mismatch", "identity agent_id does not match manifest", EXIT_POLICY
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
    if root_status.stdout.strip():
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

    checks = [{"check": "root_sha", "pass": True}, {"check": "root_clean", "pass": True}]
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
                raise ToolError(
                    "child_dirty", f"submodule {path} is dirty", EXIT_POLICY
                )
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
        with open(baseline_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "baseline_unreadable",
            f"cannot read baseline manifest {baseline_path}: {exc}",
            EXIT_POLICY,
        ) from exc
    if manifest.get("schema") != SCHEMA_MANIFEST:
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


def cmd_changeset(args: argparse.Namespace) -> dict:
    baseline = load_baseline(args.baseline)

    root_status = git(args.clone, "status", "--porcelain")
    if root_status.returncode != 0:
        raise ToolError(
            "candidate_not_a_repository", root_status.stderr.strip(), EXIT_POLICY
        )
    if root_status.stdout.strip():
        raise ToolError("candidate_dirty", "candidate clone root is dirty", EXIT_POLICY)
    links = gitlinks(args.clone)
    for path in links:
        initialized, _head, _origin, clean = submodule_state(args.clone, path)
        if initialized and not clean:
            raise ToolError(
                "candidate_dirty", f"candidate submodule {path} is dirty", EXIT_POLICY
            )

    root_base = baseline["root_head_sha"]
    root_candidate = root_head(args.clone)
    if not is_ancestor(args.clone, root_base, root_candidate):
        raise ToolError(
            "root_rewind_or_diverged",
            f"candidate root {root_candidate} does not descend from baseline root {root_base}",
            EXIT_POLICY,
        )

    baseline_entries = {e["path"]: e for e in baseline.get("repositories", [])}
    changes = []
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

    no_change = root_base == root_candidate and not changes
    changeset = {
        "schema": SCHEMA_CHANGESET,
        "agent_id": identity["agent_id"] if identity else None,
        "baseline_manifest_digest": baseline["manifest_digest"],
        "root_base_sha": root_base,
        "root_candidate_sha": root_candidate,
        "changes": changes,
        "no_change": no_change,
    }
    changeset["change_id"] = canonical_digest(
        {
            "baseline_manifest_digest": changeset["baseline_manifest_digest"],
            "root_base_sha": root_base,
            "root_candidate_sha": root_candidate,
            "changes": changes,
        }
    )

    try:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(changeset, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except OSError as exc:
        raise ToolError(
            "changeset_write_failed",
            f"cannot write {args.output}: {exc}",
            EXIT_USAGE,
        ) from exc
    return {
        "ok": True,
        "reason": "changeset_generated",
        "clone_root": canonical(args.clone),
        "output_path": args.output,
        "change_id": changeset["change_id"],
        "no_change": no_change,
        "changes_count": len(changes),
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
    p.add_argument("--source", required=True)
    p.add_argument("--destination", required=True)
    p.add_argument("--revision")
    p.add_argument("--no-submodules", action="store_true")
    p.set_defaults(func=cmd_create)

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
    p.set_defaults(func=cmd_changeset)

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
    except Exception as exc:  # noqa: BLE001 - last-resort structured failure
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
