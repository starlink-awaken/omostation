from __future__ import annotations

import re


def _normalize(operation: str) -> str:
    op = operation.strip().lower()
    op = re.sub(r"_+", "_", op)
    op = re.sub(r"\s+", " ", op)
    return op


LEVEL3_PATTERNS = [
    "write_file genome.md",
    "patch genome.md",
    "ssb delete",
    "delete cross_refs",
    "delete ecos.jsonl",
    "send_message",
    "himalaya send email",
    "xurl post tweet",
    "git push",
    "rm -rf",
    "delete from",
]
LEVEL2_PATTERNS = ["cronjob create", "cronjob update", "curl post"]
LEVEL1_PATTERNS = ["delegate_task"]
LEVEL0_PATTERNS = ["read_file", "search", "search_files", "web_search"]


def check(operation: str, auto_deny: bool = False):
    op = _normalize(operation)
    for pattern in LEVEL3_PATTERNS:
        if pattern in op:
            requires = "DENY" if auto_deny else "HUMAN_CONFIRMATION"
            return {
                "allowed": False,
                "level": 3,
                "reason": f"blocked dangerous operation: {operation}",
                "requires": requires,
            }
    for pattern in LEVEL2_PATTERNS:
        if pattern in op:
            return {"allowed": False, "level": 2, "reason": f"needs triangle check: {operation}", "requires": "TRIANGLE_CHECK"}
    for pattern in LEVEL1_PATTERNS:
        if pattern in op:
            return {"allowed": True, "level": 1, "reason": f"reversible operation: {operation}", "requires": None}
    for pattern in LEVEL0_PATTERNS:
        if pattern in op:
            return {"allowed": True, "level": 0, "reason": f"read-only operation: {operation}", "requires": None}
    return {"allowed": True, "level": 0, "reason": f"default allow: {operation}", "requires": None}
