"""Pure deterministic placement filtering and scoring."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from omlxc.domain import RouteDecision, RouteProfile, RouteRequest

from .models import (
    PlacementSnapshot,
    RejectionCode,
    RouteFailure,
    RouteFailureCode,
    RoutePolicy,
    is_static_eligible,
)


class RoutePlanner:
    def __init__(self, policies: Mapping[RouteProfile, RoutePolicy]) -> None:
        if set(policies) != set(RouteProfile):
            raise ValueError("all route profiles require a policy")
        self._policies = dict(policies)

    def plan(
        self, request: RouteRequest, placements: Sequence[PlacementSnapshot]
    ) -> RouteDecision | RouteFailure:
        policy = self._policies[request.profile]
        placement_ids = tuple(placement.placement_id for placement in placements)
        if len(set(placement_ids)) != len(placement_ids):
            return RouteFailure(
                request.request_id,
                RouteFailureCode.INVALID_SNAPSHOT,
                {},
                "route_failed=invalid_snapshot; duplicate_placement_id=true",
                policy.config_version,
            )
        accepted: list[PlacementSnapshot] = []
        rejected: dict[str, str] = {}
        for placement in sorted(placements, key=lambda item: item.placement_id):
            rejection = self.evaluate(request, placement)
            if rejection is None:
                accepted.append(placement)
            else:
                rejected[placement.placement_id] = rejection.value

        if not accepted:
            code = (
                RouteFailureCode.NO_CAPACITY
                if rejected
                and all(value == RejectionCode.NO_CAPACITY.value for value in rejected.values())
                else RouteFailureCode.NO_CANDIDATE
            )
            return RouteFailure(
                request.request_id,
                code,
                rejected,
                f"route_failed={code.value}; rejected={len(rejected)}",
                policy.config_version,
            )

        defaults_used: set[str] = set()
        scored = [
            (placement, self._score(placement, policy, defaults_used)) for placement in accepted
        ]
        scored.sort(key=lambda item: (-item[1], item[0].placement_id))
        candidate_ids = tuple(item[0].placement_id for item in scored)
        scores = {item.placement_id: round(score, 12) for item, score in scored}
        selected = candidate_ids[0]
        explanation = (
            f"profile={request.profile.value}; selected={selected}; "
            f"fallbacks={len(candidate_ids) - 1}; "
            f"defaults={','.join(sorted(defaults_used)) or 'none'}"
        )
        return RouteDecision(
            request_id=request.request_id,
            selected_placement_id=selected,
            candidates=candidate_ids,
            candidate_scores=scores,
            rejected=rejected,
            fallback_chain=candidate_ids,
            config_version=policy.config_version,
            explanation=explanation,
            thinking_authorized=request.profile is RouteProfile.QUALITY
            and request.thinking_requested,
        )

    @staticmethod
    def evaluate(request: RouteRequest, placement: PlacementSnapshot) -> RejectionCode | None:
        if placement.model_id != request.model_id:
            return RejectionCode.MODEL
        if not placement.authorized:
            return RejectionCode.AUTHORIZATION
        if not placement.fresh:
            return RejectionCode.STALE
        if not placement.available:
            return RejectionCode.UNAVAILABLE
        if not request.required_capabilities.issubset(placement.capabilities):
            return RejectionCode.CAPABILITY
        if placement.context_limit is None or placement.context_limit < request.context_tokens:
            return RejectionCode.CONTEXT
        if placement.memory_admitted is not True:
            return RejectionCode.MEMORY
        if placement.available_concurrency is None or placement.available_concurrency <= 0:
            return RejectionCode.NO_CAPACITY
        if not placement.local or not placement.security_allowed:
            return RejectionCode.LOCAL_SECURITY
        assert is_static_eligible(placement)
        return None

    @staticmethod
    def _score(placement: PlacementSnapshot, policy: RoutePolicy, defaults_used: set[str]) -> float:
        defaults = policy.defaults
        bounds = policy.bounds

        def value(name: str, actual: float | int | None, default: float | int) -> float:
            if actual is None:
                defaults_used.add(name)
                return float(default)
            return float(actual)

        ttft = value("ttft", placement.ttft_ms, defaults.ttft_ms)
        throughput = value("throughput", placement.throughput_tps, defaults.throughput_tps)
        queue = value("queue", placement.queue_depth, defaults.queue_depth)
        error = value("error_rate", placement.error_rate, defaults.error_rate)
        network = value("network", placement.network_cost_ms, defaults.network_cost_ms)
        affinity = value("affinity", placement.affinity, defaults.affinity)
        desirability = {
            "loaded": 1.0 if placement.loaded else 0.0,
            "ttft": 1.0 - min(ttft / bounds.ttft_ms, 1.0),
            "throughput": min(throughput / bounds.throughput_tps, 1.0),
            "queue": 1.0 - min(queue / bounds.queue_depth, 1.0),
            "error_rate": 1.0 - error,
            "network": 1.0 - min(network / bounds.network_cost_ms, 1.0),
            "affinity": affinity,
        }
        weights = policy.weights
        return sum(
            (
                weights.loaded * desirability["loaded"],
                weights.ttft * desirability["ttft"],
                weights.throughput * desirability["throughput"],
                weights.queue * desirability["queue"],
                weights.error_rate * desirability["error_rate"],
                weights.network * desirability["network"],
                weights.affinity * desirability["affinity"],
            )
        )
