"""GaC severity 共享推导 (ADR-0171 Wave 1/2).

executor ∈ {hook_pre_edit, ci_gate} → red (阻塞 merge); 否则 → gray (warn).
共享给 gac-drift.py + gen-agent-redlines.py, 防 DRY 漂移 (code-review #1).
"""
RED_EXECUTORS = {"hook_pre_edit", "ci_gate"}


def derive_severity(rule: dict) -> str:
    """推导 rule severity: red (阻塞 merge) / gray (warn/审计)."""
    execs = set(rule.get("executor") or [])
    return "red" if (execs & RED_EXECUTORS) else "gray"
