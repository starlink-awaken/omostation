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
import json
import os
import re
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


def cmd_onboard(args: argparse.Namespace) -> int:
    """为新 agent 创建 clone + 生成基线 manifest."""
    agent_id = args.agent_id
    dest = Path(args.destination)
    manifest_path = Path(args.manifest) if args.manifest else dest.parent / f"{agent_id}-baseline.json"
    audit("onboard_start", f"agent={agent_id} dest={dest}")
    if os.path.lexists(manifest_path):
        return reject(
            "onboard",
            "manifest_collision",
            f"manifest output already exists: {manifest_path}",
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
        "--source",
        args.source,
        "--destination",
        str(dest),
    ]
    requested_submodules = list(getattr(args, "submodule", None) or [])
    if getattr(args, "all_submodules", False):
        pass
    elif requested_submodules:
        for submodule in requested_submodules:
            cmd.extend(["--submodule", submodule])
    else:
        cmd.append("--no-submodules")
    r = run(cmd)
    if r.returncode != 0:
        audit("onboard_failed", f"clone_create rc={r.returncode} stderr={r.stderr.strip()[:200]}")
        print(r.stderr, file=sys.stderr)
        return EXIT_POLICY
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
    audit("onboard_ok", f"agent={agent_id} clone={dest} manifest={manifest_path}")
    print(
        json.dumps(
            {
                "ok": True,
                "agent_id": agent_id,
                "clone": str(dest),
                "manifest": str(manifest_path),
                "verification": "verified",
                "initialized_submodules": requested_submodules if not getattr(args, "all_submodules", False) else "all",
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
    branch = f"agent/{agent_id}"
    audit("integrate_start", f"agent={agent_id} branch={branch}")
    if args.dry_run:
        audit("integrate_dry_run", f"would push {branch} and create PR")
        print(json.dumps({"ok": True, "dry_run": True, "branch": branch}))
        return EXIT_OK
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
        identity.get("schema") != "agent-clone-identity/v1"
        or identity.get("ready") is not True
        or identity.get("canonical_root") != str(clone.resolve())
        or identity.get("agent_id") != agent_id
        or identity.get("working_branch") != branch
    ):
        return reject("integrate", "identity_mismatch", "clone identity does not match integration request")
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
    remote_probe = run(["git", "-C", str(clone), "remote", "get-url", "origin"])
    if remote_probe.returncode != 0:
        return reject("integrate", "origin_unreadable", "cannot resolve origin remote")
    repo_slug = github_repo_slug(remote_probe.stdout)
    if repo_slug is None:
        return reject("integrate", "github_repository_unbound", "origin is not an exact GitHub repository URL")
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
            "origin",
            f"{head_sha}:refs/heads/{branch}",
        ]
    )
    if r.returncode != 0:
        audit("integrate_failed", f"push rc={r.returncode}")
        return EXIT_POLICY
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
                f"fix(gac): harden {agent_id} clone lifecycle",
                "--body",
                "Automated independent-clone lifecycle integration.",
            ],
            cwd=str(clone),
        )
        if created.returncode != 0 or not created.stdout.strip():
            return reject("integrate", "pr_create_failed", created.stderr.strip() or "gh pr create failed")
        pr_url = created.stdout.strip()
    audit("integrate_ok", f"pushed {branch} pr={pr_url}")
    print(
        json.dumps(
            {
                "ok": True,
                "branch": branch,
                "head_sha": head_sha,
                "change_id": verification["change_id"],
                "repository": repo_slug,
                "pushed": True,
                "pr_url": pr_url,
            }
        )
    )
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
        identity.get("schema") != "agent-clone-identity/v1"
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

    remote_probe = run(["git", "-C", str(dest), "remote", "get-url", "origin"])
    if remote_probe.returncode != 0:
        return reject("retire", "origin_unreadable", "cannot resolve origin remote")
    repo_slug = github_repo_slug(remote_probe.stdout)
    if repo_slug is None:
        return reject("retire", "github_repository_unbound", "origin is not an exact GitHub repository URL")
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
    sp.add_argument("--source", default=str(ROOT))
    sp.add_argument("--destination", required=True)
    sp.add_argument("--manifest")
    onboard_mode = sp.add_mutually_exclusive_group()
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
