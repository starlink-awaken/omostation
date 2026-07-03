#!/usr/bin/env python3
"""Audit write ownership of staged files to prevent mysterious rollbacks and manual overwrites."""
import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
OWNERS_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "write-owners.yaml"


def get_git_user() -> str:
    """获取当前 Git 提交用户名."""
    try:
        res = subprocess.run(
            ["git", "config", "user.name"],
            cwd=WORKSPACE, capture_output=True, text=True, check=False
        )
        return res.stdout.strip()
    except Exception:
        return ""


def get_staged_files() -> list[str]:
    """获取暂存区的文件列表."""
    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=WORKSPACE, capture_output=True, text=True, check=False
        )
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def load_owners() -> list[dict]:
    """读取 write-owners.yaml."""
    if not OWNERS_YAML.is_file():
        return []
    import yaml  # noqa: PLC0415
    try:
        data = yaml.safe_load(OWNERS_YAML.read_text(encoding="utf-8")) or {}
        return data.get("write_owners") or []
    except Exception as e:
        print(f"⚠️ 读取 write-owners.yaml 失败: {e}", file=sys.stderr)
        return []


def match_path(file_path: str, pattern: str) -> bool:
    """ fnmatch 路径匹配."""
    return fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(file_path, f"*/{pattern}")


# 显式身份白名单 (2026-07-03 修订 r2: 原"用户名含 agent/crush/serena 即豁免"是子串匹配,
# user.name="X-Plane Audit Agent" 含 Agent → 全部提交被豁免, 审计器空转;
# 反之人类别名 starlink-awaken 不在名单会被误报。改为精确集合。
# ⚠️ 本修复曾于 07-03 上午被未知进程回滚一次 (回滚异常第三案), 若再次消失请查 git log 恢复。)
HUMAN_ALIASES = {"夏明星", "xiamingxing", "starlink-awaken", "owner"}
AGENT_IDENTITIES = {"x-plane audit agent", "claude", "claude cowork", "serena", "crush"}


def audit_staged(staged_files: list[str], owners: list[dict], current_user: str) -> list[str]:
    """审计暂存区文件，返回违规信息列表."""
    violations = []
    is_agent_run = bool(os.environ.get("AGENT_WORKFLOW_RUN_ID"))
    is_ci = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
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
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit staged changes for Write Ownership")
    parser.add_argument("--staged", action="store_true", help="Audit staged files in git index")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args()

    staged_files = get_staged_files() if args.staged else []
    owners = load_owners()
    current_user = get_git_user() or "unknown"

    violations = audit_staged(staged_files, owners, current_user)

    report = {
        "ok": len(violations) == 0,
        "current_user": current_user,
        "staged_files_audited": len(staged_files),
        "violations": violations
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if report["ok"]:
            print(f"✅ Write-Owner Audit: PASS (Audited {len(staged_files)} files, user={current_user})")
        else:
            print("🚨 Write-Owner Audit: FAIL (Ownership Violations Detected)", file=sys.stderr)
            for v in violations:
                print(f"   - {v}", file=sys.stderr)
            print("   Rule: Principal B - Only declared owner can modify state files.", file=sys.stderr)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
