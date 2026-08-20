"""Thin Cockpit client for the canonical B.D.S.K. BOS persona endpoint."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from cockpit.adapters.agora import resolve_bos_uri as _resolve_bos_uri

_PERSONA_URI = "bos://persona/bdsk/evaluate"
_COMPUTE_URI = "bos://compute/aetherforge/infer"
_ROLES = ("builder", "devil", "sage", "keeper")


def _not_proven(error_code: str) -> dict[str, Any]:
    return {
        "status": "error",
        "proof_state": "not_proven",
        "verdict": "NOT_PROVEN",
        "error_code": error_code,
        "engine_source": "bos_persona_not_proven",
        "compute_uri": _COMPUTE_URI,
    }


def _persona_payload(response: Any) -> Mapping[str, Any] | None:
    current = response
    for _depth in range(4):
        if not isinstance(current, Mapping):
            return None
        if "proof_state" in current:
            return current
        nested = current.get("result")
        if nested is current:
            return None
        current = nested
    return None


def _proved_view(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    if (
        payload.get("status") != "ok"
        or payload.get("proof_state") != "proven"
        or payload.get("compute_uri") != _COMPUTE_URI
    ):
        return None
    reviews = payload.get("board_reviews")
    if not isinstance(reviews, Mapping):
        return None
    opinions: dict[str, str] = {}
    for role in _ROLES:
        review = reviews.get(role)
        if not isinstance(review, Mapping):
            return None
        opinion = review.get("opinion")
        if not isinstance(opinion, str) or not opinion:
            return None
        opinions[role] = opinion

    topic_digest = payload.get("topic_digest")
    recommendation = payload.get("recommendation")
    verdict = payload.get("verdict")
    risk_score = payload.get("risk_score")
    if not isinstance(topic_digest, str) or not topic_digest.startswith("sha256:"):
        return None
    if not isinstance(recommendation, str) or not isinstance(verdict, str):
        return None
    if isinstance(risk_score, bool) or not isinstance(risk_score, int):
        return None

    return {
        "status": "ok",
        "proof_state": "proven",
        "engine_source": "bos_persona_bdsk",
        "persona_uri": _PERSONA_URI,
        "compute_uri": _COMPUTE_URI,
        "topic_digest": topic_digest,
        "verdict": verdict,
        "risk_score": risk_score,
        "conclusion": recommendation,
        **opinions,
    }


class DynamicBDSKAdjudicator:
    """Compatibility facade that delegates all evaluation to Agora BOS."""

    @staticmethod
    def adjudicate(
        topic: str,
        *,
        context: str = "",
        mode: str = "deep",
    ) -> dict[str, Any]:
        try:
            response = asyncio.run(
                _resolve_bos_uri(
                    _PERSONA_URI,
                    topic=topic,
                    context=context,
                    mode=mode,
                )
            )
        except Exception:
            return _not_proven("persona_route_unavailable")

        payload = _persona_payload(response)
        if payload is None:
            return _not_proven("invalid_persona_response")
        if payload.get("proof_state") != "proven":
            code = payload.get("error_code")
            return _not_proven(
                code if isinstance(code, str) else "persona_evaluation_not_proven"
            )
        proved = _proved_view(payload)
        return proved if proved is not None else _not_proven("invalid_persona_response")
