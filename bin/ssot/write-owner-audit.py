#!/usr/bin/env python3
"""Audit write ownership of a change set to prevent mysterious rollbacks and manual overwrites.

采集面有两种: `--staged` (git 索引) 与 `--range <base>..<head>` (交付的改动集)。
索引面在门禁实际运行的场合 (CI checkout 之后、post-commit、手工跑门禁) 恒为空集,
所以真正能看见交付的是范围面。
"""

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
OWNERS_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "write-owners.yaml"


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
    if args.staged:
        files = get_staged_files()
    else:
        try:
            spec = resolve_range(args.git_range)
            files = get_range_files(spec)
        except RuntimeError as e:
            # 采集面拿不到 ≠ 通过: 记下原因, 报告里如实呈现.
            spec, files, unavailable = args.git_range, [], str(e)
        face = f"range:{spec}"
        env_exemption = False

    violations = (
        []
        if unavailable
        else audit_staged(files, owners, current_user, apply_env_exemption=env_exemption)
    )

    report = {
        "ok": not violations and not unavailable,
        "current_user": current_user,
        "face": face,
        "files_audited": len(files),
        "rules_loaded": len(owners),
        "staged_files_audited": len(files) if args.staged else 0,
        "violations": violations,
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
