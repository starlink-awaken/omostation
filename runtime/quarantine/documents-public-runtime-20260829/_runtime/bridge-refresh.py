#!/usr/bin/env python3
"""bridge-refresh.py — Documents↔Workspace 桥接快照生成器

从 Workspace 真实 SSOT 拉取数据, 重写 DASHBOARD.md 的 AUTOGEN 标记区块:
  - AUTOGEN:WORKSPACE-BRIDGE  ← .omo/state/system.yaml + health.yaml
  - AUTOGEN:CARDS-VIEW        ← data/cards/cards.db

用法:
  python3 bridge-refresh.py           # 重写 DASHBOARD 两个区块
  python3 bridge-refresh.py --check   # 只检查保鲜度 (health 快照 >7 天 exit 1), 不写
  python3 bridge-refresh.py --stdout  # 打印区块内容, 不写文件

设计: 消灭「手抄数字」— 桥接数据只能由本脚本生成, 每块自带生成时间戳。
无第三方依赖 (yaml 用正则解析扁平键, 避免 pyyaml 环境问题)。
v1.0 | 2026-07-02
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parents[2]
WS_ROOT = Path(os.environ.get("WORKSPACE_ROOT", DOCS_ROOT.parent / "Workspace"))

SYSTEM_YAML = WS_ROOT / ".omo/state/system.yaml"
HEALTH_YAML = WS_ROOT / ".omo/state/health.yaml"
CARDS_DB = WS_ROOT / "data/cards/cards.db"
DASHBOARD = DOCS_ROOT / "@驾驶舱/_control/DASHBOARD.md"

ACTIVE_STATUSES = ("active", "identified", "in_progress", "planned")
STALE_DAYS = 7


def yget(path: Path, key: str) -> str | None:
    m = re.search(rf"^{re.escape(key)}:\s*['\"]?([^'\"\n]+)", path.read_text(encoding="utf-8"), re.M)
    return m.group(1).strip() if m else None


def workspace_block() -> str:
    sy = SYSTEM_YAML.read_text(encoding="utf-8")
    phase = yget(SYSTEM_YAML, "current_phase")
    pstatus = yget(SYSTEM_YAML, "phase_status")
    wave = yget(SYSTEM_YAML, "current_wave")
    updated = yget(SYSTEM_YAML, "updated_at")
    milestones = sorted(int(n) for n in re.findall(r"^phase(\d+)_status:\s*completed", sy, re.M))
    hs = yget(HEALTH_YAML, "health_score")
    hgen = yget(HEALTH_YAML, "generated_at")
    online = yget(HEALTH_YAML, "service_online_ratio")
    ht = HEALTH_YAML.read_text(encoding="utf-8")
    contrib = dict(re.findall(r"^\s+(governance|freshness|runtime):\s*([\d.]+)", ht, re.M))
    ms = "/".join(str(m) for m in milestones[-8:])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    # 双轨: 优先读 health.yaml 原生字段 (compass_radar 2026-07-02 起输出), 否则派生
    gov_native = yget(HEALTH_YAML, "health_governance_track")
    run_native = yget(HEALTH_YAML, "health_runtime_track")
    if gov_native and gov_native.isdigit():
        dual = f"治理轨 **{gov_native}** · 运行轨 **{run_native}**（health.yaml 原生）"
    else:
        try:
            gov_track = (float(contrib.get("governance", 0)) + float(contrib.get("freshness", 0))) / 70 * 100
            run_track = float(contrib.get("runtime", 0)) / 30 * 100
            dual = f"治理轨 **{gov_track:.0f}** · 运行轨 **{run_track:.0f}**（派生）"
        except (ValueError, ZeroDivisionError):
            dual = "拆分失败"
    return "\n".join([
        f"> ⏱ 生成于 {now} · bridge-refresh.py", "",
        "| 项 | 值 | 来源 |",
        "|----|----|------|",
        f"| current_phase | **{phase}**（{pstatus} · {wave}） | system.yaml ({updated}) |",
        f"| 健康分（复合） | **{hs} / 100**（governance {contrib.get('governance','?')}/50 · freshness {contrib.get('freshness','?')}/20 · runtime {contrib.get('runtime','?')}/30） | health.yaml ({hgen}) |",
        f"| 健康分（双轨） | {dual}（/100 · 服务在线率 {float(online or 0):.0%}） | bridge-refresh 派生 |",
        f"| 已完成里程碑 | Phase {ms}（近 8 个） | system.yaml |",
    ])


def cards_block() -> str:
    conn = sqlite3.connect(str(CARDS_DB))
    q = conn.execute
    total = q("SELECT COUNT(*) FROM cards").fetchone()[0]
    ph = ",".join("?" * len(ACTIVE_STATUSES))
    active = q(f"SELECT COUNT(*) FROM cards WHERE status IN ({ph})", ACTIVE_STATUSES).fetchone()[0]
    by_type_active = q(f"SELECT type, COUNT(*) FROM cards WHERE status IN ({ph}) GROUP BY type ORDER BY 2 DESC", ACTIVE_STATUSES).fetchall()
    by_domain = q(f"SELECT COALESCE(domain,'-'), COUNT(*) FROM cards WHERE status IN ({ph}) GROUP BY 1 ORDER BY 2 DESC", ACTIVE_STATUSES).fetchall()
    by_type_all = q("SELECT type, COUNT(*) FROM cards GROUP BY type ORDER BY 2 DESC").fetchall()
    open_debts = q(f"SELECT priority, title FROM cards WHERE type='debt' AND status IN ({ph}) ORDER BY priority", ACTIVE_STATUSES).fetchall()
    conn.close()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    W = 70
    lines = ["```", "═" * W,
             f"  CARDS DASHBOARD — 生成于 {now} (cards.db · 总卡片 {total})", "═" * W, "",
             f"  活跃卡片 ({'/'.join(ACTIVE_STATUSES)}): {active}", "  " + "─" * 40]
    lines += [f"  {t:<12} {n:>3}" for t, n in by_type_active]
    lines += ["", "  活跃按域:", "  " + "─" * 40]
    lines += [f"  {d:<12} {n:>3}" for d, n in by_domain]
    lines += ["", "  全量按类型 (含终态):", "  " + "─" * 40]
    lines += [f"  {t:<12} {n:>3}" for t, n in by_type_all]
    if open_debts:
        lines += ["", f"  开启债务 ({len(open_debts)}):"]
        lines += [f"    {p or '?'} · {t[:52]}" for p, t in open_debts]
    lines += ["═" * W, "```"]
    return "\n".join(lines)


def replace_block(text: str, tag: str, body: str) -> str:
    begin = f"<!-- AUTOGEN:{tag} BEGIN (bridge-refresh.py · 勿手改) -->"
    end = f"<!-- AUTOGEN:{tag} END -->"
    if begin not in text or end not in text:
        raise SystemExit(f"❌ DASHBOARD 缺 {tag} 标记")
    pre, rest = text.split(begin, 1)
    _, post = rest.split(end, 1)
    return f"{pre}{begin}\n{body}\n{end}{post}"


def staleness() -> tuple[bool, str]:
    hgen = yget(HEALTH_YAML, "generated_at")
    try:
        dt = datetime.fromisoformat((hgen or "").replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - dt).days
        return age <= STALE_DAYS, f"health.yaml 快照 {age} 天前 ({hgen})"
    except ValueError:
        return False, f"health.yaml generated_at 不可解析: {hgen}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    for p in (SYSTEM_YAML, HEALTH_YAML, CARDS_DB):
        if not p.exists():
            print(f"❌ Workspace 源不可达: {p} (可设 WORKSPACE_ROOT)")
            return 2

    fresh, msg = staleness()
    if args.check:
        print(("✅ " if fresh else "🔴 过期: ") + msg)
        return 0 if fresh else 1

    wb, cb = workspace_block(), cards_block()
    if args.stdout:
        print(wb, "\n", cb)
        return 0
    text = DASHBOARD.read_text(encoding="utf-8")
    text = replace_block(text, "WORKSPACE-BRIDGE", wb)
    text = replace_block(text, "CARDS-VIEW", cb)
    DASHBOARD.write_text(text, encoding="utf-8")
    
    html_file = DOCS_ROOT / "@驾驶舱" / "METAOS-DASHBOARD.html"
    if html_file.exists():
        h_text = html_file.read_text(encoding="utf-8")
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        h_text = re.sub(r"更新时间: [^<]+", f"更新时间: {now_ts}", h_text)
        html_file.write_text(h_text, encoding="utf-8")

    print(f"✅ DASHBOARD 桥接区块已刷新 ({msg})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
