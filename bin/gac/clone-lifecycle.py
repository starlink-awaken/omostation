#!/usr/bin/env python3
"""clone-lifecycle.py — 自动化 agent clone 生命周期管道 (最理想架构核心).

连接独立 clone 拓扑的全流程:
  onboard  → 为新 agent 创建 clone + 生成 manifest
  snapshot → 为当前 clone 生成基线 manifest
  changeset → 生成跨仓变更集 + claim 校验
  integrate → 推送分支 + 创建 PR (dry-run 默认)
  retire → 清理 clone + 释放资源

设计原则:
- 每个子命令都是幂等的 (可重试)
- 全程审计日志 (audit log)
- 失败安全 (fail-closed with clear error)
- 与 agent-clone.py / swarm-discipline.py 集成

长期维护: 所有拓扑操作走此入口, 不收口到裸 git 命令.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # workspace root
AGENT_CLONE = ROOT / "bin" / "gac" / "agent-clone.py"

EXIT_OK = 0
EXIT_POLICY = 1
EXIT_USAGE = 2
RMTREE_AVOIDS_SYMLINK_ATTACKS = shutil.rmtree.avoids_symlink_attacks
FD_BOUND_DELETE_SUPPORTED = (
    RMTREE_AVOIDS_SYMLINK_ATTACKS
    and hasattr(os, "O_DIRECTORY")
    and hasattr(os, "O_NOFOLLOW")
    and all(function in os.supports_dir_fd for function in (os.open, os.stat, os.unlink, os.rmdir))
)


class RetirementRaceError(OSError):
    """The inode bound for retirement no longer matches its directory entry."""


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)


def audit(action: str, details: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"[{ts}] LIFECYCLE={action} {details}"
    print(line, file=sys.stderr)


def reject(action: str, reason: str, message: str, **details: object) -> int:
    payload = {"ok": False, "reason": reason, "message": message, **details}
    audit(f"{action}_blocked", f"reason={reason} message={message}")
    print(json.dumps(payload, sort_keys=True), file=sys.stderr)
    return EXIT_POLICY


def github_repo_slug(remote_url: str) -> str | None:
    """Return an exact owner/repository slug for a GitHub remote."""
    match = re.fullmatch(
        r"(?:https?://github\.com/|ssh://git@github\.com/|git@github\.com:)"
        r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?",
        remote_url.strip(),
    )
    return f"{match.group(1)}/{match.group(2)}" if match else None


def run_provenance_guard(
    clone: Path,
    identity: dict,
    *,
    platform_base: str | None = None,
    platform_head: str | None = None,
) -> tuple[bool, str | None]:
    """Re-enter the canonical clone guard, optionally narrowing delivery authors."""
    env = os.environ.copy()
    env["AGENT_ID"] = str(identity.get("agent_id", ""))
    command = [sys.executable, str(AGENT_CLONE)]
    if platform_base is not None or platform_head is not None:
        if platform_base is None or platform_head is None:
            return False, "platform provenance requires both base and head"
        command.extend(
            [
                "retirement-provenance",
                "--clone",
                str(clone),
                "--platform-base",
                platform_base,
                "--platform-head",
                platform_head,
                "--json",
            ]
        )
    else:
        command.extend(
            ["guard", "--workspace", str(clone), "--require-clone", "--json"]
        )
    guarded = run(command, env=env)
    if guarded.returncode != 0:
        return False, guarded.stdout.strip() or guarded.stderr.strip() or "provenance guard failed"
    return True, None


def live_origin_repository_slug(clone: Path) -> tuple[str | None, str | None]:
    """Resolve the exact live origin repository without weakening later provenance checks."""
    remote_probe = run(["git", "-C", str(clone), "remote", "get-url", "origin"])
    if remote_probe.returncode != 0:
        return None, "cannot resolve origin remote"
    slug = github_repo_slug(remote_probe.stdout)
    return (slug, None) if slug else (None, "origin is not an exact GitHub repository URL")


def live_origin_fetch_push_repository_slug(clone: Path) -> tuple[str | None, str | None]:
    """Require one exact fetch and push origin bound to the same GitHub repository."""
    slugs: list[str] = []
    for direction, options in (
        ("fetch", ["--all"]),
        ("push", ["--push", "--all"]),
    ):
        probe = run(
            ["git", "-C", str(clone), "remote", "get-url", *options, "origin"]
        )
        remotes = [line.strip() for line in probe.stdout.splitlines() if line.strip()]
        if probe.returncode != 0 or len(remotes) != 1:
            return None, f"origin must expose exactly one {direction} URL"
        slug = github_repo_slug(remotes[0])
        if slug is None:
            return None, f"origin {direction} is not an exact GitHub repository URL"
        slugs.append(slug)
    if slugs[0] != slugs[1]:
        return None, "origin fetch and push repositories differ"
    return slugs[0], None


def provenance_receipt_repository_slug(clone: Path) -> tuple[str | None, str | None]:
    """Read the canonical repository from a receipt after its guard succeeded."""
    try:
        receipt = json.loads((clone / ".git" / "agent-clone-provenance.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"provenance receipt unreadable: {exc}"
    canonical_repository = (receipt.get("repository") or {}).get(
        "canonical_repository", ""
    )
    match = re.fullmatch(
        r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)",
        canonical_repository,
    )
    if not match:
        return None, "provenance receipt repository is invalid"
    return f"{match.group(1)}/{match.group(2)}", None


def bound_repository_slug(clone: Path, identity: dict) -> tuple[str | None, str | None]:
    """Resolve a lifecycle repository, live-verifying new provenance identities."""
    if identity.get("provenance_required") is True:
        guarded, guard_error = run_provenance_guard(clone, identity)
        if not guarded:
            return None, guard_error
        return provenance_receipt_repository_slug(clone)
    return live_origin_repository_slug(clone)


def workflow_activity(root: Path) -> tuple[list[str], list[str], list[str]]:
    workflow_root = root / ".omo" / "_delivery" / "agent-workflows"
    locks = [str(path) for path in (workflow_root / "locks").glob("*") if path.is_file()]
    active_runs: list[str] = []
    errors: list[str] = []
    for run_file in (workflow_root / "runs").glob("*.yaml"):
        try:
            content = run_file.read_text(encoding="utf-8")
        except OSError:
            errors.append(str(run_file))
            continue
        if re.search(r"(?m)^status:\s*(?:active|in_progress|running|executing)\s*$", content):
            active_runs.append(str(run_file))
    return locks, active_runs, errors


def remove_opened_tree_contents(directory_fd: int) -> None:
    """Remove entries below an already-open directory without path escape.

    Retirement already requires a clean clone with zero workflow leases. The
    threat model therefore excludes an actively hostile same-UID writer, which
    POSIX cannot lock out from a re-stat/unlink window. Directory identity is
    FD-bound and non-directories are unlinked without following symlinks, matching
    the platform's symlink-safe ``rmtree`` boundary.
    """
    with os.scandir(directory_fd) as entries:
        for entry in entries:
            entry_stat = os.stat(entry.name, dir_fd=directory_fd, follow_symlinks=False)
            if stat.S_ISDIR(entry_stat.st_mode):
                child_fd = os.open(
                    entry.name,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=directory_fd,
                )
                try:
                    child_stat = os.fstat(child_fd)
                    if not os.path.samestat(entry_stat, child_stat):
                        raise RetirementRaceError(f"directory entry changed before open: {entry.name}")
                    remove_opened_tree_contents(child_fd)
                    current_stat = os.stat(entry.name, dir_fd=directory_fd, follow_symlinks=False)
                    if not os.path.samestat(child_stat, current_stat):
                        raise RetirementRaceError(f"directory entry changed before removal: {entry.name}")
                    os.rmdir(entry.name, dir_fd=directory_fd)
                finally:
                    os.close(child_fd)
            else:
                current_stat = os.stat(entry.name, dir_fd=directory_fd, follow_symlinks=False)
                if not os.path.samestat(entry_stat, current_stat):
                    raise RetirementRaceError(f"file entry changed before removal: {entry.name}")
                os.unlink(entry.name, dir_fd=directory_fd)


def remove_payload_by_fd(payload: Path, expected_stat: os.stat_result) -> None:
    """Delete only the payload inode opened and matched to ``expected_stat``."""
    if not FD_BOUND_DELETE_SUPPORTED:
        raise RetirementRaceError("platform lacks fd-bound symlink-safe recursive deletion")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent_fd = os.open(payload.parent, flags)
    payload_fd = -1
    try:
        path_stat = os.stat(payload.name, dir_fd=parent_fd, follow_symlinks=False)
        if not os.path.samestat(expected_stat, path_stat):
            raise RetirementRaceError("payload changed before fd binding")
        payload_fd = os.open(payload.name, flags, dir_fd=parent_fd)
        opened_stat = os.fstat(payload_fd)
        if not os.path.samestat(expected_stat, opened_stat):
            raise RetirementRaceError("opened payload does not match verified clone")
        remove_opened_tree_contents(payload_fd)
        final_stat = os.stat(payload.name, dir_fd=parent_fd, follow_symlinks=False)
        if not os.path.samestat(opened_stat, final_stat):
            raise RetirementRaceError("payload path changed during fd-bound deletion")
        os.rmdir(payload.name, dir_fd=parent_fd)
    finally:
        if payload_fd >= 0:
            os.close(payload_fd)
        os.close(parent_fd)


def quarantine_remove_verified(
    dest: Path,
    expected_stat: os.stat_result,
    expected_head: str,
    post_quarantine: object | None = None,
) -> tuple[bool, str]:
    """Atomically isolate the checked inode before recursive deletion."""
    quarantine = Path(
        tempfile.mkdtemp(
            prefix=f".{dest.name}.retire-quarantine-",
            dir=str(dest.parent),
        )
    )
    payload = quarantine / "payload"

    def restore(message: str) -> tuple[bool, str]:
        if not os.path.lexists(dest) and os.path.lexists(payload):
            os.rename(payload, dest)
            quarantine.rmdir()
            return False, f"{message}; original path restored"
        return False, f"{message}; inspect preserved payload at {payload}"

    try:
        os.rename(dest, payload)
        moved_stat = payload.lstat()
        if payload.is_symlink() or not os.path.samestat(expected_stat, moved_stat):
            return restore("destination changed at quarantine boundary")
        head = run(["git", "-C", str(payload), "rev-parse", "HEAD"])
        if head.returncode != 0 or head.stdout.strip() != expected_head:
            return restore("clone HEAD changed at quarantine boundary")
        status = run(["git", "-C", str(payload), "status", "--porcelain", "--ignore-submodules=none"])
        if status.returncode != 0 or status.stdout.strip():
            return restore("clone became dirty at quarantine boundary")
        locks, active_runs, state_errors = workflow_activity(payload)
        if locks or active_runs or state_errors:
            return restore("workflow lease or lock appeared at quarantine boundary")
        if post_quarantine is not None:
            try:
                verdict = post_quarantine(payload)
            except Exception as exc:  # fail closed before an irreversible operation
                return restore(f"post-quarantine verification failed: {exc}")
            if verdict is not True:
                return restore("post-quarantine verification changed")
        if not FD_BOUND_DELETE_SUPPORTED:
            return restore("platform lacks fd-bound symlink-safe recursive deletion")
        remove_payload_by_fd(payload, moved_stat)
        quarantine.rmdir()
        return True, str(quarantine)
    except OSError as exc:
        if not os.path.lexists(payload):
            try:
                quarantine.rmdir()
            except OSError:
                pass
        return False, f"secure retirement failed: {exc}; inspect {quarantine}"


# ``abort-unready`` intentionally has a narrower contract than ``retire``.  It
# is the only escape hatch for a clone that *never became a writer*.  Keep its
# evidence and Git reads local to this file so the mature ready-clone retirement
# path stays unchanged.
def _canonical_json_digest(payload: dict, exclude: str | None = None) -> str:
    body = {key: value for key, value in payload.items() if key != exclude} if exclude else payload
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _isolated_git_env() -> dict[str, str]:
    """Discard ambient Git config/redirects for every abort eligibility probe."""
    keep = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    keep.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
    return keep


def _git_abort(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return run(["git", "-C", str(repo), *args], env=_isolated_git_env())


def _abort_reject(reason: str) -> tuple[None, str]:
    return None, reason


def _safe_external_json(
    path_value: str, dest: Path, label: str, *, must_be_external: bool = True
) -> tuple[dict | None, str | None]:
    path = Path(path_value).expanduser().absolute()
    try:
        st = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError as exc:
        return _abort_reject(f"{label}_unreadable:{exc}")
    if (
        stat.S_ISLNK(st.st_mode)
        or not stat.S_ISREG(st.st_mode)
        or (must_be_external and (resolved == dest or dest in resolved.parents))
    ):
        return _abort_reject(f"{label}_unsafe_path")
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not os.path.samestat(st, path.lstat()):
            return _abort_reject(f"{label}_raced")
    except (OSError, json.JSONDecodeError) as exc:
        return _abort_reject(f"{label}_invalid:{exc}")
    return (payload, None) if isinstance(payload, dict) else _abort_reject(f"{label}_invalid")


def _exact_github_slug(url: str) -> str | None:
    # github_repo_slug deliberately already rejects credential-bearing HTTPS URLs.
    return github_repo_slug(url)


def _one_origin_url(repo: Path, push: bool = False) -> tuple[str | None, str | None]:
    all_args = ["remote", "get-url"] + (["--push", "--all"] if push else ["--all"]) + ["origin"]
    got = _git_abort(repo, *all_args)
    values = [line.strip() for line in got.stdout.splitlines() if line.strip()]
    if got.returncode != 0 or len(values) != 1:
        return _abort_reject("origin_unreadable_or_ambiguous")
    if _exact_github_slug(values[0]) is None:
        return _abort_reject("origin_not_exact_github")
    return values[0], None


def _no_local_url_rewrites(repo: Path) -> bool:
    rewritten = _git_abort(repo, "config", "--local", "--get-regexp", r"^url\..*\.(insteadOf|pushInsteadOf)$")
    return rewritten.returncode == 1 and not rewritten.stdout.strip()


def _abort_worktree_clean(repo: Path, *, independent_root: bool) -> bool:
    status = _git_abort(repo, "status", "--porcelain", "--ignored", "--ignore-submodules=none")
    if status.returncode != 0 or status.stdout.strip():
        return False
    stash = _git_abort(repo, "stash", "list", "--format=%H")
    if stash.returncode != 0 or stash.stdout.strip():
        return False
    common = _git_abort(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    git_dir = repo / ".git"
    if common.returncode != 0 or (independent_root and (not git_dir.is_dir() or Path(common.stdout.strip()).resolve() != git_dir.resolve())):
        return False
    common_dir = Path(common.stdout.strip())
    if (common_dir / "objects" / "info" / "alternates").exists():
        return False
    worktrees = _git_abort(repo, "worktree", "list", "--porcelain")
    if worktrees.returncode != 0 or sum(line.startswith("worktree ") for line in worktrees.stdout.splitlines()) != 1:
        return False
    if any((common_dir / marker).exists() for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "sequencer")):
        return False
    return True


def _actor_has_activity(root: Path, actor: str, *, require_root: bool) -> bool:
    workflow_root = root / ".omo" / "_delivery" / "agent-workflows"
    if not workflow_root.is_dir():
        return require_root
    for lock in (workflow_root / "locks").glob("*"):
        if lock.is_file() and actor in lock.read_text(encoding="utf-8", errors="replace"):
            return True
    for run_file in (workflow_root / "runs").glob("*.yaml"):
        try:
            text = run_file.read_text(encoding="utf-8")
        except OSError:
            return True
        active = re.search(r"(?m)^status:\s*(?:active|in_progress|running|executing)\s*$", text)
        actor_match = re.search(r"(?m)^actor:\s*([^\s#]+)", text)
        claim_match = re.search(rf"(?m)^\s*actor:\s*{re.escape(actor)}\s*$", text)
        if active and ((actor_match and actor_match.group(1) == actor) or claim_match):
            return True
    return False


def _abort_assessment(args: argparse.Namespace, physical: Path, logical: Path) -> tuple[dict | None, str | None]:
    """Return an immutable eligibility digest; every failed predicate is deny-by-default."""
    # After the atomic quarantine move the physical name is ``payload`` while
    # the immutable identity continues to bind the original logical ``ws``.
    if physical.is_symlink() or logical.name != "ws":
        return _abort_reject("unsafe_destination")
    try:
        if physical.resolve(strict=True) != physical or logical.resolve(strict=False) != logical:
            return _abort_reject("destination_resolution_mismatch")
        initial = physical.lstat()
    except OSError as exc:
        return _abort_reject(f"destination_unreadable:{exc}")
    git_dir = physical / ".git"
    identity_path = git_dir / "agent-clone-identity.json"
    try:
        identity_stat = identity_path.lstat()
        if not stat.S_ISREG(identity_stat.st_mode) or stat.S_ISLNK(identity_stat.st_mode):
            return _abort_reject("identity_unsafe")
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _abort_reject(f"identity_unreadable:{exc}")
    branch = f"agent/{args.agent_id}--{args.delivery_attempt_id}"
    frozen = identity.get("frozen_root_sha")
    if (
        identity.get("schema") != "agent-clone-identity/v2"
        or identity.get("agent_id") != args.agent_id
        or identity.get("actor_id") != args.agent_id
        or identity.get("delivery_attempt_id") != args.delivery_attempt_id
        or identity.get("canonical_root") != str(logical)
        or identity.get("working_branch") != branch
        or identity.get("ready") is not False
        or identity.get("readiness_status") != "degraded"
        or identity.get("profile") not in {"custom", "root-only"}
        or identity.get("readiness_profile") != identity.get("profile")
        or identity.get("provenance_required") is True
        or any(identity.get(key) not in {None, "", False} for key in ("provenance_status", "provenance_receipt_digest"))
        or (git_dir / "agent-clone-provenance.json").exists()
        or not isinstance(frozen, str)
        or not re.fullmatch(r"[0-9a-f]{40,64}", frozen)
    ):
        return _abort_reject("identity_mismatch")
    baseline, error = _safe_external_json(args.baseline, logical, "baseline")
    if error:
        return None, error
    readiness, error = _safe_external_json(args.readiness, logical, "readiness")
    if error:
        return None, error
    if (
        baseline.get("schema") != "agent-clone-manifest/v2"
        or not isinstance(baseline.get("manifest_digest"), str)
        or baseline.get("manifest_digest") != _canonical_json_digest(baseline, "manifest_digest")
        or readiness.get("schema") != "clone-readiness/v2"
        or not isinstance(readiness.get("receipt_digest"), str)
        or readiness.get("receipt_digest") != _canonical_json_digest(readiness, "receipt_digest")
    ):
        return _abort_reject("artifact_digest_mismatch")
    if (
        baseline.get("agent_id") != args.agent_id
        or baseline.get("actor_id") != args.agent_id
        or baseline.get("delivery_attempt_id") != args.delivery_attempt_id
        or baseline.get("canonical_root") != str(logical)
        or baseline.get("root_head_sha") != frozen
        or baseline.get("branch") != branch
        or baseline.get("detached") is not False
        or readiness.get("agent_id") != args.agent_id
        or readiness.get("actor_id") != args.agent_id
        or readiness.get("delivery_attempt_id") != args.delivery_attempt_id
        or readiness.get("working_branch") != branch
        or readiness.get("root_head_sha") != frozen
        or identity.get("readiness_receipt_digest") != readiness.get("receipt_digest")
        or readiness.get("profile") != identity.get("profile")
        or readiness.get("status") != "degraded"
        or readiness.get("degraded_checks") != ["writer_admission"]
        or readiness.get("checks", {}).get("writer_admission", {}).get("status") != "degraded"
        or any(check.get("status") != "pass" for key, check in readiness.get("checks", {}).items() if key != "writer_admission" and check.get("required"))
    ):
        return _abort_reject("artifact_binding_mismatch")
    internal, error = _safe_external_json(
        str(git_dir / "agent-clone-readiness.json"), logical, "internal_readiness", must_be_external=False
    )
    if error or internal != readiness:
        return _abort_reject("internal_readiness_mismatch")
    fetch_url, error = _one_origin_url(physical)
    push_url, push_error = _one_origin_url(physical, push=True)
    if error or push_error or fetch_url != push_url or not _no_local_url_rewrites(physical):
        return _abort_reject("origin_mismatch")
    expected = args.expected_repository
    authority_urls = [identity.get("source_url"), baseline.get("origin_url"), readiness.get("source_url"), fetch_url]
    if any(not isinstance(value, str) or _exact_github_slug(value) != expected for value in authority_urls):
        return _abort_reject("repository_authority_mismatch")
    symbolic = _git_abort(physical, "symbolic-ref", "--short", "-q", "HEAD")
    head = _git_abort(physical, "rev-parse", "HEAD")
    if symbolic.returncode != 0 or symbolic.stdout.strip() != branch or head.returncode != 0 or head.stdout.strip() != frozen:
        return _abort_reject("head_or_branch_mismatch")
    if not _abort_worktree_clean(physical, independent_root=True):
        return _abort_reject("clone_not_clean_or_isolated")
    # HEAD's reflog includes the clone transport's pre-attempt checkout.  The
    # identity-bound private branch is the sole authority for attempt work.
    log = _git_abort(physical, "reflog", "show", "--format=%H", branch)
    if log.returncode != 0:
        return _abort_reject("reflog_unreadable")
    for sha in {line.strip() for line in log.stdout.splitlines() if line.strip()}:
        ancestral = _git_abort(physical, "merge-base", "--is-ancestor", sha, frozen)
        if ancestral.returncode != 0:
            return _abort_reject("reflog_contains_new_work")
    pinned = {}
    index = _git_abort(physical, "ls-files", "--stage")
    if index.returncode != 0:
        return _abort_reject("gitlinks_unreadable")
    for line in index.stdout.splitlines():
        if "\t" in line and line.startswith("160000 "):
            meta, path = line.split("\t", 1)
            pinned[path] = meta.split()[1]
    required_paths = identity.get("required_submodules") or []
    if sorted(required_paths) != sorted(readiness.get("initialized_submodules") or []):
        return _abort_reject("required_submodules_mismatch")
    children = []
    baseline_children = {entry.get("path"): entry for entry in baseline.get("repositories", []) if isinstance(entry, dict)}
    for entry in readiness.get("required_submodules") or []:
        path, pin = entry.get("path"), entry.get("pinned_sha")
        child = physical / str(path)
        baseline_child = baseline_children.get(path)
        if (
            path not in required_paths
            or pinned.get(path) != pin
            or entry.get("child_head") != pin
            or not entry.get("initialized")
            or not isinstance(baseline_child, dict)
            or baseline_child.get("pinned_sha") != pin
            or baseline_child.get("child_head") != pin
            or baseline_child.get("origin") != entry.get("origin")
        ):
            return _abort_reject("child_gitlink_mismatch")
        child_head = _git_abort(child, "rev-parse", "HEAD")
        child_origin, child_error = _one_origin_url(child)
        expected_origin = entry.get("expected_origin")
        if (
            child_head.returncode != 0
            or child_head.stdout.strip() != pin
            or child_error
            or child_origin != expected_origin
            or not _no_local_url_rewrites(child)
            or not _abort_worktree_clean(child, independent_root=False)
        ):
            return _abort_reject("child_state_mismatch")
        children.append({"path": path, "head": pin, "origin": child_origin})
    claims_root = Path(args.claims_root).expanduser().absolute()
    if _actor_has_activity(physical, args.agent_id, require_root=False) or _actor_has_activity(claims_root, args.agent_id, require_root=True):
        return _abort_reject("active_workflow_or_claim")
    remote_ref = f"refs/heads/{branch}"
    remote = _git_abort(physical, "ls-remote", "--exit-code", "--heads", "origin", remote_ref)
    if remote.returncode != 2 or remote.stdout.strip():
        return _abort_reject("attempt_branch_exists_or_remote_unreadable")
    prs = run(["gh", "pr", "list", "--repo", expected, "--head", branch, "--state", "all", "--json", "number,url,headRefName", "--limit", "100"], cwd=str(physical), env=_isolated_git_env())
    try:
        pr_payload = json.loads(prs.stdout or "[]")
    except json.JSONDecodeError:
        return _abort_reject("pr_query_invalid")
    if prs.returncode != 0 or pr_payload:
        return _abort_reject("attempt_pr_exists_or_query_failed")
    state = {
        "identity_digest": _canonical_json_digest(identity),
        "baseline_digest": baseline["manifest_digest"],
        "readiness_digest": readiness["receipt_digest"],
        "head": frozen,
        "branch": branch,
        "origin": fetch_url,
        "children": children,
        "tag_attribution": "unbound_not_gate",
    }
    return ({"state": state, "state_digest": _canonical_json_digest(state), "initial_stat": initial}, None)


def _authorization_payload(args: argparse.Namespace, dest: Path, state_digest: str) -> dict:
    receipt = {
        "schema": "clone-abort-authorization/v1",
        "status": "authorized",
        "actor_id": args.agent_id,
        "agent_id": args.agent_id,
        "delivery_attempt_id": args.delivery_attempt_id,
        "repository": args.expected_repository,
        "destination": str(dest),
        "state_digest": state_digest,
        "consistency": "double-read-non-atomic",
    }
    receipt["receipt_digest"] = _canonical_json_digest(receipt, "receipt_digest")
    return receipt


def _open_nofollow_directory_chain(abs_parent: Path) -> int:
    """Open an absolute directory by FD, rejecting every symlink component."""
    if not abs_parent.is_absolute():
        raise OSError("authorization parent must be absolute")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(abs_parent.anchor, flags)
    try:
        for component in abs_parent.parts[1:]:
            child_fd = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = child_fd
        return fd
    except Exception:
        os.close(fd)
        raise


def _same_nofollow_directory_chain(abs_parent: Path, original_fd: int) -> bool:
    """Re-open the named path and prove it remains the initial directory inode."""
    current_fd = -1
    try:
        current_fd = _open_nofollow_directory_chain(abs_parent)
        return os.path.samestat(os.fstat(original_fd), os.fstat(current_fd))
    except OSError:
        return False
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def _write_authorization(path_value: str, payload: dict, dest: Path) -> bool:
    path = Path(path_value).expanduser().absolute()
    if path == dest or dest in path.parents or path.is_symlink():
        return False
    # O_NOFOLLOW covers only the leaf.  Every extant parent must also be a
    # non-symlink and resolve outside the clone before an authorization can be
    # made durable there.
    parent = path.parent
    while True:
        try:
            parent_stat = parent.lstat()
            resolved_parent = parent.resolve(strict=True)
        except OSError:
            return False
        if stat.S_ISLNK(parent_stat.st_mode) or resolved_parent == dest or dest in resolved_parent.parents:
            return False
        if parent == parent.parent:
            break
        parent = parent.parent
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    parent_fd = -1
    created = False
    written_stat: os.stat_result | None = None
    try:
        parent_fd = _open_nofollow_directory_chain(path.parent)
        fd = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_fd,
        )
        created = True
    except FileExistsError:
        try:
            fd = os.open(path.name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
            with os.fdopen(fd, "r", encoding="utf-8") as handle:
                existing = json.load(handle)
            return (
                isinstance(existing, dict)
                and existing == payload
                and _same_nofollow_directory_chain(path.parent, parent_fd)
            )
        except (OSError, json.JSONDecodeError):
            return False
    except OSError:
        return False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
            written_stat = os.fstat(handle.fileno())
        os.fsync(parent_fd)
        if created and _same_nofollow_directory_chain(path.parent, parent_fd):
            return True
        # The FD can still refer to the directory where this invocation wrote.
        # Remove only the inode we created; never follow a raced replacement.
        try:
            current = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
            if written_stat is not None and os.path.samestat(current, written_stat):
                os.unlink(path.name, dir_fd=parent_fd)
                os.fsync(parent_fd)
        except OSError:
            pass
        return False
    except OSError:
        return False
    finally:
        if parent_fd >= 0:
            os.close(parent_fd)


def _absent_authorized(args: argparse.Namespace, dest: Path) -> bool:
    if not getattr(args, "evidence", None):
        return False
    receipt, error = _safe_external_json(args.evidence, dest, "authorization")
    return bool(
        error is None
        and receipt
        and receipt.get("schema") == "clone-abort-authorization/v1"
        and receipt.get("status") == "authorized"
        and receipt.get("actor_id") == args.agent_id
        and receipt.get("agent_id") == args.agent_id
        and receipt.get("delivery_attempt_id") == args.delivery_attempt_id
        and receipt.get("repository") == args.expected_repository
        and receipt.get("destination") == str(dest)
        and receipt.get("receipt_digest") == _canonical_json_digest(receipt, "receipt_digest")
    )


def cmd_abort_unready(args: argparse.Namespace) -> int:
    """Remove only a never-writer, degraded clone after a double-read authorization."""
    dest = Path(args.destination).expanduser().absolute()
    audit("abort_unready_start", f"dest={dest} actor={args.agent_id} attempt={args.delivery_attempt_id}")
    if not os.path.lexists(dest):
        if _absent_authorized(args, dest):
            print(json.dumps({"ok": True, "already_absent": str(dest), "authorized": True}))
            return EXIT_OK
        return reject("abort_unready", "absent_without_authorization", "destination is absent without exact authorization evidence")
    assessment, error = _abort_assessment(args, dest, dest)
    if error:
        return reject("abort_unready", error, "clone is not eligible for unready abort")
    result = {"ok": True, "dry_run": not args.apply, "destination": str(dest), "state_digest": assessment["state_digest"], "assessment": assessment["state"]}
    if not args.apply:
        print(json.dumps(result, sort_keys=True))
        return EXIT_OK
    if not args.evidence:
        return reject("abort_unready", "evidence_required", "--apply requires --evidence")
    authorization = _authorization_payload(args, dest, assessment["state_digest"])
    if not _write_authorization(args.evidence, authorization, dest):
        return reject("abort_unready", "authorization_write_failed", "cannot exclusively write matching authorization receipt")

    def second_read(payload: Path) -> bool:
        checked, second_error = _abort_assessment(args, payload, dest)
        return second_error is None and checked is not None and checked["state_digest"] == assessment["state_digest"]

    removed, detail = quarantine_remove_verified(dest, assessment["initial_stat"], assessment["state"]["head"], second_read)
    if not removed:
        return reject("abort_unready", "second_read_or_delete_failed", detail)
    print(json.dumps({"ok": True, "removed": str(dest), "state_digest": assessment["state_digest"], "authorization": str(Path(args.evidence).absolute())}, sort_keys=True))
    return EXIT_OK


def cmd_onboard(args: argparse.Namespace) -> int:
    """为新 agent 创建 clone + 生成基线 manifest."""
    agent_id = args.agent_id
    delivery_attempt_id = getattr(args, "delivery_attempt_id", None)
    if not delivery_attempt_id:
        timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        delivery_attempt_id = f"a{timestamp}-{secrets.token_hex(4)}"
    dest = Path(args.destination)
    artifact_stem = f"{agent_id}-{delivery_attempt_id}"
    manifest_path = (
        Path(args.manifest)
        if args.manifest
        else dest.parent / f"{artifact_stem}-baseline.json"
    )
    readiness_path = (
        Path(args.readiness)
        if getattr(args, "readiness", None)
        else dest.parent / f"{artifact_stem}-readiness.json"
    )
    provenance_path = (
        Path(args.provenance)
        if getattr(args, "provenance", None)
        else dest.parent / f"{artifact_stem}-provenance.json"
    )
    audit(
        "onboard_start",
        f"agent={agent_id} attempt={delivery_attempt_id} dest={dest}",
    )
    if os.path.lexists(manifest_path):
        return reject(
            "onboard",
            "manifest_collision",
            f"manifest output already exists: {manifest_path}",
        )
    if os.path.lexists(readiness_path):
        return reject(
            "onboard",
            "readiness_collision",
            f"readiness output already exists: {readiness_path}",
        )
    if os.path.lexists(provenance_path):
        return reject(
            "onboard",
            "provenance_collision",
            f"provenance output already exists: {provenance_path}",
        )
    if os.path.lexists(dest):
        return reject("onboard", "destination_collision", f"destination already exists: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    # 1. 创建 clone
    cmd = [
        sys.executable,
        str(AGENT_CLONE),
        "create",
        "--agent-id",
        agent_id,
        "--delivery-attempt-id",
        delivery_attempt_id,
        "--source",
        args.source,
        "--revision",
        args.revision,
        "--destination",
        str(dest),
    ]
    if getattr(args, "transport_source", None):
        cmd.extend(["--transport-source", args.transport_source])
    for mapping in getattr(args, "submodule_source", None) or []:
        cmd.extend(["--submodule-source", mapping])
    requested_submodules = list(getattr(args, "submodule", None) or [])
    requested_profile = getattr(args, "profile", None)
    effective_profile = requested_profile
    if getattr(args, "all_submodules", False):
        effective_profile = "full"
        cmd.extend(["--profile", "full"])
    elif requested_submodules:
        effective_profile = "custom"
        for submodule in requested_submodules:
            cmd.extend(["--submodule", submodule])
    else:
        effective_profile = requested_profile or "governance"
        cmd.extend(["--profile", effective_profile])
    r = run(cmd)
    if r.returncode != 0:
        audit("onboard_failed", f"clone_create rc={r.returncode} stderr={r.stderr.strip()[:200]}")
        print(r.stderr, file=sys.stderr)
        return EXIT_POLICY
    try:
        create_payload = json.loads(r.stdout)
    except json.JSONDecodeError:
        create_payload = {}
    provenance_payload: dict = {}
    if effective_profile in {"governance", "full"}:
        expected_repository = getattr(args, "expected_repository", None)
        if not expected_repository:
            origin = run(["git", "-C", str(dest), "remote", "get-url", "origin"])
            expected_repository = github_repo_slug(origin.stdout) if origin.returncode == 0 else None
        if not expected_repository:
            audit("onboard_failed", f"provenance authority unavailable recoverable_clone={dest}")
            return reject(
                "onboard",
                "repository_provenance_unbound",
                "named writer profile requires an explicit GitHub repository authority",
                recoverable_clone=str(dest),
            )
        cmd = [
            sys.executable,
            str(AGENT_CLONE),
            "provenance",
            "--clone",
            str(dest),
            "--expected-repository",
            expected_repository,
            "--output",
            str(provenance_path),
        ]
        r = run(cmd)
        if r.returncode != 0:
            audit("onboard_failed", f"provenance rc={r.returncode} recoverable_clone={dest}")
            print(r.stderr, file=sys.stderr)
            return EXIT_POLICY
        try:
            provenance_payload = json.loads(r.stdout)
        except json.JSONDecodeError:
            provenance_payload = {}
    # 2. 生成基线 manifest
    cmd = [
        sys.executable,
        str(AGENT_CLONE),
        "manifest",
        "--clone",
        str(dest),
        "--output",
        str(manifest_path),
    ]
    r = run(cmd)
    if r.returncode != 0:
        audit("onboard_failed", f"manifest rc={r.returncode} recoverable_clone={dest}")
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "manifest_failed",
                    "recoverable_clone": str(dest),
                    "manifest": str(manifest_path),
                    "next_safe_action": "rerun manifest with a new output path, then verify",
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return EXIT_POLICY
    # 3. 成功前必须验证刚生成的 manifest
    cmd = [
        sys.executable,
        str(AGENT_CLONE),
        "verify",
        "--clone",
        str(dest),
        "--manifest",
        str(manifest_path),
    ]
    r = run(cmd)
    if r.returncode != 0:
        audit("onboard_failed", f"verify rc={r.returncode} recoverable_clone={dest}")
        return EXIT_POLICY
    readiness_payload: dict = {}
    if effective_profile is not None:
        cmd = [
            sys.executable,
            str(AGENT_CLONE),
            "readiness",
            "--clone",
            str(dest),
            "--manifest",
            str(manifest_path),
            "--output",
            str(readiness_path),
        ]
        r = run(cmd)
        if r.returncode != 0:
            audit("onboard_failed", f"readiness rc={r.returncode} recoverable_clone={dest}")
            print(r.stderr, file=sys.stderr)
            return EXIT_POLICY
        try:
            readiness_payload = json.loads(r.stdout)
        except json.JSONDecodeError:
            readiness_payload = {}
    audit("onboard_ok", f"agent={agent_id} clone={dest} manifest={manifest_path}")
    print(
        json.dumps(
            {
                "ok": True,
                "agent_id": agent_id,
                "actor_id": agent_id,
                "delivery_attempt_id": delivery_attempt_id,
                "clone": str(dest),
                "manifest": str(manifest_path),
                "verification": "verified",
                "requested_revision": args.revision,
                "profile": effective_profile,
                "provenance": (
                    str(provenance_path)
                    if effective_profile in {"governance", "full"}
                    else None
                ),
                "provenance_status": provenance_payload.get("status"),
                "provenance_digest": provenance_payload.get("receipt_digest"),
                "readiness": str(readiness_path) if effective_profile is not None else None,
                "readiness_status": readiness_payload.get("status"),
                "readiness_digest": readiness_payload.get("receipt_digest"),
                "initialized_submodules": create_payload.get(
                    "initialized_submodules",
                    requested_submodules if not getattr(args, "all_submodules", False) else "all",
                ),
                "transport": create_payload.get("transport"),
            },
            indent=2,
        )
    )
    return EXIT_OK


def cmd_snapshot(args: argparse.Namespace) -> int:
    """为当前 clone 生成基线 manifest."""
    clone = Path(args.clone)
    output = Path(args.output)
    audit("snapshot_start", f"clone={clone}")
    cmd = [sys.executable, str(AGENT_CLONE), "manifest", "--clone", str(clone), "--output", str(output)]
    r = run(cmd)
    if r.returncode != 0:
        audit("snapshot_failed", f"rc={r.returncode}")
        print(r.stderr, file=sys.stderr)
        return EXIT_POLICY
    audit("snapshot_ok", f"clone={clone} output={output}")
    print(json.dumps({"ok": True, "manifest": str(output)}, indent=2))
    return EXIT_OK


def cmd_readiness(args: argparse.Namespace) -> int:
    """Resume or regenerate an identical readiness binding after interruption."""
    audit("readiness_start", f"clone={args.clone} manifest={args.manifest}")
    cmd = [
        sys.executable,
        str(AGENT_CLONE),
        "readiness",
        "--clone",
        str(args.clone),
        "--manifest",
        str(args.manifest),
        "--output",
        str(args.output),
    ]
    r = run(cmd)
    if r.returncode != 0:
        audit("readiness_failed", f"rc={r.returncode}")
        print(r.stderr, file=sys.stderr)
        return EXIT_POLICY
    audit("readiness_ok", f"clone={args.clone} output={args.output}")
    print(r.stdout, end="" if r.stdout.endswith("\n") else "\n")
    return EXIT_OK


def cmd_provenance(args: argparse.Namespace) -> int:
    """Resume or verify an identical repository/author provenance binding."""
    audit("provenance_start", f"clone={args.clone}")
    cmd = [
        sys.executable,
        str(AGENT_CLONE),
        "provenance",
        "--clone",
        str(args.clone),
        "--expected-repository",
        args.expected_repository,
        "--output",
        str(args.output),
    ]
    r = run(cmd)
    if r.returncode != 0:
        audit("provenance_failed", f"rc={r.returncode}")
        print(r.stderr, file=sys.stderr)
        return EXIT_POLICY
    audit("provenance_ok", f"clone={args.clone} output={args.output}")
    print(r.stdout, end="" if r.stdout.endswith("\n") else "\n")
    return EXIT_OK


def cmd_changeset(args: argparse.Namespace) -> int:
    """生成跨仓变更集 + claim 校验."""
    clone = Path(args.clone)
    baseline = Path(args.baseline)
    output = Path(args.output)
    audit("changeset_start", f"clone={clone} baseline={baseline}")
    cmd = [
        sys.executable,
        str(AGENT_CLONE),
        "changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline),
        "--output",
        str(output),
    ]
    if args.verify_claims:
        cmd.append("--verify-claims")
        claims_root = getattr(args, "claims_root", None)
        if claims_root:
            cmd.extend(["--claims-root", str(claims_root)])
    r = run(cmd)
    if r.returncode != 0:
        audit("changeset_failed", f"rc={r.returncode} stderr={r.stderr.strip()[:200]}")
        print(r.stderr, file=sys.stderr)
        if output.is_file():
            print(output.read_text(), file=sys.stderr)
        return EXIT_POLICY
    # 读取结果；请求 claim 校验时，缺失/禁用/不完整的收据不可推进。
    cs = json.loads(output.read_text())
    claim_verification = cs.get("claim_verification")
    if args.verify_claims and (
        not isinstance(claim_verification, dict)
        or claim_verification.get("enabled") is not True
        or claim_verification.get("all_covered") is not True
    ):
        audit("changeset_claim_verification_unavailable", "missing, disabled, or incomplete receipt")
        print(json.dumps(cs, indent=2), file=sys.stderr)
        return EXIT_POLICY
    violations = (claim_verification or {}).get("violations", [])
    if violations:
        audit("changeset_scope_creep", f"violations={violations}")
        print(json.dumps(cs, indent=2))
        return EXIT_POLICY
    audit(
        "changeset_ok",
        f"change_id={cs.get('change_id', '?')[:12]} changes={len(cs.get('changes', []))}",
    )
    print(json.dumps(cs, indent=2))
    return EXIT_OK


def cmd_integrate(args: argparse.Namespace) -> int:
    """推送分支 + 创建 PR (dry-run 默认)."""
    clone = Path(args.clone)
    agent_id = args.agent_id
    requested_attempt = getattr(args, "delivery_attempt_id", None)
    branch = (
        f"agent/{agent_id}--{requested_attempt}"
        if requested_attempt
        else f"agent/{agent_id}"
    )
    audit("integrate_start", f"agent={agent_id} branch={branch}")
    if clone.is_symlink() or not (clone / ".git").is_dir():
        return reject(
            "integrate",
            "independent_clone_required",
            "real integration requires an independent clone with a local .git directory",
        )
    common = run(["git", "-C", str(clone), "rev-parse", "--path-format=absolute", "--git-common-dir"])
    if common.returncode != 0 or Path(common.stdout.strip()).resolve() != (clone / ".git").resolve():
        return reject("integrate", "independent_clone_required", "git common dir is not clone-local")
    try:
        identity = json.loads((clone / ".git" / "agent-clone-identity.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return reject("integrate", "identity_unreadable", str(exc))
    if (
        identity.get("schema") != "agent-clone-identity/v2"
        or identity.get("ready") is not True
        or identity.get("canonical_root") != str(clone.resolve())
        or identity.get("agent_id") != agent_id
    ):
        return reject("integrate", "identity_mismatch", "clone identity does not match integration request")
    identity_attempt = identity.get("delivery_attempt_id")
    if (
        identity.get("actor_id") != agent_id
        or not identity_attempt
        or requested_attempt != identity_attempt
    ):
        return reject(
            "integrate",
            "delivery_attempt_mismatch",
            "requested actor/attempt does not match clone identity",
        )
    branch = identity.get("working_branch", "")
    if args.dry_run:
        audit("integrate_dry_run", f"would publish new {branch} and create PR")
        print(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": True,
                    "branch": branch,
                    "actor_id": agent_id,
                    "delivery_attempt_id": identity_attempt,
                }
            )
        )
        return EXIT_OK
    baseline = getattr(args, "baseline", None)
    changeset = getattr(args, "changeset", None)
    claims_root = getattr(args, "claims_root", None)
    if not baseline or not changeset or not claims_root:
        return reject(
            "integrate",
            "verified_changeset_required",
            "--apply requires --baseline, --claims-root, and a current --verify-claims changeset",
        )
    branch_probe = run(["git", "-C", str(clone), "branch", "--show-current"])
    if branch_probe.returncode != 0 or branch_probe.stdout.strip() != branch:
        return reject(
            "integrate",
            "branch_mismatch",
            f"current branch {branch_probe.stdout.strip()!r} != {branch!r}",
        )
    status = run(["git", "-C", str(clone), "status", "--porcelain", "--ignore-submodules=none"])
    if status.returncode != 0 or status.stdout.strip():
        return reject("integrate", "clone_dirty", "clone must be clean before integration")
    verify_cmd = [
        sys.executable,
        str(AGENT_CLONE),
        "verify-changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline),
        "--changeset",
        str(changeset),
        "--agent-id",
        agent_id,
        "--claims-root",
        str(claims_root),
        "--json",
    ]
    if identity_attempt:
        verify_cmd.extend(["--delivery-attempt-id", identity_attempt])
    verified = run(verify_cmd)
    if verified.returncode != 0:
        return reject(
            "integrate",
            "changeset_verification_failed",
            verified.stdout.strip() or verified.stderr.strip() or "changeset verification failed",
        )
    try:
        verification = json.loads(verified.stdout)
    except json.JSONDecodeError:
        return reject("integrate", "changeset_verification_invalid", "verifier returned invalid JSON")
    if verification.get("no_change") is True or not verification.get("changed_paths"):
        return reject("integrate", "changeset_empty", "integration requires at least one verified changed path")
    head_probe = run(["git", "-C", str(clone), "rev-parse", "HEAD"])
    if head_probe.returncode != 0:
        return reject("integrate", "head_unreadable", "cannot resolve clone HEAD")
    head_sha = head_probe.stdout.strip()
    if head_sha != verification.get("root_head_sha"):
        return reject("integrate", "changeset_head_raced", "clone HEAD changed after changeset verification")
    repo_slug, provenance_error = bound_repository_slug(clone, identity)
    if repo_slug is None:
        return reject(
            "integrate",
            "github_repository_unbound",
            provenance_error or "repository provenance is unavailable",
        )
    owner = repo_slug.split("/", 1)[0]
    final_verification = run(verify_cmd)
    if final_verification.returncode != 0:
        return reject(
            "integrate",
            "claims_changed_before_push",
            final_verification.stdout.strip()
            or final_verification.stderr.strip()
            or "claims changed before push",
        )
    # 推送分支
    r = run(
        [
            "git",
            "-C",
            str(clone),
            "push",
            "--porcelain",
            f"--force-with-lease=refs/heads/{branch}:",
            "origin",
            f"{head_sha}:refs/heads/{branch}",
        ]
    )
    if r.returncode != 0:
        audit("integrate_failed", f"push rc={r.returncode}")
        return EXIT_POLICY
    new_branch_marker = f":refs/heads/{branch}\t[new branch]"
    if not any(
        line.startswith("*\t") and line.endswith(new_branch_marker)
        for line in r.stdout.splitlines()
    ):
        return reject(
            "integrate",
            "delivery_attempt_reused",
            "remote attempt ref was not newly created by this integration",
        )
    base = getattr(args, "base", "main")
    existing = run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo_slug,
            "--head",
            branch,
            "--base",
            base,
            "--state",
            "open",
            "--json",
            "url,headRefName,headRefOid,headRepositoryOwner",
            "--limit",
            "1",
        ],
        cwd=str(clone),
    )
    if existing.returncode != 0:
        return reject("integrate", "pr_query_failed", existing.stderr.strip() or "gh pr list failed")
    try:
        prs = json.loads(existing.stdout or "[]")
    except json.JSONDecodeError:
        return reject("integrate", "pr_query_invalid", "gh pr list returned invalid JSON")
    matching_prs = [
        pr
        for pr in prs
        if pr.get("headRefName") == branch
        and (pr.get("headRepositoryOwner") or {}).get("login") == owner
        and pr.get("headRefOid") == head_sha
    ]
    if prs and not matching_prs:
        return reject(
            "integrate",
            "pr_identity_mismatch",
            "open PR candidates do not match exact repository owner, branch, and verified HEAD",
        )
    if matching_prs:
        pr_url = matching_prs[0].get("url", "")
    else:
        created = run(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                repo_slug,
                "--base",
                base,
                "--head",
                f"{owner}:{branch}",
                "--title",
                f"fix(gac): deliver {agent_id} attempt {identity_attempt or 'legacy'}",
                "--body",
                "Automated independent-clone lifecycle integration.",
            ],
            cwd=str(clone),
        )
        if created.returncode != 0 or not created.stdout.strip():
            return reject("integrate", "pr_create_failed", created.stderr.strip() or "gh pr create failed")
        pr_url = created.stdout.strip()
    audit("integrate_ok", f"pushed {branch} pr={pr_url}")
    result = {
        "ok": True,
        "branch": branch,
        "head_sha": head_sha,
        "change_id": verification["change_id"],
        "repository": repo_slug,
        "pushed": True,
        "pr_url": pr_url,
    }
    if identity_attempt:
        result.update(
            {
                "actor_id": identity["actor_id"],
                "delivery_attempt_id": identity_attempt,
            }
        )
    print(json.dumps(result))
    return EXIT_OK


PLATFORM_PR_FIELDS = {
    "base_ref_name",
    "base_ref_oid",
    "branch",
    "head_ref_oid",
    "merge_commit_oid",
    "number",
    "owner",
    "repository",
    "state",
    "url",
}


def query_platform_rebased_pr(repo_slug: str, pr_number: int) -> tuple[dict | None, str | None]:
    """Read one exact PR through a scalar, strict-schema GitHub projection."""
    query = run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--repo",
            repo_slug,
            "--json",
            "number,url,state,baseRefName,baseRefOid,headRefOid,headRefName,headRepository,headRepositoryOwner,mergeCommit",
            "--jq",
            (
                "{number:.number,url:.url,state:.state,base_ref_name:.baseRefName,"
                "base_ref_oid:.baseRefOid,head_ref_oid:.headRefOid,branch:.headRefName,"
                "repository:.headRepository.nameWithOwner,owner:.headRepositoryOwner.login,"
                "merge_commit_oid:.mergeCommit.oid}"
            ),
        ]
    )
    if query.returncode != 0:
        return None, query.stderr.strip() or "gh pr view failed"
    try:
        payload = json.loads(query.stdout)
    except json.JSONDecodeError as exc:
        return None, f"gh pr view returned invalid JSON: {exc}"
    if not isinstance(payload, dict) or set(payload) != PLATFORM_PR_FIELDS:
        return None, "gh pr view returned a missing or extra field"
    scalar_string_fields = PLATFORM_PR_FIELDS - {"number"}
    if (
        isinstance(payload["number"], bool)
        or not isinstance(payload["number"], int)
        or any(not isinstance(payload[field], str) or not payload[field] for field in scalar_string_fields)
        or not re.fullmatch(r"[0-9a-f]{40}", payload["base_ref_oid"])
        or not re.fullmatch(r"[0-9a-f]{40}", payload["head_ref_oid"])
        or not re.fullmatch(r"[0-9a-f]{40}", payload.get("merge_commit_oid") or "")
    ):
        return None, "gh pr view returned invalid field types or values"
    return payload, None


def build_platform_rebased_source_proof(
    clone: Path,
    repo_slug: str,
    branch: str,
    original_head: str,
    pr: dict,
) -> tuple[dict | None, str | None, str | None]:
    """Prove that GitHub's rewritten PR head has exactly the original delivery tree."""
    platform_head = pr["head_ref_oid"]
    platform_base = pr["base_ref_oid"]
    for label, sha in (("head", platform_head), ("base", platform_base)):
        present = run(["git", "-C", str(clone), "cat-file", "-e", f"{sha}^{{commit}}"])
        if present.returncode != 0:
            return None, "platform_object_missing", f"platform {label} commit is not in the local object database"

    merge_base = run(["git", "-C", str(clone), "merge-base", original_head, platform_base])
    original_base = merge_base.stdout.strip()
    if merge_base.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", original_base):
        return None, "platform_original_base_unavailable", "cannot resolve original delivery base"

    patch = run(
        [
            "git",
            "-C",
            str(clone),
            "diff",
            "--binary",
            "--full-index",
            original_base,
            original_head,
            "--",
        ]
    )
    if patch.returncode != 0:
        return None, "platform_patch_unavailable", patch.stderr.strip() or "cannot create full-index patch"
    changed = run(
        [
            "git",
            "-C",
            str(clone),
            "diff",
            "--name-only",
            "-z",
            original_base,
            original_head,
            "--",
        ]
    )
    if changed.returncode != 0:
        return None, "platform_patch_unavailable", changed.stderr.strip() or "cannot enumerate changed paths"
    changed_paths = [path for path in changed.stdout.split("\0") if path]

    with tempfile.TemporaryDirectory(prefix="clone-platform-rebase-proof-") as temp_dir:
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(Path(temp_dir) / "index")
        read_tree = run(["git", "-C", str(clone), "read-tree", platform_base], env=env)
        if read_tree.returncode != 0:
            return None, "platform_patch_apply_failed", read_tree.stderr.strip() or "cannot seed temporary index"
        applied = run(
            ["git", "-C", str(clone), "apply", "--cached", "--binary", "--index", "-"],
            env=env,
            input=patch.stdout,
        )
        if applied.returncode != 0:
            return None, "platform_patch_apply_failed", applied.stderr.strip() or "cannot apply original delivery patch"
        written = run(["git", "-C", str(clone), "write-tree"], env=env)
        if written.returncode != 0:
            return None, "platform_patch_apply_failed", written.stderr.strip() or "cannot write proof tree"
        reproduced_tree = written.stdout.strip()

    platform_tree_probe = run(["git", "-C", str(clone), "rev-parse", f"{platform_head}^{{tree}}"])
    platform_tree = platform_tree_probe.stdout.strip()
    if platform_tree_probe.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", platform_tree):
        return None, "platform_object_missing", "cannot resolve platform head tree"
    if reproduced_tree != platform_tree:
        return None, "platform_tree_mismatch", "original delivery patch does not reproduce platform head tree"

    proof = {
        "schema": "platform-rebased-source-proof/v1",
        "repository": repo_slug,
        "pr_number": pr["number"],
        "pr_url": pr["url"],
        "branch": branch,
        "original_head_sha": original_head,
        "platform_head_sha": platform_head,
        "platform_base_sha": platform_base,
        "original_base_sha": original_base,
        "platform_tree_sha": platform_tree,
        "changed_paths": changed_paths,
        "changed_paths_digest": hashlib.sha256(
            ("\n".join(changed_paths) + ("\n" if changed_paths else "")).encode("utf-8")
        ).hexdigest(),
    }
    proof["receipt_digest"] = _canonical_json_digest(proof)
    return proof, None, None


# T1-02 squash-successor 退场 receipt schema 常量
_SQUASH_PROOF_SCHEMA = "clone-squash-successor-retirement-proof/v1"
_SQUASH_DELETE_INTENT_SCHEMA = "clone-squash-successor-retirement-delete-intent/v1"
_SQUASH_SETTLEMENT_SCHEMA = "clone-squash-successor-retirement-settlement/v1"


def _persist_receipt_atomically(path: Path, payload: dict) -> tuple[bool, str | None]:
    """原子写入 receipt 文件: O_CREAT|O_EXCL|O_NOFOLLOW + fsync。"""
    payload_bytes = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    parent = path.resolve().parent
    for p in [parent] + list(parent.parents):
        if p.is_symlink():
            return False, f"parent chain contains symlink: {p}"
        if p == Path("/"):
            break
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY, 0o644)
    except FileExistsError:
        try:
            existing = path.read_bytes()
            if existing == payload_bytes:
                return True, None
            return False, f"receipt already exists with different content: {path}"
        except OSError as e:
            return False, f"cannot read existing receipt: {e}"
    except OSError as e:
        return False, f"cannot create receipt: {e}"
    try:
        os.write(fd, payload_bytes)
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        dir_fd = os.open(parent, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass
    return True, None


def _read_external_receipt(path: Path) -> tuple[dict | None, str | None]:
    """安全读取外部 receipt 文件。"""
    if not path.is_file():
        return None, None
    if path.is_symlink():
        return None, f"receipt is symlink: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return None, f"cannot read receipt: {e}"
    return data, None


def _verify_source_tag(dest: Path, tag_name: str, source_head: str) -> tuple[dict | None, str | None]:
    """P4: exact annotated source tag。"""
    tag_ref = run(["git", "-C", str(dest), "rev-parse", f"refs/tags/{tag_name}^{{tag}}"])
    if tag_ref.returncode != 0:
        return None, f"tag {tag_name} is not an annotated tag object"
    tag_obj = tag_ref.stdout.strip()
    peeled = run(["git", "-C", str(dest), "rev-parse", f"refs/tags/{tag_name}^{{commit}}"])
    if peeled.returncode != 0 or peeled.stdout.strip() != source_head:
        return None, f"tag {tag_name} peeled to {peeled.stdout.strip()}, expected {source_head}"
    remote_tag = run(["git", "-C", str(dest), "ls-remote", "--exit-code", "--tags",
                       "origin", f"refs/tags/{tag_name}"])
    if remote_tag.returncode != 0:
        return None, f"remote tag {tag_name} not found"
    remote_lines = remote_tag.stdout.strip().splitlines()
    if len(remote_lines) < 1:
        return None, f"remote tag {tag_name} not found"
    remote_tag_obj = remote_lines[0].split()[0]
    if remote_tag_obj != tag_obj:
        return None, f"remote tag object {remote_tag_obj} != local {tag_obj}"
    return {"tag_object": tag_obj, "peeled_commit": peeled.stdout.strip()}, None


def _verify_delivery_base(dest: Path, source_head: str, pr_base: str,
                          delivery_base: str, frozen_root: str) -> tuple[bool, str | None]:
    """P5: explicit delivery base。"""
    mb = run(["git", "-C", str(dest), "merge-base", source_head, pr_base])
    if mb.returncode != 0:
        return False, "merge-base failed"
    if mb.stdout.strip() != delivery_base:
        return False, f"merge-base = {mb.stdout.strip()}, expected {delivery_base}"
    anc = run(["git", "-C", str(dest), "merge-base", "--is-ancestor", frozen_root, delivery_base])
    if anc.returncode != 0:
        return False, "frozen_root is not ancestor of delivery_base"
    anc2 = run(["git", "-C", str(dest), "merge-base", "--is-ancestor", delivery_base, pr_base])
    if anc2.returncode != 0:
        return False, "delivery_base is not ancestor of pr_base"
    rng = run(["git", "-C", str(dest), "rev-list", "--count", f"{delivery_base}..{source_head}"])
    if rng.returncode != 0 or int(rng.stdout.strip()) == 0:
        return False, "delivery_base..source_head is empty"
    return True, None


def _verify_squash_topology(dest: Path, merge_commit: str, pr_base: str,
                            source_head: str) -> tuple[bool, str | None]:
    """P7: one-parent squash topology。"""
    cat = run(["git", "-C", str(dest), "cat-file", "-t", merge_commit])
    if cat.returncode != 0 or cat.stdout.strip() != "commit":
        return False, f"merge commit {merge_commit[:12]} not found"
    parents = run(["git", "-C", str(dest), "rev-parse", f"{merge_commit}^@"])
    if parents.returncode != 0:
        return False, "cannot read merge commit parents"
    parent_list = parents.stdout.strip().splitlines()
    if len(parent_list) != 1:
        return False, f"merge commit has {len(parent_list)} parents, expected 1"
    if parent_list[0] != pr_base:
        return False, f"merge parent {parent_list[0][:12]} != PR base {pr_base[:12]}"
    return True, None


def _verify_patch_tree_equiv(dest: Path, delivery_base: str, source_head: str,
                             merge_commit: str) -> tuple[dict | None, str | None]:
    """P8: patch-to-tree equivalence。

    验证 delivery_base..source_head 的 patch 应用到 PR base tree 后
    是否等于 squash merge tree。
    """
    # 获取 PR base tree (merge commit 的 parent tree)
    pr_base_tree = run(["git", "-C", str(dest), "rev-parse", f"{merge_commit}^{{tree}}"])
    if pr_base_tree.returncode != 0:
        return None, "cannot resolve merge tree"
    merge_tree_sha = pr_base_tree.stdout.strip()

    # 获取 PR base 的 tree (parent of merge commit)
    parent_ref = run(["git", "-C", str(dest), "rev-parse", f"{merge_commit}^"])
    if parent_ref.returncode != 0:
        return None, "cannot resolve merge parent"
    parent_tree = run(["git", "-C", str(dest), "rev-parse", f"{parent_ref.stdout.strip()}^{{tree}}"])
    if parent_tree.returncode != 0:
        return None, "cannot resolve parent tree"
    parent_tree_sha = parent_tree.stdout.strip()

    # 生成 delivery patch
    patch = run(["git", "-C", str(dest), "diff", "--binary", "--full-index",
                 f"{delivery_base}..{source_head}"])
    if patch.returncode != 0:
        return None, "failed to generate delivery patch"
    if not patch.stdout.strip():
        return None, "delivery patch is empty"

    # changed-path 列表
    paths = run(["git", "-C", str(dest), "diff", "--name-only",
                 f"{delivery_base}..{source_head}"])
    if paths.returncode != 0:
        return None, "failed to enumerate changed paths"
    changed_paths = [p for p in paths.stdout.strip().splitlines() if p.strip()]
    if not changed_paths:
        return None, "no changed paths"

    # 在 temp index 上: seed from parent tree, apply patch, write tree
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_index = Path(tmpdir) / "index"
        env = {**os.environ, "GIT_INDEX_FILE": str(tmp_index)}
        r = run(["git", "-C", str(dest), "read-tree", parent_tree_sha], env=env)
        if r.returncode != 0:
            return None, f"failed to seed temp index: {r.stderr}"
        proc = subprocess.run(
            ["git", "-C", str(dest), "apply", "--binary", "--cached"],
            input=patch.stdout, capture_output=True, text=True, env=env
        )
        if proc.returncode != 0:
            return None, f"patch apply failed: {proc.stderr}"
        written = run(["git", "-C", str(dest), "write-tree"], env=env)
        if written.returncode != 0:
            return None, "failed to write reproduced tree"
        reproduced_tree = written.stdout.strip()

    digest = hashlib.sha256(patch.stdout.encode("utf-8")).hexdigest()
    return {"changed_path_count": len(changed_paths),
            "patch_digest": f"sha256:{digest}",
            "reproduced_tree": reproduced_tree,
            "merge_tree": merge_tree_sha,
            "tree_match": reproduced_tree == merge_tree_sha}, None


def _verify_current_main(dest: Path, merge_commit: str) -> tuple[str | None, str | None]:
    """P9: current remote main。"""
    main_ref = run(["git", "-C", str(dest), "rev-parse", "origin/main"])
    if main_ref.returncode != 0:
        return None, "cannot resolve origin/main"
    main_sha = main_ref.stdout.strip()
    anc = run(["git", "-C", str(dest), "merge-base", "--is-ancestor", merge_commit, main_sha])
    if anc.returncode != 0:
        return None, "merge commit is not ancestor of origin/main"
    main_ref2 = run(["git", "-C", str(dest), "rev-parse", "origin/main"])
    if main_ref2.returncode != 0 or main_ref2.stdout.strip() != main_sha:
        return None, "origin/main changed during verification (race)"
    return main_sha, None


def _retire_squash_successor(args: argparse.Namespace, dest: Path,
                              squash_pr: int, squash_tag: str,
                              squash_base: str, evidence_path: Path) -> int:
    """T1-02 squash-successor 退场 mode: P1-P11 proof + receipt 链 + fail-closed 退场。"""
    resolved = dest.resolve()

    # 幂等已缺席处理
    if not os.path.lexists(dest):
        return _retire_squash_replay_absent(dest, resolved, squash_pr, squash_tag,
                                             squash_base, evidence_path)

    # P1: clone identity / local state
    if not dest.is_dir() or dest.is_symlink():
        return reject("retire", "invalid_destination", f"invalid destination: {dest}")
    git_dir = dest / ".git"
    if not git_dir.is_dir():
        return reject("retire", "independent_clone_required", f"independent clone required: {dest}")
    common = run(["git", "-C", str(dest), "rev-parse", "--path-format=absolute", "--git-common-dir"])
    if common.returncode != 0 or Path(common.stdout.strip()).resolve() != git_dir.resolve():
        return reject("retire", "linked_worktree", "git common dir is not clone-local")
    identity_path = git_dir / "agent-clone-identity.json"
    try:
        identity = json.loads(identity_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        return reject("retire", "identity_unreadable", str(e))
    if identity.get("ready") is not True or identity.get("canonical_root") != str(resolved):
        return reject("retire", "identity_mismatch", "identity does not match destination")
    frozen_root = identity.get("frozen_root_sha")
    branch = identity.get("working_branch")
    head_sha = run(["git", "-C", str(dest), "rev-parse", "HEAD"]).stdout.strip()
    status = run(["git", "-C", str(dest), "status", "--porcelain", "--ignore-submodules=none"])
    if status.returncode != 0 or status.stdout.strip():
        return reject("retire", "clone_dirty", "clone is dirty")
    locks, active_runs, state_errors = workflow_activity(dest)
    if locks or active_runs or state_errors:
        return reject("retire", "active_lease_or_lock", "workflow locks present")

    # P2: repository / origin
    # Squash successors have no PR base in the source branch ancestry.  Resolve
    # the live origin for the PR lookup first; P6 below re-enters the
    # provenance guard with the exact PR base and source head.
    repo_slug, prov_error = live_origin_repository_slug(dest)
    if repo_slug is None:
        return reject("retire", "github_repository_unbound", prov_error or "repository unbound")
    owner = repo_slug.split("/", 1)[0]

    # P3: exact merged PR
    pr = query_platform_rebased_pr(repo_slug, squash_pr)
    if pr[0] is None:
        return reject("retire", "squash_pr_invalid", pr[1] or "PR query failed")
    pr = pr[0]
    if pr.get("state") != "MERGED":
        return reject("retire", "squash_pr_not_merged", f"PR state={pr.get('state')}")
    if pr.get("base_ref_name") != "main" or pr.get("repository") != repo_slug:
        return reject("retire", "squash_pr_identity_mismatch", "PR identity mismatch")
    if pr.get("head_ref_oid") != head_sha or pr.get("branch") != branch:
        return reject("retire", "squash_pr_head_mismatch", "PR head mismatch")

    # P4: annotated source tag
    tag_info, tag_error = _verify_source_tag(dest, squash_tag, head_sha)
    if tag_info is None:
        return reject("retire", "squash_tag_invalid", tag_error or "tag verification failed")

    # P5: explicit delivery base
    ok, base_error = _verify_delivery_base(dest, head_sha, pr["base_ref_oid"], squash_base, frozen_root)
    if not ok:
        return reject("retire", "squash_delivery_base_invalid", base_error or "delivery base invalid")

    # P6: delivery-only author/committer identity
    guarded, guard_error = run_provenance_guard(dest, identity,
                                                 platform_base=squash_base, platform_head=head_sha)
    if not guarded:
        return reject("retire", "clone_provenance_mismatch", guard_error or "provenance guard failed")

    # P7: one-parent squash topology
    merge_commit = pr["merge_commit_oid"]
    ok, topo_error = _verify_squash_topology(dest, merge_commit, pr["base_ref_oid"], head_sha)
    if not ok:
        return reject("retire", "squash_topology_invalid", topo_error or "topology invalid")

    # P8: patch-to-tree equivalence
    tree_info, tree_error = _verify_patch_tree_equiv(dest, squash_base, head_sha, merge_commit)
    if tree_info is None:
        return reject("retire", "squash_tree_mismatch", tree_error or"tree mismatch")
    if not tree_info["tree_match"]:
        return reject("retire", "squash_tree_mismatch",
                      f"source_tree={tree_info['source_tree'][:12]} != merge_tree={tree_info['merge_tree'][:12]}")

    # P9: current remote main
    main_sha, main_error = _verify_current_main(dest, merge_commit)
    if main_sha is None:
        return reject("retire", "squash_main_invalid", main_error or"main invalid")

    # P10: surviving source branch
    remote_ref = f"refs/heads/{branch}"
    remote = run(["git", "-C", str(dest), "ls-remote", "--exit-code", "--heads", "origin", remote_ref])
    remote_lines = [line.split() for line in remote.stdout.splitlines() if line.strip()]
    if remote.returncode == 0 and (len(remote_lines) != 1 or remote_lines[0][0] != head_sha):
        return reject("retire", "squash_remote_branch_contradiction", "remote branch contradicts HEAD")

    # P11: external receipt chain — proof
    merge_tree_sha = run(["git", "-C", str(dest), "rev-parse", f"{merge_commit}^{{tree}}"]).stdout.strip()
    proof_payload = {
        "schema": _SQUASH_PROOF_SCHEMA,
        "canonical_repository": repo_slug,
        "pr_number": squash_pr,
        "branch": branch,
        "owner": owner,
        "destination": str(resolved),
        "frozen_root": frozen_root,
        "delivery_base": squash_base,
        "source_head": head_sha,
        "tag_name": squash_tag,
        "tag_object": tag_info["tag_object"],
        "peeled_tag_target": tag_info["peeled_commit"],
        "pr_base": pr["base_ref_oid"],
        "squash_commit": merge_commit,
        "squash_parent": pr["base_ref_oid"],
        "squash_tree": merge_tree_sha,
        "current_main": main_sha,
        "changed_path_count": tree_info["changed_path_count"],
        "patch_digest": tree_info["patch_digest"],
        "actor": identity.get("actor_id", ""),
        "delivery_attempt_id": identity.get("delivery_attempt_id", ""),
        "status": "verified_for_retirement",
    }
    proof_payload["receipt_digest"] = _canonical_json_digest(proof_payload)
    ok, proof_error = _persist_receipt_atomically(evidence_path, proof_payload)
    if not ok:
        return reject("retire", "squash_proof_persist_failed", proof_error or"proof persist failed")

    # Quarantine + deletion
    initial_stat = dest.lstat()
    removed, removal_detail = quarantine_remove_verified(dest, initial_stat, head_sha)
    if not removed:
        return reject("retire", "destination_raced", removal_detail)

    # delete-intent
    di_path = Path(f"{evidence_path}.delete-intent")
    di_payload = {
        "schema": _SQUASH_DELETE_INTENT_SCHEMA,
        "proof_digest": proof_payload["receipt_digest"],
        "destination": str(resolved),
        "repository": repo_slug,
        "actor": identity.get("actor_id", ""),
        "delivery_attempt_id": identity.get("delivery_attempt_id", ""),
        "pr_number": squash_pr,
        "merge_commit": merge_commit,
        "source_head": head_sha,
        "status": "delete_authorized",
    }
    di_payload["receipt_digest"] = _canonical_json_digest(di_payload)
    ok, di_error = _persist_receipt_atomically(di_path, di_payload)
    if not ok:
        return reject("retire", "squash_delete_intent_failed", di_error or"delete-intent failed")

    # settlement
    st_path = Path(f"{evidence_path}.settled")
    st_payload = {
        "schema": _SQUASH_SETTLEMENT_SCHEMA,
        "proof_digest": proof_payload["receipt_digest"],
        "delete_intent_digest": di_payload["receipt_digest"],
        "destination": str(resolved),
        "repository": repo_slug,
        "actor": identity.get("actor_id", ""),
        "delivery_attempt_id": identity.get("delivery_attempt_id", ""),
        "pr_number": squash_pr,
        "merge_commit": merge_commit,
        "source_head": head_sha,
        "status": "retired",
    }
    st_payload["receipt_digest"] = _canonical_json_digest(st_payload)
    ok, st_error = _persist_receipt_atomically(st_path, st_payload)
    if not ok:
        audit("retire_settlement_pending", f"settlement failed: {st_error}")
        print(json.dumps({"ok": False, "status": "settlement_pending",
                          "settlement_path": str(st_path), "error": st_error}))
        return EXIT_POLICY

    audit("retire_ok", f"squash-successor retired {dest}")
    print(json.dumps({"ok": True, "removed": str(dest), "head_sha": head_sha,
                      "merged_pr": pr.get("url", ""), "pr_number": squash_pr,
                      "evidence": str(evidence_path), "settlement": str(st_path)}))
    return EXIT_OK


def _retire_squash_replay_absent(dest: Path, resolved: Path, squash_pr: int,
                                  squash_tag: str, squash_base: str,
                                  evidence_path: Path) -> int:
    """幂等已缺席处理: 检查 receipt 链状态并恢复/确认。"""
    proof, _ = _read_external_receipt(evidence_path)
    di_path = Path(f"{evidence_path}.delete-intent")
    delete_intent, _ = _read_external_receipt(di_path)
    st_path = Path(f"{evidence_path}.settled")
    settlement, _ = _read_external_receipt(st_path)

    # Case 1: settled → 已完整退场
    if (proof and delete_intent and settlement
            and proof.get("schema") == _SQUASH_PROOF_SCHEMA
            and delete_intent.get("schema") == _SQUASH_DELETE_INTENT_SCHEMA
            and settlement.get("schema") == _SQUASH_SETTLEMENT_SCHEMA
            and delete_intent.get("proof_digest") == proof.get("receipt_digest")
            and settlement.get("proof_digest") == proof.get("receipt_digest")
            and settlement.get("delete_intent_digest") == delete_intent.get("receipt_digest")
            and proof.get("pr_number") == squash_pr
            and proof.get("delivery_base") == squash_base
            and proof.get("destination") == str(resolved)):
        audit("retire_ok", f"squash already retired (settled): {dest}")
        return EXIT_OK

    # Case 2: crash after delete, before settlement → 写 settlement
    if (proof and delete_intent and not settlement
            and proof.get("schema") == _SQUASH_PROOF_SCHEMA
            and delete_intent.get("schema") == _SQUASH_DELETE_INTENT_SCHEMA
            and delete_intent.get("proof_digest") == proof.get("receipt_digest")):
        st_payload = {
            "schema": _SQUASH_SETTLEMENT_SCHEMA,
            "proof_digest": proof["receipt_digest"],
            "delete_intent_digest": delete_intent["receipt_digest"],
            "destination": str(resolved),
            "repository": proof.get("canonical_repository", ""),
            "actor": proof.get("actor", ""),
            "delivery_attempt_id": proof.get("delivery_attempt_id", ""),
            "pr_number": proof.get("pr_number", squash_pr),
            "merge_commit": proof.get("squash_commit", ""),
            "source_head": proof.get("source_head", ""),
            "status": "retired",
        }
        st_payload["receipt_digest"] = _canonical_json_digest(st_payload)
        ok, st_error = _persist_receipt_atomically(st_path, st_payload)
        if not ok:
            audit("retire_settlement_pending", f"replay settlement failed: {st_error}")
            return EXIT_POLICY
        audit("retire_ok", f"squash settlement replay: {dest}")
        return EXIT_OK

    return reject("retire", "squash_replay_unsettled",
                  "destination absent but receipt chain incomplete or mismatched")

def cmd_retire(args: argparse.Namespace) -> int:
    """清理 clone + 释放资源."""
    raw_dest = Path(args.destination).expanduser().absolute()
    dest = raw_dest
    audit("retire_start", f"dest={dest}")

    # T1-02 squash-successor 退场: 参数校验（必须在 already_absent 之前）
    squash_pr = getattr(args, "squash_merged_pr", None)
    squash_tag = getattr(args, "source_tag", None)
    squash_base = getattr(args, "delivery_base", None)
    squash_evidence = getattr(args, "evidence", None)
    squash_args = [squash_pr, squash_tag, squash_base, squash_evidence]
    if any(a is not None for a in squash_args):
        if not all(a is not None for a in squash_args):
            return reject("retire", "squash_args_incomplete",
                          "squash-merged-pr / source-tag / delivery-base / evidence 必须同时提供")
        if getattr(args, "platform_rebased_pr", None) is not None:
            return reject("retire", "squash_platform_exclusive",
                          "squash-merged-pr 与 platform-rebased-pr 互斥")
        if not re.fullmatch(r"[0-9a-f]{40}", squash_base):
            return reject("retire", "delivery_base_invalid",
                          f"delivery-base 必须 40-hex: {squash_base!r}")
        evidence_path = Path(squash_evidence).expanduser().absolute()
        if evidence_path.is_symlink():
            return reject("retire", "evidence_symlink", f"evidence 不能是 symlink: {evidence_path}")
        try:
            evidence_path.relative_to(raw_dest)
            return reject("retire", "evidence_inside_clone",
                          f"evidence 必须在 clone 外部: {evidence_path}")
        except ValueError:
            pass
        return _retire_squash_successor(args, dest, squash_pr, squash_tag, squash_base, evidence_path)

    if not os.path.lexists(dest):
        audit("retire_ok", f"already_absent {dest}")
        print(json.dumps({"ok": True, "already_absent": str(dest)}))
        return EXIT_OK
    if dest.is_symlink():
        return reject("retire", "symlink_destination", f"refusing symlink destination: {dest}")
    try:
        resolved = dest.resolve(strict=True)
    except OSError as exc:
        return reject("retire", "destination_unreadable", str(exc))
    if resolved != dest or dest.name != "ws":
        return reject("retire", "dangerous_destination", f"unexpected clone destination: {dest}")
    initial_stat = dest.lstat()
    protected = {Path("/"), Path.home().resolve(), ROOT.resolve(), ROOT.parent.resolve()}
    if resolved in protected:
        return reject("retire", "dangerous_destination", f"protected destination: {dest}")
    git_dir = dest / ".git"
    if not git_dir.is_dir():
        reason = "linked_worktree" if git_dir.is_file() else "independent_clone_required"
        return reject("retire", reason, f"independent clone .git directory required: {dest}")
    common = run(["git", "-C", str(dest), "rev-parse", "--path-format=absolute", "--git-common-dir"])
    if common.returncode != 0 or Path(common.stdout.strip()).resolve() != git_dir.resolve():
        return reject("retire", "linked_worktree", "git common dir is not clone-local")
    identity_path = git_dir / "agent-clone-identity.json"
    try:
        identity = json.loads(identity_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return reject("retire", "identity_unreadable", str(exc))
    schema = identity.get("schema")
    if (
        schema not in {"agent-clone-identity/v1", "agent-clone-identity/v2"}
        or identity.get("ready") is not True
        or identity.get("canonical_root") != str(resolved)
    ):
        return reject("retire", "identity_mismatch", "clone identity does not match destination")
    if schema == "agent-clone-identity/v2":
        actor_id = identity.get("actor_id")
        delivery_attempt_id = identity.get("delivery_attempt_id")
        if (
            identity.get("agent_id") != actor_id
            or not isinstance(actor_id, str)
            or not actor_id
            or not isinstance(delivery_attempt_id, str)
            or not delivery_attempt_id
            or identity.get("working_branch") != f"agent/{actor_id}--{delivery_attempt_id}"
        ):
            return reject("retire", "identity_mismatch", "v2 clone identity is not bound to one actor and delivery attempt")
    branch_probe = run(["git", "-C", str(dest), "branch", "--show-current"])
    branch = branch_probe.stdout.strip()
    if branch_probe.returncode != 0 or branch != identity.get("working_branch"):
        return reject("retire", "branch_mismatch", "current branch does not match clone identity")
    head_probe = run(["git", "-C", str(dest), "rev-parse", "HEAD"])
    if head_probe.returncode != 0:
        return reject("retire", "head_unreadable", "cannot resolve clone HEAD")
    head_sha = head_probe.stdout.strip()
    status = run(["git", "-C", str(dest), "status", "--porcelain", "--ignore-submodules=none"])
    if status.returncode != 0 or status.stdout.strip():
        return reject("retire", "clone_dirty", "clone or initialized submodule is dirty")

    locks, active_runs, state_errors = workflow_activity(dest)
    if locks or active_runs or state_errors:
        return reject(
            "retire",
            "active_lease_or_lock",
            "workflow leases or locks are still present",
            locks=locks,
            active_runs=active_runs,
            unreadable=state_errors,
        )

    platform_pr_number = getattr(args, "platform_rebased_pr", None)
    if platform_pr_number is not None and (
        isinstance(platform_pr_number, bool)
        or not isinstance(platform_pr_number, int)
        or platform_pr_number <= 0
    ):
        return reject("retire", "platform_pr_invalid", "platform-rebased PR must be a positive integer")
    if (
        platform_pr_number is not None
        and identity.get("provenance_required") is not True
    ):
        return reject(
            "retire",
            "platform_provenance_required",
            "platform-rebased retirement requires a provenance-bound clone",
        )

    if platform_pr_number is None:
        repo_slug, provenance_error = bound_repository_slug(dest, identity)
    else:
        # The exact PR base is needed before provenance can distinguish imported
        # platform commits from this clone's delivery commits.  Resolve only the
        # live GitHub origin here; the full receipt/origin/author guard runs below.
        repo_slug, provenance_error = live_origin_repository_slug(dest)
    if repo_slug is None:
        return reject(
            "retire",
            "github_repository_unbound",
            provenance_error or "repository provenance is unavailable",
        )
    owner = repo_slug.split("/", 1)[0]

    platform_pr: dict | None = None
    platform_proof: dict | None = None
    expected_remote_head = head_sha
    if platform_pr_number is not None:
        platform_pr, query_error = query_platform_rebased_pr(repo_slug, platform_pr_number)
        if platform_pr is None:
            return reject("retire", "platform_pr_query_invalid", query_error or "cannot query exact PR")
        if platform_pr["state"] != "MERGED":
            return reject("retire", "platform_pr_not_merged", "platform-rebased PR is not merged")
        if (
            platform_pr["number"] != platform_pr_number
            or platform_pr["repository"] != repo_slug
            or platform_pr["owner"] != owner
            or platform_pr["branch"] != branch
            or platform_pr["base_ref_name"] != "main"
        ):
            return reject(
                "retire",
                "platform_pr_identity_mismatch",
                "platform-rebased PR does not match repository, owner, branch, number, and base",
            )
        expected_remote_head = platform_pr["head_ref_oid"]
        if identity.get("provenance_required") is True:
            guarded, guard_error = run_provenance_guard(
                dest,
                identity,
                platform_base=platform_pr["base_ref_oid"],
                platform_head=expected_remote_head,
            )
            if not guarded:
                return reject(
                    "retire",
                    "clone_provenance_mismatch",
                    guard_error or "platform-aware provenance guard failed",
                )
            verified_repo_slug, verified_repo_error = provenance_receipt_repository_slug(
                dest
            )
            if verified_repo_slug != repo_slug:
                return reject(
                    "retire",
                    "platform_repository_binding_mismatch",
                    verified_repo_error
                    or "verified provenance repository differs from the queried PR repository",
                )
        platform_proof, proof_reason, proof_error = build_platform_rebased_source_proof(
            dest,
            repo_slug,
            branch,
            head_sha,
            platform_pr,
        )
        if platform_proof is None:
            return reject(
                "retire",
                proof_reason or "platform_proof_invalid",
                proof_error or "platform-rebased source proof failed",
            )

    remote_ref = f"refs/heads/{branch}"
    remote = run(["git", "-C", str(dest), "ls-remote", "--exit-code", "--heads", "origin", remote_ref])
    remote_lines = [line.split() for line in remote.stdout.splitlines() if line.strip()]
    if remote.returncode == 0:
        if len(remote_lines) != 1 or len(remote_lines[0]) != 2 or remote_lines[0][1] != remote_ref:
            return reject("retire", "remote_ref_invalid", "remote branch query returned an ambiguous result")
        if remote_lines[0][0] != expected_remote_head:
            return reject(
                "retire",
                "head_not_pushed",
                f"surviving remote branch contradicts expected source {expected_remote_head}",
            )
    elif remote.returncode != 2 or remote_lines:
        return reject("retire", "remote_query_failed", remote.stderr.strip() or "cannot query remote branch")
    if platform_pr is None:
        pr_query = run(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                repo_slug,
                "--head",
                branch,
                "--state",
                "merged",
                "--json",
                "number,url,headRefOid,headRefName,headRepositoryOwner",
                "--limit",
                "100",
            ],
            cwd=str(dest),
        )
        if pr_query.returncode != 0:
            return reject("retire", "pr_query_failed", pr_query.stderr.strip() or "gh pr list failed")
        try:
            merged_prs = json.loads(pr_query.stdout or "[]")
        except json.JSONDecodeError:
            return reject("retire", "pr_query_invalid", "gh pr list returned invalid JSON")
        matching_prs = [
            pr
            for pr in merged_prs
            if pr.get("headRefOid") == head_sha
            and pr.get("headRefName") == branch
            and (pr.get("headRepositoryOwner") or {}).get("login") == owner
        ]
        if not matching_prs:
            return reject("retire", "pr_not_merged", "no merged PR matches clone HEAD")
        merged_pr_url = matching_prs[0].get("url", "")
    else:
        merged_pr_url = platform_pr["url"]

    if dest.is_symlink() or not os.path.samestat(initial_stat, dest.lstat()):
        return reject("retire", "destination_raced", "destination changed during retirement checks")
    final_head = run(["git", "-C", str(dest), "rev-parse", "HEAD"])
    if final_head.returncode != 0 or final_head.stdout.strip() != head_sha:
        return reject("retire", "head_raced", "clone HEAD changed during retirement checks")
    final_status = run(["git", "-C", str(dest), "status", "--porcelain", "--ignore-submodules=none"])
    if final_status.returncode != 0 or final_status.stdout.strip():
        return reject("retire", "clone_raced_dirty", "clone changed during retirement checks")
    if platform_pr is not None:
        live_repo_slug, live_repo_error = live_origin_fetch_push_repository_slug(dest)
        if live_repo_slug != repo_slug:
            return reject(
                "retire",
                "platform_origin_raced",
                live_repo_error
                or "origin fetch/push repository changed after platform provenance verification",
            )
        live_pr, live_error = query_platform_rebased_pr(repo_slug, platform_pr_number)
        if live_pr is None:
            return reject("retire", "platform_proof_raced", live_error or "cannot re-read exact PR")
        if live_pr != platform_pr:
            return reject("retire", "platform_proof_raced", "platform-rebased PR changed during retirement checks")

    def verify_platform_at_quarantine(_payload: Path) -> bool:
        if platform_pr is None:
            return True
        quarantine_pr, _error = query_platform_rebased_pr(repo_slug, platform_pr_number)
        quarantine_repo_slug, _repo_error = live_origin_fetch_push_repository_slug(
            _payload
        )
        return quarantine_pr == platform_pr and quarantine_repo_slug == repo_slug

    removed, removal_detail = quarantine_remove_verified(
        dest,
        initial_stat,
        head_sha,
        verify_platform_at_quarantine if platform_pr is not None else None,
    )
    if not removed:
        return reject("retire", "destination_raced", removal_detail)
    audit("retire_ok", f"removed {dest}")
    print(
        json.dumps(
            {
                "ok": True,
                "removed": str(dest),
                "head_sha": head_sha,
                "merged_pr": merged_pr_url,
                **(
                    {"platform_rebased_source_proof": platform_proof}
                    if platform_proof is not None
                    else {}
                ),
            }
        )
    )
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clone-lifecycle", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    # onboard
    sp = sub.add_parser("onboard", help="创建 clone + 生成 manifest")
    sp.add_argument("--agent-id", required=True)
    sp.add_argument(
        "--delivery-attempt-id",
        help="single delivery attempt; generated when omitted",
    )
    sp.add_argument("--source", default=str(ROOT))
    sp.add_argument("--transport-source", help="optional verified local root transport source")
    sp.add_argument(
        "--submodule-source",
        action="append",
        default=[],
        help="repeatable root-gitlink=local-child-repository transport mapping",
    )
    sp.add_argument(
        "--revision",
        default="origin/main",
        help="source revision to pin before creating the private branch (default: origin/main)",
    )
    sp.add_argument("--destination", required=True)
    sp.add_argument("--manifest")
    sp.add_argument("--readiness", help="external clone-readiness/v1 receipt path")
    sp.add_argument("--provenance", help="external clone-provenance/v1 receipt path")
    sp.add_argument(
        "--expected-repository",
        help="canonical GitHub owner/repository authority; defaults to the created clone origin",
    )
    onboard_mode = sp.add_mutually_exclusive_group()
    onboard_mode.add_argument(
        "--profile",
        choices=("root-only", "governance", "full"),
        help="named root-gitlink profile (default: governance)",
    )
    onboard_mode.add_argument(
        "--submodule",
        action="append",
        default=[],
        help="initialize only this root gitlink; repeat for multiple paths",
    )
    onboard_mode.add_argument(
        "--all-submodules",
        action="store_true",
        help="initialize every root gitlink (never recursive)",
    )
    sp.set_defaults(func=cmd_onboard)
    # snapshot
    sp = sub.add_parser("snapshot", help="生成基线 manifest")
    sp.add_argument("--clone", required=True)
    sp.add_argument("--output", required=True)
    sp.set_defaults(func=cmd_snapshot)
    # provenance recovery
    sp = sub.add_parser("provenance", help="恢复或复核 clone provenance receipt")
    sp.add_argument("--clone", required=True)
    sp.add_argument("--expected-repository", required=True)
    sp.add_argument("--output", required=True)
    sp.set_defaults(func=cmd_provenance)
    # readiness recovery
    sp = sub.add_parser("readiness", help="恢复或复核 clone readiness receipt")
    sp.add_argument("--clone", required=True)
    sp.add_argument("--manifest", required=True)
    sp.add_argument("--output", required=True)
    sp.set_defaults(func=cmd_readiness)
    # changeset
    sp = sub.add_parser("changeset", help="生成变更集 + claim 校验")
    sp.add_argument("--clone", required=True)
    sp.add_argument("--baseline", required=True)
    sp.add_argument("--output", required=True)
    sp.add_argument("--verify-claims", action="store_true")
    sp.add_argument("--claims-root", help="authoritative workspace containing workflow runs")
    sp.set_defaults(func=cmd_changeset)
    # integrate
    sp = sub.add_parser("integrate", help="推送 + PR")
    sp.add_argument("--clone", required=True)
    sp.add_argument("--agent-id", required=True)
    sp.add_argument("--delivery-attempt-id", required=True)
    sp.add_argument("--base", default="main")
    sp.add_argument("--baseline", help="baseline manifest bound to the verified changeset")
    sp.add_argument("--changeset", help="current changeset created with --verify-claims")
    sp.add_argument("--claims-root", help="same authoritative claims root used by the changeset")
    integrate_mode = sp.add_mutually_exclusive_group()
    integrate_mode.add_argument("--dry-run", dest="dry_run", action="store_true")
    integrate_mode.add_argument("--apply", dest="dry_run", action="store_false")
    sp.set_defaults(dry_run=True)
    sp.set_defaults(func=cmd_integrate)
    # retire
    sp = sub.add_parser("retire", help="清理 clone")
    sp.add_argument("--destination", required=True)
    sp.add_argument(
        "--platform-rebased-pr",
        type=int,
        help="exact merged PR number whose server-side rebase rewrote the source commit",
    )
    # T1-02 squash-successor 退场 mode
    sp.add_argument("--squash-merged-pr", type=int,
                    help="exact merged PR number for one-parent squash merge (T1-02)")
    sp.add_argument("--source-tag",
                    help="annotated source tag for squash-successor retirement")
    sp.add_argument("--delivery-base",
                    help="40-hex commit SHA: merge-base(source_head, pr_base)")
    sp.add_argument("--evidence",
                    help="external proof receipt path outside clone")
    sp.set_defaults(func=cmd_retire)
    # abort-unready -- intentionally separate from ready-clone retirement.
    sp = sub.add_parser("abort-unready", help="双读清理从未获 writer admission 的降级 clone")
    sp.add_argument("--destination", required=True)
    sp.add_argument("--agent-id", required=True)
    sp.add_argument("--delivery-attempt-id", required=True)
    sp.add_argument("--expected-repository", required=True)
    sp.add_argument("--baseline", required=True)
    sp.add_argument("--readiness", required=True)
    sp.add_argument("--claims-root", required=True)
    mode = sp.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="write authorization then remove the verified clone")
    mode.add_argument("--dry-run", action="store_true", help="assess only (default)")
    sp.add_argument("--evidence", help="exclusive clone-abort-authorization/v1 output (required with --apply)")
    sp.set_defaults(func=cmd_abort_unready, apply=False)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        audit("lifecycle_error", f"{type(exc).__name__}: {exc}")
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
