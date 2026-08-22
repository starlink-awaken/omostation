#!/usr/bin/env python3
"""agent-clone-onboard.py — 自动化 delivery-attempt clone 入列.

检测活跃 workflow run → 为每个 delivery attempt 创建独立 clone.

核心逻辑:
1. 扫描 .omo/_delivery/agent-workflows/runs/ 中的活跃 run
2. 提取稳定 actor_id 与一次性 delivery_attempt_id
3. 检查 ~/agents/<actor>/attempts/<attempt>/ws 是否已存在 clone
4. 缺失则自动 onboard (create + manifest)
5. 生成入列报告 (JSON)

幂等: 同一 workflow run 派生同一 attempt；不同 run 不会折叠到 actor 级 clone.
安全: dry-run 默认, 需 --apply 才真正创建.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_CLONE = ROOT / "bin" / "gac" / "agent-clone.py"
LIFECYCLE = ROOT / "bin" / "gac" / "clone-lifecycle.py"
RUNS_DIR = ROOT / ".omo" / "_delivery" / "agent-workflows" / "runs"
AGENTS_DIR = Path.home() / "agents"

EXIT_OK = 0
EXIT_POLICY = 1
IDENTITY_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def detect_active_agents() -> dict[str, dict]:
    """从活跃 workflow runs 检测 agent."""
    agents: dict[str, dict] = {}
    if not RUNS_DIR.is_dir():
        return agents
    for run_file in sorted(RUNS_DIR.glob("*.yaml"), reverse=True)[:50]:
        try:
            import yaml
            data = yaml.safe_load(run_file.read_text()) or {}
        except Exception:
            continue
        status = str(data.get("status", "")).lower()
        if status in ("closed", "closeout", "done", "failed", "cancelled"):
            continue
        # 提取 agent_id: 从 run_id 前缀 (格式: 20260803T135152Z-<workflow>-<uuid>)
        run_id = data.get("run_id", "")
        context = data.get("context", {}) or {}
        agent_id = context.get("agent_id") or context.get("actor") or extract_agent_from_runid(run_id)
        if not isinstance(agent_id, str) or not IDENTITY_COMPONENT_RE.fullmatch(agent_id):
            continue
        explicit_attempt = context.get("delivery_attempt_id")
        delivery_attempt_id = (
            explicit_attempt
            if isinstance(explicit_attempt, str)
            and IDENTITY_COMPONENT_RE.fullmatch(explicit_attempt)
            else attempt_id_from_run(run_id)
        )
        attempt_key = f"{agent_id}:{delivery_attempt_id}"
        if attempt_key not in agents:
            agents[attempt_key] = {
                "agent_id": agent_id,
                "delivery_attempt_id": delivery_attempt_id,
                "run_id": run_id,
                "workflow": data.get("workflow_id", "?"),
                "objective": (data.get("objective", "") or "")[:80],
                "source_run": str(run_file.name),
            }
    return agents


def attempt_id_from_run(run_id: str) -> str:
    """Derive one stable, ref-safe attempt identity from a workflow run."""
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:16]
    return f"run-{digest}"


def new_manual_attempt_id() -> str:
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return f"manual-{timestamp}-{secrets.token_hex(4)}"


def extract_agent_from_runid(run_id: str) -> str:
    """从 run_id 提取 agent 标识."""
    # 格式: 20260803T135152Z-<workflow>-<uuid>
    parts = run_id.split("-")
    if len(parts) >= 2:
        return parts[1]
    return ""


def clone_exists(agent_id: str, delivery_attempt_id: str) -> bool:
    """检查 delivery attempt 是否已有身份完全匹配的独立 clone."""
    identity_file = (
        AGENTS_DIR
        / agent_id
        / "attempts"
        / delivery_attempt_id
        / "ws"
        / ".git"
        / "agent-clone-identity.json"
    )
    try:
        identity = json.loads(identity_file.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return (
        identity.get("schema") == "agent-clone-identity/v2"
        and identity.get("agent_id") == agent_id
        and identity.get("actor_id") == agent_id
        and identity.get("delivery_attempt_id") == delivery_attempt_id
        and identity.get("working_branch")
        == f"agent/{agent_id}--{delivery_attempt_id}"
    )


def onboard_agent(
    agent_id: str,
    delivery_attempt_id: str | None = None,
    dry_run: bool = True,
    profile: str = "governance",
) -> dict:
    """为单个 agent 创建 clone."""
    delivery_attempt_id = delivery_attempt_id or new_manual_attempt_id()
    dest = AGENTS_DIR / agent_id / "attempts" / delivery_attempt_id / "ws"
    result = {
        "agent_id": agent_id,
        "actor_id": agent_id,
        "delivery_attempt_id": delivery_attempt_id,
        "destination": str(dest),
        "dry_run": dry_run,
    }
    if dry_run:
        result["status"] = "would_create"
        return result
    # 确保父目录存在
    dest.parent.mkdir(parents=True, exist_ok=True)
    # 使用 clone-lifecycle onboard
    cmd = [
        sys.executable, str(LIFECYCLE), "onboard",
        "--agent-id", agent_id,
        "--delivery-attempt-id", delivery_attempt_id,
        "--source", str(ROOT),
        "--destination", str(dest),
        "--profile", profile,
    ]
    r = run(cmd)
    result["returncode"] = r.returncode
    result["status"] = "created" if r.returncode == 0 else "failed"
    if r.returncode != 0:
        result["error"] = r.stderr.strip()[:200]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="真正创建 clone (默认 dry-run)")
    parser.add_argument("--agent-id", help="仅处理指定 agent")
    parser.add_argument(
        "--delivery-attempt-id",
        help="manual delivery attempt; generated when omitted",
    )
    parser.add_argument(
        "--profile",
        choices=("root-only", "governance", "full"),
        default="governance",
        help="clone submodule profile (default: governance)",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)
    dry_run = not args.apply
    # 检测 agent
    if args.agent_id:
        attempt_id = args.delivery_attempt_id or new_manual_attempt_id()
        agents = {
            f"{args.agent_id}:{attempt_id}": {
                "agent_id": args.agent_id,
                "delivery_attempt_id": attempt_id,
                "source_run": "manual",
            }
        }
    else:
        agents = detect_active_agents()
    if not agents:
        print("未检测到活跃 agent", file=sys.stderr)
        return EXIT_OK
    # 处理每个 agent
    results = []
    existing = 0
    for _attempt_key, info in sorted(agents.items()):
        agent_id = info["agent_id"]
        delivery_attempt_id = info["delivery_attempt_id"]
        if clone_exists(agent_id, delivery_attempt_id):
            existing += 1
            results.append(
                {
                    "agent_id": agent_id,
                    "delivery_attempt_id": delivery_attempt_id,
                    "status": "exists",
                }
            )
            continue
        r = onboard_agent(
            agent_id,
            delivery_attempt_id=delivery_attempt_id,
            dry_run=dry_run,
            profile=args.profile,
        )
        r.update(info)
        results.append(r)
    # 输出报告
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dry_run": dry_run,
        "total_active_agents": len(agents),
        "existing_clones": existing,
        "processed": len([r for r in results if r["status"] != "exists"]),
        "results": results,
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"活跃 agent: {len(agents)}, 已有 clone: {existing}, 需创建: {report['processed']}")
        for r in results:
            status = r["status"]
            agent = r["agent_id"]
            attempt = r["delivery_attempt_id"]
            if status == "exists":
                print(f"  ✅ {agent}/{attempt}: 已有 clone")
            elif status == "would_create":
                print(f"  📋 {agent}/{attempt}: 待创建 (dry-run)")
            elif status == "created":
                print(f"  🆕 {agent}/{attempt}: 已创建")
            elif status == "failed":
                print(f"  ❌ {agent}/{attempt}: 失败 - {r.get('error', '?')[:60]}")
    # 如果有失败返回非零
    failed = [r for r in results if r.get("status") == "failed"]
    return EXIT_POLICY if failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
