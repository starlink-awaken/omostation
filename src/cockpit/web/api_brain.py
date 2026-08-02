"""cockpit.web.api_brain — 个人数字大脑 Web API (Phase 48 MVP).

路由:
    POST /api/brain/ask        — 问答
    GET  /api/brain/context    — 记忆上下文
    POST /api/brain/remember   — 手动记忆
    GET  /api/brain/history    — 对话历史
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

# 复用 CLI 命令模块的存储和搜索逻辑
from cockpit.commands.brain import (
    get_history,
    get_preferences,
    kos_search_sync,
    llm_complete,
    store_conversation,
    store_preference,
)

router = APIRouter(prefix="/api/brain", tags=["brain"])


@router.post("/ask")
async def brain_ask(payload: dict[str, Any]) -> dict[str, Any]:
    """问答端点 — 检索 KOS + 加载记忆 + LLM 回答."""
    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    # 1. KOS 搜索
    kos_result = kos_search_sync(question)
    results = kos_result.get("results", [])

    # 2. 加载记忆
    prefs = get_preferences(limit=10)
    recent = get_history(limit=6)
    memory_parts = []
    if prefs:
        memory_parts.append("用户偏好:\n" + "\n".join(f"  • {p['key']}: {p['value']}" for p in prefs[:5]))
    if recent:
        memory_parts.append("最近对话:\n" + "\n".join(f"  [{h['role']}] {h['content'][:80]}" for h in recent[-4:]))
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

    # 4. LLM
    answer = llm_complete(prompt)
    store_conversation("user", question)
    store_conversation("assistant", answer or "[无回答]", sources=source_ids)

    # 知识激活: 追加相关知识推荐 (Phase 49 T1)
    knowledge_suggestions: list[dict[str, Any]] = []
    try:
        from cockpit.knowledge_activation import (
            ActivationContext,
            recommend_for_context,
        )

        suggestions = recommend_for_context(
            ActivationContext.RESEARCH,
            content=question,
            limit=3,
        )
        knowledge_suggestions = [
            {
                "title": s.get("title", ""),
                "score": s.get("score"),
                "snippet": (s.get("snippet") or s.get("content") or "")[:120],
            }
            for s in suggestions
            if s.get("title")
        ]
    except Exception:
        pass  # KOS 不可用时静默降级

    return {
        "answer": answer or "",
        "sources": [
            {
                "id": r.get("id") or r.get("title") or "",
                "title": r.get("title") or r.get("name") or "",
                "score": r.get("score"),
            }
            for r in results[:5]
        ],
        "memory_used": {
            "preferences": len(prefs),
            "history": len(recent),
        },
        "fallback": not bool(answer),
        "knowledge_suggestions": knowledge_suggestions,
    }


@router.get("/context")
async def brain_context() -> dict[str, Any]:
    """获取记忆上下文."""
    prefs = get_preferences()
    history = get_history(limit=20)
    return {
        "preferences": [{"key": p["key"], "value": p["value"]} for p in prefs],
        "recent_history": [{"role": h["role"], "content": h["content"][:200]} for h in history[-10:]],
        "total_conversations": len(history),
    }


@router.post("/remember")
async def brain_remember(payload: dict[str, Any]) -> dict[str, str]:
    """手动存入偏好/事实."""
    fact = (payload.get("fact") or "").strip()
    if not fact:
        raise HTTPException(status_code=400, detail="fact is required")

    if ":" in fact or "：" in fact:
        sep = ":" if ":" in fact else "："
        key, _, value = fact.partition(sep)
        key, value = key.strip(), value.strip()
    else:
        key = fact[:20].strip()
        value = fact.strip()

    store_preference(key, value, source="explicit")
    return {"status": "ok", "key": key, "value": value}


@router.get("/history")
async def brain_history(limit: int = 30) -> list[dict[str, Any]]:
    """获取对话历史."""
    return get_history(limit=limit)
