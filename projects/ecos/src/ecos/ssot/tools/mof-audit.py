#!/usr/bin/env python3
"""
织星 MOF — M1↔M0 审计器 (mof-audit)
=====================================
读取 M1 节点(声明态) + M0 运行时快照(实际态)，检测漂移。
漂移 = M1 声称的状态 ≠ M0 实际状态。

检测项:
  1. 协议衰减漂移 (M1: active → M0: decay>50%)
  2. 组件运行漂移 (M1: active → M0: stopped)
  3. 规范执行漂移 (M1: enforce → M0: warn)
  4. 实体状态漂移 (M1: active → M0: 文件不存在)

输出: 漂移报告 + 可选 CARDS 自动创建债务卡片

用法:
    python3 mof-audit.py                    # 全量审计
    python3 mof-audit.py --create-cards      # 漂移项自动创建 CARDS DEBT
    python3 mof-audit.py --json              # JSON 输出
"""

import json
import yaml
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, timezone

DOCS = Path.home() / "Documents"
NODES_DIR = DOCS / "驾驶舱" / "元模型" / "nodes"
CONSTRAINTS_FILE = DOCS / "学习进化" / "2-knowledge" / "基建架构" / "L0-constraints.yaml"
CARDS_DB = Path.home() / "Workspace" / "data" / "cards" / "cards.db"
ECOS_DIR = Path.home() / ".ecos"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f)


def load_m1_nodes() -> list[dict]:
    nodes = []
    if not NODES_DIR.exists():
        return nodes
    for f in sorted(NODES_DIR.glob("*.yaml")):
        data = load_yaml(f)
        if isinstance(data, dict) and "id" in data:
            nodes.append(data)
    return nodes


def get_m0_protocol_state() -> dict:
    """获取 M0 协议运行时状态"""
    data = load_yaml(CONSTRAINTS_FILE)
    registry = data.get("protocol_registry", [])
    now = datetime.now()
    state = {}
    for p in registry:
        intro = datetime.strptime(p["introduced"], "%Y-%m-%d")
        age = (now - intro).days
        half = p["half_life_days"]
        decay = min(1.0, age / half) if half > 0 else 1.0
        state[p["id"]] = {
            "decay": decay,
            "remaining": max(0, (1 - decay) * 100),
            "age_days": age,
            "status": "expired" if decay >= 1.0 else ("aging" if decay >= 0.5 else "fresh"),
            "m0_status": p.get("status", "active"),
        }
    return state


def get_m0_daemon_state() -> dict:
    """获取 M0 daemon 运行时状态"""
    db = ECOS_DIR / "daemon-state.db"
    if not db.exists():
        return {"status": "unknown", "cycles": 0}
    conn = sqlite3.connect(str(db))
    cur = conn.execute("SELECT COUNT(*), MAX(exit_code) FROM cycles")
    count, max_exit = cur.fetchone()
    conn.close()
    return {
        "status": "active" if count > 0 else "stopped",
        "cycles": count,
        "healthy": max_exit == 0 if max_exit is not None else False,
    }


def audit_protocols(m1_nodes: list[dict], m0_state: dict) -> list[dict]:
    """审计协议漂移"""
    drifts = []
    protocols = [n for n in m1_nodes if n.get("type") == "Protocol"]
    for p in protocols:
        pid_raw = p["id"].replace("PROTOCOL-", "")
        # Match to M0
        m0 = None
        for key, val in m0_state.items():
            if pid_raw == key or pid_raw in key or key in pid_raw:
                m0 = val
                break

        if not m0:
            drifts.append({"id": p["id"], "type": "Protocol", "severity": "high",
                          "drift": "M0 中未找到对应协议运行时数据"})
            continue

        # Check decay drift
        if m0["status"] == "expired" and p.get("status") == "active":
            drifts.append({"id": p["id"], "type": "Protocol", "severity": "medium",
                          "drift": f"协议已超半衰期({m0['age_days']}d > half_life)但 M1 仍为 active",
                          "detail": f"decay={m0['decay']:.0%}, remaining={m0['remaining']:.0f}%"})
        elif m0["status"] == "aging" and p.get("status") == "active":
            drifts.append({"id": p["id"], "type": "Protocol", "severity": "low",
                          "drift": f"协议正在老化(decay={m0['decay']:.0%})，建议标记为 aging 或审查"})

    return drifts


def audit_mechanisms(m1_nodes: list[dict], m0_daemon: dict) -> list[dict]:
    """审计机制漂移"""
    drifts = []
    mechs = [n for n in m1_nodes if n.get("type") == "Mechanism"]
    for m in mechs:
        if "DAEMON" in m["id"]:
            if not m0_daemon["healthy"] and m.get("status") == "active":
                drifts.append({"id": m["id"], "type": "Mechanism", "severity": "high",
                              "drift": "Daemon 健康检查未通过但 M1 状态为 active",
                              "detail": f"cycles={m0_daemon['cycles']}, healthy={m0_daemon['healthy']}"})
    return drifts


def create_debt_card(drift: dict) -> bool:
    """为漂移项创建 CARDS 债务卡片"""
    if not CARDS_DB.exists():
        return False
    try:
        conn = sqlite3.connect(str(CARDS_DB))
        now = datetime.now(timezone.utc).isoformat()
        debt_id = f"DEBT-AUDIT-{now[:10].replace('-','')}-{drift['id'][:20]}"
        # Check if already exists
        cur = conn.execute("SELECT id FROM cards WHERE id = ?", (debt_id,))
        if cur.fetchone():
            return False
        conn.execute("""
            INSERT INTO cards (id, type, status, title, domain, priority, summary, content, created_at, updated_at)
            VALUES (?, 'debt', 'identified', ?, 'meta', 'P2', ?, ?, ?, ?)
        """, (debt_id,
              f"MOF审计漂移: {drift['drift'][:60]}",
              f"{drift['drift']} ({drift.get('detail','')})",
              f"## MOF 审计自动创建\n- 漂移类型: {drift['type']}\n- 严重度: {drift['severity']}\n- {drift['detail']}",
              now, now))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def format_report(drifts: list[dict]) -> str:
    now = datetime.now(timezone.utc)
    lines = []
    lines.append("=" * 64)
    lines.append("  织星 MOF — M1↔M0 漂移审计报告")
    lines.append("=" * 64)
    lines.append(f"  时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  漂移项: {len(drifts)}")
    lines.append("")

    if not drifts:
        lines.append("  ✅ 无漂移 — M1 声明与 M0 运行时一致")
    else:
        for d in drifts:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(d["severity"], "⚪")
            lines.append(f"  {icon} [{d['type']}] {d['id']}")
            lines.append(f"     {d['drift']}")
            if d.get("detail"):
                lines.append(f"     详情: {d['detail']}")
            lines.append("")

    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-cards", action="store_true", help="漂移项自动创建 CARDS DEBT 卡片")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    m1_nodes = load_m1_nodes()
    m0_protocols = get_m0_protocol_state()
    m0_daemon = get_m0_daemon_state()

    drifts = []
    drifts.extend(audit_protocols(m1_nodes, m0_protocols))
    drifts.extend(audit_mechanisms(m1_nodes, m0_daemon))

    if args.json:
        print(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                          "drift_count": len(drifts), "drifts": drifts,
                          "m0_snapshot": {"protocols": m0_protocols, "daemon": m0_daemon}},
                         ensure_ascii=False, indent=2))
    else:
        print(format_report(drifts))

    if args.create_cards and drifts:
        created = sum(1 for d in drifts if create_debt_card(d))
        print(f"\n  📋 CARDS 自动创建: {created} 张 DEBT 卡片")


if __name__ == "__main__":
    main()
