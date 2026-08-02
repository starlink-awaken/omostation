"""brain_memory.py — 偏好提取 + 记忆自动更新.

从对话中自动提取用户偏好，注入后续对话 prompt。
"""

from __future__ import annotations

import re

from cockpit.brain_core import store_preference

# 偏好提取正则（中文 + 英文常见表达）
_PREF_PATTERNS = [
    r"我喜欢(.+?)(?:[。！，,]|$)",
    r"我不喜欢(.+?)(?:[。！，,]|$)",
    r"请?不要(.+?)(?:[。！，,]|$)",
    r"记住(.+?)(?:[。！，,]|$)",
    r"以后(.+?)(?:[。！，,]|$)",
    r"总是(.+?)(?:[。！，,]|$)",
    r"千万别(.+?)(?:[。！，,]|$)",
    r"I like(.+?)(?:\.|!|,|$)",
    r"I don't like(.+?)(?:\.|!|,|$)",
    r"always (.+?)(?:\.|!|,|$)",
    r"never (.+?)(?:\.|!|,|$)",
]


def extract_preferences(text: str) -> list[tuple[str, str]]:
    """从用户文本中提取偏好 (key, value) 对.

    返回的 key 归一化为小写 + 下划线，用于去重存储。
    """
    prefs = []
    seen_keys: set[str] = set()
    for pattern in _PREF_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            content = match.group(1).strip().rstrip("。！，,.")
            if len(content) < 2:
                continue
            key = _normalize_key(content)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            prefs.append((key, content))
    return prefs


def _normalize_key(content: str) -> str:
    """归一化 key: 小写 + 去标点 + 截断.

    例: "用 Markdown 写周报" → "用_markdown_写周报"
    """
    key = content[:20].strip().lower()
    key = re.sub(r"[^\w一-鿿]", "_", key)
    key = re.sub(r"_+", "_", key).strip("_")
    return key or "pref"


def store_preferences(prefs: list[tuple[str, str]], source: str = "inferred") -> int:
    """批量存储偏好，返回实际写入数量."""
    count = 0
    for key, value in prefs:
        if key and value:
            store_preference(key, value, source=source)
            count += 1
    return count


def auto_extract_and_store(text: str, source: str = "inferred") -> list[tuple[str, str]]:
    """从文本提取偏好并自动存储. 返回提取到的偏好列表."""
    prefs = extract_preferences(text)
    store_preferences(prefs, source=source)
    return prefs
