# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""微信聊天导出解析器 — 将微信导出txt解析为JSON-LD格式。"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

TECH_KEYWORDS = [
    "Rust",
    "Go",
    "Python",
    "TypeScript",
    "JavaScript",
    "Tokio",
    "async",
    "pandas",
    "numpy",
    "PyTorch",
    "分布式",
    "Raft",
    "Paxos",
    "WebAssembly",
]

URL_PATTERN = re.compile(r"https?://[^\s]+")


def parse_line(line: str) -> dict[str, Any] | None:
    """解析单行微信消息。

    格式: YYYY-MM-DD HH:MM:SS 发送者: 内容
    返回结构化字典或 None（如果行格式不匹配）。
    """
    pattern = re.compile(r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+([^:]+?):\s*(.+)$")
    match = pattern.match(line.strip())
    if not match:
        return None

    timestamp_str = match.group(1).strip()
    sender = match.group(2).strip()
    content = match.group(3).strip()

    try:
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S").isoformat()
    except ValueError:
        return None

    urls = URL_PATTERN.findall(content)
    topics = [kw for kw in TECH_KEYWORDS if kw.lower() in content.lower()]

    return {
        "timestamp": timestamp,
        "sender": sender,
        "content": content,
        "urls": urls,
        "topics": topics,
    }


def parse_file(input_path: str | Path) -> list[dict[str, Any]]:
    """解析整个微信导出文件。"""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {input_path}")

    messages: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            msg = parse_line(line)
            if msg:
                messages.append(msg)
    return messages


def to_jsonld(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """将解析结果转换为JSON-LD格式。"""
    facts: list[dict[str, Any]] = []
    for msg in messages:
        fact_id = str(uuid.uuid4())
        facts.append(
            {
                "id": fact_id,
                "@type": "ChatMessage",
                "topic": msg.get("sender", "unknown"),
                "pred": "said_about",
                "content": msg["content"],
                "metadata": {
                    "source": "wechat",
                    "timestamp": msg["timestamp"],
                    "sender": msg["sender"],
                    "urls": msg["urls"],
                    "topics": msg["topics"],
                },
            }
        )

    return {
        "@context": "https://sharedbrain.local/kg/personal/v1",
        "source": "wechat_export",
        "facts": facts,
    }
