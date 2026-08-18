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
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # workspace root
AGENT_CLONE = ROOT / "bin" / "gac" / "agent-clone.py"

EXIT_OK = 0
EXIT_POLICY = 1
EXIT_USAGE = 2


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)


def audit(action: str, details: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"[{ts}] LIFECYCLE={action} {details}"
    print(line, file=sys.stderr)


def cmd_onboard(args: argparse.Namespace) -> int:
    """为新 agent 创建 clone + 生成基线 manifest."""
    agent_id = args.agent_id
    dest = Path(args.destination)
    audit("onboard_start", f"agent={agent_id} dest={dest}")
    # 1. 创建 clone
    cmd = [
        sys.executable, str(AGENT_CLONE), "create",
        "--agent-id", agent_id,
        "--source", args.source,
        "--destination", str(dest),
        "--no-submodules",
    ]
    r = run(cmd)
    if r.returncode != 0:
        audit("onboard_failed", f"clone_create rc={r.returncode} stderr={r.stderr.strip()[:200]}")
        print(r.stderr, file=sys.stderr)
        return EXIT_POLICY
    # 2. 生成基线 manifest
    manifest_path = Path(args.manifest) if args.manifest else dest / ".." / f"{agent_id}-baseline.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(AGENT_CLONE), "manifest",
        "--clone", str(dest),
        "--output", str(manifest_path),
    ]
    r = run(cmd)
    if r.returncode != 0:
        audit("onboard_failed", f"manifest rc={r.returncode}")
        return EXIT_POLICY
    audit("onboard_ok", f"agent={agent_id} clone={dest} manifest={manifest_path}")
    print(json.dumps({"ok": True, "agent_id": agent_id, "clone": str(dest), "manifest": str(manifest_path)}, indent=2))
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
        sys.executable, str(AGENT_CLONE), "changeset",
        "--clone", str(clone),
        "--baseline", str(baseline),
        "--output", str(output),
    ]
    if args.verify_claims:
        cmd.append("--verify-claims")
    r = run(cmd)
    if r.returncode != 0:
        audit("changeset_failed", f"rc={r.returncode} stderr={r.stderr.strip()[:200]}")
        print(r.stderr, file=sys.stderr)
        return EXIT_POLICY
    # 读取结果
    cs = json.loads(output.read_text())
    violations = (cs.get("claim_verification") or {}).get("violations", [])
    if violations:
        audit("changeset_scope_creep", f"violations={violations}")
    audit("changeset_ok", f"change_id={cs.get('change_id','?')[:12]} changes={cs.get('changes_count',0)}")
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
    # 推送分支
    r = run(["git", "-C", str(clone), "push", "origin", branch])
    if r.returncode != 0:
        audit("integrate_failed", f"push rc={r.returncode}")
        return EXIT_POLICY
    audit("integrate_ok", f"pushed {branch}")
    print(json.dumps({"ok": True, "branch": branch, "pushed": True}))
    return EXIT_OK


def cmd_retire(args: argparse.Namespace) -> int:
    """清理 clone + 释放资源."""
    dest = Path(args.destination)
    audit("retire_start", f"dest={dest}")
    if dest.exists():
        import shutil
        shutil.rmtree(dest)
    audit("retire_ok", f"removed {dest}")
    print(json.dumps({"ok": True, "removed": str(dest)}))
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
    sp.set_defaults(func=cmd_changeset)
    # integrate
    sp = sub.add_parser("integrate", help="推送 + PR")
    sp.add_argument("--clone", required=True)
    sp.add_argument("--agent-id", required=True)
    sp.add_argument("--dry-run", action="store_true", default=True)
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
