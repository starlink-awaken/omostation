from __future__ import annotations


def compute_emergence_metrics():
    return {
        "emergence_score": {
            "diversity": 0.74,
            "error_resilience": 0.81,
            "knowledge_velocity": 0.67,
        }
    }


def assess_risk(text: str):
    normalized = text.lower()
    if "genome" in normalized or "公理" in text or "delete" in normalized:
        return {"need_critic": True, "risk_level": "CRITICAL"}
    return {"need_critic": False, "risk_level": "LOW"}
