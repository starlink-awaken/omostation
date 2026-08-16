"""Evidence-bound model enrichment and fixture evaluation for KEMS P3."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from .policy import PolicyAnalysis


class EnrichmentProvider(Protocol):
    def __call__(self, baseline: PolicyAnalysis) -> dict[str, Any]: ...


@dataclass(frozen=True)
class EnrichedClaim:
    text: str
    evidence_indexes: tuple[int, ...]


@dataclass(frozen=True)
class EnrichmentResult:
    schema_version: str
    summary: str
    claims: tuple[EnrichedClaim, ...]
    model_id: str
    fallback_used: bool
    review_flags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["claims"] = [asdict(claim) for claim in self.claims]
        result["review_flags"] = list(self.review_flags)
        return result


def enrich_policy(
    baseline: PolicyAnalysis,
    provider: EnrichmentProvider,
    *,
    model_id: str,
) -> EnrichmentResult:
    """Accept model prose only when every claim cites baseline evidence."""
    try:
        payload = provider(baseline)
        claims_payload = payload.get("claims", [])
        claims = tuple(
            EnrichedClaim(str(item["text"]), tuple(int(index) for index in item.get("evidence_indexes", [])))
            for item in claims_payload
        )
        invalid = [
            claim
            for claim in claims
            if not claim.evidence_indexes
            or any(index >= len(baseline.evidence) or index < 0 for index in claim.evidence_indexes)
        ]
        if invalid:
            raise ValueError("model claim is missing valid baseline evidence")
        return EnrichmentResult(
            "kems.policy-enrichment.v1", str(payload.get("summary", baseline.summary)), claims, model_id, False, ()
        )
    except (KeyError, TypeError, ValueError, IndexError):
        return EnrichmentResult(
            "kems.policy-enrichment.v1",
            baseline.summary,
            (),
            "deterministic-baseline",
            True,
            ("model_output_rejected",),
        )


@dataclass(frozen=True)
class EvaluationReport:
    schema_version: str
    checked_fields: int
    matched_fields: int
    missing_fields: tuple[str, ...]
    status: str

    @property
    def accuracy(self) -> float:
        return self.matched_fields / self.checked_fields if self.checked_fields else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "accuracy": self.accuracy, "missing_fields": list(self.missing_fields)}


def evaluate_policy_fixture(result: PolicyAnalysis, expected: dict[str, str]) -> EvaluationReport:
    """Compare a result with a human-authored fixture without claiming production accuracy."""
    actual = {
        "title": result.title,
        "document_type": result.document_type,
        "issuer": result.issuer or "",
        "document_number": result.document_number or "",
    }
    missing = tuple(field for field, value in expected.items() if actual.get(field) != value)
    checked = len(expected)
    matched = checked - len(missing)
    return EvaluationReport(
        "kems.policy-evaluation.v1", checked, matched, missing, "pass" if not missing else "needs_review"
    )
