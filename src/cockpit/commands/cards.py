"""cockpit.commands.cards — L4 自我层 CARDS 抓手 (P74-W0).

镜像 P49 stdio_rpc helper 模式: 暴露 ~/Documents/驾驶舱/CARDS/ 为
bos://persona/cards/* URI, 让 5 仓 (L3 cockpit + I0 agora + L2 引擎 + L1 runtime + L0 protocol)
经 cockpit L3 入口访问 L4 自我层数据.

子命令:
  list            列所有 CARDS (按子目录 debts/deliverys/ideas/researchs/tasks)
  get <id>        查 1 个 card (按 ID 或 path)
  search <query>  全文搜 (按 title + tags + body 关键词)
  serve           stdio JSON-RPC serve mode (P49 helper 镜像, 暴露给 agora long-live pool)

SSOT: data/cards/cards.db (SQLite), MD 文件是 cards generate 自动生成.
"""

from __future__ import annotations

import argparse
import json as _json  # P74-W0: avoid unused warning
import re
import sys
from pathlib import Path

from .base import _get_console, _get_err


def _get_cockpit_dir() -> Path:
    """Resolve standard @驾驶舱 or 驾驶舱 folder in Documents."""
    d = Path.home() / "Documents" / "@驾驶舱"
    if d.exists():
        return d
    return Path.home() / "Documents" / "驾驶舱"


CARDS_ROOT = _get_cockpit_dir() / "CARDS"

VALID_CATEGORIES = ("debts", "deliverys", "ideas", "researchs", "tasks")


def _iter_cards(root: Path = CARDS_ROOT):
    """迭代所有 .md card (category, path, frontmatter, body)."""
    for cat in VALID_CATEGORIES:
        cat_dir = root / cat
        if not cat_dir.exists():
            continue
        for md in sorted(cat_dir.glob("*.md")):
            fm, body = _parse_frontmatter(md)
            yield cat, md, fm, body


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    """解析 YAML frontmatter (简化版, key: value)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_text, body = parts[1].strip(), parts[2].strip()
    fm: dict = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, body


def cmd_cards(args: argparse.Namespace) -> int:
    c, e = _get_console(), _get_err()
    if args.cards_command == "serve":
        return _serve_stdio()
    if args.cards_command == "list":
        return _do_list(c, e)
    if args.cards_command == "get":
        return _do_get(args.id, c, e)
    if args.cards_command == "search":
        return _do_search(args.query, c, e)
    e.print("[red]用法: cockpit cards {list|get <id>|search <query>|serve}[/]")
    return 1


def _do_list(c, e) -> int:
    if not CARDS_ROOT.exists():
        e.print(f"[red]L4 CARDS_ROOT 不存在: {CARDS_ROOT}[/]")
        return 1
    count = 0
    for cat in VALID_CATEGORIES:
        cat_dir = CARDS_ROOT / cat
        if not cat_dir.exists():
            continue
        c.print(f"\n[bold cyan]── {cat} ({sum(1 for _ in cat_dir.glob('*.md'))} cards) ──[/]")
        for cat_name, path, fm, _ in _iter_cards():
            if cat_name != cat:
                continue
            title = fm.get("title", path.stem)
            status = fm.get("status", "?")
            priority = fm.get("priority", "?")
            c.print(f"  [{priority}] {path.stem[:50]:50s} [dim]({status})[/] {title[:40]}")
            count += 1
    c.print(f"\n[green]总计 {count} cards[/]")
    return 0


def _do_get(card_id: str, c, e) -> int:
    if not card_id:
        e.print("[red]用法: cockpit cards get <id>[/]")
        return 1
    for cat, path, fm, body in _iter_cards():
        if path.stem == card_id or fm.get("id") == card_id or path.name == card_id:
            c.print(f"[bold cyan]── {path.stem} ──[/]")
            c.print(f"  category: {cat}")
            for k in ("id", "type", "status", "title", "domain", "priority", "created", "tags"):
                if k in fm:
                    c.print(f"  {k}: {fm[k]}")
            c.print("\n  --- body (前 30 行) ---")
            for line in body.splitlines()[:30]:
                c.print(f"  {line}")
            return 0
    e.print(f"[red]card '{card_id}' 未找到[/]")
    return 1


def _do_search(query: str, c, e) -> int:
    if not query:
        e.print("[red]用法: cockpit cards search <query>[/]")
        return 1
    pat = re.compile(query, re.IGNORECASE)
    count = 0
    for cat, path, fm, body in _iter_cards():
        title = fm.get("title", "")
        tags = fm.get("tags", "")
        if pat.search(title) or pat.search(tags) or pat.search(body):
            c.print(f"  [{cat}] {path.stem[:50]:50s} {title[:50]}")
            count += 1
    c.print(f"\n[green]匹配 {count} cards[/]")
    return 0


def _serve_stdio() -> int:
    """P74-W0: stdio JSON-RPC serve mode (P49 stdio_rpc helper 镜像).

    协议: 每行 stdin 1 个 JSON request
      {"action": "list"|"get"|"search", "args": {...}}
    返回: 1 行 JSON response
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line == "QUIT":
            break
        try:
            req = _json.loads(line)
        except _json.JSONDecodeError as exc:
            sys.stdout.write(_json.dumps({"status": "error", "error": f"json_decode: {exc}"}) + "\n")
            sys.stdout.flush()
            continue
        action = req.get("action", "")
        args = req.get("args", {}) or {}
        if action == "list":
            cards = []
            for cat, path, fm, _ in _iter_cards():
                cards.append(
                    {
                        "category": cat,
                        "id": path.stem,
                        "title": fm.get("title", ""),
                        "status": fm.get("status", ""),
                        "priority": fm.get("priority", ""),
                        "path": str(path),
                    }
                )
            resp = {"status": "ok", "result": {"count": len(cards), "cards": cards}}
        elif action == "get":
            card_id = args.get("id", "")
            for cat, path, fm, body in _iter_cards():
                if path.stem == card_id or fm.get("id") == card_id:
                    resp = {
                        "status": "ok",
                        "result": {
                            "category": cat,
                            "id": path.stem,
                            "path": str(path),
                            "frontmatter": fm,
                            "body": body,
                        },
                    }
                    break
            else:
                resp = {"status": "error", "error": f"card '{card_id}' 未找到"}
        elif action == "search":
            query = args.get("query", "")
            pat = re.compile(query, re.IGNORECASE)
            matches = []
            for cat, path, fm, body in _iter_cards():
                if pat.search(fm.get("title", "")) or pat.search(fm.get("tags", "")) or pat.search(body):
                    matches.append({"category": cat, "id": path.stem, "title": fm.get("title", "")})
            resp = {"status": "ok", "result": {"count": len(matches), "matches": matches}}
        else:
            resp = {"status": "error", "error": f"unknown action: {action}"}
        sys.stdout.write(_json.dumps(resp, ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()
    return 0


__all__ = ["cmd_cards", "CARDS_ROOT", "VALID_CATEGORIES"]
