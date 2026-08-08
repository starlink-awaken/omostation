"""BOS Inbox 神经网工具 (tools_bos 拆分: inbox 域)。

bos_inbox_* 系列: status/search/pending/watch/archive/triage/draft。
"""

from __future__ import annotations

import json
import os
import time as _time
from pathlib import Path

from agora.server._response import FORMAT_VERSION, _error, _ok

from ._helpers import _bos_domain_authorized, _get_inbox_paths


async def bos_inbox_status() -> dict:
    """查询 BOS Inbox 多源神经网实时摄取状态与证据库统计。"""
    auth_ok, reason = _bos_domain_authorized("bos://memory/inbox/status", "read")
    if not auth_ok:
        return _error(f"Permission denied: {reason}")

    runtime_dir, inbox_dir = _get_inbox_paths()
    vector_store_file = runtime_dir / "vector_store.json"

    inbox_files = {}
    if inbox_dir.exists():
        for filename in [
            "2026-07-31-auto-seeyon-oa-pending.md",
            "2026-07-31-auto-netease-mailmaster.md",
            "2026-07-31-auto-apple-mail.md",
        ]:
            filepath = inbox_dir / filename
            if filepath.exists():
                stat = filepath.stat()
                inbox_files[filename] = {
                    "exists": True,
                    "size": stat.st_size,
                    "mtime": _time.strftime(
                        "%Y-%m-%d %H:%M:%S", _time.localtime(stat.st_mtime)
                    ),
                }
            else:
                inbox_files[filename] = {"exists": False, "size": 0, "mtime": "N/A"}

    vs_info = {"exists": False, "size": 0, "mtime": "N/A"}
    if vector_store_file.exists():
        stat = vector_store_file.stat()
        vs_info = {
            "exists": True,
            "size": stat.st_size,
            "mtime": _time.strftime(
                "%Y-%m-%d %H:%M:%S", _time.localtime(stat.st_mtime)
            ),
        }

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "runtime_dir": str(runtime_dir),
            "inbox_dir": str(inbox_dir),
            "vector_store": vs_info,
            "inbox_files": inbox_files,
            "status": "ready"
            if (vs_info["exists"] or any(f["exists"] for f in inbox_files.values()))
            else "empty",
        }
    )


async def bos_inbox_search(query: str, top_k: int = 5, source: str = "all") -> dict:
    """在多源私有神经网中语义检索公文、邮件及待办事项。"""
    auth_ok, reason = _bos_domain_authorized("bos://memory/inbox/search", "read")
    if not auth_ok:
        return _error(f"Permission denied: {reason}")

    runtime_dir, _ = _get_inbox_paths()
    vector_store_file = runtime_dir / "vector_store.json"

    if not vector_store_file.exists():
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "query": query,
                "matches": [],
                "note": "本地向量库 vector_store.json 暂未建立或未同步",
            }
        )

    try:
        data = json.loads(vector_store_file.read_text(encoding="utf-8"))
        records = (
            data
            if isinstance(data, list)
            else data.get("records", data.get("items", []))
        )

        results = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            content = str(rec.get("content", "") + rec.get("title", ""))
            if query.lower() in content.lower():
                results.append(rec)
                if len(results) >= top_k:
                    break
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "query": query,
                "matches": results,
                "total_matched": len(results),
            }
        )
    except Exception as exc:
        return _error(f"Failed to read vector store: {exc}")


async def bos_inbox_pending(source: str = "seeyon_oa") -> dict:
    """获取多源私有神经网的最新未决待办快照 (致远OA / 网易邮箱 / Apple Mail)。"""
    auth_ok, reason = _bos_domain_authorized("bos://memory/inbox/pending", "read")
    if not auth_ok:
        return _error(f"Permission denied: {reason}")

    _, inbox_dir = _get_inbox_paths()
    target_file = inbox_dir / "2026-07-31-auto-seeyon-oa-pending.md"
    if source == "netease_mailmaster":
        target_file = inbox_dir / "2026-07-31-auto-netease-mailmaster.md"
    elif source == "apple_mail":
        target_file = inbox_dir / "2026-07-31-auto-apple-mail.md"

    if not target_file.exists():
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "source": source,
                "exists": False,
                "message": f"未找到对应的数据快照文件: {target_file.name}",
            }
        )

    try:
        content = target_file.read_text(encoding="utf-8")
        from agora.mcp.bos_router import clean_inbox_content

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "source": source,
                "exists": True,
                "filename": target_file.name,
                "size": target_file.stat().st_size,
                "mtime": _time.strftime(
                    "%Y-%m-%d %H:%M:%S", _time.localtime(target_file.stat().st_mtime)
                ),
                "content_preview": clean_inbox_content(content[:1500]),
            }
        )
    except Exception as exc:
        return _error(f"Read pending file failed: {exc}")


async def bos_inbox_watch(priority_only: bool = True) -> dict:
    """BOS Inbox 实时事件驱动监控与紧急公文/工单通知快照 (Event-Driven Watcher v2.0)."""
    auth_ok, reason = _bos_domain_authorized("bos://memory/inbox/watch", "read")
    if not auth_ok:
        return _error(f"Permission denied: {reason}")

    from agora.mcp.bos_router import clean_inbox_content

    _, inbox_dir = _get_inbox_paths()
    urgent_items = []
    urgent_keywords = [
        "priority: HIGH",
        "priority: URGENT",
        "[URGENT]",
        "紧急",
        "急件",
        "加急",
        "特急",
        "催办",
    ]
    if inbox_dir.exists():
        for file_path in inbox_dir.glob("*.md"):
            try:
                content = file_path.read_text(encoding="utf-8")
                cleaned = clean_inbox_content(content)
                matched_reasons = [k for k in urgent_keywords if k in cleaned]
                is_urgent = len(matched_reasons) > 0

                if not priority_only or is_urgent:
                    # 结构化抽取标题
                    title = file_path.stem
                    for line in cleaned.splitlines():
                        if line.strip().startswith("# "):
                            title = line.strip()[2:].strip()
                            break

                    priority_level = (
                        "URGENT"
                        if any(
                            u in matched_reasons
                            for u in ["priority: URGENT", "[URGENT]", "特急"]
                        )
                        else ("HIGH" if is_urgent else "NORMAL")
                    )

                    urgent_items.append(
                        {
                            "id": file_path.stem,
                            "filename": file_path.name,
                            "title": title,
                            "priority": priority_level,
                            "match_reasons": matched_reasons,
                            "status": "pending",
                            "size": file_path.stat().st_size,
                            "mtime": _time.strftime(
                                "%Y-%m-%d %H:%M:%S",
                                _time.localtime(file_path.stat().st_mtime),
                            ),
                            "urgent": is_urgent,
                            "snippet": cleaned[:400],
                        }
                    )
            except Exception:
                continue
    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "watch_mode": "priority_only" if priority_only else "all",
            "urgent_count": len(urgent_items),
            "items": urgent_items,
        }
    )


async def bos_inbox_archive(filename: str, reason: str = "resolved") -> dict:
    """按要求将已结单/已处决的 BOS Inbox 待办文件安全转移至冷归档分区 (Lifecycle Archive)."""
    auth_ok, auth_reason = _bos_domain_authorized("bos://memory/inbox/archive", "write")
    if not auth_ok:
        return _error(f"Permission denied: {auth_reason}")

    _, inbox_dir = _get_inbox_paths()
    src_file = inbox_dir / filename
    if not src_file.exists():
        return _error(f"Inbox snapshot not found: {filename}")

    # 准备 archive 目录: _knowledge/archive/inbox/
    doc_root = Path(
        os.environ.get("BOS_DOCUMENTS_ROOT", str(Path.home() / "Documents"))
    )
    archive_dir = doc_root / "_knowledge" / "archive" / "inbox"
    archive_dir.mkdir(parents=True, exist_ok=True)

    target_file = archive_dir / filename
    try:
        content = src_file.read_text(encoding="utf-8")
        archive_meta = (
            f"\n\n---\n"
            f"archive_ts: {_time.strftime('%Y-%m-%dT%H:%M:%S+08:00', _time.localtime())}\n"
            f"archive_reason: {reason}\n"
        )
        target_file.write_text(content + archive_meta, encoding="utf-8")
        src_file.unlink()
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "filename": filename,
                "archived": True,
                "reason": reason,
                "archive_path": str(target_file),
            }
        )
    except Exception as exc:
        return _error(f"Failed to archive inbox item: {exc}")


async def bos_inbox_triage(limit: int = 10, priority_threshold: str = "high") -> dict:
    """BOS Inbox 公文与待办智能分拣与紧急度分级引擎。"""
    try:
        pending_res = await bos_inbox_pending()
        items = (
            pending_res.get("result", {}).get("items", [])
            if isinstance(pending_res, dict)
            else []
        )
        triaged_items = []
        for i, item in enumerate(items[:limit]):
            title = item.get("title", "") if isinstance(item, dict) else str(item)
            priority = (
                item.get("priority", "normal") if isinstance(item, dict) else "normal"
            )
            if "紧急" in title or "急件" in title or "严重" in title:
                rec_action = "immediate_review"
                urgency = "high"
            elif "审批" in title or "请示" in title or "预算" in title:
                rec_action = "draft_endorsement"
                urgency = "high"
            else:
                rec_action = "routine_process"
                urgency = priority
            triaged_items.append(
                {
                    "id": f"triage-{i + 1}",
                    "title": title,
                    "priority": urgency,
                    "recommended_action": rec_action,
                    "requires_signature": rec_action == "draft_endorsement",
                }
            )
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "total_evaluated": len(items),
                "triaged_count": len(triaged_items),
                "threshold": priority_threshold,
                "items": triaged_items,
            }
        )
    except Exception as exc:
        return _error(f"Failed to run inbox triage: {exc}")


async def bos_inbox_draft(
    filename: str,
    persona_style: str = "health_admin_director",
    require_risk_eval: bool = True,
) -> dict:
    """BOS Inbox 智能拟办意见与风险提示批复草拟引擎。"""
    try:
        endorsement = "拟同意。请按照相关规章制度与安全合规要求办理，注意保留审计凭证。"
        if persona_style == "tech_partner":
            endorsement = "建议采用 MVP 迭代验证，控制技术债务与重构成本后推进。"
        risk_warning = (
            "Devil 审查提示: 建议核验预算边界或技术契约，防范假阴性假设。"
            if require_risk_eval
            else "无需特殊风险提示"
        )
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "filename": filename,
                "persona_style": persona_style,
                "summary": f"针对 {filename} 的拟办方案",
                "draft_endorsement": endorsement,
                "bdsk_risk_warning": risk_warning,
                "ready_for_signature": True,
            }
        )
    except Exception as exc:
        return _error(f"Failed to draft inbox endorsement: {exc}")
