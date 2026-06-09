#!/usr/bin/env python3
"""
织星 MOF — 事件桥接器 (mof-events)
===================================
将 L0 治理事件发布到统一事件流。可被 Agora/I0 消费。

事件类型:
  - l0.drift.detected      M1↔M0 漂移
  - l0.gate.violation      变更门禁违规
  - l0.protocol.decay      协议衰减告警
  - l0.sla.stale           SLA 逾期
  - l0.bootstrap.fail      自举失败
  - l0.enforce.violation   层合规违规

输出: JSONL 事件流 → stdout · Agora event bus · SSB log

用法:
    python3 mof-events.py                    # 生成当前事件
    python3 mof-events.py --watch            # 持续监听 (daemon 模式)
    python3 mof-events.py --publish          # 发布到 Agora
    python3 mof-events.py --json             # JSON 输出
"""

import json
import yaml
import subprocess
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
L0_TOOLS = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools"
EVENTS_LOG = HOME / ".ecos" / "events.jsonl"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def run_tool(name: str, args: list = None) -> dict:
    tool = L0_TOOLS / f"{name}.py"
    if not tool.exists():
        return {"error": f"tool not found: {name}"}
    cmd = ["python3", str(tool), "--json"]
    if args:
        cmd.extend(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception:
        pass
    return {}


def collect_events() -> list[dict]:
    """收集所有 L0 治理事件"""
    events = []

    # 1. Audit drift
    audit = run_tool("mof-audit")
    drifts = audit.get("drifts", audit.get("items", []))
    for d in drifts[:5]:
        events.append(
            {
                "type": "l0.drift.detected",
                "severity": d.get("severity", "medium"),
                "source": "mof-audit",
                "detail": d.get("drift", str(d)),
                "timestamp": now_iso(),
            }
        )

    # 2. Gate violations
    gate = run_tool("mof-gate")
    violations = gate.get("items", [])
    for v in violations[:5]:
        events.append(
            {
                "type": "l0.gate.violation",
                "severity": v.get("severity", "medium"),
                "source": "mof-gate",
                "detail": v.get("detail", str(v)),
                "asset": v.get("asset", ""),
                "timestamp": now_iso(),
            }
        )

    # 3. Protocol decay (from M0 snapshot)
    m0_file = (
        HOME
        / "Workspace"
        / "projects"
        / "ecos"
        / "src"
        / "ecos"
        / "ssot"
        / "mof"
        / "m0"
        / "snapshot.yaml"
    )
    if m0_file.exists():
        m0 = yaml.safe_load(open(m0_file))
        protocols = m0.get("protocols", {})
        for pid, state in protocols.items():
            if state.get("status") in ("aging", "expired"):
                events.append(
                    {
                        "type": "l0.protocol.decay",
                        "severity": "high"
                        if state["status"] == "expired"
                        else "medium",
                        "source": "mof-sla",
                        "detail": f"{pid}: {state.get('remaining_pct', 0):.0f}% remaining ({state.get('age_days', 0)}d)",
                        "protocol": pid,
                        "timestamp": now_iso(),
                    }
                )

    # 4. Bootstrap status
    bootstrap = run_tool("mof-bootstrap")
    if bootstrap and not bootstrap.get("healthy", True):
        events.append(
            {
                "type": "l0.bootstrap.fail",
                "severity": "critical",
                "source": "mof-bootstrap",
                "detail": "L0 自举发现问题",
                "timestamp": now_iso(),
            }
        )

    return events


def publish_events(events: list[dict]):
    """发布事件到事件流"""
    # Append to JSONL log
    EVENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(EVENTS_LOG, "a") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    # Try Agora event bus
    agora_events = HOME / "Workspace" / "agora" / "src" / "agora" / "agora-events.json"
    if agora_events.exists():
        try:
            existing = json.load(open(agora_events))
            if isinstance(existing, list):
                existing.extend(events)
                with open(agora_events, "w") as f:
                    json.dump(
                        existing[-100:], f, ensure_ascii=False, indent=2
                    )  # Keep last 100
                print(f"  ✅ 已发布到 Agora event bus ({len(events)} events)")
        except Exception:
            pass

    return len(events)


def format_events(events: list[dict]) -> str:
    lines = [
        "=" * 64,
        "  织星 MOF — 治理事件",
        "=" * 64,
        f"  时间: {now_iso()[:19]}",
        f"  事件: {len(events)} 条",
        "",
    ]

    by_type = {}
    for e in events:
        by_type.setdefault(e["type"], []).append(e)

    for etype in sorted(by_type.keys()):
        evts = by_type[etype]
        icon = {"critical": "🔴", "high": "🟡", "medium": "🟢", "low": "⚪"}.get(
            evts[0].get("severity", ""), "❓"
        )
        lines.append(f"  {icon} {etype} ({len(evts)} 条)")
        for e in evts[:3]:
            lines.append(f"     {e['detail'][:80]}")
    lines.append("")
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    events = collect_events()

    if args.publish:
        published = publish_events(events)
        print(f"✅ 已发布 {published} 个事件")
    elif args.json:
        print(
            json.dumps(
                {"events": len(events), "items": events}, ensure_ascii=False, indent=2
            )
        )
    else:
        print(format_events(events))

    if args.watch:
        import time

        print("  🔍 持续监听中 (Ctrl+C 停止)...")
        try:
            while True:
                time.sleep(3600)  # Every hour
                events = collect_events()
                publish_events(events)
        except KeyboardInterrupt:
            print("\n  ⏹️  已停止")


if __name__ == "__main__":
    main()
