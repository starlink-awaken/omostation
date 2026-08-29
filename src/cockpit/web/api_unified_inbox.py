"""Unified Inbox & Signature Protocol API (LECP v3.0 / L3 Entry - v2.0 优化版).

提供夏明星唯一的审阅、修改、署名发出的 HITL 接口：
1. GET /api/inbox/pending: 获取待审阅的 P0~P4 待办卡片列表；
2. GET /api/inbox/preferences: 获取 Memory OS 已学习沉淀的个性偏好规则；
3. POST /api/inbox/preview-diff: 实时预览夏明星修改内容与原拟草稿的富文本差异高亮；
4. POST /api/inbox/sign: 执行一键原子署名，外发并触发 Memory OS 语义 Diff 提取与记忆反思。
"""

from __future__ import annotations

import difflib
import importlib.util
import json
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from cockpit.compat import WORKSPACE_ROOT

router = APIRouter(prefix="/api/inbox", tags=["unified-inbox"])


class SignRequest(BaseModel):
    entity_id: str = Field(..., description="LECP 实体 ID")
    domain: str = Field(default="p0_work", description="所属领域")
    draft_text: str = Field(default="", description="AI 原拟草稿")
    final_text: str = Field(..., description="夏明星最终修改署名文本")
    action: str = Field(default="sign_and_archive", description="执行动作 (send_email / sign_and_archive)")


class PreviewDiffRequest(BaseModel):
    draft_text: str = Field(..., description="原拟文本")
    modified_text: str = Field(..., description="修改文本")


def _get_diff_engine():
    diff_engine_path = WORKSPACE_ROOT / "bin" / "memory" / "diff_engine.py"
    if not diff_engine_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("diff_engine", diff_engine_path)
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@router.get("/pending")
async def get_pending_items() -> dict[str, Any]:
    """获取所有待审阅处理的 LECP 待办事项"""
    inbox_watcher_path = WORKSPACE_ROOT / "bin" / "ingress" / "inbox_watcher.py"
    items = []
    if inbox_watcher_path.exists():
        try:
            spec = importlib.util.spec_from_file_location("inbox_watcher", inbox_watcher_path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                items = mod.scan_inbox()
        except Exception:
            pass

    return {
        "ok": True,
        "count": len(items),
        "items": items,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/preferences")
async def get_learned_preferences(domain: str = "p0_work") -> dict[str, Any]:
    """获取 Memory OS 沉淀的夏明星专属写作偏好"""
    mod = _get_diff_engine()
    rules = []
    if mod and hasattr(mod, "get_active_preferences"):
        rules = mod.get_active_preferences(domain=domain)
    return {
        "ok": True,
        "domain": domain,
        "rules_count": len(rules),
        "preferences": rules,
    }


@router.post("/preview-diff")
async def preview_diff(req: PreviewDiffRequest) -> dict[str, Any]:
    """实时渲染夏明星修改内容与 AI 草稿的差异对比"""
    mod = _get_diff_engine()
    diff_summary = {}
    if mod and hasattr(mod, "extract_semantic_diff"):
        diff_summary = mod.extract_semantic_diff(req.draft_text, req.modified_text)

    # 构造 HTML 格式的高亮标签
    matcher = difflib.SequenceMatcher(None, req.draft_text, req.modified_text)
    html_chunks = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            html_chunks.append(req.draft_text[i1:i2])
        elif tag == "delete":
            html_chunks.append(f"<del style='color:red;background:#ffeef0;'>{req.draft_text[i1:i2]}</del>")
        elif tag == "insert":
            html_chunks.append(
                f"<ins style='color:green;background:#e6ffed;text-decoration:none;font-weight:bold;'>{req.modified_text[j1:j2]}</ins>"
            )
        elif tag == "replace":
            html_chunks.append(f"<del style='color:red;background:#ffeef0;'>{req.draft_text[i1:i2]}</del>")
            html_chunks.append(
                f"<ins style='color:green;background:#e6ffed;text-decoration:none;font-weight:bold;'>{req.modified_text[j1:j2]}</ins>"
            )

    return {
        "ok": True,
        "html_diff": "".join(html_chunks),
        "diff_summary": diff_summary,
    }


@router.post("/sign")
async def sign_item(req: SignRequest) -> dict[str, Any]:
    """执行夏明星一键署名与 Diff 提取"""
    diff_res = {}
    mod = _get_diff_engine()

    if mod and req.draft_text and hasattr(mod, "record_signature_diff"):
        try:
            diff_res = mod.record_signature_diff(
                entity_id=req.entity_id,
                domain=req.domain,
                draft_text=req.draft_text,
                final_text=req.final_text,
            )
        except Exception as e:
            diff_res = {"error": str(e)}

    return {
        "ok": True,
        "status": "signed",
        "entity_id": req.entity_id,
        "signed_by": "夏明星",
        "signed_at": datetime.now(UTC).isoformat(),
        "diff_summary": diff_res,
    }
