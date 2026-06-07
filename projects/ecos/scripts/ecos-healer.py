#!/usr/bin/env python3
"""
eCOS v5 — 自治愈框架 (ecos-healer)
=====================================
Phase 8.3 / 自愈能力
失败自动恢复 + 重试逻辑 + 降级策略。
当 daemon 检测到异常时，自动尝试恢复动作。

用法:
    python3 ecos-healer.py --check-health    # 检查并自愈
    python3 ecos-healer.py --dry-run         # 预览（不执行恢复）
    python3 ecos-healer.py --status          # 查看自愈历史

自愈规则:
    freshness → CLAUDE.md 过期 → 生成警告报告
    consistency → CARDS↔STATE 不一致 → 生成 diff
    protocol → 协议衰减超 80% → 标记审查
    daemon → daemon 无响应 → 尝试重启
"""

import sys
import json
import subprocess
import time
import sqlite3
import argparse
from datetime import datetime, timezone
from pathlib import Path


DOCS = Path.home() / "Documents"
ECOS = Path.home() / ".ecos"
SCRIPTS = ECOS / "scripts"
HEALER_DB = ECOS / "healer-state.db"


def init_db():
    HEALER_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(HEALER_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS heal_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_type TEXT NOT NULL,
            issue TEXT NOT NULL,
            action TEXT NOT NULL,
            result TEXT NOT NULL,
            duration_ms INTEGER DEFAULT 0,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def run_script(path: Path, args: list = None, timeout: int = 30) -> tuple[int, str]:
    if not path.exists():
        return 2, f"脚本不存在: {path}"
    cmd = ["python3", str(path)]
    if args:
        cmd.extend(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip()
    except subprocess.TimeoutExpired:
        return 1, "超时"
    except Exception as e:
        return 1, str(e)


def record_heal(conn: sqlite3.Connection, check_type: str, issue: str,
                action: str, result: str, duration_ms: int):
    conn.execute(
        "INSERT INTO heal_attempts (check_type, issue, action, result, duration_ms, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (check_type, issue, action, result, duration_ms,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def heal_freshness(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """自愈: CLAUDE.md 保鲜"""
    script = SCRIPTS / "check-claude-freshness.py"
    if not script.exists():
        return {"rule": "freshness", "status": "skipped", "reason": "脚本不存在"}

    start = time.time()
    code, out = run_script(script, ["--root", str(DOCS), "--max-age-days", "60", "--json"])

    try:
        data = json.loads(out)
        stale = data.get("stale", 0)
    except (json.JSONDecodeError, ValueError):
        stale = 0

    if stale == 0:
        duration = int((time.time() - start) * 1000)
        record_heal(conn, "freshness", "检查", "无操作-全部新鲜", "pass", duration)
        return {"rule": "freshness", "status": "ok", "detail": "全部新鲜"}

    # 有过期文件: 生成告警报告
    if not dry_run:
        report_path = ECOS / "freshness-alert.md"
        report_path.write_text(
            f"# 保鲜告警 — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"发现 {stale} 个过期 CLAUDE.md 文件。建议更新后重检。\n"
            f"```\n{out[:500]}\n```\n"
        )
        duration = int((time.time() - start) * 1000)
        record_heal(conn, "freshness", f"{stale} 过期文件",
                    "生成告警报告", "pass", duration)
        return {"rule": "freshness", "status": "healed",
                "detail": f"已生成告警报告: {report_path}", "stale": stale}

    return {"rule": "freshness", "status": "dry-run", "stale": stale}


def heal_consistency(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """自愈: CARDS↔STATE 一致性"""
    script = ECOS / "scripts" / "check-cards-state-consistency.py"
    if not script.exists():
        return {"rule": "consistency", "status": "skipped", "reason": "脚本不存在"}

    cards_db = Path.home() / "Workspace" / "data" / "cards" / "cards.db"
    if not cards_db.exists():
        return {"rule": "consistency", "status": "skipped", "reason": "cards.db 不存在"}

    start = time.time()
    code, out = run_script(script, ["--db", str(cards_db), "--vault", str(DOCS)])
    duration = int((time.time() - start) * 1000)

    if code == 0:
        record_heal(conn, "consistency", "检查", "无操作-全部一致", "pass", duration)
        return {"rule": "consistency", "status": "ok", "detail": "CARDS↔STATE 全部一致"}

    # 不一致: 生成 diff
    if not dry_run:
        diff_path = ECOS / "consistency-diff.md"
        diff_path.write_text(
            f"# 一致性 DIFF — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"```\n{out[:500]}\n```\n"
        )
        record_heal(conn, "consistency", "不一致",
                    "生成 DIFF 报告", "pass", duration)
        return {"rule": "consistency", "status": "healed",
                "detail": f"已生成 DIFF: {diff_path}"}

    return {"rule": "consistency", "status": "dry-run", "detail": out[:100]}


def heal_protocol(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """自愈: 协议衰减 — 标记超期协议"""
    compiler = SCRIPTS / "ecos-constraint-compiler.py"
    if not compiler.exists():
        return {"rule": "protocol", "status": "skipped", "reason": "编译器不存在"}

    start = time.time()
    code, out = run_script(compiler, ["--json"])
    duration = int((time.time() - start) * 1000)

    try:
        data = json.loads(out)
        decay = data.get("decay", [])
        expired = [d for d in decay if d.get("status") == "expired"]
    except (json.JSONDecodeError, ValueError):
        expired = []

    if not expired:
        record_heal(conn, "protocol", "检查", "无操作-无超期", "pass", duration)
        return {"rule": "protocol", "status": "ok", "detail": "无协议超期"}

    # 有协议超期: 标记审查
    if not dry_run:
        expired_names = [d["protocol"] for d in expired]
        alert_path = ECOS / "protocol-alert.md"
        alert_path.write_text(
            f"# 协议衰减告警 — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"以下协议已超半衰期: {', '.join(expired_names)}\n"
            f"建议审查协议版本或更新 half_life 配置。\n"
        )
        record_heal(conn, "protocol", f"超期: {expired_names}",
                    "生成审查标记", "pass", duration)
        return {"rule": "protocol", "status": "healed",
                "detail": f"已标记: {expired_names}", "protocols": expired}

    return {"rule": "protocol", "status": "dry-run", "expired": expired}


def heal_daemon(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """自愈: daemon 健康"""
    daemon_script = SCRIPTS / "ecos-daemon.py"
    if not daemon_script.exists():
        return {"rule": "daemon", "status": "skipped", "reason": "daemon 不存在"}

    start = time.time()
    code, out = run_script(daemon_script, ["--status"])
    duration = int((time.time() - start) * 1000)

    if code == 0:
        record_heal(conn, "daemon", "状态检查", "无操作-运行中", "pass", duration)
        return {"rule": "daemon", "status": "ok", "detail": "daemon 运行中"}

    # daemon 异常: 尝试单次运行
    if not dry_run:
        recover_code, recover_out = run_script(daemon_script, ["--once"])
        if recover_code == 0:
            record_heal(conn, "daemon", "无响应",
                        "单次触发恢复", "pass", duration)
            return {"rule": "daemon", "status": "healed", "detail": "daemon 已恢复"}
        else:
            record_heal(conn, "daemon", "无响应",
                        "恢复失败", "fail", duration)
            return {"rule": "daemon", "status": "failed",
                    "detail": "daemon 恢复失败"}

    return {"rule": "daemon", "status": "dry-run"}


def format_report(results: list[dict]) -> str:
    lines = []
    lines.append("=" * 56)
    lines.append("  eCOS v5 — 自治愈报告")
    lines.append("=" * 56)
    for r in results:
        icon = {"ok": "✅", "healed": "🔄", "skipped": "⏭️",
                "failed": "❌", "dry-run": "🔍"}.get(r["status"], "?")
        detail = r.get("detail") or r.get("reason") or ""
        lines.append(f"  {icon} {r['rule']:12s} → {r['status']:8s} {detail[:60]}")
    lines.append(f"\n{'='*56}")
    return "\n".join(lines)


def show_status(conn: sqlite3.Connection):
    cursor = conn.execute("""
        SELECT check_type, action, result, timestamp FROM heal_attempts
        ORDER BY id DESC LIMIT 10
    """)
    rows = cursor.fetchall()
    print(f"\n{'='*56}")
    print(f"  自愈历史 (最近 {len(rows)})")
    print(f"{'='*56}")
    for check_type, action, result, ts in rows:
        icon = "✅" if result == "pass" else ("🔄" if result == "healed" else "❌")
        print(f"  {icon} [{check_type:12s}] {action[:30]:30s} {ts[:19]}")
    print()


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 自治愈框架")
    parser.add_argument("--check-health", action="store_true", help="检查所有项目并自愈")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不执行恢复")
    parser.add_argument("--status", action="store_true", help="查看自愈历史")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    conn = init_db()

    if args.status:
        show_status(conn)
        conn.close()
        return

    if args.check_health or args.dry_run:
        healers = [
            heal_freshness,
            heal_consistency,
            heal_protocol,
            heal_daemon,
        ]

        results = []
        for heal in healers:
            r = heal(conn, dry_run=args.dry_run)
            results.append(r)

        conn.close()

        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(format_report(results))

        failed = [r for r in results if r.get("status") == "failed"]
        sys.exit(1 if failed else 0)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
