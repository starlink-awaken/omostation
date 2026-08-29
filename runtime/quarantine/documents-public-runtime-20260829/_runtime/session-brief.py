#!/usr/bin/env python3
"""session-brief.py — L4 会话启动简报生成器

聚合 5 源生成 @驾驶舱/_control/BRIEF.md, 替代 §0 启动序列的多文件手动读取:
  1. 域三源一致性     (domain-sync.py)
  2. Workspace 桥接    (.omo/state/system.yaml + health.yaml)
  3. CARDS 开启项      (data/cards/cards.db)
  4. 桥接保鲜度        (bridge-refresh.py --check 逻辑)
  5. 人类信号尾部      (@驾驶舱/_control/SIGNALS.md)

用法: python3 session-brief.py [--stdout]
建议: 挂 cron 每晨生成; Agent 会话启动只读 BRIEF.md 一个文件。
与 Workspace 侧 ecos-brief.py (daemon/协议简报) 互补, 不重复。
v1.0 | 2026-07-02
"""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parents[2]
WS_ROOT = Path(os.environ.get("WORKSPACE_ROOT", DOCS_ROOT.parent / "Workspace"))
RUNTIME = DOCS_ROOT / "@公共/_runtime"
BRIEF = DOCS_ROOT / "@驾驶舱/_control/BRIEF.md"
SIGNALS = DOCS_ROOT / "@驾驶舱/_control/SIGNALS.md"
ACTIVE = ("active", "identified", "in_progress", "planned")


def yget(path: Path, key: str) -> str:
    try:
        m = re.search(rf"^{re.escape(key)}:\s*['\"]?([^'\"\n]+)", path.read_text(encoding="utf-8"), re.M)
        return m.group(1).strip() if m else "?"
    except OSError:
        return "不可达"


def run_gate(script: str, *args: str) -> tuple[bool, str]:
    try:
        r = subprocess.run([sys.executable, str(RUNTIME / script), *args],
                           capture_output=True, text=True, timeout=60,
                           env={**os.environ, "WORKSPACE_ROOT": str(WS_ROOT)})
        tail = (r.stdout.strip().splitlines() or ["(无输出)"])[-1]
        return r.returncode == 0, tail
    except Exception as e:  # noqa: BLE001
        return False, f"执行失败: {e}"


def cards_summary() -> list[str]:
    db = WS_ROOT / "data/cards/cards.db"
    if not db.exists():
        return ["- ⚠️ cards.db 不可达"]
    conn = sqlite3.connect(str(db))
    ph = ",".join("?" * len(ACTIVE))
    active = conn.execute(f"SELECT COUNT(*) FROM cards WHERE status IN ({ph})", ACTIVE).fetchone()[0]
    debts = conn.execute(
        f"SELECT priority, title FROM cards WHERE type='debt' AND status IN ({ph}) ORDER BY priority", ACTIVE).fetchall()
    conn.close()
    out = [f"- 活跃卡片 **{active}** 张"]
    out += [f"- 开启债务 {p or '?'}: {t}" for p, t in debts]
    return out


def kos_status() -> str:
    """KOS 索引状态。实际 db = ~/.kos/kos-index.sqlite (kos ingest 写入, 2026-07-02 实测);
    kos-index.yaml 宣称的 ~/Documents/.kos-index.db 为过期设计, 保留兜底。"""
    for db in (Path.home() / ".kos/kos-index.sqlite", DOCS_ROOT / ".kos-index.db"):
        if db.exists():
            age = (datetime.now(timezone.utc).timestamp() - db.stat().st_mtime) / 86400
            return f"{'✅' if age <= 10 else '🟡'} 索引 {age:.0f} 天前更新（{db.name}，周日 cron 重建）"
    return "🔴 索引未构建（`kos ingest ~/Documents/@<域>`，路线 §三.7）"


def human_signals(n: int = 5) -> list[str]:
    """SIGNALS.md 中最近的人类信号 (YAML 格式解析)。"""
    if not SIGNALS.exists():
        return []
    text = SIGNALS.read_text(encoding="utf-8")
    # 提取 message 字段: 缩进的 "- message: "..." 或 '...""
    msgs = re.findall(r'^\s{4}message:\s*"(.+?)"', text, re.M)
    return [f"- {m}" for m in msgs[-n:]]


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ok_sync, sync_msg = run_gate("domain-sync.py")
    ok_bridge, bridge_msg = run_gate("bridge-refresh.py", "--check")
    ok_async, async_msg = run_gate("async-audit.py")
    ok_alive, alive_msg = run_gate("async-audit.py", "--health")

    lines = [
        "# BRIEF — 会话启动简报（生成物·勿手改）", "",
        f"> ⏱ {now} · session-brief.py · Agent 启动读本文件即可，深入再按指针跳转", "",
        "## 门禁",
        f"- {'✅' if ok_sync else '🔴'} 域三源: {sync_msg}",
        f"- {'✅' if ok_bridge else '🔴'} 桥接保鲜: {bridge_msg}",
        f"- {'✅' if ok_async else '🔴'} 异步任务: {async_msg}",
        f"- {'✅' if ok_alive else '🔴'} 任务活性: {alive_msg}",
        f"- KOS: {kos_status()}", "",
        "## Workspace（omostation）",
        f"- Phase **{yget(WS_ROOT / '.omo/state/system.yaml', 'current_phase')}**"
        f"（{yget(WS_ROOT / '.omo/state/system.yaml', 'phase_status')}"
        f" · {yget(WS_ROOT / '.omo/state/system.yaml', 'current_wave')}）",
        f"- 治理健康分 **{yget(WS_ROOT / '.omo/state/health.yaml', 'health_score')}/100**"
        f" · 服务在线率 {yget(WS_ROOT / '.omo/state/health.yaml', 'service_online_ratio')}", "",
        "## CARDS 开启项",
        *cards_summary(), "",
        "## 最近信号（人类）",
        *(human_signals() or ["- (无)"]), "",
        "## 指针",
        "- 全局状态 → `@驾驶舱/_control/DASHBOARD.md`（桥接区块已自动生成）",
        "- 域注册 → `@驾驶舱/_control/DOMAIN-INDEX.md`（表格由 domain-sync 生成）",
        "- Workspace 深入 → `~/Workspace/CLAUDE.md` §0（bootstrap + status）",
    ]
    out = "\n".join(lines) + "\n"
    if "--stdout" in sys.argv:
        print(out)
    else:
        BRIEF.write_text(out, encoding="utf-8")
        print(f"✅ BRIEF.md 已生成 ({'门禁全绿' if ok_sync and ok_bridge else '⚠️ 有门禁未过'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
