#!/usr/bin/env python3
"""G-CONV.7 / ADR-0220 swarm coordination discipline — pure gates + FS helpers.

Decision functions are pure (injectable paths) so unit tests drive the real
logic without a multi-agent swarm. Side effects (locks, event log) live here
but stay thin.

Gates:
  D1 ADR atomic claim
  D2 branch occupancy lock
  D3 shared worktree claim-before-write
  D4 escape-hatch allowlist
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc

DEFAULT_REGISTRY = ".omo/_truth/registry/swarm-coordination.yaml"
ADR_FILE_RE = re.compile(r"^\.omo/_knowledge/decisions/(\d{4})-.*\.md$")
BRANCH_RE = re.compile(r"^work/[a-z0-9][a-z0-9-]*$")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_iso(dt: datetime | None = None) -> str:
    d = dt or _utc_now()
    return d.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_registry(root: Path) -> dict[str, Any]:
    path = root / DEFAULT_REGISTRY
    if not path.is_file():
        return {"version": 0, "escape_hatch_exemptions": [], "delivery": {}}
    try:
        import yaml  # noqa: PLC0415

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {"version": 0, "escape_hatch_exemptions": [], "delivery": {}}


def delivery_path(root: Path, key: str, default: str) -> Path:
    reg = load_registry(root)
    rel = (reg.get("delivery") or {}).get(key) or default
    return root / rel


def emit_conflict_event(
    root: Path,
    kind: str,
    detail: dict[str, Any],
    *,
    session: str = "",
) -> Path:
    """Append a structured conflict event for the 72h observation window."""
    events = delivery_path(
        root, "conflict_events", ".omo/_delivery/swarm-conflicts/events.jsonl"
    )
    events.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": _utc_iso(),
        "kind": kind,
        "session": session or None,
        "detail": detail,
    }
    with events.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return events


# ── D1 ADR atomic claim ──────────────────────────────────────────────


def list_existing_adr_numbers(
    decisions_dir: Path, *, include_remote: bool = True
) -> set[int]:
    """ADRs on disk (+ optionally origin/main tree) so stale bases still see
    concurrently-merged ADRs and cannot double-allocate a number."""
    nums: set[int] = set()
    if decisions_dir.is_dir():
        for path in decisions_dir.iterdir():
            m = re.match(r"^(\d{4})-", path.name)
            if m:
                nums.add(int(m.group(1)))
    if include_remote:
        # 并发 main 可能已合并新 ADR — 本地 base 陈旧时仍防撞号 (0396 撞号教训)
        try:
            out = subprocess.run(
                ["git", "ls-tree", "--name-only", "origin/main", str(decisions_dir)],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            for line in out.stdout.splitlines():
                m = re.match(r"^(\d{4})-", Path(line).name)
                if m:
                    nums.add(int(m.group(1)))
        except (OSError, subprocess.SubprocessError):
            pass
    return nums


def load_adr_claims(claims_dir: Path) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    if not claims_dir.is_dir():
        return out
    for path in claims_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        n = payload.get("number")
        if isinstance(n, int):
            out[n] = {**payload, "_claim_file": path.name}
    return out


def next_free_adr(existing: set[int], claimed: dict[int, dict]) -> int:
    taken = set(existing) | set(claimed)
    candidate = (max(taken) + 1) if taken else 1
    while candidate in taken:
        candidate += 1
    return candidate


def acquire_adr_claim(
    root: Path,
    session: str,
    *,
    number: int | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Atomically claim next (or specific) ADR number for session.

    Uses an exclusive flock on .omo/_delivery/adr-claims/.lock so concurrent
    claimers cannot double-allocate the same number (D1).
    """
    if not session:
        return False, {"error": "session required"}
    claims_dir = delivery_path(root, "adr_claims_dir", ".omo/_delivery/adr-claims")
    claims_dir.mkdir(parents=True, exist_ok=True)
    lock_path = claims_dir / ".lock"
    decisions = root / ".omo" / "_knowledge" / "decisions"

    with lock_path.open("a+", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        existing = list_existing_adr_numbers(decisions)
        claimed = load_adr_claims(claims_dir)
        # session already has a claim → return it
        for n, payload in claimed.items():
            if payload.get("session") == session:
                return True, {
                    "number": n,
                    "next_id": f"{n:04d}",
                    "session": session,
                    "reused": True,
                    "claim_path": str(claims_dir / f"{session}.json"),
                }
        target = number if number is not None else next_free_adr(existing, claimed)
        if target in existing:
            emit_conflict_event(
                root,
                "adr_renumber_race",
                {"number": target, "reason": "already_on_disk", "session": session},
                session=session,
            )
            return False, {
                "error": f"ADR-{target:04d} already exists on disk",
                "number": target,
            }
        holder = claimed.get(target)
        if holder and holder.get("session") != session:
            emit_conflict_event(
                root,
                "adr_renumber_race",
                {
                    "number": target,
                    "holder": holder.get("session"),
                    "challenger": session,
                },
                session=session,
            )
            return False, {
                "error": f"ADR-{target:04d} claimed by session={holder.get('session')}",
                "number": target,
                "holder": holder.get("session"),
            }
        payload = {
            "number": target,
            "next_id": f"{target:04d}",
            "session": session,
            "claimed_at": _utc_iso(),
            "gate": "d1_adr_atomic_claim",
            "note": "ADR-0220 D1; release by deleting claim after ADR lands on main",
        }
        claim_path = claims_dir / f"{session}.json"
        claim_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return True, {
            "number": target,
            "next_id": f"{target:04d}",
            "session": session,
            "reused": False,
            "claim_path": str(claim_path.relative_to(root)),
        }


def check_adr_write_authorized(
    root: Path,
    rel_path: str,
    session: str | None,
) -> tuple[bool, str]:
    """D1: writing a new ADR file requires matching session claim."""
    m = ADR_FILE_RE.match(rel_path.replace("\\", "/"))
    if not m:
        return True, "not_an_adr_path"
    number = int(m.group(1))
    decisions = root / ".omo" / "_knowledge" / "decisions"
    # existing file on disk (edit) is allowed
    if (decisions / Path(rel_path).name).is_file():
        return True, "existing_adr_edit"
    claims = load_adr_claims(
        delivery_path(root, "adr_claims_dir", ".omo/_delivery/adr-claims")
    )
    holder = claims.get(number)
    if holder is None:
        emit_conflict_event(
            root,
            "adr_renumber_race",
            {"number": number, "path": rel_path, "reason": "no_claim"},
            session=session or "",
        )
        return False, f"ADR-{number:04d} write requires prior claim (next-adr-id --claim)"
    # D1 fail-closed: empty/missing session must NOT inherit a foreign claim
    sess = (session or "").strip()
    if not sess:
        emit_conflict_event(
            root,
            "adr_renumber_race",
            {
                "number": number,
                "path": rel_path,
                "holder": holder.get("session"),
                "reason": "empty_session",
            },
            session="",
        )
        return False, (
            f"ADR-{number:04d} write requires AGENT_WORKFLOW_SESSION / --session "
            f"matching claim holder={holder.get('session')}"
        )
    if holder.get("session") != sess:
        emit_conflict_event(
            root,
            "adr_renumber_race",
            {
                "number": number,
                "path": rel_path,
                "holder": holder.get("session"),
                "writer": sess,
            },
            session=sess,
        )
        return False, (
            f"ADR-{number:04d} claimed by session={holder.get('session')}, "
            f"not {sess}"
        )
    return True, "claim_ok"


# ── D2 branch occupancy ──────────────────────────────────────────────


def load_branch_claims(claims_dir: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not claims_dir.is_dir():
        return out
    for path in claims_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        branch = payload.get("branch")
        if isinstance(branch, str):
            out[branch] = {**payload, "_claim_file": path.name}
    return out


def _shadow_mirror_claim(branch: str, session: str, *, release: bool = False) -> dict[str, Any]:
    """D2 文件锁 → 共享 SQLite 双写 (BET-Y1Q1-T1-05A shadow).

    shadow 语义: 文件锁是权威判定源, 本镜像失败只落 shadow_events,
    不改变调用方返回值. warning/fail 阶段翻开关时只改处置不改判定.
    返回 {"token": int} 供 claim 文件持久化 (submit 时 token-check 用).
    """
    out: dict[str, Any] = {}
    try:
        _here = str(Path(__file__).resolve().parent)
        if _here not in sys.path:
            sys.path.insert(0, _here)
        import coordination_store as cs

        if release:
            cs.release_resource("branch", branch, owner=session)
            return out
        claim = cs.claim_resource("branch", branch, owner=session, ttl_hours=24)
        if claim is None:
            # 文件锁判成功但镜像已有 active holder → 观察面记录漂移,
            # 不翻转文件锁判定 (shadow 阶段文件锁说了算)
            existing = cs.active_claim("branch", branch)
            cs.emit_shadow_event(
                "mirror_drift", "branch", branch,
                {"holder": existing.owner if existing else "unknown",
                 "session": session},
            )
            if existing:
                out["token"] = existing.token  # 复用既有 claim 的 token, 防误报 stale
        else:
            cs.emit_shadow_event("write_ok", "branch", branch, {"token": claim.token})
            out["token"] = claim.token
    except Exception as exc:  # noqa: BLE001 — shadow 镜像永不反噬主流程
        try:
            _here = str(Path(__file__).resolve().parent)
            if _here not in sys.path:
                sys.path.insert(0, _here)
            import coordination_store as cs
            cs.emit_shadow_event("write_fail", "branch", branch, {"error": str(exc)})
        except Exception:
            pass
        print(
            f"[swarm-shadow] mirror {'release' if release else 'claim'} failed "
            f"for {branch}: {exc}",
            file=sys.stderr,
        )
    return out


def acquire_branch_lock(
    root: Path,
    session: str,
    branch: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Register occupancy for work/<session>. Refuse if held by another session."""
    if not session:
        return False, {"error": "session required"}
    branch = branch or f"work/{session}"
    if not BRANCH_RE.match(branch):
        return False, {"error": f"invalid branch name: {branch}"}
    claims_dir = delivery_path(
        root, "branch_claims_dir", ".omo/_delivery/branch-claims"
    )
    claims_dir.mkdir(parents=True, exist_ok=True)
    lock_path = claims_dir / ".lock"
    with lock_path.open("a+", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        claims = load_branch_claims(claims_dir)
        holder = claims.get(branch)
        if holder and holder.get("session") != session:
            emit_conflict_event(
                root,
                "branch_hijack",
                {
                    "branch": branch,
                    "holder": holder.get("session"),
                    "challenger": session,
                },
                session=session,
            )
            return False, {
                "error": f"branch {branch} occupied by session={holder.get('session')}",
                "holder": holder.get("session"),
                "branch": branch,
            }
        payload = {
            "branch": branch,
            "session": session,
            "claimed_at": _utc_iso(),
            "gate": "d2_branch_occupancy",
        }
        path = claims_dir / f"{session}.json"
        mirror = _shadow_mirror_claim(branch, session)
        if "token" in mirror:
            payload["coordination_token"] = mirror["token"]
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return True, {
            "branch": branch,
            "session": session,
            "claim_path": str(path.relative_to(root)),
            "reused": bool(holder),
            **({"coordination_token": mirror["token"]} if "token" in mirror else {}),
        }


def check_branch_available(
    root: Path, branch: str, session: str
) -> tuple[bool, str]:
    claims = load_branch_claims(
        delivery_path(root, "branch_claims_dir", ".omo/_delivery/branch-claims")
    )
    holder = claims.get(branch)
    if holder is None:
        return True, "free"
    if holder.get("session") == session:
        return True, "owned"
    return False, f"occupied by {holder.get('session')}"


def release_branch_lock(
    root: Path, session: str, purge_orphans: bool = False
) -> bool:
    """释放 session 的 branch claim.

    B3 (ADR-0367): purge_orphans=True 时顺带清理孤儿 claim —
    分支已不存在 (本地/远端 refs 均无) 的 claim 文件直接删除,
    防止 session 异常退出后 claim 永久残留 (G-CONV.7 D2).
    """
    claims_dir = delivery_path(
        root, "branch_claims_dir", ".omo/_delivery/branch-claims"
    )
    path = claims_dir / f"{session}.json"
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        _shadow_mirror_claim(payload.get("branch", f"work/{session}"), session, release=True)
        path.unlink()
    if purge_orphans and claims_dir.is_dir():
        for claim_file in claims_dir.glob("*.json"):
            if claim_file.name == ".lock":
                continue
            try:
                payload = json.loads(claim_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            branch = payload.get("branch")
            if isinstance(branch, str) and not _branch_exists_locally(root, branch):
                claim_file.unlink()
    return True


def _branch_exists_locally(root: Path, branch: str) -> bool:
    """branch 是否仍存在于本地或远端 refs (for-each-ref, 无网络调用)."""
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "for-each-ref", "--format=%(refname:short)",
             "refs/heads", "refs/remotes"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        refs = set(r.stdout.splitlines())
    except Exception:
        return True  # 无法判断时保守保留 claim
    return branch in refs or f"remotes/origin/{branch}" in refs


def _branch_has_open_pr(root: Path, branch: str) -> bool:
    """安全网: branch 有 open PR 则视为 active, GC 跳过 (防误清正在用的 claim)."""
    try:
        repo = subprocess.run(
            ["git", "-C", str(root), "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, check=False,
        ).stdout.strip()
        repo = re.sub(r".*github.com[:/]", "", repo).replace(".git", "").strip()
        if not repo:
            return False
        r = subprocess.run(
            ["gh", "pr", "list", "--repo", repo, "--head", branch,
             "--state", "open", "--json", "number"],
            capture_output=True, text=True, check=False, timeout=15,
        )
        out = r.stdout.strip()
        return bool(out and out != "[]")
    except Exception:
        return False


def claim_gc(
    root: Path, ttl_hours: int = 168, dry_run: bool = False
) -> dict[str, Any]:
    """GC 过期 claim 文件 (branch-claims + agent-claims + adr-claims).

    D1 (2026-08-04): claim 有 acquire/release 但无 auto-expire, 长期累积垃圾
    (本轮实证 branch-claims 含 2026-08-03 前的 ci-fix/d2-swarm-dashboard 残留).
    GC 规则:
      1. claimed_at/created_at + ttl_hours < now → 过期候选
      2. 对应 branch 有 open PR → 跳过 (active safety net)
      3. 过期 + 无 PR → 清理

    ttl_hours 默认 168 (7 天): claim 是长期占位 (worktree 可能跨天), 短 TTL 误清风险高.
    返回 {reclaimed, skipped, errors}.
    """
    import time
    from datetime import datetime

    now = time.time()
    ttl_seconds = ttl_hours * 3600
    result: dict[str, Any] = {"reclaimed": [], "skipped": [], "errors": []}

    claim_sources = [
        ("branch-claims",
         delivery_path(root, "branch_claims_dir", ".omo/_delivery/branch-claims"),
         ".json"),
        ("agent-claims",
         delivery_path(root, "agent_claims_dir", ".omo/_delivery/agent-claims"),
         ".yaml"),
        ("adr-claims",
         delivery_path(root, "adr_claims_dir", ".omo/_delivery/adr-claims"),
         ".json"),
    ]

    for kind, claims_dir, ext in claim_sources:
        if not claims_dir.is_dir():
            continue
        for path in claims_dir.glob(f"*{ext}"):
            if path.name == ".lock":
                continue
            label = f"{kind}/{path.name}"
            try:
                text = path.read_text(encoding="utf-8")
                ts_field = None
                branch = None
                if ext == ".json":
                    payload = json.loads(text)
                    ts_field = payload.get("claimed_at") or payload.get("created_at")
                    branch = payload.get("branch")
                else:
                    # agent-claims 是简单 yaml (无嵌套), 行级解析免 yaml 依赖
                    for line in text.splitlines():
                        stripped = line.strip()
                        if stripped.startswith("created_at:"):
                            ts_field = stripped.split(":", 1)[1].strip()
                        elif stripped.startswith("branch:"):
                            branch = stripped.split(":", 1)[1].strip()

                if not ts_field:
                    result["skipped"].append(f"{label}: 无时间戳")
                    continue
                try:
                    ts = datetime.fromisoformat(
                        ts_field.replace("Z", "+00:00")
                    ).timestamp()
                except (ValueError, TypeError):
                    result["skipped"].append(f"{label}: 时间戳无法解析 ({ts_field})")
                    continue

                age_seconds = now - ts
                if age_seconds < ttl_seconds:
                    result["skipped"].append(
                        f"{label}: 未过期 ({int(age_seconds / 3600)}h)"
                    )
                    continue

                age_hours = int(age_seconds / 3600)
                if branch and _branch_has_open_pr(root, branch):
                    result["skipped"].append(f"{label}: branch {branch} 有 open PR")
                    continue

                if dry_run:
                    result["reclaimed"].append(f"{label} [dry-run] ({age_hours}h)")
                else:
                    path.unlink()
                    result["reclaimed"].append(f"{label} ({age_hours}h)")
            except Exception as e:
                result["errors"].append(f"{label}: {e}")

    return result


# ── D3 shared worktree claim ─────────────────────────────────────────


def is_isolated_work_branch(branch: str) -> bool:
    return bool(re.match(r"^(work|pr)/", branch or ""))


def git_current_branch(root: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return (r.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def active_workflow_claimed_paths(root: Path) -> list[str]:
    """Collect claimed paths from active agent-workflow runs (if any)."""
    runs_dir = root / ".omo" / "_delivery" / "agent-workflows" / "runs"
    if not runs_dir.is_dir():
        return []
    paths: list[str] = []
    for path in sorted(runs_dir.glob("*.yaml"), reverse=True)[:40]:
        try:
            import yaml  # noqa: PLC0415

            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, dict):
            continue
        status = str(data.get("status") or data.get("state") or "").lower()
        if status in {"closed", "closeout", "done", "failed", "cancelled"}:
            continue
        for claim in data.get("claims") or []:
            if isinstance(claim, dict):
                for p in claim.get("paths") or []:
                    if isinstance(p, str):
                        paths.append(p)
            elif isinstance(claim, str):
                paths.append(claim)
        # alternate shapes
        for p in data.get("claimed_paths") or []:
            if isinstance(p, str):
                paths.append(p)
    return paths


def path_covered_by_claim(claimed: list[str], changed: str) -> bool:
    changed = changed.replace("\\", "/").lstrip("./")
    for c in claimed:
        c = c.replace("\\", "/").lstrip("./")
        if changed == c or changed.startswith(c.rstrip("/") + "/"):
            return True
        if c.endswith("/**") and changed.startswith(c[:-3]):
            return True
    return False


def path_matches_allow_globs(path: str, globs: list[str]) -> bool:
    import fnmatch  # noqa: PLC0415

    path = path.replace("\\", "/").lstrip("./")
    for g in globs:
        g = g.replace("\\", "/")
        if fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, g.lstrip("./")):
            return True
        # directory ** style
        if g.endswith("/**") and path.startswith(g[:-3]):
            return True
    return False


def check_shared_worktree_writes(
    root: Path,
    staged_paths: list[str],
    *,
    branch: str | None = None,
    claimed_paths: list[str] | None = None,
    allow_globs: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """D3: on shared (non-work/*) tree, every staged path needs claim or allowlist."""
    branch = branch if branch is not None else git_current_branch(root)
    if is_isolated_work_branch(branch):
        return True, []
    # Also treat presence of AGENT_WORKFLOW_RUN_ID + claims as compliant on main
    if claimed_paths is None:
        claimed_paths = active_workflow_claimed_paths(root)
    if allow_globs is None:
        reg = load_registry(root)
        allow_globs = list(reg.get("shared_worktree_allow_path_globs") or [])
    violations: list[str] = []
    for p in staged_paths:
        rel = p.replace("\\", "/").lstrip("./")
        if path_matches_allow_globs(rel, allow_globs):
            continue
        if path_covered_by_claim(claimed_paths, rel):
            continue
        # D1 ADR special case
        if ADR_FILE_RE.match(rel):
            ok, reason = check_adr_write_authorized(
                root, rel, os.environ.get("AGENT_WORKFLOW_SESSION") or ""
            )
            if ok:
                continue
            violations.append(f"{rel}: {reason}")
            continue
        violations.append(
            f"{rel}: unclaimed write on shared worktree (branch={branch or 'unknown'})"
        )
    if violations:
        emit_conflict_event(
            root,
            "unclaimed_write",
            {"branch": branch, "paths": staged_paths, "violations": violations},
            session=os.environ.get("AGENT_WORKFLOW_SESSION") or "",
        )
        return False, violations
    return True, []


# ── D4 escape hatch ──────────────────────────────────────────────────


def list_escape_exemptions(root: Path) -> list[dict[str, Any]]:
    reg = load_registry(root)
    items = reg.get("escape_hatch_exemptions") or []
    return [x for x in items if isinstance(x, dict) and x.get("active", True)]


def check_escape_hatch(
    root: Path,
    *,
    flag: str,
    escape_id: str | None,
) -> tuple[bool, str]:
    """D4: flag in {ci_local_skip, no_verify_push, no_verify_commit} needs allowlist id."""
    flag = flag.strip().lower().replace("-", "_")
    if flag not in {"ci_local_skip", "no_verify_push", "no_verify_commit"}:
        return False, f"unknown escape flag: {flag}"
    if not escape_id:
        emit_conflict_event(
            root,
            "escape_hatch_abuse",
            {"flag": flag, "reason": "missing_escape_id"},
        )
        return False, f"{flag} requires SWARM_ESCAPE_ID / --escape-id from allowlist"
    for item in list_escape_exemptions(root):
        if item.get("id") != escape_id:
            continue
        allow = [str(a).lower().replace("-", "_") for a in (item.get("allow") or [])]
        if flag in allow:
            # record legitimate use
            log_dir = delivery_path(
                root, "escape_log_dir", ".omo/_delivery/swarm-escape"
            )
            log_dir.mkdir(parents=True, exist_ok=True)
            rec = {
                "ts": _utc_iso(),
                "flag": flag,
                "escape_id": escape_id,
                "reason": item.get("reason"),
            }
            (log_dir / f"{_utc_now().strftime('%Y%m%dT%H%M%SZ')}-{escape_id}.json").write_text(
                json.dumps(rec, indent=2) + "\n", encoding="utf-8"
            )
            return True, f"exempt:{escape_id}"
        return False, f"escape_id={escape_id} does not allow {flag}"
    emit_conflict_event(
        root,
        "escape_hatch_abuse",
        {"flag": flag, "escape_id": escape_id, "reason": "unknown_id"},
    )
    return False, f"escape_id={escape_id} not in allowlist"


def argv_has_no_verify(argv: list[str]) -> bool:
    """True if argv requests git --no-verify (not -n: push -n is dry-run)."""
    return "--no-verify" in argv


def argv_has_dangerous(argv: list[str]) -> bool:
    """T1-07 (BET-Y1Q1-T1-07): True if argv is a high-risk git op agents must not run.

    clean -f[d|x], reset --hard, stash -u/--include-untracked — destroy peer agents'
    uncommitted work in a shared tree (2026-08-06 实测 4 次产物丢失). No escape,
    agents 禁做. rebase-on-shared-branch 由 swarm-git bash 层判 (需 git rev-parse).
    """
    sub = next((a for a in argv if a and not a.startswith("-")), "")
    # clean -f[d|x]: force remove untracked. 短 flag 合并判 (fd/fdx/df/xdf 或 -f -d 组合)
    if sub == "clean":
        short = "".join(f.lstrip("-") for f in argv if f.startswith("-") and not f.startswith("--"))
        if "f" in short and ("d" in short or "x" in short) and "n" not in short:
            return True
    # reset --hard
    if sub == "reset" and "--hard" in argv:
        return True
    # stash -u / --include-untracked
    if sub == "stash" and ("-u" in argv or "--include-untracked" in argv):
        return True
    return False


def no_verify_flag_for_argv(argv: list[str]) -> str:
    """Map git subcommand to escape flag name."""
    # find first non-flag token after git
    tokens = [a for a in argv if not a.startswith("-") or a in {"--no-verify"}]
    # crude: look for commit/push keywords
    joined = " ".join(argv)
    if "commit" in argv or " commit " in f" {joined} ":
        return "no_verify_commit"
    return "no_verify_push"


def check_git_argv_escape(
    root: Path,
    argv: list[str],
    escape_id: str | None,
) -> tuple[bool, str]:
    """D4 fail-closed for agent git wrappers: --no-verify only with allowlist id."""
    if not argv_has_no_verify(argv):
        return True, "no_escape_needed"
    flag = no_verify_flag_for_argv(argv)
    return check_escape_hatch(root, flag=flag, escape_id=escape_id)


# ── 72h observation window ───────────────────────────────────────────


def start_conflict_window(root: Path) -> dict[str, Any]:
    path = delivery_path(
        root, "conflict_window", ".omo/_delivery/swarm-conflicts/window.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    reg = load_registry(root)
    hours = int((reg.get("observation") or {}).get("window_hours") or 72)
    now = _utc_now()
    payload = {
        "window_start": _utc_iso(now),
        "window_hours": hours,
        "window_end_target": _utc_iso(now + timedelta(hours=hours)),
        "gate": "g-conv.7",
        "adr": "0220",
        "note": "M1 concurrent_main_conflict_zero observation; pass only after full window with count=0",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def read_conflict_events(root: Path, since_iso: str | None = None) -> list[dict]:
    events_path = delivery_path(
        root, "conflict_events", ".omo/_delivery/swarm-conflicts/events.jsonl"
    )
    if not events_path.is_file():
        return []
    since = None
    if since_iso:
        try:
            since = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
        except ValueError:
            since = None
    out: list[dict] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since:
            try:
                ts = datetime.fromisoformat(str(rec.get("ts", "")).replace("Z", "+00:00"))
            except ValueError:
                continue
            if ts < since:
                continue
        out.append(rec)
    return out


_PR_SUBJECT_RE = re.compile(r"\(#\d+\)\s*$")


def scan_orphan_commits(
    root: Path,
    since_iso: str | None,
    *,
    emit: bool = False,
) -> list[dict[str, Any]]:
    """Detect likely orphan / direct-to-main commits since window start.

    Heuristics (conservative):
      1) Local main commits not on origin/main (unpushed direct work on shared main)
      2) origin/main first-parent non-merge commits since window whose subject
         does NOT end with (#NNN) GitHub PR trailer — possible direct push or
         non-PR land (squash PR subjects usually include (#N)).

    Returns list of {sha, subject, kind_detail} without necessarily emitting.
    """
    orphans: list[dict[str, Any]] = []
    since_arg = []
    if since_iso:
        # git --since accepts ISO-ish
        since_arg = [f"--since={since_iso.replace('T', ' ').replace('Z', '')}"]

    def _git(args: list[str]) -> str:
        try:
            r = subprocess.run(
                ["git", *args],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            return r.stdout if r.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            return ""

    # (1) unpushed on local main
    unpushed = _git(
        ["log", "origin/main..main", "--first-parent", "--no-merges", "--format=%H\t%s"]
        + since_arg
    )
    for line in unpushed.splitlines():
        if not line.strip() or "\t" not in line:
            continue
        sha, subj = line.split("\t", 1)
        orphans.append(
            {
                "sha": sha[:12],
                "subject": subj,
                "detail": "unpushed_local_main",
            }
        )

    # (2) origin/main first-parent without PR trailer
    remote_log = _git(
        [
            "log",
            "origin/main",
            "--first-parent",
            "--no-merges",
            "--format=%H\t%s",
            *since_arg,
        ]
    )
    for line in remote_log.splitlines():
        if not line.strip() or "\t" not in line:
            continue
        sha, subj = line.split("\t", 1)
        if _PR_SUBJECT_RE.search(subj):
            continue
        # skip known automation chore merges without PR number only if empty
        orphans.append(
            {
                "sha": sha[:12],
                "subject": subj,
                "detail": "main_no_pr_trailer",
            }
        )

    # de-dupe by sha
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for o in orphans:
        if o["sha"] in seen:
            continue
        seen.add(o["sha"])
        uniq.append(o)

    if emit:
        existing = {
            (e.get("detail") or {}).get("sha")
            for e in read_conflict_events(root, since_iso=since_iso)
            if e.get("kind") == "orphan_commit"
        }
        for o in uniq:
            if o["sha"] in existing:
                continue
            emit_conflict_event(
                root,
                "orphan_commit",
                {"sha": o["sha"], "subject": o["subject"], "detail": o["detail"]},
            )
    return uniq


def conflict_window_status(
    root: Path,
    *,
    scan_orphans: bool = True,
    emit_orphans: bool = False,
) -> dict[str, Any]:
    path = delivery_path(
        root, "conflict_window", ".omo/_delivery/swarm-conflicts/window.json"
    )
    if not path.is_file():
        return {
            "window_start": None,
            "window_end_or_null": None,
            "elapsed_hours": 0.0,
            "conflict_count": 0,
            "event_breakdown": {},
            "m1_conflict_zero_verdict": "window_open",
            "note": "window not started; call swarm-discipline-cli.py window-start",
        }
    meta = json.loads(path.read_text(encoding="utf-8"))
    start_s = meta.get("window_start")
    try:
        start = datetime.fromisoformat(str(start_s).replace("Z", "+00:00"))
    except ValueError:
        start = _utc_now()
    now = _utc_now()
    elapsed = (now - start).total_seconds() / 3600.0
    hours = float(meta.get("window_hours") or 72)
    # Advisory orphan scan by default (do NOT auto-emit into M1 counter —
    # heuristics can false-positive). Use emit_orphans=True to record.
    orphan_hits: list[dict[str, Any]] = []
    if scan_orphans:
        orphan_hits = scan_orphan_commits(root, start_s, emit=emit_orphans)
    events = read_conflict_events(root, since_iso=start_s)
    breakdown: dict[str, int] = {}
    for e in events:
        k = str(e.get("kind") or "unknown")
        breakdown[k] = breakdown.get(k, 0) + 1
    count = len(events)
    if elapsed < hours:
        verdict = "window_open"
    elif count == 0:
        verdict = "pass"
    else:
        verdict = "fail"
    return {
        "window_start": start_s,
        "window_end_or_null": None if elapsed < hours else _utc_iso(now),
        "window_hours_target": hours,
        "elapsed_hours": round(elapsed, 3),
        "conflict_count": count,
        "event_breakdown": breakdown,
        "m1_conflict_zero_verdict": verdict,
        "orphan_commits_scanned": orphan_hits[:20],
        "events_sample": events[:20],
    }


def main_probe() -> int:
    """Minimal self-check when executed as script."""
    root = Path(__file__).resolve().parents[2]
    print(json.dumps({"root": str(root), "registry": load_registry(root).get("version")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_probe())
