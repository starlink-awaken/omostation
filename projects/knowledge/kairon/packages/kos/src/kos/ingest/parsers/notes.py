# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""Markdown 笔记解析器 — 将 Markdown 笔记解析为 JSON-LD 事实。"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

# ── Markdown 解析 ──


def parse_markdown(md: str) -> list[dict[str, Any]]:
    """解析 Markdown 文本，提取主题、子主题、知识点和代码片段。"""
    facts: list[dict[str, Any]] = []
    lines = md.split("\n")
    current_topic: str | None = None
    current_subtopic: str | None = None
    in_code_block = False
    code_lang = ""
    code_lines: list[str] = []

    for line in lines:
        # Code block detection
        code_match = re.match(r"^```(\w*)", line)
        if code_match:
            if in_code_block:
                # End code block
                if code_lines:
                    fact_id = str(uuid.uuid4())
                    facts.append(
                        {
                            "id": fact_id,
                            "@type": "CodeSnippet",
                            "topic": current_topic or "untitled",
                            "pred": "contains_code",
                            "content": "\n".join(code_lines),
                            "metadata": {"language": code_lang},
                        }
                    )
                    code_lines = []
                in_code_block = False
                code_lang = ""
            else:
                in_code_block = True
                code_lang = code_match.group(1) or "text"
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Topic (H1)
        topic_match = re.match(r"^#\s+(.+)$", line)
        if topic_match:
            current_topic = topic_match.group(1).strip()
            fact_id = str(uuid.uuid4())
            facts.append(
                {
                    "id": fact_id,
                    "@type": "Topic",
                    "topic": current_topic,
                    "pred": "is_topic",
                    "content": current_topic,
                }
            )
            continue

        # SubTopic (H2)
        subtopic_match = re.match(r"^##\s+(.+)$", line)
        if subtopic_match:
            current_subtopic = subtopic_match.group(1).strip()
            fact_id = str(uuid.uuid4())
            facts.append(
                {
                    "id": fact_id,
                    "@type": "SubTopic",
                    "topic": current_topic or current_subtopic,
                    "pred": "is_subtopic",
                    "content": current_subtopic,
                }
            )
            continue

        # Knowledge points (list items under a subtopic)
        kp_match = re.match(r"^-\s+(.+)$", line)
        if kp_match and current_subtopic:
            fact_id = str(uuid.uuid4())
            facts.append(
                {
                    "id": fact_id,
                    "@type": "KnowledgePoint",
                    "topic": current_topic or current_subtopic,
                    "pred": "describes",
                    "content": kp_match.group(1).strip(),
                    "metadata": {"subtopic": current_subtopic},
                }
            )

    # Handle code block at end of file
    if in_code_block and code_lines:
        fact_id = str(uuid.uuid4())
        facts.append(
            {
                "id": fact_id,
                "@type": "CodeSnippet",
                "topic": current_topic or "untitled",
                "pred": "contains_code",
                "content": "\n".join(code_lines),
                "metadata": {"language": code_lang},
            }
        )

    return facts


def parse_file(input_path: str | Path) -> list[dict[str, Any]]:
    """解析 Markdown 文件。"""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {input_path}")
    md = path.read_text(encoding="utf-8")
    return parse_markdown(md)
