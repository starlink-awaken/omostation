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


def bound_repository_slug(clone: Path, identity: dict) -> tuple[str | None, str | None]:
    """Resolve a lifecycle repository, live-verifying new provenance identities."""
    if identity.get("provenance_required") is True:
        env = os.environ.copy()
        env["AGENT_ID"] = str(identity.get("agent_id", ""))
        guarded = run(
            [
                sys.executable,
                str(AGENT_CLONE),
                "guard",
                "--workspace",
                str(clone),
                "--require-clone",
                "--json",
            ],
            env=env,
        )
        if guarded.returncode != 0:
            return None, guarded.stdout.strip() or guarded.stderr.strip() or "provenance guard failed"
        try:
            receipt = json.loads((clone / ".git" / "agent-clone-provenance.json").read_text())
        except (OSError, json.JSONDecodeError) as exc:
            return None, f"provenance receipt unreadable: {exc}"
        canonical_repository = (receipt.get("repository") or {}).get("canonical_repository", "")
        match = re.fullmatch(
            r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)",
            canonical_repository,
        )
        if not match:
            return None, "provenance receipt repository is invalid"
        return f"{match.group(1)}/{match.group(2)}", None
    remote_probe = run(["git", "-C", str(clone), "remote", "get-url", "origin"])
    if remote_probe.returncode != 0:
        return None, "cannot resolve origin remote"
    slug = github_repo_slug(remote_probe.stdout)
    return (slug, None) if slug else (None, "origin is not an exact GitHub repository URL")


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


def cmd_retire(args: argparse.Namespace) -> int:
    """清理 clone + 释放资源."""
    raw_dest = Path(args.destination).expanduser().absolute()
    dest = raw_dest
    audit("retire_start", f"dest={dest}")
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
    if (
        identity.get("schema")
        not in {"agent-clone-identity/v1", "agent-clone-identity/v2"}
        or identity.get("ready") is not True
        or identity.get("canonical_root") != str(resolved)
    ):
        return reject("retire", "identity_mismatch", "clone identity does not match destination")
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

    repo_slug, provenance_error = bound_repository_slug(dest, identity)
    if repo_slug is None:
        return reject(
            "retire",
            "github_repository_unbound",
            provenance_error or "repository provenance is unavailable",
        )
    owner = repo_slug.split("/", 1)[0]
    remote_ref = f"refs/heads/{branch}"
    remote = run(["git", "-C", str(dest), "ls-remote", "--exit-code", "--heads", "origin", remote_ref])
    remote_lines = [line.split() for line in remote.stdout.splitlines() if line.strip()]
    if remote.returncode == 0:
        if len(remote_lines) != 1 or len(remote_lines[0]) != 2 or remote_lines[0][1] != remote_ref:
            return reject("retire", "remote_ref_invalid", "remote branch query returned an ambiguous result")
        if remote_lines[0][0] != head_sha:
            return reject(
                "retire",
                "head_not_pushed",
                f"surviving remote branch contradicts clone HEAD {head_sha}",
            )
    elif remote.returncode != 2 or remote_lines:
        return reject("retire", "remote_query_failed", remote.stderr.strip() or "cannot query remote branch")
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

    if dest.is_symlink() or not os.path.samestat(initial_stat, dest.lstat()):
        return reject("retire", "destination_raced", "destination changed during retirement checks")
    final_head = run(["git", "-C", str(dest), "rev-parse", "HEAD"])
    if final_head.returncode != 0 or final_head.stdout.strip() != head_sha:
        return reject("retire", "head_raced", "clone HEAD changed during retirement checks")
    final_status = run(["git", "-C", str(dest), "status", "--porcelain", "--ignore-submodules=none"])
    if final_status.returncode != 0 or final_status.stdout.strip():
        return reject("retire", "clone_raced_dirty", "clone changed during retirement checks")
    removed, removal_detail = quarantine_remove_verified(dest, initial_stat, head_sha)
    if not removed:
        return reject("retire", "destination_raced", removal_detail)
    audit("retire_ok", f"removed {dest}")
    print(
        json.dumps(
            {
                "ok": True,
                "removed": str(dest),
                "head_sha": head_sha,
                "merged_pr": matching_prs[0].get("url", ""),
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
