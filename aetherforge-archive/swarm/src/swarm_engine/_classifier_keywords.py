"""Keyword sets for IntentClassifier heuristic rules (ARCH-003 SRP refactor).

Extracted from intent_classifier.py to reduce file size.
"""

from __future__ import annotations

from ._classifier_types import ComplexityLevel

# Keywords that strongly indicate COMPLEX work
COMPLEX_KEYWORDS: frozenset[str] = frozenset(
    {
        "analyze",
        "analyse",
        "research",
        "comprehensive",
        "all",
        "entire",
        "multiple",
        "parallel",
        "coordinate",
        "across",
        "compare",
        "investigate",
        "evaluate",
        "audit",
        "refactor",
        "redesign",
        "architect",
        "plan",
        "strategy",
        "deploy",
        "migrate",
        "integrate",
        "orchestrate",
        "benchmark",
        "review all",
        "full",
        "complete",
        "end-to-end",
        "end to end",
        "thorough",
        "systematic",
        "cross-functional",
        "multi-stage",
        "production",
        "scalable",
        "enterprise",
        "microservice",
        "distributed",
        "concurrent",
        "optimization",
        "performance",
        "security",
        "vulnerability",
        "threat",
        "authentication",
        "authorization",
        "encryption",
        "CI/CD",
        "pipeline",
        "automation",
    }
)

# Keywords that push toward MODERATE (step-sequencing language)
STEP_KEYWORDS: frozenset[str] = frozenset(
    {
        "then",
        "after",
        "and then",
        "followed by",
        "step",
        "next",
        "first",
        "second",
        "third",
        "finally",
        "lastly",
        "subsequently",
        "once",
        "before",
        "when done",
        "sequence",
        "consequently",
        "afterwards",
        "prior to",
        "subsequent",
        "step by step",
        "in order",
        "gradually",
        "proceed",
        "continue",
    }
)

# Keywords that pull toward SIMPLE (single-action verbs)
SIMPLE_KEYWORDS: frozenset[str] = frozenset(
    {
        "list",
        "show",
        "check",
        "get",
        "find",
        "print",
        "display",
        "read",
        "cat",
        "view",
        "ping",
        "status",
        "version",
        "help",
        "count",
        "echo",
        "whoami",
        "pwd",
        "ls",
        "ps",
        "inspect",
        "query",
        "fetch",
        "retrieve",
        "lookup",
        "search",
        "validate",
        "verify",
        "test",
        "run",
        "execute",
        "start",
        "stop",
        "restart",
        "reload",
        "refresh",
        "update",
    }
)

# Conjunctions that break the "single-step" assumption
CONJUNCTIONS: frozenset[str] = frozenset({"and", "or", "then", "while", "but", "also"})

# Role suggestions keyed by complexity tier
DEFAULT_ROLES: dict[ComplexityLevel, list[str]] = {
    ComplexityLevel.SIMPLE: ["executor"],
    ComplexityLevel.MODERATE: ["planner", "executor"],
    ComplexityLevel.COMPLEX: ["coordinator", "researcher", "analyst", "executor", "reviewer"],
}
