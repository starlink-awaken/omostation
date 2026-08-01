"""Brain 核心共享层 — CLI + Web API 共用 (DRY).

抽取 brain.py 和 api_brain.py 的重复逻辑:
- KOS 搜索 (连接池复用 + 超时缩短)
- 记忆加载 + prompt 构建
- 来源格式化
- 偏好解析
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

# ── Storage (从 brain.py 迁移) ──────────────────────────────────────

_BRAIN_TABLES_DDL = """
CREATE TABLE IF NOT EXISTS brain_conversations (
    id TEXT PRIMARY KEY,
    user TEXT NOT NULL DEFAULT 'default',
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources TEXT,
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
    return Path.home() / ".workspace" / "data.db"


def _get_db() -> sqlite3.Connection:
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_BRAIN_TABLES_DDL)
    # 迁移: 确保 sources 列存在
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(brain_conversations)").fetchall()}
    if "sources" not in cols:
        conn.execute("ALTER TABLE brain_conversations ADD COLUMN sources TEXT")
    conn.commit()
    return conn


# ── Conversation storage ───────────────────────────────────────────

def store_conversation(
    role: str,
    content: str,
    sources: list[str] | None = None,
    user: str = "default",
) -> str:
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
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO brain_preferences (key, value, source, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, source=excluded.source, updated_at=excluded.updated_at",
            (key, value, source, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_preferences(limit: int = 50) -> list[dict]:
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT key, value, source, updated_at FROM brain_preferences "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"key": r["key"], "value": r["value"], "source": r["source"], "updated_at": r["updated_at"]}
            for r in rows
        ]
    finally:
        conn.close()


def parse_fact(fact: str) -> tuple[str, str]:
    """解析 key:value 格式偏好. 返回 (key, value)."""
    if ":" in fact or "：" in fact:
        sep = ":" if ":" in fact else "："
        key, _, value = fact.partition(sep)
        return key.strip(), value.strip()
    # 无冒号: 用前 20 字符做 key
    return fact[:20].strip(), fact.strip()


# ── KOS Search (连接池复用) ──────────────────────────────────────

try:
    import httpx
    _kos_client: httpx.Client | None = None
except ImportError:
    _kos_client = None  # type: ignore[assignment]


def _get_kos_client():
    """复用 KOS HTTP 连接池 (模块级单例)."""
    global _kos_client
    if _kos_client is None:
        import httpx
        kos_url = os.environ.get("KOS_API_URL", "http://localhost:8766")
        _kos_client = httpx.Client(
            base_url=kos_url,
            timeout=httpx.Timeout(5.0, connect=2.0),
        )
    return _kos_client


def kos_search(query: str, limit: int = 5) -> dict:
    """KOS 搜索 — 连接池复用 + 超时缩短 + 优雅降级."""
    try:
        client = _get_kos_client()
        resp = client.get("/api/v1/search", params={
            "q": query, "mode": "hybrid", "limit": limit,
        })
        resp.raise_for_status()
        data = resp.json()
        return {"results": data.get("results", [])}
    except Exception as e:
        return {"error": str(e), "results": []}


def kos_context(query: str) -> dict:
    """KOS 上下文构建."""
    try:
        client = _get_kos_client()
        resp = client.get("/api/v1/context", params={
            "q": query, "mode": "balanced",
        })
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e), "context": ""}


# ── LLM Gateway (best-effort) ─────────────────────────────────────

def llm_complete(prompt: str, model: str = "deepseek-v4-flash") -> str:
    """调用 LLM Gateway. 失败返回空字符串."""
    gateway_url = os.environ.get("LLM_GATEWAY_URL", "http://localhost:3000")
    try:
        import httpx
        resp = httpx.post(
            f"{gateway_url}/api/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 2048,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        pass
    # 降级: ollama 本地
    try:
        import httpx
        resp = httpx.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "qwen2.5:latest",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")
    except Exception:
        return ""


# ── Prompt 构建 (单一源头) ────────────────────────────────────────

def build_brain_prompt(
    question: str,
    knowledge_results: list[dict],
    preferences: list[dict],
    recent_history: list[dict],
) -> str:
    """构建 Brain LLM prompt — CLI + Web 共享."""
    # 偏好约束
    pref_constraints = ""
    if preferences:
        lines = [f"- 用户{p['key']}: {p['value']}" for p in preferences[:5]]
        pref_constraints = "## 用户偏好约束\n" + "\n".join(lines)

    # 知识文本
    knowledge_text = ""
    if knowledge_results:
        for r in knowledge_results[:5]:
            title = r.get("title") or r.get("name") or ""
            content = r.get("content") or r.get("snippet") or r.get("text") or ""
            if title or content:
                knowledge_text += f"\n### {title}\n{content}\n"

    # 历史上下文
    history_text = ""
    if recent_history:
        history_text = "\n".join(
            f"[{h['role']}] {h['content'][:80]}" for h in recent_history[-4:]
        )

    return f"""你是用户的个人数字大脑助手。

{pref_constraints or "(无用户偏好)"}

## 知识库搜索结果
{knowledge_text or "(无相关搜索结果)"}

## 最近对话上下文
{history_text or "(无历史)"}

## 用户问题
{question}

请结合知识库和用户偏好回答。如果知识库有相关信息，引用来源。用中文回答。"""


# ── 来源格式化 ────────────────────────────────────────────────────

def format_sources_cli(results: list[dict]) -> str:
    """CLI 格式: 带 score + snippet 的来源列表."""
    if not results:
        return "  (无外部知识来源)"
    lines = []
    for i, r in enumerate(results[:5], 1):
        title = r.get("title") or r.get("name") or r.get("id", "unknown")
        score = r.get("score")
        score_str = f" [score={score:.3f}]" if isinstance(score, (int, float)) else ""
        snippet = (r.get("snippet") or r.get("content") or "")[:120]
        lines.append(f"  {i}. {title}{score_str}")
        if snippet:
            lines.append(f"     {snippet}")
    return "\n".join(lines)


# ── 核心问答流程 ──────────────────────────────────────────────────

def ask(question: str, user: str = "default") -> dict:
    """核心问答: KOS 搜索 + 记忆加载 + LLM 调用 + 存储.
    返回 {answer, sources, fallback, memory_used}.
    """
    # 1. KOS 搜索
    kos_result = kos_search(question)
    results = kos_result.get("results", [])

    # 2. 加载记忆
    prefs = get_preferences(limit=10)
    recent = get_history(limit=6)

    # 3. 构建 prompt
    prompt = build_brain_prompt(question, results, prefs, recent)

    # 4. LLM 调用
    answer = llm_complete(prompt)

    # 5. 提取来源 ID
    source_ids = []
    source_objs = []
    for r in results[:5]:
        sid = r.get("id") or r.get("title") or ""
        title = r.get("title") or r.get("name") or ""
        if sid or title:
            source_ids.append(sid)
            source_objs.append({
                "id": sid,
                "title": title,
                "score": r.get("score"),
            })

    # 6. 自动提取偏好
    try:
        from cockpit.brain_memory import auto_extract_and_store
        auto_extract_and_store(question, source="inferred")
    except Exception:
        pass  # 偏好提取失败不影响主流程

    # 7. 存储对话
    store_conversation("user", question, user=user)
    store_conversation("assistant", answer or "[无回答]", sources=source_ids, user=user)

    return {
        "answer": answer or "",
        "sources": source_objs,
        "fallback": not bool(answer),
        "memory_used": {
            "preferences": len(prefs),
            "history": len(recent),
        },
    }
