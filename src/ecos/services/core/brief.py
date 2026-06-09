#!/usr/bin/env python3
"""
eCOS v5 Phase 8.1 — 会话简报生成器 (ecos-brief)
===================================================
Agent 每次会话启动时运行，聚合当前系统状态到一页简报。

用法:
    python3 ecos-brief.py                              # 标准简报
    python3 ecos-brief.py --output ~/Documents/驾驶舱/brief.md  # 写入文件
    python3 ecos-brief.py --json                       # JSON 输出

依赖:
    - ecos-sla-tracker.py
    - ecos-health-check.py
    - cards.db (SQLite)
    - ecos-constraint-validator.py
"""

import json
import argparse
import subprocess
import sqlite3
from datetime import datetime
from pathlib import Path


def _get_cockpit_dir() -> Path:
    """Resolve standard @驾驶舱 or 驾驶舱 folder in Documents."""
    d = Path.home() / "Documents" / "@驾驶舱"
    if d.exists():
        return d
    return Path.home() / "Documents" / "驾驶舱"


SCRIPTS = _get_cockpit_dir() / "scripts"
DOCS = Path.home() / "Documents"
CARDS_DB = Path.home() / "Workspace" / "data" / "cards" / "cards.db"


def run_script(name: str, args: list[str] = None, timeout: int = 30) -> tuple[str, int]:
    """运行脚本并返回 (输出, 退出码)"""
    script = SCRIPTS / name
    if not script.exists():
        return f"⚠️ 脚本缺失: {script}", 2
    cmd = ["python3", str(script)]
    if args:
        cmd.extend(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "⚠️ 超时", 1
    except FileNotFoundError as e:
        return f"⚠️ {e}", 2


def get_sla() -> dict:
    out, _ = run_script("ecos-sla-tracker.py", ["--json"])
    try:
        return json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return {"uptime": None, "consecutive_passes": 0, "total": 0}


def get_top_cards(n: int = 3) -> list[dict]:
    if not CARDS_DB.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{CARDS_DB}?mode=ro", uri=True)
        cursor = conn.execute(
            """
            SELECT id, title, status, domain, priority
            FROM cards
            WHERE status NOT IN ('done','resolved','discarded','archived','cancelled','superseded')
            ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END, created_at
            LIMIT ?
        """,
            (n,),
        )
        cards = [
            {
                "id": row[0],
                "title": row[1][:50],
                "status": row[2],
                "domain": row[3],
                "priority": row[4] or "",
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        return cards
    except Exception as e:
        return [{"id": "error", "title": str(e)[:50]}]


def check_claude_guards() -> dict:
    """保鲜前移 — Agent 使用 CLAUDE.md 前即时校验。检测到过期文件时返回上下文警告。"""
    stale = []
    fresh = 0
    max_age = 60
    now = datetime.now()

    for f in DOCS.rglob("CLAUDE.md"):
        if f.is_file() and not f.is_symlink():
            age = (now - datetime.fromtimestamp(f.stat().st_mtime)).days
            if age > max_age:
                domain = (
                    str(f.parent.relative_to(DOCS))
                    if DOCS in f.parents
                    else str(f.parent.name)
                )
                stale.append(
                    {
                        "file": str(f.relative_to(DOCS)),
                        "domain": domain,
                        "age_days": age,
                    }
                )
            else:
                fresh += 1

    return {
        "total": fresh + len(stale),
        "fresh": fresh,
        "stale": len(stale),
        "stale_files": stale,
        "warning": f"⚠️ {len(stale)} 个 CLAUDE.md 过期，Agent 路由规则可能过时"
        if stale
        else "✅ 全部新鲜",
        "action_required": len(stale) > 0,
    }


def get_protocol_risks() -> list[dict]:
    """从约束校验器获取协议衰减风险"""
    out, _ = run_script(
        str(
            Path.home()
            / "Documents"
            / "学习进化"
            / "2-knowledge"
            / "基建架构"
            / "ecos-constraint-validator.py"
        ),
        ["--json"],
        timeout=15,
    )
    risks = []
    try:
        data = json.loads(out)
        now = datetime.now()
        for p in data.get("protocols", []):
            intro = datetime.strptime(p["introduced"], "%Y-%m-%d")
            age = (now - intro).days
            decay = (
                min(1.0, age / p["half_life_days"]) if p["half_life_days"] > 0 else 1.0
            )
            if decay > 0.8:
                risks.append(
                    {
                        "protocol": p["id"],
                        "version": p["version"],
                        "remaining": max(0, (1 - decay) * 100),
                        "age_days": age,
                        "half_life": p["half_life_days"],
                    }
                )
    except (json.JSONDecodeError, KeyError, ValueError):
        pass
    return risks


def get_event_count_since(since_hours: int = 24) -> int:
    """统计最近事件数"""
    event_file = Path.home() / ".ecos" / "events" / "event-stream.jsonl"
    if not event_file.exists():
        return 0
    try:
        # 获取文件修改时间做简单判断
        mtime = datetime.fromtimestamp(event_file.stat().st_mtime)
        age = (datetime.now() - mtime).total_seconds() / 3600
        if age < since_hours:
            return 1  # 有活动
        return 0
    except OSError:
        return 0


def format_brief(
    sla: dict,
    cards: list[dict],
    risks: list[dict],
    health_pass: bool,
    health_output: str,
    event_count: int,
    claude_guards: dict = None,
) -> str:
    """生成 Markdown 简报"""
    now = datetime.now()
    lines = []

    # 头部
    lines.append(f"# 📋 会话简报 — {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("> eCOS v5 Phase 8.1 · 自动生成 · Agent 启动必读")
    lines.append("")

    # ── 保鲜前移: Agent 使用 CLAUDE.md 前的即时校验 (第一条) ──
    if claude_guards:
        if claude_guards["action_required"]:
            lines.append("## 🔴 CLAUDE.md 保鲜告警 — 使用前必读")
            lines.append(f"> {claude_guards['warning']}")
            lines.append(
                "> Agent: 以下文件的域路由规则可能过时，执行前先验证内容是否仍然正确。"
            )
            lines.append("")
            for sf in claude_guards["stale_files"]:
                lines.append(
                    f"- **{sf['file']}** — {sf['age_days']}d 未更新 ({sf['domain']})"
                )
            lines.append("")
            lines.append(
                f"> 总计: {claude_guards['total']} 个 CLAUDE.md · {claude_guards['fresh']} 新鲜 · {claude_guards['stale']} 过期"
            )
            lines.append("")
        else:
            lines.append("## ✅ CLAUDE.md 保鲜")
            lines.append(
                f"全部 {claude_guards['total']} 个 CLAUDE.md 新鲜 — Agent 可安全使用路由规则。"
            )
            lines.append("")

    # 健康状态
    if health_pass:
        lines.append("## 🟢 系统健康")
    else:
        lines.append("## 🔴 系统异常")
    lines.append(
        f"`ecos-health-check.py` → {'✅ 全部通过' if health_pass else '⚠️ 存在告警'}"
    )
    lines.append("")

    # SLA
    lines.append("## 📊 健康 SLA")
    if sla["total"] and sla["total"] > 0:
        uptime_bar = "█" * int(sla["uptime"] / 10) + "░" * (
            10 - int(sla["uptime"] / 10)
        )
        lines.append(f"- Uptime: **{sla['uptime']}%** [{uptime_bar}]")
        lines.append(f"- 连续通过: **{sla['consecutive_passes']}** 次")
        lines.append(f"- 总检查: {sla['total']} 次")
        if sla.get("last_failure"):
            lines.append(f"- 最近失败: {sla['last_failure']['timestamp'][:19]}")
        else:
            lines.append("- 最近失败: 无 ✅")
    else:
        lines.append("- ⏳ SLA 数据累积中")
    lines.append("")

    # Top 卡片
    lines.append("## 📋 优先卡片")
    if cards:
        for c in cards:
            pri = f"[{c['priority']}]" if c.get("priority") else ""
            lines.append(f"- {pri} **{c['title']}** — {c['domain']} ({c['status']})")
    else:
        lines.append("- CARDS 数据库不可读")
    lines.append("")

    # 协议风险
    lines.append("## ⚠️ 风险项")
    if risks:
        for r in risks:
            icon = "🔴" if r["remaining"] < 10 else "🟡"
            lines.append(
                f"- {icon} {r['protocol']} v{r['version']}: 剩余价值 "
                f"**{r['remaining']:.0f}%** ({r['age_days']}d / {r['half_life']}d 半衰期)"
            )
    else:
        lines.append("- ✅ 无重大风险")
    lines.append("")

    # L0 架构健康
    lines.append("## 🧬 L0 架构治理")
    m0_file = (
        Path.home()
        / "Workspace"
        / "projects"
        / "ecos"
        / "src"
        / "ecos"
        / "ssot"
        / "mof"
        / "M0-snapshot.yaml"
    )
    if m0_file.exists():
        try:
            import yaml

            with open(m0_file) as f:
                m0 = yaml.safe_load(f)
            lines.append(f"- M1 节点: {m0.get('m1_node_count', '?')} 个")
            daemon = m0.get("daemon", {})
            lines.append(
                f"- Daemon: {'🟢' if daemon.get('healthy') else '🟡'} {daemon.get('cycles', 0)} 周期"
            )
            protocols = m0.get("protocols", {})
            aging = [
                p
                for p, s in protocols.items()
                if s.get("status") in ("aging", "expired")
            ]
            if aging:
                lines.append(f"- ⚠️ 老化协议: {', '.join(aging)}")
            else:
                lines.append("- ✅ 协议全健康")
        except Exception:
            lines.append("- ⏳ M0 快照不可读")
    else:
        lines.append("- ⏳ M0 快照未生成")
    lines.append("")

    # 活动
    lines.append("## 🔄 系统活动")
    if event_count > 0:
        lines.append("- ✅ 过去 24h 内有活动")
    else:
        lines.append("- ⏳ 过去 24h 无新活动")

    # 最后健康输出的精简行
    if not health_pass and health_output:
        for line in health_output.split("\n"):
            if "⚠️" in line or "❌" in line:
                lines.append(f"  - {line.strip()}")
                break

    lines.append("")
    lines.append("---")
    lines.append(
        "> 下一步: `python3 ~/Documents/@驾驶舱/scripts/ecos-health-check.py` 查看详情"
    )
    return "\n".join(lines)


def check_freshness(output_path: str) -> bool:
    """检查简报是否在 1 小时内"""
    p = Path(output_path)
    if not p.exists():
        return False
    age = (
        datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)
    ).total_seconds() / 3600
    return age < 1


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 会话简报")
    parser.add_argument(
        "--output",
        type=str,
        default=str(SCRIPTS.parent / "brief.md"),
        help="输出文件路径 (默认 驾驶舱/brief.md)",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--force", action="store_true", help="强制刷新")
    args = parser.parse_args()

    # 自动刷新检查: 如果简报 < 1h 且非强制，跳过
    if not args.force and check_freshness(args.output):
        age = (
            datetime.now() - datetime.fromtimestamp(Path(args.output).stat().st_mtime)
        ).total_seconds() / 60
        print(f"  ⏩ 简报在 {age:.0f} 分钟前生成，跳过刷新。使用 --force 强制。")
        return

    # ── 保鲜前移: Agent 使用 CLAUDE.md 前的即时校验 (最先执行) ──
    claude_guards = check_claude_guards()

    # 收集数据
    sla = get_sla()
    cards = get_top_cards(3)
    risks = get_protocol_risks()
    event_count = get_event_count_since(24)
    health_output, health_code = run_script(
        "ecos-health-check.py", ["--json"], timeout=45
    )

    # 解析健康结果
    health_pass = True
    try:
        health_data = json.loads(health_output)
        results = health_data.get("results", [])
        health_pass = all(r.get("pass") is not False for r in results)
    except (json.JSONDecodeError, TypeError, AttributeError):
        health_pass = health_code == 0

    text = format_brief(
        sla, cards, risks, health_pass, health_output, event_count, claude_guards
    )

    if args.json:
        print(
            json.dumps(
                {
                    "generated_at": datetime.now().isoformat(),
                    "brief": text,
                    "sla": sla,
                    "cards": cards,
                    "risks": risks,
                    "health_pass": health_pass,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.output:
        Path(args.output).write_text(text)
        print(f"  ✅ 会话简报已生成: {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
