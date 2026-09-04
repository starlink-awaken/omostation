"""cockpit.commands.brain — 个人数字大脑 CLI 入口 (Phase 48 MVP).

子命令:
    cockpit brain ask "问题"       → 知识检索 + 记忆上下文 + LLM 回答
    cockpit brain context          → 显示当前记忆摘要
    cockpit brain remember "事实"  → 手动存入偏好/事实
    cockpit brain history [--n N]  → 查看对话历史

架构: Brain CLI → kos_proxy (KOS 搜索) + brain_storage (SQLite) + LLM Gateway
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

# ── Storage ──────────────────────────────────────────────────────

_BRAIN_TABLES_DDL = """
CREATE TABLE IF NOT EXISTS brain_conversations (
    id TEXT PRIMARY KEY,
    user TEXT NOT NULL DEFAULT 'default',
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
_sources TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS brain_preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'explicit',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_brain_conv_user_time
    ON brain_conversations(user, created_at DESC);
"""


def _db_path() -> Path:
    """Brain 存储路径 — 复用 cockpit 的 SQLite DB."""
    return Path.home() / ".workspace" / "data.db"


def _migrate_brain_tables(conn: sqlite3.Connection) -> None:
    """Schema 迁移 — 确保 brain 表结构最新."""
    # 检查 brain_conversations 是否有 sources 列
    existing = conn.execute("PRAGMA table_info(brain_conversations)").fetchall()
    col_names = {row["name"] for row in existing}
    if "sources" not in col_names:
        conn.execute("ALTER TABLE brain_conversations ADD COLUMN sources TEXT")
    # 检查 brain_preferences 是否存在
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='brain_preferences'").fetchone()
    if not tables:
        conn.executescript("""
            CREATE TABLE brain_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'explicit',
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)


def _get_db() -> sqlite3.Connection:
    """获取 SQLite 连接，自动建表 + 迁移."""
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_BRAIN_TABLES_DDL)
    _migrate_brain_tables(conn)
    conn.commit()
    return conn


# ── Conversation storage ──────────────────────────────────────────


def store_conversation(
    role: str,
    content: str,
    sources: list[str] | None = None,
    user: str = "default",
) -> str:
    """存储一条对话记录，返回 id."""
    conn = _get_db()
    try:
        rid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO brain_conversations (id, user, role, content, sources) VALUES (?, ?, ?, ?, ?)",
            (rid, user, role, content, json.dumps(sources or [], ensure_ascii=False)),
        )
        conn.commit()
        return rid
    finally:
        conn.close()


def get_history(limit: int = 20, user: str = "default") -> list[dict]:
    """获取最近 N 条对话."""
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT id, role, content, sources, created_at FROM brain_conversations "
            "WHERE user = ? ORDER BY created_at DESC LIMIT ?",
            (user, limit),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "sources": json.loads(r["sources"] or "[]"),
                "created_at": r["created_at"],
            }
            for r in reversed(rows)
        ]
    finally:
        conn.close()


# ── Preferences ───────────────────────────────────────────────────


def store_preference(key: str, value: str, source: str = "explicit") -> None:
    """存储或更新用户偏好."""
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO brain_preferences (key, value, source, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, source=excluded.source, updated_at=excluded.updated_at",
            (key, value, source, datetime.now(UTC).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_preferences(limit: int = 50) -> list[dict]:
    """获取所有偏好."""
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT key, value, source, updated_at FROM brain_preferences ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"key": r["key"], "value": r["value"], "source": r["source"], "updated_at": r["updated_at"]} for r in rows
        ]
    finally:
        conn.close()


# ── KOS Search (sync wrapper) ─────────────────────────────────────


def kos_search_sync(query: str, limit: int = 5) -> dict:
    """同步调用 KOS 搜索 API."""
    import httpx

    kos_url = os.environ.get("KOS_API_URL", "http://localhost:8766")
    try:
        resp = httpx.get(
            f"{kos_url}/api/v1/search",
            params={"q": query, "mode": "hybrid", "limit": limit},
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e), "results": []}


def kos_context_sync(query: str) -> dict:
    """同步调用 KOS 上下文构建 API."""
    import httpx

    kos_url = os.environ.get("KOS_API_URL", "http://localhost:8766")
    try:
        resp = httpx.get(
            f"{kos_url}/api/v1/context",
            params={"q": query, "mode": "balanced"},
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e), "context": ""}


# ── LLM Gateway (best-effort) ─────────────────────────────────────


def llm_complete(prompt: str, model: str = "deepseek-v4-flash") -> str:
    """调用统一推理接入层 (llm-router) 生成回答。失败时返回空字符串。"""
    from cockpit.llm_router import complete as llm_router_complete

    content, _source = llm_router_complete(prompt, model=model, temperature=0.7, max_tokens=2048)
    return content or ""


def _format_sources(results: list[dict]) -> str:
    """格式化来源列表."""
    if not results:
        return "  (无外部知识来源)"
    lines = []
    for i, r in enumerate(results[:5], 1):
        title = r.get("title") or r.get("name") or r.get("id", "unknown")
        score = r.get("score", "")
        score_str = f" [score={score:.3f}]" if isinstance(score, float) else ""
        lines.append(f"  {i}. {title}{score_str}")
    return "\n".join(lines)


# ── Command handlers ──────────────────────────────────────────────


def cmd_brain_ask(args: argparse.Namespace) -> int:
    """cockpit brain ask — 知识检索 + 记忆 + LLM 回答."""
    question = " ".join(getattr(args, "question", []))
    if not question:
        print('❌ 请提供问题: cockpit brain ask "你的问题"')
        return 1

    # 1. 检索 KOS 知识
    print("🔍 检索知识库...")
    kos_result = kos_search_sync(question)
    results = kos_result.get("results", [])
    if isinstance(kos_result, dict) and "error" in kos_result and not results:
        print(f"⚠️  KOS 搜索失败: {kos_result['error']}")

    # 2. 加载记忆上下文
    prefs = get_preferences(limit=10)
    recent_history = get_history(limit=6)
    memory_parts = []
    if prefs:
        memory_parts.append("用户偏好:\n" + "\n".join(f"  • {p['key']}: {p['value']}" for p in prefs[:5]))
    if recent_history:
        memory_parts.append(
            "最近对话:\n" + "\n".join(f"  [{h['role']}] {h['content'][:80]}" for h in recent_history[-4:])
        )
    memory_context = "\n\n".join(memory_parts) if memory_parts else "(无历史记忆)"

    # 3. 构建 prompt
    knowledge_text = ""
    source_ids = []
    if results:
        for r in results[:5]:
            title = r.get("title") or r.get("name") or ""
            content = r.get("content") or r.get("snippet") or r.get("text") or ""
            if title or content:
                knowledge_text += f"\n### {title}\n{content}\n"
                source_ids.append(r.get("id") or title)

    prompt = f"""你是用户的个人数字大脑助手。基于以下知识库结果和用户记忆，回答用户的问题。

## 用户记忆上下文
{memory_context}

## 知识库搜索结果
{knowledge_text or "(无相关搜索结果)"}

## 用户问题
{question}

请给出有用、准确的回答。如果知识库有相关信息，请引用来源。用中文回答。"""

    # 4. 调用 LLM
    print("🧠 生成回答...")
    answer = llm_complete(prompt)

    if answer:
        print(f"\n{'=' * 60}")
        print(answer)
        print(f"{'=' * 60}")
        print(f"\n📚 知识来源:\n{_format_sources(results)}")
        store_conversation("user", question)
        store_conversation("assistant", answer, sources=source_ids)
    else:
        # LLM 不可用，返回知识检索结果
        print(f"\n{'=' * 60}")
        print("⚠️  LLM 暂不可用，返回知识检索结果:\n")
        if results:
            for i, r in enumerate(results[:5], 1):
                title = r.get("title") or r.get("name") or "unknown"
                content = r.get("content") or r.get("snippet") or r.get("text") or ""
                print(f"  [{i}] {title}")
                print(f"      {content[:200]}")
                print()
        else:
            print("  未找到相关知识。")
        print(f"{'=' * 60}")
        store_conversation("user", question)
        store_conversation("assistant", f"[知识检索] 找到 {len(results)} 条结果", sources=source_ids)

    return 0


def cmd_brain_context(_args: argparse.Namespace) -> int:
    """cockpit brain context — 显示记忆摘要 (支持 --json, --dry-run 与 Rich 表格)."""
    from rich.console import Console
    from rich.table import Table
    from cockpit.domain.exit_codes import ExitCode

    prefs = get_preferences()
    history = get_history(limit=10)
    is_json = getattr(_args, "json", False)
    is_dry_run = getattr(_args, "dry_run", False)

    if is_json:
        payload: dict[str, Any] = {
            "status": "ok",
            "db_path": str(_db_path()),
            "preferences_count": len(prefs),
            "history_count": len(history),
            "preferences": prefs,
            "recent_history": history[-10:],
            "ready": True,
        }
        if is_dry_run:
            payload["dry_run"] = True
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return int(ExitCode.SUCCESS)

    console = Console()
    console.print("[bold cyan]🧠 个人数字大脑 — 记忆与偏好摘要[/bold cyan]")
    if is_dry_run:
        console.print("[yellow][DRY-RUN 模式][/yellow]")

    pref_table = Table(title=f"📌 用户偏好 ({len(prefs)} 条)", border_style="cyan")
    pref_table.add_column("来源 (Source)", style="dim")
    pref_table.add_column("键名 (Key)", style="bold cyan")
    pref_table.add_column("取值 (Value)", style="white")

    if prefs:
        for p in prefs[:10]:
            src = "👤 explicit" if p["source"] == "explicit" else "🔍 extracted"
            pref_table.add_row(src, str(p["key"]), str(p["value"]))
    else:
        pref_table.add_row("-", "(暂无偏好记录)", "-")
    console.print(pref_table)

    hist_table = Table(title=f"💬 最近对话历史 ({len(history)} 条)", border_style="green")
    hist_table.add_column("角色 (Role)", style="bold")
    hist_table.add_column("时间 (Time)", style="dim")
    hist_table.add_column("内容摘要 (Snippet)", style="white")

    if history:
        for h in history[-6:]:
            role_icon = "👤 user" if h["role"] == "user" else "🧠 assistant"
            ts = str(h.get("created_at", ""))[:19]
            snippet = str(h.get("content", ""))[:80].replace("\n", " ")
            hist_table.add_row(role_icon, ts, snippet)
    else:
        hist_table.add_row("-", "-", "(暂无对话记录)")
    console.print(hist_table)

    console.print(f"\n[dim]存储位置: {_db_path()}[/dim]")
    return int(ExitCode.SUCCESS)


def cmd_brain_remember(args: argparse.Namespace) -> int:
    """cockpit brain remember — 手动存入事实/偏好."""
    fact = " ".join(getattr(args, "fact", []))
    if not fact:
        print('❌ 请提供要记住的内容: cockpit brain remember "我喜欢用 Markdown"')
        return 1

    # 尝试解析 key: value 格式
    if ":" in fact or "：" in fact:
        sep = ":" if ":" in fact else "："
        key, _, value = fact.partition(sep)
        key, value = key.strip(), value.strip()
    else:
        # 无冒号: 用前 20 字符做 key，完整内容做 value
        key = fact[:20].strip()
        value = fact.strip()

    store_preference(key, value, source="explicit")
    print(f"✅ 已记住: {key} = {value}")
    return 0


def cmd_brain_history(args: argparse.Namespace) -> int:
    """cockpit brain history — 查看对话历史."""
    limit = getattr(args, "limit", 20)
    history = get_history(limit=limit)

    if not history:
        print("📭 暂无对话历史。")
        return 0

    print(f"💬 最近 {len(history)} 条对话:")
    print("-" * 60)
    for h in history:
        role_icon = "👤" if h["role"] == "user" else "🧠"
        ts = h.get("created_at", "")[:19]
        content = h["content"]
        if len(content) > 200:
            content = content[:200] + "..."
        print(f"{role_icon} [{ts}]")
        print(f"   {content}")
        if h.get("sources"):
            print(f"   📚 来源: {', '.join(h['sources'][:3])}")
        print()
    return 0


# ── Main dispatcher ───────────────────────────────────────────────


def cmd_brain_weekly(args: argparse.Namespace) -> int:
    """cockpit brain weekly — 基于本周 KOS 变更 + 对话历史生成周报素材 (Phase 49 T3)."""
    from cockpit.knowledge_activation import (
        ActivationContext,
        format_recommendations,
        recommend_for_context,
    )

    days = getattr(args, "days", 7)

    print("=" * 60)
    print(f"📝 周报素材生成 (回顾 {days} 天)")
    print("=" * 60)

    # 1. 从对话历史提取话题
    recent_history = get_history(limit=50)
    history_text = ""
    if recent_history:
        history_lines = [f"{h['role']}: {h['content'][:100]}" for h in recent_history[-20:]]
        history_text = "\n".join(history_lines)

    # 2. 知识推荐
    recommendations = recommend_for_context(
        ActivationContext.WEEKLY_REPORT,
        content=history_text[:500],
        limit=8,
    )

    # 3. 构建周报 prompt
    weekly_prompt = f"""基于以下信息生成本周工作总结素材：

## 本周对话摘要
{history_text or "(无最近对话)"}

## 知识库推荐内容
{format_recommendations(recommendations, ActivationContext.WEEKLY_REPORT) or "(无推荐)"}

请生成结构化周报素材：
1. **本周重点** (3-5 条)
2. **知识沉淀** (新增/学习的知识点)
3. **下周关注** (基于知识推荐)
4. **风险/阻塞** (如有)

用中文输出，Markdown 格式。"""

    print("\n🎯 正在生成周报素材...\n")

    result = llm_complete(weekly_prompt)
    if result:
        print(result)
    else:
        print("⚠️  LLM 暂不可用，输出知识推荐:\n")
        if recommendations:
            print(format_recommendations(recommendations, ActivationContext.WEEKLY_REPORT))
        else:
            print("  (暂无推荐内容)")

    print(f"\n{'=' * 60}")
    return 0


def cmd_brain_gongwen(args: argparse.Namespace) -> int:
    """cockpit brain gongwen "主题" — 基于 KOS 知识库辅助公文写作 (Phase 49 T3)."""
    from cockpit.knowledge_activation import (
        ActivationContext,
        format_recommendations,
        recommend_for_context,
    )

    topic = " ".join(getattr(args, "topic", []))
    if not topic:
        print('❌ 请提供公文主题: cockpit brain gongwen "卫健委通知"')
        return 1

    print("=" * 60)
    print(f"📄 公文写作辅助 — {topic}")
    print("=" * 60)

    # 1. KOS 检索相关政策/规范
    print(f"\n🔍 检索与【{topic}】相关的知识...\n")
    recommendations = recommend_for_context(
        ActivationContext.DOCUMENT,
        content=topic,
        limit=10,
    )

    # 2. 构建公文写作 prompt
    rec_text = format_recommendations(recommendations, ActivationContext.DOCUMENT) or "(无相关知识)"

    gongwen_prompt = f"""辅助公文写作：{topic}

## 相关知识与政策依据
{rec_text}

请生成：
1. **写作大纲** (3-5 个章节)
2. **关键要点** (每章节 2-3 个核心观点)
3. **政策引用** (从上述知识中提取)
4. **注意事项** (公文格式/用语规范)

用中文输出，Markdown 格式。"""

    result = llm_complete(gongwen_prompt)
    if result:
        print(result)
    else:
        print("⚠️  LLM 暂不可用，仅显示相关知识:\n")
        if recommendations:
            print(format_recommendations(recommendations, ActivationContext.DOCUMENT))
        else:
            print("  (暂无相关知识)")

    print(f"\n{'=' * 60}")
    return 0


def cmd_brain(args: argparse.Namespace) -> int:  # pyright: ignore[reportUnusedParameter]
    """cockpit brain — 个人数字大脑主入口."""
    subcommand = getattr(args, "brain_subcommand", None)
    if subcommand == "ask":
        return cmd_brain_ask(args)
    elif subcommand == "context":
        return cmd_brain_context(args)
    elif subcommand == "remember":
        return cmd_brain_remember(args)
    elif subcommand == "history":
        return cmd_brain_history(args)
    elif subcommand == "weekly":
        return cmd_brain_weekly(args)
    elif subcommand == "gongwen":
        return cmd_brain_gongwen(args)
    else:
        # 默认显示 context
        return cmd_brain_context(args)
