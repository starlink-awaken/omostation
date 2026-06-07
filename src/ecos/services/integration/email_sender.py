from __future__ import annotations


def classify_risk(to: str, subject: str, body: str) -> str:
    text = f"{to}\n{subject}\n{body}".lower()
    if any(keyword in text for keyword in ("密码", "confidential", "token")):
        return "P0"
    return "P1"
