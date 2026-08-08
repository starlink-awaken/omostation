#!/usr/bin/env python3
"""Scene Card Intake Pipeline — 邮件/文件/消息→结构化事项摄入引擎.

The intake pipeline takes raw input from multiple sources, extracts structured
content, enriches with knowledge, and adds to the decision inbox.

Sources: email, file, message, manual, oa (办公自动化), sms

Flow:
  raw_input → source_extractor → structured_content → knowledge_enrich → inbox_intent

SSOT:  ecos/src/ecos/ssot/registry/scene-cards.yaml
Engine: bin/ssot/scene-card-intake-pipeline.py
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Data types ──

@dataclass
class EnrichedContent:
    title: str = ""
    description: str = ""
    category: str = "general"
    priority: str = "P3"
    deadline: str | None = None
    related_knowledge: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    extraction_method: str = "raw"


@dataclass
class IntakeResult:
    ok: bool = False
    intent_id: str = ""
    scene_id: str = ""
    journey_id: str = ""
    enriched: EnrichedContent | None = None
    error: str = ""


# ── Helpers ──

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ── Source extractors ──

def _extract_email(raw: str) -> EnrichedContent:
    """Extract structured content from email text."""
    lines = raw.strip().split("\n")
    title = ""
    description = raw
    sender = ""
    # Try to extract subject
    for line in lines:
        if line.lower().startswith("subject:") or line.lower().startswith("主题"):
            title = line.split(":", 1)[1].strip()
            break
        if line.lower().startswith("from:") or line.lower().startswith("发件人"):
            sender = line.split(":", 1)[1].strip()
    if not title:
        title = raw[:80].strip()
    tags = ["email"]
    if sender:
        tags.append(f"from:{sender}")
    # Priority detection
    priority = _detect_priority(raw)
    return EnrichedContent(
        title=title,
        description=raw[:500],
        category="email",
        priority=priority,
        tags=tags,
        extraction_method="email_extractor",
        confidence=0.8,
    )


def _extract_file(raw: str, filename: str = "") -> EnrichedContent:
    """Extract structured content from a file."""
    title = filename or raw[:60].strip()
    lines = raw.strip().split("\n")
    # Try to find a title from the first non-empty line
    for line in lines[:5]:
        line = line.strip()
        if line and not line.startswith("#") and len(line) > 5:
            title = line[:80]
            break
    priority = _detect_priority(raw)
    tags = ["file"]
    if filename:
        ext = Path(filename).suffix.lower()
        tags.append(f"ext:{ext}")
    return EnrichedContent(
        title=title,
        description=raw[:500],
        category="file",
        priority=priority,
        tags=tags,
        extraction_method="file_extractor",
        confidence=0.7,
    )


def _extract_message(raw: str) -> EnrichedContent:
    """Extract structured content from a chat message."""
    title = raw[:80].strip()
    priority = _detect_priority(raw)
    return EnrichedContent(
        title=title,
        description=raw[:500],
        category="message",
        priority=priority,
        tags=["message"],
        extraction_method="message_extractor",
        confidence=0.6,
    )


def _extract_oa(raw: str) -> EnrichedContent:
    """Extract structured content from OA notification."""
    content = EnrichedContent(
        title=raw[:80].strip(),
        description=raw[:500],
        category="oa",
        priority=_detect_priority(raw),
        tags=["oa"],
        extraction_method="oa_extractor",
        confidence=0.75,
    )
    # OA often has deadline info
    deadline = _detect_deadline(raw)
    if deadline:
        content.deadline = deadline
    return content


def _extract_sms(raw: str) -> EnrichedContent:
    """Extract structured content from SMS."""
    return EnrichedContent(
        title=raw[:80].strip(),
        description=raw[:500],
        category="sms",
        priority=_detect_priority(raw),
        tags=["sms"],
        extraction_method="sms_extractor",
        confidence=0.5,
    )


def _extract_manual(raw: str) -> EnrichedContent:
    """Extract structured content from manual input."""
    return EnrichedContent(
        title=raw[:80].strip(),
        description=raw[:500],
        category="manual",
        priority=_detect_priority(raw),
        tags=["manual"],
        extraction_method="manual_input",
        confidence=0.9,
    )


# ── Priority/deadline detection ──

_PRIORITY_KEYWORDS = {
    "P0": {"紧急", "urgent", "critical", "立即", "immediately", "asap", "事故", "故障", "危机"},
    "P1": {"重要", "important", "high", "高优先级", "今天", "today", "截止"},
    "P2": {"一般", "medium", "normal", "本周", "this week", "尽快"},
}


def _detect_priority(text: str) -> str:
    """Detect priority from text content."""
    lower = text.lower()
    for priority, keywords in _PRIORITY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in lower:
                return priority
    return "P3"


_DEADLINE_PATTERNS = [
    (r"截止(?:日期|时间)?[:：]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})", 1),
    (r"deadline[:：]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})", 1),
    (r"due[:：]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})", 1),
    (r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*(?:前|之前|前完成)", 1),
]


def _detect_deadline(text: str) -> str | None:
    """Detect deadline from text content."""
    for pattern, group in _DEADLINE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(group)
    return None


# ── Knowledge enrichment (lightweight) ──

def _enrich_with_knowledge(content: EnrichedContent, kos_dir: Path | None = None) -> EnrichedContent:
    """Enrich content with knowledge from KOS index.

    This is a lightweight version. For full enrichment, use the KOS MCP server.
    """
    # Simple tag-based enrichment: add related tags based on content
    text = f"{content.title} {content.description}".lower()

    knowledge_tags = {
        "技术": ["deploy", "release", "bug", "fix", "pr", "merge", "代码", "部署", "上线"],
        "管理": ["meeting", "review", "plan", "report", "会议", "评审", "计划", "报告"],
        "客户": ["customer", "client", "user", "feedback", "客户", "用户", "反馈", "投诉"],
        "财务": ["invoice", "budget", "cost", "payment", "发票", "预算", "费用", "付款"],
        "人事": ["hire", "onboard", "leave", "请假", "招聘", "入职", "离职"],
    }

    for category, keywords in knowledge_tags.items():
        for kw in keywords:
            if kw in text:
                content.tags.append(category)
                content.related_knowledge.append(f"tag:{category}")
                break

    content.tags = list(set(content.tags))
    content.related_knowledge = list(set(content.related_knowledge))
    return content


# ── Main intake pipeline ──

EXTRACTORS = {
    "email": _extract_email,
    "file": _extract_file,
    "message": _extract_message,
    "manual": _extract_manual,
    "oa": _extract_oa,
    "sms": _extract_sms,
}


def intake(
    workspace_root: Path,
    source: str,
    raw_content: str,
    scene_id: str,
    journey_id: str | None = None,
    filename: str = "",
    enrich: bool = True,
) -> IntakeResult:
    """Run the full intake pipeline: extract → enrich → add to inbox.

    Args:
        workspace_root: Root of the workspace.
        source: Source type (email, file, message, manual, oa, sms).
        raw_content: Raw input content.
        scene_id: Target scene ID.
        journey_id: Target journey ID (uses first journey if None).
        filename: Original filename (for file source).
        enrich: Whether to run knowledge enrichment.

    Returns:
        IntakeResult with the created intent ID and enriched content.
    """
    # Step 1: Extract structured content
    extractor = EXTRACTORS.get(source)
    if extractor is None:
        return IntakeResult(ok=False, error=f"Unknown source: {source}")

    if source == "file":
        enriched = extractor(raw_content, filename=filename)
    else:
        enriched = extractor(raw_content)

    # Step 2: Knowledge enrichment
    if enrich:
        enriched = _enrich_with_knowledge(enriched)

    # Step 3: Add to decision inbox
    try:
        import importlib.util
        import sys

        engine_path = workspace_root / "bin" / "ssot" / "scene-card-decision-inbox.py"
        spec = importlib.util.spec_from_file_location("scene_card_decision_inbox_intake", str(engine_path))
        if spec is None or spec.loader is None:
            return IntakeResult(ok=False, error="decision inbox engine unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        scene = module.load_scene(workspace_root, scene_id)
        if scene is None:
            return IntakeResult(ok=False, error=f"Scene {scene_id} not found")

        jid = journey_id or (scene.journeys[0].id if scene.journeys else "")
        if not jid:
            return IntakeResult(ok=False, error="Scene has no journeys")

        intent = module.add_intent(
            workspace_root,
            scene_id=scene_id,
            journey_id=jid,
            source=source,
            raw_content=raw_content,
            priority=enriched.priority,
        )
        # Store structured content in evidence
        module.update_intent_status(
            workspace_root,
            intent_id=intent.id,
            new_status="pending",
            actor="intake_pipeline",
        )

        return IntakeResult(
            ok=True,
            intent_id=intent.id,
            scene_id=scene_id,
            journey_id=jid,
            enriched=enriched,
        )
    except Exception as exc:
        return IntakeResult(ok=False, error=str(exc))


def batch_intake(
    workspace_root: Path,
    items: list[dict[str, Any]],
    scene_id: str,
) -> list[IntakeResult]:
    """Run batch intake for multiple items."""
    results = []
    for item in items:
        result = intake(
            workspace_root,
            source=item.get("source", "manual"),
            raw_content=item.get("content", ""),
            scene_id=scene_id,
            journey_id=item.get("journey_id"),
            filename=item.get("filename", ""),
            enrich=item.get("enrich", True),
        )
        results.append(result)
    return results


def preview_intake(
    raw_content: str,
    source: str = "manual",
    filename: str = "",
) -> EnrichedContent:
    """Preview what the intake pipeline would produce without persisting."""
    extractor = EXTRACTORS.get(source)
    if extractor is None:
        return EnrichedContent(description=f"Unknown source: {source}", confidence=0.0)
    if source == "file":
        enriched = extractor(raw_content, filename=filename)
    else:
        enriched = extractor(raw_content)
    enriched = _enrich_with_knowledge(enriched)
    return enriched
