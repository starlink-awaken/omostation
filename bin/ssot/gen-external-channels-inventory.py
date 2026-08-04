#!/usr/bin/env python3
"""External Channels Inventory 生成器 (ECCP P0).

聚合 3 源 → .omo/_truth/registry/external-channels.yaml (Backstage 式 inventory SSOT).
对标: Backstage software catalog (集中 inventory + 关系图).

源:
  1. iris external.resources (cd kairon + uv entry_points) — iris 连接器 (exposed)
  2. runtime/scripts ingest/fetch 脚本 — 散落外源 (orphan, 待 P3 收编)
  3. mesh external-resource-pack-proposals — 外源 pack 提案 (proposal)

用法:
  python3 bin/ssot/gen-external-channels-inventory.py
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
KAIRON = WORKSPACE / "projects/kairon"
RUNTIME_SCRIPTS = WORKSPACE / "projects/runtime/scripts"
MESH_PROPOSALS = WORKSPACE / ".omo/_knowledge/workflow-mesh/external-resource-pack-proposals"
OUTPUT = WORKSPACE / ".omo/_truth/registry/external-channels.yaml"


def scan_iris_resources() -> list[dict]:
    """扫 iris external.resources entry points + health (uv in kairon monorepo)."""
    code = (
        "import importlib.metadata as m\n"
        "for ep in m.entry_points(group='external.resources'):\n"
        "    try:\n"
        "        cls = ep.load()\n"
        "        inst = cls()\n"
        "        desc = inst.external_descriptor()\n"
        "        avail = desc.get('health', {}).get('available', False)\n"
        "        print(f'{ep.name}|{ep.value}|{avail}')\n"
        "    except Exception as e:\n"
        "        print(f'{ep.name}|{ep.value}|error:{type(e).__name__}')"
    )
    r = subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", "-c", code],
        cwd=KAIRON, capture_output=True, text=True, timeout=180, check=False,
    )
    channels: list[dict] = []
    for line in r.stdout.splitlines():
        line = line.strip()
        parts = line.split("|", 2)
        if len(parts) < 2:
            continue
        name, target = parts[0], parts[1]
        avail = parts[2] if len(parts) > 2 else "unknown"
        if avail.startswith("error:"):
            health = "error"
        elif avail == "True":
            health = "available"
        elif avail == "False":
            health = "unavailable"
        else:
            health = "unknown"
        channels.append({
            "id": f"iris:{name}",
            "kind": "knowledge_source",
            "provider": "kairon.iris",
            "connector": target,
            "entry_point": "external.resources",
            "health": health,
            "status": "exposed",
        })
    return channels


def scan_runtime_ingest() -> list[dict]:
    """扫 runtime/scripts ingest/fetch (散落 orphan, 待 P3 收编)."""
    channels: list[dict] = []
    if not RUNTIME_SCRIPTS.is_dir():
        return channels
    for p in sorted(RUNTIME_SCRIPTS.glob("*.py")):
        name = p.stem
        if not any(k in name for k in ("ingest", "fetch")):
            continue
        kind = "knowledge_source"
        if "oa" in name:
            kind = "knowledge_source"
        channels.append({
            "id": f"ingest:{name}",
            "kind": kind,
            "provider": "runtime.scripts",
            "connector": f"runtime/scripts/{p.name}",
            "entry_point": None,
            "health": "pending",
            "status": "orphan",
        })
    return channels


def scan_mesh_proposals() -> list[dict]:
    """扫 mesh external-resource-pack-proposals (外源 pack 提案)."""
    channels: list[dict] = []
    if not MESH_PROPOSALS.is_dir():
        return channels
    for p in sorted(MESH_PROPOSALS.glob("*.yaml")):
        channels.append({
            "id": f"mesh-proposal:{p.stem}",
            "kind": "tool_pack",
            "provider": "mesh.proposal",
            "connector": str(p.relative_to(WORKSPACE)),
            "entry_point": "external-resource-pack-proposals",
            "health": "pending",
            "status": "proposal",
        })
    return channels


def emit_yaml(channels: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    totals = {
        "channels": len(channels),
        "exposed": sum(1 for c in channels if c["status"] == "exposed"),
        "orphan": sum(1 for c in channels if c["status"] == "orphan"),
        "proposal": sum(1 for c in channels if c["status"] == "proposal"),
    }
    health_summary = {
        "available": sum(1 for c in channels if c.get("health") == "available"),
        "unavailable": sum(1 for c in channels if c.get("health") == "unavailable"),
        "error": sum(1 for c in channels if c.get("health") == "error"),
        "pending": sum(1 for c in channels if c.get("health") in ("pending", "unknown")),
        "available_rate": 0.0,
    }
    health_summary["available_rate"] = round(
        health_summary["available"] / len(channels) * 100, 1
    ) if channels else 0.0
    lines = [
        "# External Channels Inventory SSOT (ECCP P0)",
        "# 自动生成, 请勿手动编辑",
        "# 生成器: bin/ssot/gen-external-channels-inventory.py",
        f"# 生成时间: {now}",
        "# 对标: Backstage software catalog (集中 inventory)",
        "",
        "version: '1.0'",
        f"generated_at: '{now}'",
        "generator: bin/ssot/gen-external-channels-inventory.py",
        "policy_digest: external-connection-fabric/v1",
        "totals:",
        f"  channels: {totals['channels']}",
        f"  exposed: {totals['exposed']}",
        f"  orphan: {totals['orphan']}",
        f"  proposal: {totals['proposal']}",
        "health_summary:",
        f"  available: {health_summary['available']}",
        f"  unavailable: {health_summary['unavailable']}",
        f"  error: {health_summary['error']}",
        f"  pending: {health_summary['pending']}",
        f"  available_rate: {health_summary['available_rate']}",
        "",
        "channels:",
    ]
    for c in channels:
        lines.append(f"  - id: {c['id']}")
        lines.append(f"    kind: {c['kind']}")
        lines.append(f"    provider: {c['provider']}")
        lines.append(f"    connector: {c['connector']}")
        if c["entry_point"]:
            lines.append(f"    entry_point: {c['entry_point']}")
        lines.append(f"    health: {c['health']}")
        lines.append(f"    status: {c['status']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    channels: list[dict] = []
    channels += scan_iris_resources()
    channels += scan_runtime_ingest()
    channels += scan_mesh_proposals()

    yaml = emit_yaml(channels)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(yaml, encoding="utf-8")

    exposed = sum(1 for c in channels if c["status"] == "exposed")
    orphan = sum(1 for c in channels if c["status"] == "orphan")
    proposal = sum(1 for c in channels if c["status"] == "proposal")
    print(f"✅ inventory 生成: {OUTPUT.relative_to(WORKSPACE)}")
    print(f"   channels: {len(channels)} (exposed={exposed}, orphan={orphan}, proposal={proposal})")
    if orphan:
        print(f"   ⚠️ orphan (待 P3 收编): {[c['id'] for c in channels if c['status'] == 'orphan']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
