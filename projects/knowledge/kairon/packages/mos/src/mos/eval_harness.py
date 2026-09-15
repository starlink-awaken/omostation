"""Small Memory OS eval harness (Phase 2 v0).

Scores intent routing + write/recall preference path. Not a production accuracy claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mos.routing import classify_intent
from mos.service import MemoryOS

# 15 fixture cases (v0) — expand later toward 50+
EVAL_CASES: list[dict[str, Any]] = [
    {"id": "i1", "kind": "intent", "query": "who calls function foo", "expect_intent": "code_structure"},
    {"id": "i2", "kind": "intent", "query": "open tasks and debt list", "expect_intent": "task_debt"},
    {"id": "i3", "kind": "intent", "query": "my preference is vegetarian", "expect_intent": "preference_self"},
    {"id": "i4", "kind": "intent", "query": "which ADR documents Memory OS", "expect_intent": "file_note"},
    {"id": "i5", "kind": "intent", "query": "hello world general", "expect_intent": "general"},
    {"id": "i6", "kind": "intent", "query": "knowledge card slug", "expect_intent": "card_ops"},
    {"id": "i7", "kind": "intent", "query": "who invested in Acme", "expect_intent": "entity_relation"},
    {
        "id": "p1",
        "kind": "preference_roundtrip",
        "write": "user prefers dark mode UI and large fonts",
        "query": "dark mode fonts preference",
        "expect_substring": "dark",
    },
    {
        "id": "p2",
        "kind": "preference_roundtrip",
        "write": "allergic to peanuts and shellfish",
        "query": "food allergy peanuts",
        "expect_substring": "peanut",
    },
    {
        "id": "p3",
        "kind": "preference_roundtrip",
        "write": "timezone is Asia/Shanghai",
        "query": "what timezone",
        "expect_substring": "shanghai",
    },
    {
        "id": "f1",
        "kind": "forget",
        "write": "temporary secret code red-alpha",
        "query": "red-alpha",
        "expect_after_forget_empty": True,
    },
    {
        "id": "f2",
        "kind": "forget",
        "write": "ephemeral token zebra-99",
        "query": "zebra-99",
        "expect_after_forget_empty": True,
    },
    {
        "id": "r1",
        "kind": "intent",
        "query": "caller of bar method",
        "expect_intent": "code_structure",
    },
    {
        "id": "r2",
        "kind": "preference_roundtrip",
        "write": "meeting language must be Chinese",
        "query": "meeting language Chinese",
        "expect_substring": "chinese",
    },
    {
        "id": "r3",
        "kind": "intent",
        "query": "find vault notes about governance",
        "expect_intent": "file_note",
    },
]


@dataclass
class EvalReport:
    total: int
    passed: int
    failed: list[dict[str, Any]]

    @property
    def score(self) -> float:
        return (self.passed / self.total) if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "score": round(self.score, 4),
            "failed": self.failed,
        }


def run_eval(mos: MemoryOS | None = None) -> EvalReport:
    engine = mos or MemoryOS()
    failed: list[dict[str, Any]] = []
    passed = 0
    for case in EVAL_CASES:
        kind = case["kind"]
        ok = False
        detail: dict[str, Any] = {"id": case["id"], "kind": kind}
        if kind == "intent":
            got = classify_intent(case["query"])
            ok = got == case["expect_intent"]
            detail.update({"query": case["query"], "got": got, "expect": case["expect_intent"]})
        elif kind == "preference_roundtrip":
            w = engine.write({"type": "semantic", "content": case["write"], "confidence": 0.95})
            r = engine.recall(case["query"], intent="preference_self")
            blob = " ".join(str(h.get("snippet") or "") for h in r.hits).lower()
            ok = w.ok and case["expect_substring"].lower() in blob
            detail.update({"query": case["query"], "hits": r.count, "blob": blob[:120]})
        elif kind == "forget":
            w = engine.write({"type": "episodic", "content": case["write"], "confidence": 0.9})
            mid = w.envelope_id
            r1 = engine.recall(case["query"], intent="general")
            engine.forget(mid)
            r2 = engine.recall(case["query"], intent="general")
            still = any(str(h.get("id")) == mid for h in r2.hits)
            ok = w.ok and r1.count >= 1 and (not still) and (r2.empty or not still)
            detail.update({"memory_id": mid, "before": r1.count, "after": r2.count, "still": still})
        if ok:
            passed += 1
        else:
            failed.append(detail)
    return EvalReport(total=len(EVAL_CASES), passed=passed, failed=failed)
