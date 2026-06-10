#!/usr/bin/env python3
"""CARDS — MetaOS 统一追踪体系 CLI.
SSOT: SQLite database at data/cards/cards.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[4] / "data" / "cards" / "cards.db"


def _get_cockpit_dir() -> Path:
    """Resolve standard @驾驶舱 or 驾驶舱 folder in Documents."""
    d = Path.home() / "Documents" / "@驾驶舱"
    if d.exists():
        return d
    return Path.home() / "Documents" / "@驾驶舱"


# ── schema ──────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    status      TEXT NOT NULL,
    title       TEXT NOT NULL,
    domain      TEXT NOT NULL DEFAULT 'meta',
    priority    TEXT NOT NULL DEFAULT 'P2',
    summary     TEXT DEFAULT '',
    content     TEXT DEFAULT '',
    parent_id   TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    deadline    TEXT,
    review_due  TEXT,
    tags        TEXT DEFAULT '[]',
    extra       TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS card_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id     TEXT NOT NULL REFERENCES cards(id),
    old_status  TEXT,
    new_status  TEXT NOT NULL,
    changed_at  TEXT NOT NULL,
    changed_by  TEXT DEFAULT 'cli',
    note        TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_cards_status ON cards(status);
CREATE INDEX IF NOT EXISTS idx_cards_domain ON cards(domain);
CREATE INDEX IF NOT EXISTS idx_cards_priority ON cards(priority);
CREATE INDEX IF NOT EXISTS idx_cards_type ON cards(type);
CREATE INDEX IF NOT EXISTS idx_history_card_id ON card_history(card_id);
"""

STATUS_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
ACTIVE_STATUSES = {"flash", "incubating", "promoted", "queue", "ingest", "digest",
                   "analyze", "planned", "active", "blocked", "identified", "scored",
                   "in_progress", "draft", "review", "published", "maintained"}

VALID_TYPES = {"idea", "research", "task", "debt", "delivery"}
VALID_DOMAINS = {"ai-research", "family", "infra", "work", "creative", "meta"}
VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}


# ── helpers ─────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def _record_history(conn, card_id: str, old_status: str | None, new_status: str, note: str = ""):
    conn.execute(
        "INSERT INTO card_history (card_id, old_status, new_status, changed_at, note) VALUES (?, ?, ?, ?, ?)",
        (card_id, old_status, new_status, _now(), note)
    )


def _format_row(row: sqlite3.Row) -> str:
    """Format a single card for terminal display."""
    tags = json.loads(row["tags"] or "[]")
    tag_str = " ".join(f"#{t}" for t in tags) if tags else ""
    deadline_str = f" ⏰{row['deadline']}" if row["deadline"] else ""
    parent_str = f" ← {row['parent_id']}" if row["parent_id"] else ""
    return (
        f"[{row['priority']}] {row['id']}  {row['status']:12s}  "
        f"{row['domain']:12s}  {row['title']}{parent_str}{deadline_str}  {tag_str}"
    )


# ── commands ────────────────────────────────────────────

def cmd_init(args=None):
    """Initialize (or re-initialize) the database."""
    conn = _get_db()
    conn.close()
    print(f"✅ CARDS database initialized at {DB_PATH}")


def cmd_create(args):
    """Create a new card."""
    if args.type not in VALID_TYPES:
        print(f"❌ Invalid type: {args.type}. Must be one of {VALID_TYPES}")
        return 1
    if args.domain not in VALID_DOMAINS:
        print(f"❌ Invalid domain: {args.domain}. Must be one of {VALID_DOMAINS}")
        return 1
    if args.priority not in VALID_PRIORITIES:
        print(f"❌ Invalid priority: {args.priority}")
        return 1

    conn = _get_db()

    # Generate ID
    today = datetime.now().strftime("%Y-%m-%d")
    prefix = {"idea": "IDEA", "research": "RES", "task": "TASK", "debt": "DEBT", "delivery": "DEL"}
    type_prefix = prefix[args.type]
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM cards WHERE id LIKE ?",
        (f"{type_prefix}-{today}-%",)
    ).fetchone()
    seq = row["cnt"] + 1
    card_id = f"{type_prefix}-{today}-{seq:03d}"

    now = _now()
    tags = json.dumps(args.tags if args.tags else [])
    extra = json.dumps({"severity": args.severity} if args.severity else {})

    default_status = {"idea": "flash", "research": "identified"}.get(args.type, "planned")
    conn.execute(
        """INSERT INTO cards (id, type, status, title, domain, priority, summary, content, parent_id, created_at, updated_at, deadline, tags, extra)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (card_id, args.type, args.status or default_status,
         args.title, args.domain, args.priority, args.summary or "", args.content or "",
         args.parent or None, now, now, args.deadline or None, tags, extra)
    )
    _record_history(conn, card_id, None, args.status or default_status, "created")
    conn.commit()
    conn.close()
    print(f"✅ Created {card_id}: {args.title}")
    return 0


def cmd_list(args):
    """List cards with optional filters."""
    conn = _get_db()
    conditions = []
    params = []

    if args.status:
        statuses = [s.strip() for s in args.status.split(",")]
        placeholders = ",".join("?" for _ in statuses)
        conditions.append(f"status IN ({placeholders})")
        params.extend(statuses)
    else:
        # Default: only active cards
        conditions.append("status NOT IN ('done','resolved','discarded','archived','superseded','cancelled')")

    if getattr(args, 'card_type', None):
        conditions.append("type = ?")
        params.append(args.card_type)
    if args.domain:
        conditions.append("domain = ?")
        params.append(args.domain)
    if getattr(args, 'priority', None):
        priorities = [p.strip() for p in args.priority.split(",")]
        placeholders = ",".join("?" for _ in priorities)
        conditions.append(f"priority IN ({placeholders})")
        params.extend(priorities)

    where = " AND ".join(conditions) if conditions else "1=1"
    order = "ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 END, created_at DESC"

    rows = conn.execute(
        f"SELECT * FROM cards WHERE {where} {order} LIMIT ?",
        params + [args.limit or 50]
    ).fetchall()
    conn.close()

    if not rows:
        print("(no cards)")
        return 0

    print(f"\n{'─' * 80}")
    for row in rows:
        print(_format_row(row))
    print(f"{'─' * 80}")
    print(f"{len(rows)} cards")
    return 0


def cmd_show(args):
    """Show full content of a single card."""
    conn = _get_db()
    row = conn.execute("SELECT * FROM cards WHERE id = ?", (args.id,)).fetchone()
    if not row:
        conn.close()
        print(f"❌ Card not found: {args.id}")
        return 1

    print(f"\n{'─' * 80}")
    print(f"[{row['priority']}] {row['id']}")
    print(f"  Type: {row['type']}  |  Status: {row['status']}  |  Domain: {row['domain']}")
    print(f"  Created: {row['created_at']}  |  Updated: {row['updated_at']}")
    if row['deadline']:
        print(f"  Deadline: {row['deadline']}")
    if row['review_due']:
        print(f"  Review due: {row['review_due']}")
    if row['parent_id']:
        print(f"  Parent: {row['parent_id']}")
    tags = json.loads(row['tags'] or '[]')
    if tags:
        print(f"  Tags: {' '.join(f'#{t}' for t in tags)}")
    extra = json.loads(row['extra'] or '{}')
    if extra:
        print(f"  Extra: {json.dumps(extra)}")
    print(f"\n{'─' * 80}")
    print(f"Title: {row['title']}")
    if row['summary']:
        print(f"\nSummary: {row['summary']}")
    if row['content']:
        print(f"\n{row['content']}")
    print(f"{'─' * 80}")

    # Show history
    history = conn.execute(
        "SELECT * FROM card_history WHERE card_id = ? ORDER BY changed_at DESC LIMIT 10",
        (args.id,)
    ).fetchall()
    if history:
        print("\nHistory:")
        for h in history:
            arrow = f"{h['old_status'] or '∅'} → {h['new_status']}"
            print(f"  {h['changed_at']}  {arrow:20s}  {h['note']}")
    conn.close()
    return 0


def cmd_update(args):
    """Update a card's status and/or content."""
    conn = _get_db()
    row = conn.execute("SELECT * FROM cards WHERE id = ?", (args.id,)).fetchone()
    if not row:
        conn.close()
        print(f"❌ Card not found: {args.id}")
        return 1

    old_status = row["status"]
    new_status = args.status or old_status
    new_summary = args.summary if args.summary is not None else row["summary"]
    new_content = args.content if args.content is not None else row["content"]
    new_priority = args.priority if args.priority else row["priority"]
    new_deadline = args.deadline if args.deadline is not None else row["deadline"]
    new_review_due = args.review_due if args.review_due is not None else row["review_due"]

    note = args.note or "updated"

    conn.execute(
        """UPDATE cards SET status=?, summary=?, content=?, priority=?, deadline=?, review_due=?, updated_at=?
           WHERE id=?""",
        (new_status, new_summary, new_content, new_priority, new_deadline, new_review_due, _now(), args.id)
    )
    if new_status != old_status:
        _record_history(conn, args.id, old_status, new_status, note)
    conn.commit()
    conn.close()
    print(f"✅ Updated {args.id}: {old_status} → {new_status}")
    return 0


def cmd_dashboard(args):
    """Print dashboard-style aggregation."""
    conn = _get_db()

    # Cards by priority
    rows = conn.execute(
        """SELECT priority, COUNT(*) as cnt, GROUP_CONCAT(id || ': ' || title, '; ') as titles
           FROM cards WHERE status NOT IN ('done','resolved','discarded','archived','superseded','cancelled')
           GROUP BY priority ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 END"""
    ).fetchall()

    # Cards by type
    type_rows = conn.execute(
        """SELECT type, COUNT(*) as cnt FROM cards
           WHERE status NOT IN ('done','resolved','discarded','archived','superseded','cancelled')
           GROUP BY type ORDER BY cnt DESC"""
    ).fetchall()

    # Cards by domain
    domain_rows = conn.execute(
        """SELECT domain, COUNT(*) as cnt FROM cards
           WHERE status NOT IN ('done','resolved','discarded','archived','superseded','cancelled')
           GROUP BY domain ORDER BY cnt DESC"""
    ).fetchall()

    conn.close()

    print(f"\n{'═' * 70}")
    print(f"  CARDS DASHBOARD  —  {_now()}")
    print(f"{'═' * 70}")

    print("\n  By Priority:")
    print(f"  {'─' * 40}")
    for r in rows:
        bar = "█" * min(r["cnt"], 20)
        print(f"  {r['priority']:4s}  {r['cnt']:2d} cards  {bar}")

    print("\n  By Type:")
    print(f"  {'─' * 40}")
    for r in type_rows:
        print(f"  {r['type']:12s}  {r['cnt']:2d}")

    print("\n  By Domain:")
    print(f"  {'─' * 40}")
    for r in domain_rows:
        print(f"  {r['domain']:16s}  {r['cnt']:2d}")

    total = sum(r["cnt"] for r in rows)
    print(f"\n  {'─' * 40}")
    print(f"  Total active:  {total} cards")
    print(f"{'═' * 70}\n")
    return 0


def cmd_check(args):
    """Check constraints and report violations."""
    conn = _get_db()
    violations = []
    now = datetime.now(timezone.utc)

    # Check idea pool size
    idea_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM cards WHERE type='idea' AND status IN ('flash','incubating')"
    ).fetchone()["cnt"]
    if idea_count > 10:
        violations.append(f"⚠️  Idea pool overflow: {idea_count} (>10 max)")

    # Check overdue deadlines
    overdue = conn.execute(
        "SELECT id, title, deadline FROM cards WHERE deadline IS NOT NULL AND deadline < ? AND status NOT IN ('done','resolved','discarded','archived','superseded','cancelled')",
        (now.strftime("%Y-%m-%d"),)
    ).fetchall()
    for r in overdue:
        violations.append(f"⚠️  OVERDUE: {r['id']} '{r['title']}' (since {r['deadline']})")

    # Check review_due
    review_overdue = conn.execute(
        "SELECT id, title, review_due FROM cards WHERE review_due IS NOT NULL AND review_due < ? AND status NOT IN ('done','resolved','discarded','archived','superseded','cancelled')",
        (now.strftime("%Y-%m-%d"),)
    ).fetchall()
    for r in review_overdue:
        violations.append(f"🔴 REVIEW OVERDUE: {r['id']} '{r['title']}' (since {r['review_due']})")

    # Check flash ideas older than 48h
    two_days_ago = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    flash_old = conn.execute(
        "SELECT id, title, created_at FROM cards WHERE type='idea' AND status='flash' AND created_at < ?",
        (two_days_ago,)
    ).fetchall()
    for r in flash_old:
        violations.append(f"💡 Stale flash idea: {r['id']} '{r['title']}' (created {r['created_at']})")

    # Check incubating > 14 days
    from datetime import timedelta
    two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
    incubating_stale = conn.execute(
        "SELECT id, title, created_at FROM cards WHERE type='idea' AND status='incubating' AND created_at < ?",
        (two_weeks_ago,)
    ).fetchall()
    for r in incubating_stale:
        violations.append(f"💡 Incubating > 14 days: {r['id']} '{r['title']}' (since {r['created_at']})")

    conn.close()

    if not violations:
        print("✅ All checks passed.")
        return 0

    print("\n📋 Constraint Check Results:\n")
    for v in violations:
        print(f"  {v}")
    print(f"\n  ── {len(violations)} violation(s) ──\n")
    return 1 if violations else 0


def cmd_search(args):
    """Search cards by keyword in title, summary, content, and tags."""
    conn = _get_db()
    query = f"%{args.query}%"
    rows = conn.execute(
        """SELECT * FROM cards WHERE
           title LIKE ? OR summary LIKE ? OR content LIKE ? OR tags LIKE ?
           ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 END
           LIMIT ?""",
        (query, query, query, query, args.limit or 20)
    ).fetchall()
    conn.close()

    if not rows:
        print(f"No results for: {args.query}")
        return 0

    print(f"\nSearch: '{args.query}' — {len(rows)} results")
    print(f"{'─' * 80}")
    for row in rows:
        print(_format_row(row))
    print(f"{'─' * 80}\n")
    return 0


def cmd_generate(args=None):
    """Generate Markdown views from SQLite DB for Obsidian browsing."""
    conn = _get_db()
    # Resolve output dir: if --output given, use it; else derive from DB_PATH
    if args and hasattr(args, 'output') and args.output:
        output_dir = Path(args.output)
    else:
        # Obsidian vault is at ~/Documents/ (separate from Workspace)
        output_dir = _get_cockpit_dir() / "CARDS"

    rows = conn.execute(
        """SELECT * FROM cards
           WHERE status NOT IN ('done','resolved','discarded','archived','superseded','cancelled')
           ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 END"""
    ).fetchall()

    generated = 0
    for row in rows:
        type_dir = output_dir / f"{row['type']}s"
        type_dir.mkdir(parents=True, exist_ok=True)
        md_path = type_dir / f"{row['id']}.md"

        tags = json.loads(row['tags'] or '[]')
        deadline_line = f"deadline: {row['deadline']}\n" if row['deadline'] else ""
        review_line = f"review_due: {row['review_due']}\n" if row['review_due'] else ""
        parent_line = f"parent: {row['parent_id']}\n" if row['parent_id'] else ""

        content = f"""---
id: {row['id']}
type: {row['type']}
status: {row['status']}
title: {row['title']}
domain: {row['domain']}
priority: {row['priority']}
created: {row['created_at'][:10]}
{deadline_line}{review_line}{parent_line}tags: [{', '.join(tags)}]
---

> ⚠️ 此文件由 `cards generate` 从 SQLite 自动生成。手动修改会被覆盖。SSOT 在 `data/cards/cards.db`。

# {row['title']}

## 摘要
{row['summary'] or '(暂无摘要)'}

## 详情
{row['content'] or '(暂无内容)'}
"""
        md_path.write_text(content, encoding="utf-8")
        generated += 1

    # Also generate README
    readme_path = output_dir / "README.md"
    if not readme_path.exists():
        readme_path.write_text("""# CARDS — 自动生成视图

> ⚠️ 此目录下的所有 .md 文件由 `cards generate` 从 SQLite 自动生成。
> 手动修改会被覆盖。SSOT 在 `data/cards/cards.db`。

使用 `cards list` / `cards show <id>` / `cards dashboard` 查看最新状态。
""", encoding="utf-8")

    conn.close()
    print(f"✅ Generated {generated} card views in {output_dir}")
    return 0


def cmd_daemon(args=None):
    """Run generate + check + DASHBOARD update in one shot."""
    import sys as _sys

    print("🔄 CARDS daemon running...")
    ret = 0

    # 1. Generate CARDS views
    print("  → Generating CARDS views...")
    cmd_generate(args)

    # 2. Generate architecture views
    print("  → Generating architecture views...")
    cmd_generate_views(args)

    # 3. Run checks
    print("  → Running checks...")
    check_ret = cmd_check(args)
    if check_ret != 0:
        ret = check_ret

    # 3. Update DASHBOARD
    print("  → Updating DASHBOARD...")
    dashboard_path = _get_cockpit_dir() / "DASHBOARD.md"
    try:
        import io
        old_stdout = _sys.stdout
        _sys.stdout = io.StringIO()
        cmd_dashboard(args)
        dashboard_output = _sys.stdout.getvalue()
        _sys.stdout = old_stdout
    except Exception:
        dashboard_output = "# DASHBOARD\n\n(update failed)\n"

    if dashboard_path.exists():
        orig = dashboard_path.read_text(encoding="utf-8")
        # Find and replace the CARDS section
        marker = "## CARDS 聚合视图"
        new_section = f"""{marker}

> ⚠️ 自动生成于 {_now()}。Agent 启动时通过 MCP cards_status 获取实时数据。

```
{dashboard_output.strip()}
```
"""
        if marker in orig:
            before = orig[:orig.index(marker)]
            after = orig[orig.index(marker):]
            if "## 当前信号" in after:
                after = after[after.index("## 当前信号"):]
            else:
                after = ""
            new_dashboard = before + new_section + "\n" + after
        else:
            new_dashboard = orig + "\n" + new_section
        dashboard_path.write_text(new_dashboard, encoding="utf-8")
        print("  → DASHBOARD updated")

    print("✅ Daemon complete")
    return ret


def cmd_generate_views(args=None):
    """Generate architecture views (Layer A+B) from SSOT SSOT sources."""
    views_dir = _get_cockpit_dir() / "生成"
    views_dir.mkdir(parents=True, exist_ok=True)

    conn = _get_db()
    now = _now()
    generated = 0

    # ── V1-snapshot: 数字快照 ──
    total = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    active = conn.execute(
        "SELECT COUNT(*) FROM cards WHERE status NOT IN ('done','resolved','discarded','archived','superseded','cancelled')"
    ).fetchone()[0]
    closed = total - active

    v1 = f"""# V1 数字快照（自动生成）

> 生成: {now} | 源: CARDS SQLite

| 指标 | 数值 |
|------|------|
| 卡片总数 | {total} |
| 活跃卡片 | {active} |
| 已关闭 | {closed} |
| 审计历史 | {conn.execute('SELECT COUNT(*) FROM card_history').fetchone()[0]} 条 |
"""
    conn.close()
    (views_dir / "V1-数字快照.md").write_text(v1, encoding="utf-8")
    generated += 1

    # ── V2-开发: 从 LAYER-INDEX 提取 ──
    layer_index = Path.home() / "Workspace" / "LAYER-INDEX.md"
    v2 = f"""# V2 开发视图（自动生成）

> 生成: {now} | 源: Workspace/LAYER-INDEX.md

"""
    if layer_index.exists():
        text = layer_index.read_text(encoding="utf-8")
        # Extract layer sections
        for layer in ["I0", "L1", "L2", "L3", "L4", "治理层"]:
            if layer in text:
                v2 += f"### {layer}\n\n> 详见 LAYER-INDEX.md\n\n"
        v2 += "\n> 完整包清单 → `Workspace/LAYER-INDEX.md`\n"
    else:
        v2 += "> ⚠️ LAYER-INDEX.md 未找到\n"
    (views_dir / "V2-开发视图.md").write_text(v2, encoding="utf-8")
    generated += 1

    # ── V4-运行: MCP工具（从源码扫描）+ 生命周期钩子 ──
    mcp_tools = {}
    mcp_server_path = Path(__file__).resolve().parent / "mcp_server.py"
    if mcp_server_path.exists():
        text = mcp_server_path.read_text(encoding="utf-8")
        import re
        # Find all @mcp.tool() decorated functions
        for match in re.finditer(r'@mcp\.tool\(\)\s*\nasync def (\w+)\(', text):
            tool_name = match.group(1)
            mcp_tools[tool_name] = "omo (cards server)"

    v4 = f"""# V4 运行视图（自动生成）

> 生成: {now} | 源: mcp_server.py 源码扫描 + CLAUDE.md §9
> ⚠️ 本文件由 `cards generate-views` 自动生成·每次 daemon 刷新

## Agent 生命周期钩子

| 钩子 | 触发 |
|------|------|
| on_session_start | MEMORY→STATE→DASHBOARD→cards_status+check→画像 |
| on_domain_enter | 读域CLAUDE.md+STATE.md |
| before_task | todo_write（≥3步） |
| after_task | 更新CARDS卡片·检查STATE/DASHBOARD |
| on_session_end | cards daemon |

## MCP Tools（从源码扫描）

| Tool | Server |
|------|--------|
"""
    for name, server in sorted(mcp_tools.items()):
        v4 += f"| {name} | {server} |\n"
    v4 += f"\n> 共 {len(mcp_tools)} 个 MCP tools 已注册\n"
    (views_dir / "V4-运行视图.md").write_text(v4, encoding="utf-8")
    generated += 1

    # ── V6-运营: Phase进度 + 债务看板 ──
    conn2 = _get_db()
    debt_count = conn2.execute(
        "SELECT COUNT(*) FROM cards WHERE type='debt' AND status NOT IN ('resolved','accepted')"
    ).fetchone()[0]
    conn2.close()

    v6 = f"""# V6 运营视图（自动生成）

> 生成: {now} | 源: CARDS DB + DASHBOARD

## 系统统计

| 指标 | 数值 |
|------|------|
| 活跃卡片 | {active} |
| 活跃债务 | {debt_count} |
| 卡片类型分布 | task({
    _get_db().execute("SELECT COUNT(*) FROM cards WHERE type='task' AND status!='done'").fetchone()[0]
})·idea({
    _get_db().execute("SELECT COUNT(*) FROM cards WHERE type='idea' AND status NOT IN ('discarded')").fetchone()[0]
})·debt({debt_count})·delivery·research |

## Phase 进度

→ 详见 `驾驶舱/DASHBOARD.md`
"""
    (views_dir / "V6-运营视图.md").write_text(v6, encoding="utf-8")
    generated += 1

    # ── V8-数据: SSOT 清单（从文件系统扫描） ──
    ssot_items = []
    # Check each SSOT location
    checks = [
        ("CARDS DB", "SQLite", DB_PATH, DB_PATH.exists()),
        ("OMO 治理", "YAML", Path.home() / "Workspace" / ".omo", (Path.home() / "Workspace" / ".omo").exists()),
        ("Vault", "Markdown", Path.home() / "Documents" / "学习进化", (Path.home() / "Documents" / "学习进化").exists()),
        ("驾驶舱", "MD+SQLite", _get_cockpit_dir(), _get_cockpit_dir().exists()),
        ("MADF 视图", "Markdown(自动生成)", views_dir, views_dir.exists()),
    ]
    for name, fmt, path, exists in checks:
        status = "✅" if exists else "❌ 缺失"
        short = str(path).replace(str(Path.home()), "~")
        ssot_items.append(f"| {name} | {fmt} | `{short}` | {status} |")

    v8 = f"""# V8 数据视图（自动生成）

> 生成: {now} | 源: 文件系统扫描
> ⚠️ 本文件由 `cards generate-views` 自动生成·每次 daemon 刷新

## SSOT 位置（实时扫描）

| SSOT | 格式 | 位置 | 状态 |
|------|------|------|------|
{chr(10).join(ssot_items)}

## CARDS Schema

```
cards (id, type, status, title, domain, priority, summary, content, parent_id, created_at, updated_at, deadline, review_due, tags[JSON], extra[JSON])
card_history (id, card_id, old_status, new_status, changed_at, changed_by, note)
```
"""
    (views_dir / "V8-数据视图.md").write_text(v8, encoding="utf-8")
    generated += 1

    print(f"✅ Generated {generated} architecture views in {views_dir}")
    return 0


def cmd_minerva_ingest(args):
    """Bridge: trigger Minerva deep research for a CARDS research card, store results, advance status."""
    conn = _get_db()
    row = conn.execute("SELECT * FROM cards WHERE id = ?", (args.id,)).fetchone()
    if not row:
        conn.close()
        print(f"❌ Card not found: {args.id}")
        return 1
    if row["type"] != "research":
        conn.close()
        print(f"❌ Card {args.id} is type '{row['type']}', not 'research'")
        return 1

    question = row["title"]
    if row["summary"]:
        question = f"{row['title']}: {row['summary']}"

    level = getattr(args, 'level', 'L1') or 'L1'
    kairon_dir = str(Path(__file__).resolve().parents[4] / "projects" / "kairon")

    print(f"🔬 Minerva research: {question[:80]}...")
    print(f"   Level: {level}  |  Card: {args.id}")

    # Call Minerva
    try:
        result = subprocess.run(
            ["uv", "--directory", kairon_dir, "run", "minerva", "research", question, "--level", level, "--json"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print(f"⚠️  Minerva exited with code {result.returncode}")
            print(f"   stderr: {result.stderr[:200]}")
            # Still save partial output
            minerva_output = result.stdout or result.stderr
        else:
            minerva_output = result.stdout
    except subprocess.TimeoutExpired:
        print("⚠️  Minerva timed out (5min). Saving partial results.")
        minerva_output = "(Minerva timed out)"
    except FileNotFoundError:
        print("❌ Minerva not found. Ensure kairon project is installed.")
        conn.close()
        return 1

    # Build enriched content
    old_content = row["content"] or ""
    new_content = f"""{old_content}

## Minerva 研究报告 (L{level})
> 自动生成于 {_now()}

{minerva_output[:5000] if len(minerva_output) > 5000 else minerva_output}
"""
    # Update card: store minerva output, advance to digest
    old_status = row["status"]
    new_status = "digest"

    extra = json.loads(row["extra"] or "{}")
    extra["minerva_level"] = level
    extra["minerva_generated_at"] = _now()

    conn.execute(
        "UPDATE cards SET status=?, content=?, extra=?, updated_at=? WHERE id=?",
        (new_status, new_content, json.dumps(extra), _now(), args.id)
    )
    _record_history(conn, args.id, old_status, new_status, f"minerva-ingest (L{level})")
    conn.commit()
    conn.close()
    print(f"✅ {args.id}: {old_status} → {new_status} (Minerva L{level} complete)")
    return 0


def cmd_migrate(args):
    """Import v1 CARDS/*.md files into SQLite."""
    cards_dir = Path(args.source)
    if not cards_dir.exists():
        print(f"❌ Source directory not found: {cards_dir}")
        return 1

    conn = _get_db()
    imported = 0
    skipped = 0

    for md_file in sorted(cards_dir.rglob("*.md")):
        if md_file.name == "README.md":
            continue

        text = md_file.read_text(encoding="utf-8")

        # Parse YAML frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1]
                body = parts[2].strip()
            else:
                print(f"⚠️  Skipping {md_file.name}: malformed frontmatter")
                skipped += 1
                continue
        else:
            print(f"⚠️  Skipping {md_file.name}: no frontmatter")
            skipped += 1
            continue

        # Simple YAML parsing (flat key: value only)
        fm = {}
        for line in frontmatter_text.strip().split("\n"):
            line = line.strip()
            if ":" in line:
                key, _, val = line.partition(":")
                fm[key.strip()] = val.strip()

        card_id = fm.get("id", "")
        if not card_id:
            print(f"⚠️  Skipping {md_file.name}: no id")
            skipped += 1
            continue

        # Check if exists
        existing = conn.execute("SELECT id FROM cards WHERE id = ?", (card_id,)).fetchone()
        if existing:
            print(f"⏭  Skipping {card_id}: already exists")
            skipped += 1
            continue

        now = _now()
        tags = json.dumps([t.strip() for t in fm.get("tags", "").strip("[]").split(",") if t.strip()])
        extra = json.dumps({
            "severity": fm.get("severity", ""),
            "task_type": fm.get("task_type", ""),
        } if fm.get("severity") or fm.get("task_type") else {})

        conn.execute(
            """INSERT INTO cards (id, type, status, title, domain, priority, summary, content, parent_id, created_at, updated_at, deadline, review_due, tags, extra)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                card_id,
                fm.get("type", "task"),
                fm.get("status", "planned"),
                fm.get("title", md_file.stem),
                fm.get("domain", "meta"),
                fm.get("priority", "P2"),
                fm.get("summary", ""),
                body,
                fm.get("parent") or None,
                fm.get("created", now),
                now,
                fm.get("deadline") or None,
                fm.get("review_due") or None,
                tags,
                extra,
            )
        )
        _record_history(conn, card_id, None, fm.get("status", "planned"), "imported from v1")
        imported += 1
        print(f"✅ {card_id}: {fm.get('title', '')}")

    conn.commit()
    conn.close()
    print(f"\n📦 Imported {imported} cards, skipped {skipped}")
    return 0


# ── main ────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CARDS — MetaOS Unified Tracking CLI")
    sub = parser.add_subparsers(dest="command")

    # init
    sub.add_parser("init", help="Initialize database")

    # create
    p = sub.add_parser("create", help="Create a new card")
    p.add_argument("type", choices=list(VALID_TYPES))
    p.add_argument("title")
    p.add_argument("--domain", default="meta", choices=list(VALID_DOMAINS))
    p.add_argument("--priority", default="P2", choices=list(VALID_PRIORITIES))
    p.add_argument("--status")
    p.add_argument("--summary", default="")
    p.add_argument("--content", default="")
    p.add_argument("--parent")
    p.add_argument("--deadline")
    p.add_argument("--severity")
    p.add_argument("--tags", nargs="*")

    # list
    p = sub.add_parser("list", help="List cards")
    p.add_argument("--status")
    p.add_argument("--type", dest="card_type")
    p.add_argument("--domain")
    p.add_argument("--priority")
    p.add_argument("--limit", type=int)

    # show
    p = sub.add_parser("show", help="Show single card")
    p.add_argument("id")

    # update
    p = sub.add_parser("update", help="Update a card")
    p.add_argument("id")
    p.add_argument("--status")
    p.add_argument("--summary")
    p.add_argument("--content")
    p.add_argument("--priority")
    p.add_argument("--deadline")
    p.add_argument("--review-due")
    p.add_argument("--note")

    # dashboard
    sub.add_parser("dashboard", help="Print dashboard")

    # check
    sub.add_parser("check", help="Check constraints")

    # search
    p = sub.add_parser("search", help="Search cards")
    p.add_argument("query")
    p.add_argument("--limit", type=int)

    # generate
    p = sub.add_parser("generate", help="Generate Markdown views from DB")
    p.add_argument("--output", default="")

    # minerva-ingest
    p = sub.add_parser("minerva-ingest", help="Bridge: Minerva deep research → CARDS card")
    p.add_argument("id")
    p.add_argument("--level", default="L1")

    # generate-views
    sub.add_parser("generate-views", help="Generate architecture views (Layer A+B) from SSOT")

    # daemon
    sub.add_parser("daemon", help="Run generate + check + DASHBOARD update")

    # migrate
    p = sub.add_parser("migrate", help="Import v1 markdown cards")
    default_source = "Documents/@驾驶舱/CARDS" if (Path.home() / "Documents" / "@驾驶舱").exists() else "Documents/@驾驶舱/CARDS"
    p.add_argument("--source", default=str(Path.home() / default_source))

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    cmd_map = {
        "init": cmd_init,
        "create": cmd_create,
        "list": cmd_list,
        "show": cmd_show,
        "update": cmd_update,
        "dashboard": cmd_dashboard,
        "check": cmd_check,
        "search": cmd_search,
        "generate": cmd_generate,
        "generate-views": cmd_generate_views,
        "daemon": cmd_daemon,
        "minerva-ingest": cmd_minerva_ingest,
        "migrate": cmd_migrate,
    }
    return cmd_map[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
