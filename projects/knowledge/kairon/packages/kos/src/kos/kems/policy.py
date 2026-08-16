"""Deterministic first-pass analysis for health-policy documents.

This module deliberately produces reviewable facts and evidence, rather than
pretending that an LLM-generated answer is authoritative.  An LLM can be
added later as an optional enrichment step without changing this contract.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_DATE = re.compile(r"(?:20\d{2})[年./-]\s*\d{1,2}[月./-]\s*\d{1,2}日?")
_DOC_NUMBER = re.compile(r"[\u4e00-\u9fff]{1,12}[〔(（]\d{4}[〕)）]\d{1,8}号?")
_LABEL = re.compile(r"(?:发布单位|发布机构|发文机关|制定机关|牵头单位|责任单位)\s*[:：]\s*([^\n，。；;]{2,40})")

_TYPE_RULES = (
    ("通知", ("通知", "印发", "转发")),
    ("方案", ("实施方案", "工作方案", "行动计划")),
    ("办法", ("管理办法", "实施办法", "管理规定")),
    ("报告", ("报告", "总结", "分析")),
    ("意见", ("指导意见", "实施意见", "意见")),
)
_TOPIC_RULES = (
    "医疗",
    "医保",
    "药品",
    "医药",
    "卫生",
    "信息化",
    "人工智能",
    "数据",
    "复议",
    "基层",
    "三医",
)
_ACTION_WORDS = ("应当", "必须", "须", "不得", "负责", "完成", "报送", "建立", "推动")


@dataclass(frozen=True)
class Evidence:
    """A source-local quote that allows a reviewer to verify one extracted fact."""

    kind: str
    line: int
    excerpt: str


@dataclass(frozen=True)
class PolicyAnalysis:
    """Stable, JSON-serializable output for the KEMS policy-document slice."""

    schema_version: str
    source_name: str
    source_sha256: str | None
    title: str
    document_type: str
    issuer: str | None
    document_number: str | None
    dates: tuple[str, ...]
    topics: tuple[str, ...]
    summary: str
    key_points: tuple[str, ...]
    actions: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    review_flags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a transport-safe result for APIs, reports, and run records."""
        result = asdict(self)
        result["dates"] = list(self.dates)
        result["topics"] = list(self.topics)
        result["key_points"] = list(self.key_points)
        result["actions"] = list(self.actions)
        result["evidence"] = [asdict(item) for item in self.evidence]
        result["review_flags"] = list(self.review_flags)
        return result


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" \t|｜")


def _first_title(lines: list[str], source_name: str) -> str:
    for line in lines[:12]:
        cleaned = _clean_line(line)
        if cleaned.startswith("#"):
            return cleaned.lstrip("# ").strip()
    for line in lines[:8]:
        cleaned = _clean_line(line)
        if 4 <= len(cleaned) <= 120 and not cleaned.startswith(("发布", "发文", "文号")):
            return cleaned
    return Path(source_name).stem or source_name


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[。！？!?；;])\s*", text) if len(item.strip()) >= 12]


def analyze_policy_document(
    content: str,
    *,
    source_name: str = "unknown",
    source_sha256: str | None = None,
) -> PolicyAnalysis:
    """Extract a conservative KEMS policy brief from already parsed text.

    The result is intentionally deterministic.  It is suitable for fixtures,
    audit trails, and human review before any model-assisted enrichment.
    """
    if not content or not content.strip():
        raise ValueError("policy document content must not be empty")

    lines = [_clean_line(line) for line in content.splitlines()]
    lines = [line for line in lines if line]
    text = "\n".join(lines)
    title = _first_title(lines, source_name)
    dates = tuple(dict.fromkeys(_DATE.findall(text)))
    number_match = _DOC_NUMBER.search(text)
    issuer_match = _LABEL.search(text)
    document_number = number_match.group(0) if number_match else None
    issuer = issuer_match.group(1).strip() if issuer_match else None

    document_type = "通用"
    for candidate, keywords in _TYPE_RULES:
        if any(keyword in title or keyword in text[:500] for keyword in keywords):
            document_type = candidate
            break

    topics = tuple(topic for topic in _TOPIC_RULES if topic in text)
    sentences = _sentences(text)
    key_points = tuple(sentences[:5])
    summary = "".join(sentences[:3])[:360] or text[:360]
    actions = tuple(
        dict.fromkeys(line[:240] for line in lines if any(word in line for word in _ACTION_WORDS) and len(line) >= 12)
    )[:10]

    evidence: list[Evidence] = []
    for line_number, line in enumerate(lines, start=1):
        if line == title or line.lstrip("# ").strip() == title:
            evidence.append(Evidence("title", line_number, line[:240]))
        if document_number and document_number in line:
            evidence.append(Evidence("document_number", line_number, line[:240]))
        if issuer and issuer in line:
            evidence.append(Evidence("issuer", line_number, line[:240]))
        if line in actions:
            evidence.append(Evidence("action", line_number, line[:240]))
        if len(evidence) >= 20:
            break

    review_flags: list[str] = []
    if not issuer:
        review_flags.append("issuer_not_detected")
    if not document_number:
        review_flags.append("document_number_not_detected")
    if not actions:
        review_flags.append("action_items_not_detected")

    return PolicyAnalysis(
        schema_version="kems.policy-analysis.v1",
        source_name=source_name,
        source_sha256=source_sha256,
        title=title,
        document_type=document_type,
        issuer=issuer,
        document_number=document_number,
        dates=dates,
        topics=topics,
        summary=summary,
        key_points=key_points,
        actions=actions,
        evidence=tuple(evidence),
        review_flags=tuple(review_flags),
    )


def analyze_policy_file(file_path: str | Path) -> PolicyAnalysis:
    """Parse a supported KOS file, then apply the KEMS policy profile."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(path)

    from kos.indexer.engine import get_handler

    content = get_handler(path).extract_text(path)
    import hashlib

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return analyze_policy_document(
        content,
        source_name=path.name,
        source_sha256=digest,
    )
