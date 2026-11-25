#!/usr/bin/env python3
"""Audit write ownership of a change set to prevent mysterious rollbacks and manual overwrites.

采集面有两种: `--staged` (git 索引) 与 `--range <base>..<head>` (交付的改动集)。
索引面在门禁实际运行的场合 (CI checkout 之后、post-commit、手工跑门禁) 恒为空集,
所以真正能看见交付的是范围面。
"""

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
OWNERS_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "write-owners.yaml"
_ALLOWED_RUN_STATUSES = frozenset({"active", "running", "in_progress", "ok", "completed", "closed", "done", "verified"})
_CLAIM_FRESHNESS_DAYS = 14


def get_git_user() -> str:
    """获取当前 Git 提交用户名."""
    try:
        res = subprocess.run(
            ["git", "config", "user.name"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=False,
        )
        return res.stdout.strip()
    except Exception:
        return ""


def get_staged_files() -> list[str]:
    """获取暂存区的文件列表."""
    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=False,
        )
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def resolve_range(spec: str) -> str:
    """把 `--range` 的取值解析成一个可用的 git 范围.

    `auto` 的顺序: PUSH_RANGE (ADR-4443 v9 的 pre-push 约定) → `origin/main...HEAD`。
    解不出就抛，不返回空串 —— 返回空会让调用方以为「审计通过」。
    """
    if spec != "auto":
        return spec
    env = os.environ.get("PUSH_RANGE", "").strip()
    if env:
        return env
    res = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "origin/main"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode == 0:
        return "origin/main...HEAD"
    raise RuntimeError("无法定基: PUSH_RANGE 未设置且 origin/main 不可解析")


def get_range_files(spec: str) -> list[str]:
    """范围面的聚合改动文件集.

    这里用聚合口径 (`git diff --name-only <spec>`) 是**有意**的: write-ownership 判的是
    「这个文件归谁」, 按文件即可; 而 bin/change-lane-check.py 的 --range 走 per-commit,
    因为那条规则原文是「每 commit 单 lane」。两种粒度服务两条不同的规则, 不要互相照搬。
    """
    res = subprocess.run(
        ["git", "diff", "--name-only", spec],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"git diff --name-only {spec} 失败: {(res.stderr or res.stdout).strip()}"
        )
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]


def load_owners() -> list[dict]:
    """读取 write-owners.yaml."""
    if not OWNERS_YAML.is_file():
        return []
    import yaml

    try:
        data = yaml.safe_load(OWNERS_YAML.read_text(encoding="utf-8")) or {}
        return data.get("write_owners") or []
    except Exception as e:
        print(f"⚠️ 读取 write-owners.yaml 失败: {e}", file=sys.stderr)
        return []


def match_path(file_path: str, pattern: str) -> bool:
    """fnmatch 路径匹配."""
    return fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(file_path, f"*/{pattern}")


def _is_real_checkout() -> bool:
    return (WORKSPACE / "bin" / "lib" / "repo_root.py").is_file()


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path.expanduser().resolve())
        if key not in seen:
            seen.add(key)
            unique.append(path.expanduser())
    return unique


def _candidate_receipt_logs() -> list[Path]:
    override = os.environ.get("OMO_DEBT_RECEIPT_LOG", "").strip()
    if override:
        return [Path(override).expanduser()]
    candidates: list[Path] = []
    if _is_real_checkout():
        lib_dir = str(WORKSPACE / "bin" / "lib")
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        try:
            import repo_root

            candidates.append(repo_root.state_root() / ".omo" / "_delivery" / "omo-debt-writes.jsonl")
            candidates.append(
                Path.home() / ".local" / "state" / "omostation" / "prod" / ".omo" / "_delivery" / "omo-debt-writes.jsonl"
            )
            candidates.append(repo_root.code_root() / ".omo" / "_delivery" / "omo-debt-writes.jsonl")
            try:
                candidates.append(repo_root.canonical_root() / ".omo" / "_delivery" / "omo-debt-writes.jsonl")
            except RuntimeError:
                pass
        except Exception:
            pass
    return _dedupe_paths(candidates)


def _candidate_runs_dirs() -> list[Path]:
    override = os.environ.get("OMO_WORKFLOW_RUNS_DIR", "").strip()
    if override:
        return [Path(override).expanduser()]
    candidates: list[Path] = []
    if _is_real_checkout():
        lib_dir = str(WORKSPACE / "bin" / "lib")
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        try:
            import repo_root

            candidates.append(repo_root.state_root() / ".omo" / "_delivery" / "agent-workflows" / "runs")
            candidates.append(
                Path.home()
                / ".local"
                / "state"
                / "omostation"
                / "prod"
                / ".omo"
                / "_delivery"
                / "agent-workflows"
                / "runs"
            )
            candidates.append(repo_root.code_root() / ".omo" / "_delivery" / "agent-workflows" / "runs")
            try:
                candidates.append(repo_root.canonical_root() / ".omo" / "_delivery" / "agent-workflows" / "runs")
            except RuntimeError:
                pass
        except Exception:
            pass
    return _dedupe_paths(candidates)


def _range_head_rev(spec: str) -> str:
    if "..." in spec:
        head = spec.split("...", 1)[1].strip()
        return head or "HEAD"
    if ".." in spec:
        head = spec.split("..", 1)[1].strip()
        return head or "HEAD"
    return "HEAD"


def _git_file_sha256(rel_path: str, rev: str) -> str | None:
    res = subprocess.run(
        ["git", "show", f"{rev}:{rel_path}"],
        cwd=WORKSPACE,
        capture_output=True,
        check=False,
    )
    if res.returncode != 0:
        return None
    return hashlib.sha256(res.stdout).hexdigest()


def _claim_covers_path(pattern: object, rel_path: str) -> bool:
    if not isinstance(pattern, str):
        return False
    pat = pattern.strip()
    while pat.startswith("./"):
        pat = pat[2:]
    pat = pat.lstrip("/")
    if not pat or pat in {".", "/", "*", "**", "**/*"}:
        return False
    if pat == rel_path:
        return True
    if pat.endswith("/") and rel_path.startswith(pat):
        return True
    has_glob = any(ch in pat for ch in "*?[")
    if not has_glob and rel_path.startswith(f"{pat}/"):
        return True
    if has_glob and pat.replace("*", "").replace("?", "").strip("/"):
        return fnmatch.fnmatch(rel_path, pat)
    return False


def _parse_iso_ts(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _run_is_fresh(data: dict, run_file: Path, cutoff: datetime) -> bool:
    for key in ("updated_at", "created_at"):
        ts = _parse_iso_ts(data.get(key))
        if ts is not None:
            return ts >= cutoff
    for claim in data.get("claims") or []:
        if isinstance(claim, dict):
            ts = _parse_iso_ts(claim.get("claimed_at"))
            if ts is not None:
                return ts >= cutoff
    try:
        return datetime.fromtimestamp(run_file.stat().st_mtime, tz=UTC) >= cutoff
    except OSError:
        return False


def _run_covers_path(data: dict, rel_path: str) -> bool:
    for claim in data.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        for claimed_path in claim.get("paths") or []:
            if _claim_covers_path(claimed_path, rel_path):
                return True
    return False


def _find_matching_broker_receipt(rel_path: str, blob_sha: str | None) -> dict | None:
    if not blob_sha:
        return None
    for log_path in _candidate_receipt_logs():
        if not log_path.is_file():
            continue
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            if entry.get("path") == rel_path and entry.get("sha256") == blob_sha:
                return {
                    "file": rel_path,
                    "kind": "broker_receipt",
                    "log": str(log_path),
                    "command": str(entry.get("command") or ""),
                    "sha256": blob_sha,
                }
    return None


def _find_matching_workflow_claim(rel_path: str) -> dict | None:
    import yaml

    run_id_env = os.environ.get("AGENT_WORKFLOW_RUN_ID", "").strip()
    cutoff = datetime.now(UTC) - timedelta(days=_CLAIM_FRESHNESS_DAYS)

    if run_id_env:
        for runs_dir in _candidate_runs_dirs():
            candidate = runs_dir / f"{run_id_env}.yaml"
            if not candidate.is_file():
                continue
            try:
                data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            status = str(data.get("status") or "").lower()
            if status and status not in _ALLOWED_RUN_STATUSES:
                continue
            if _run_covers_path(data, rel_path):
                return {
                    "file": rel_path,
                    "kind": "workflow_claim",
                    "run_id": str(data.get("run_id") or run_id_env),
                }
        return None

    for runs_dir in _candidate_runs_dirs():
        if not runs_dir.is_dir():
            continue
        for run_file in sorted(runs_dir.glob("*.yaml"), reverse=True):
            try:
                data = yaml.safe_load(run_file.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            status = str(data.get("status") or "").lower()
            if status not in _ALLOWED_RUN_STATUSES:
                continue
            if not _run_is_fresh(data, run_file, cutoff):
                continue
            if _run_covers_path(data, rel_path):
                return {
                    "file": rel_path,
                    "kind": "workflow_claim",
                    "run_id": str(data.get("run_id") or run_file.stem),
                }
    return None


def resolve_local_proof(rel_path: str, *, head_rev: str = "HEAD") -> dict | None:
    """Resolve local proof (escape / SHA-256 broker receipt / agent-workflow claim)."""
    escape_id = os.environ.get("SWARM_ESCAPE_ID", "").strip()
    if escape_id:
        return {"file": rel_path, "kind": "escape", "escape_id": escape_id}
    blob_sha = _git_file_sha256(rel_path, head_rev)
    receipt = _find_matching_broker_receipt(rel_path, blob_sha)
    if receipt is not None:
        return receipt
    return _find_matching_workflow_claim(rel_path)


# 显式身份白名单 (2026-07-03 修订 r2: 原"用户名含 agent/crush/serena 即豁免"是子串匹配,
# user.name="X-Plane Audit Agent" 含 Agent → 全部提交被豁免, 审计器空转;
# 反之人类别名 starlink-awaken 不在名单会被误报。改为精确集合。
# ⚠️ 本修复曾于 07-03 上午被未知进程回滚一次 (回滚异常第三案), 若再次消失请查 git log 恢复。)
HUMAN_ALIASES = {"夏明星", "xiamingxing", "starlink-awaken", "owner"}
AGENT_IDENTITIES = {"x-plane audit agent", "claude", "claude cowork", "serena", "crush"}


def audit_staged(
    staged_files: list[str],
    owners: list[dict],
    current_user: str,
    *,
    apply_env_exemption: bool = True,
) -> list[str]:
    """审计改动文件，返回违规信息列表.

    apply_env_exemption=True  —— 暂存区面的历史语义: CI / AGENT_WORKFLOW_RUN_ID 一律豁免。
    apply_env_exemption=False —— 交付范围面: 只看提交者身份集合，不看环境变量。交付出来的 diff
      是这条规则唯一看得见改动的时候，若仍按 env 豁免就等于永不生效。
    """
    violations = []
    is_agent_run = bool(os.environ.get("AGENT_WORKFLOW_RUN_ID")) if apply_env_exemption else False
    is_ci = (
        os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
    ) if apply_env_exemption else False
    user_lc = current_user.lower()

    # 合规自动化提交 = 带 run-id 的 agent workflow / CI / 精确匹配的已知 agent 身份
    is_system_committer = is_agent_run or is_ci or user_lc in AGENT_IDENTITIES
    is_human = user_lc in HUMAN_ALIASES

    for f in staged_files:
        for rule in owners:
            pattern = rule.get("path")
            owner_decl = rule.get("owner", "")
            if pattern and match_path(f, pattern):
                # 检查所有权
                owner_type, owner_name = (owner_decl.split(":", 1) + [""])[:2]

                if owner_type == "human":
                    # human 文件: 人类别名 或 可追溯的自动化 (run-id/CI/已知 agent) 均可
                    if not is_human and not is_system_committer:
                        violations.append(
                            f"File '{f}' is owned by human '{owner_name}', but committed by unrecognized '{current_user}' (加身份进 HUMAN_ALIASES/AGENT_IDENTITIES)"
                        )
                elif owner_type == "script" or owner_type == "daemon":
                    # script/daemon 拥有的文件，严禁人工在非 Agent-workflow 环境下手动 commit
                    if not is_system_committer:
                        violations.append(
                            f"File '{f}' is owned by system '{owner_type}:{owner_name}', manual modifications are forbidden outside agent workflows."
                        )

    seen: set[str] = set()
    unique = []
    for v in violations:
        # 同一文件可同时命中 `.omo/debt/*` 与 `.omo/debt/**` 两条规则, 文案相同 ⇒ 去重,
        # 否则违规条数是文件数的两倍, 读数会被当成规模来引用。
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def audit_with_exemptions(
    files: list[str],
    owners: list[dict],
    current_user: str,
    *,
    apply_env_exemption: bool = True,
    verify_local_proof: bool = False,
    head_rev: str = "HEAD",
) -> tuple[list[str], list[dict]]:
    """审计改动文件，支持可选的本地证据免除 (broker SHA 回执 / workflow claim / escape)."""
    if not verify_local_proof:
        return audit_staged(files, owners, current_user, apply_env_exemption=apply_env_exemption), []

    is_agent_run = bool(os.environ.get("AGENT_WORKFLOW_RUN_ID")) if apply_env_exemption else False
    is_ci = (
        os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
    ) if apply_env_exemption else False
    user_lc = current_user.lower()
    is_system_committer = is_agent_run or is_ci or user_lc in AGENT_IDENTITIES
    is_human = user_lc in HUMAN_ALIASES

    violations: list[str] = []
    exemptions: list[dict] = []
    proof_cache: dict[str, dict | None] = {}
    recorded_exemptions: set[tuple[str, str]] = set()

    for f in files:
        for rule in owners:
            pattern = rule.get("path")
            owner_decl = rule.get("owner", "")
            if not (pattern and match_path(f, pattern)):
                continue
            owner_type, owner_name = (owner_decl.split(":", 1) + [""])[:2]
            if owner_type == "human":
                if not is_human and not is_system_committer:
                    violations.append(
                        f"File '{f}' is owned by human '{owner_name}', but committed by unrecognized '{current_user}' (加身份进 HUMAN_ALIASES/AGENT_IDENTITIES)"
                    )
            elif owner_type in {"script", "daemon"} and not is_system_committer:
                if f not in proof_cache:
                    proof_cache[f] = resolve_local_proof(f, head_rev=head_rev)
                proof = proof_cache[f]
                if proof is not None:
                    key = (f, str(proof.get("kind") or ""))
                    if key not in recorded_exemptions:
                        recorded_exemptions.add(key)
                        exemptions.append(proof)
                else:
                    violations.append(
                        f"File '{f}' is owned by system '{owner_type}:{owner_name}', "
                        "manual modifications are forbidden outside agent workflows "
                        "(请用 omo-debt CLI 写入，或先用 bin/agent-workflow.py claim 认领路径)."
                    )

    seen: set[str] = set()
    unique: list[str] = []
    for v in violations:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique, exemptions


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit write ownership of a change set")
    parser.add_argument("--staged", action="store_true", help="Audit staged files in git index")
    parser.add_argument(
        "--range",
        dest="git_range",
        default="",
        help=(
            "Audit files changed in a git range (e.g. base..head) or 'auto' "
            "(PUSH_RANGE, then origin/main...HEAD). Ownership is judged per file, "
            "so this face is aggregate."
        ),
    )
    parser.add_argument(
        "--verify-local-proof",
        action="store_true",
        help="Verify local broker SHA-256 receipts or agent-workflow claims for range mode",
    )
    parser.add_argument("--advisory", action="store_true", help="Always exit 0")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args()

    if args.staged and args.git_range:
        print(
            "❌ --staged 与 --range 的豁免语义不同 (前者按环境, 后者按身份), 不能同时给。",
            file=sys.stderr,
        )
        return 2
    if not args.staged and not args.git_range:
        print("❌ 必须显式指定采集面: --staged 或 --range <spec>.", file=sys.stderr)
        return 2

    owners = load_owners()
    current_user = get_git_user() or "unknown"

    face = "staged"
    env_exemption = True
    unavailable = ""
    head_rev = "HEAD"
    if args.staged:
        files = get_staged_files()
    else:
        try:
            spec = resolve_range(args.git_range)
            head_rev = _range_head_rev(spec)
            files = get_range_files(spec)
        except RuntimeError as e:
            # 采集面拿不到 ≠ 通过: 记下原因, 报告里如实呈现.
            spec, files, unavailable = args.git_range, [], str(e)
        face = f"range:{spec}"
        env_exemption = False

    if unavailable:
        violations, verified_exemptions = [], []
    else:
        violations, verified_exemptions = audit_with_exemptions(
            files,
            owners,
            current_user,
            apply_env_exemption=env_exemption,
            verify_local_proof=args.verify_local_proof and not args.staged,
            head_rev=head_rev,
        )

    report = {
        "ok": not violations and not unavailable,
        "current_user": current_user,
        "face": face,
        "files_audited": len(files),
        "rules_loaded": len(owners),
        "staged_files_audited": len(files) if args.staged else 0,
        "violations": violations,
        "verified_exemptions": verified_exemptions,
    }
    if unavailable:
        report["face_unavailable"] = unavailable

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if unavailable:
            print(f"⚠️ Write-Owner Audit: 采集面不可用 —— {unavailable}", file=sys.stderr)
        elif not violations:
            print(
                f"✅ Write-Owner Audit: PASS (face={face}, audited={len(files)} files, "
                f"rules={len(owners)}, user={current_user})"
            )
        else:
            tag = "ADVISORY" if args.advisory else "FAIL"
            print(f"🚨 Write-Owner Audit: {tag} (Ownership Violations Detected)", file=sys.stderr)
            for v in violations:
                print(f"   - {v}", file=sys.stderr)
            print(
                f"   Rule: Principal B - Only declared owner can modify state files. (face={face})",
                file=sys.stderr,
            )

    if args.advisory:
        return 0
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
