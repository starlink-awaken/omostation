"""ToneAdapter — Spine-side consumer of the four-domain LoRA matrix (BET-Y2Q2-T3-02).

Maps a draft task to matrix routing directives (domain / expected adapter /
persona tone) and applies the ROUGE-L tone gate: severe distortion falls back
to the neutral template. Fully self-contained (no omlxc import — the matrix
lives in another repo); the keyword table mirrors
``omlxc.dataplane.lora.matrix`` routing. Never raises: any internal error
degrades to neutral directives with the circuit-breaker flag set.
"""

from __future__ import annotations

import re
from typing import Any

try:
    from spine.cognitive.router import MindModelRouter
except Exception:  # pragma: no cover - import-time hardening
    MindModelRouter = None  # type: ignore[assignment]

DOMAINS = ("gov", "tech", "collab", "essay")
ADAPTER_NAMES = {
    "gov": "lora-gov-v2",
    "tech": "lora-tech-v2",
    "collab": "lora-collab-v1",
    "essay": "lora-essay-v1",
}
TONE_GATE = 0.75
NEUTRAL_TONE = "neutral"

_DOMAIN_KEYWORDS: dict[str, re.Pattern[str]] = {
    "collab": re.compile(r"对外协作|合作方|伙伴|联名|洽谈|签约|备忘录|合作协议|协同"),
    "essay": re.compile(r"随笔|随想|手记|感悟|杂感|札记|心境|漫谈"),
    "tech": re.compile(r"架构|ADR|技术方案|评审|接口|微服务|部署|代码|系统设计|数据模型"),
    "gov": re.compile(r"公文|政务|批复|请示|公函|函件|通知|政策|卫生(?:健康)?局|督办|审批"),
}
_DOMAIN_ORDER = ("collab", "essay", "tech", "gov")


def _lcs_len(a: list[str], b: list[str]) -> int:
    if not a or not b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            cur[j] = prev[j - 1] + 1 if x == y else (prev[j] if prev[j] >= cur[j - 1] else cur[j - 1])
        prev = cur
    return prev[len(b)]


def rouge_l(candidate: str, reference: str) -> float:
    """Character-granularity ROUGE-L F-measure in [0, 1]."""
    if not candidate.strip() and not reference.strip():
        return 1.0
    c = [ch for ch in candidate.strip() if not ch.isspace()]
    r = [ch for ch in reference.strip() if not ch.isspace()]
    if not c or not r:
        return 0.0
    lcs = _lcs_len(c, r)
    prec, rec = lcs / len(c), lcs / len(r)
    return 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)


def route_domain(task_text: str) -> str:
    text = task_text or ""
    for domain in _DOMAIN_ORDER:
        if _DOMAIN_KEYWORDS[domain].search(text):
            return domain
    return "gov"


class ToneAdapter:
    """Draft tone directives bound to the LoRA matrix domains."""

    def __init__(self, router: Any | None = None) -> None:
        try:
            self.router = router or (MindModelRouter() if MindModelRouter else None)
        except Exception:
            self.router = None

    def directives_for(
        self,
        task_text: str,
        candidate: str | None = None,
        reference: str | None = None,
    ) -> dict[str, Any]:
        """Return tone directives; never raises (circuit breaker inside)."""
        try:
            return self._directives(task_text, candidate, reference)
        except Exception as exc:
            return {
                "domain": "gov",
                "adapter": None,
                "tone": NEUTRAL_TONE,
                "fallback_neutral": True,
                "circuit_breaker_ok": False,
                "error": str(exc)[:200],
            }

    def _directives(self, task_text: str, candidate: str | None, reference: str | None) -> dict[str, Any]:
        domain = route_domain(task_text)
        tone = NEUTRAL_TONE
        if self.router is not None:
            try:
                tone = self.router.route().get("tone", NEUTRAL_TONE)
            except Exception:
                tone = NEUTRAL_TONE
        out: dict[str, Any] = {
            "domain": domain,
            "adapter": ADAPTER_NAMES[domain],
            "tone": tone,
            "fallback_neutral": False,
            "circuit_breaker_ok": True,
        }
        if candidate is not None and reference is not None:
            score = rouge_l(candidate, reference)
            out["rouge_l"] = round(score, 4)
            if score < TONE_GATE:
                out["tone"] = NEUTRAL_TONE
                out["fallback_neutral"] = True
        return out
