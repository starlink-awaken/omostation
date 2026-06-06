"""Capability matching with scoring and ranking.

Port of agentmesh engine capability-matcher.ts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capability_discovery import (
    CapabilityDefinition,
    CapabilityMatchRequest,
    CapabilityMatchResult,
    DiscoveredCapability,
    IOSchema,
    meets_capability_level,
)


@dataclass
class MatchWeights:
    type_match: float = 0.3
    tag_match: float = 0.25
    level_match: float = 0.2
    performance_match: float = 0.15
    schema_compatibility: float = 0.1


DEFAULT_WEIGHTS = MatchWeights()

_LEVEL_ORDER = {"basic": 0, "intermediate": 1, "advanced": 2, "expert": 3}


def _check_input_compatibility(data: Any, schema: IOSchema) -> bool:
    if data is None:
        return schema.type == "null"
    mapping = {"string": str, "number": (int, float), "boolean": bool, "null": type(None)}
    if schema.type in mapping:
        return isinstance(data, mapping[schema.type])  # type: ignore[arg-type]
    if schema.type == "array":
        return isinstance(data, list)
    if schema.type == "object":
        return isinstance(data, dict) and not isinstance(data, list)
    return False


def _check_output_compatibility(actual: IOSchema | None, expected: IOSchema) -> bool:
    if actual is None:
        return True
    if actual.type != expected.type:
        return False
    if expected.enum and actual.enum:
        return any(v in actual.enum for v in expected.enum)
    return True


def _calculate_schema_compatibility(request: CapabilityMatchRequest, cap: CapabilityDefinition) -> float:
    score = 1.0
    if request.input is not None and cap.input:
        if not _check_input_compatibility(request.input, cap.input):
            score -= 0.5
    if request.output_schema is not None and cap.output:
        if not _check_output_compatibility(cap.output, request.output_schema):
            score -= 0.5
    return max(0.0, score)


class CapabilityMatcher:
    """Matches agent capabilities against task requirements with scoring."""

    def __init__(self, discovered: list[DiscoveredCapability], weights: MatchWeights | None = None) -> None:
        self._caps = discovered
        self._weights = weights or DEFAULT_WEIGHTS

    def match(self, request: CapabilityMatchRequest) -> list[CapabilityMatchResult]:
        if request.mode == "exact":
            return self._match_exact(request)
        if request.mode == "fuzzy":
            return self._match_fuzzy(request)
        return self._match_any(request)

    def _match_exact(self, request: CapabilityMatchRequest) -> list[CapabilityMatchResult]:
        results: list[CapabilityMatchResult] = []
        for dc in self._caps:
            cap = dc.capability
            if request.type is not None and cap.type.value != request.type:
                continue
            if request.min_level and not meets_capability_level(cap.level, request.min_level):
                continue
            if request.max_duration_ms is not None and cap.performance and cap.performance.avg_duration_ms is not None:
                if cap.performance.avg_duration_ms > request.max_duration_ms:
                    continue
            if request.max_tokens is not None and cap.performance and cap.performance.avg_tokens is not None:
                if cap.performance.avg_tokens > request.max_tokens:
                    continue
            if request.tags:
                cap_tags = set(cap.tags or [])
                if not all(t in cap_tags for t in request.tags):
                    continue
            if request.output_schema and not _check_output_compatibility(cap.output, request.output_schema):
                continue
            reasons = [f"Type matches: {cap.type.value}"]
            if request.min_level:
                reasons.append(f"Level {cap.level.value} meets {request.min_level.value}")
            results.append(CapabilityMatchResult(agent_name=dc.agent_name, capability=cap, score=1.0, reasons=reasons))
        return sorted(results, key=lambda r: -r.score)

    def _match_fuzzy(self, request: CapabilityMatchRequest) -> list[CapabilityMatchResult]:
        results: list[CapabilityMatchResult] = []
        for dc in self._caps:
            cap = dc.capability
            total = 0.0
            weight_sum = 0.0
            reasons: list[str] = []
            w = self._weights

            if request.type:
                weight_sum += w.type_match
                if cap.type.value == request.type:
                    total += w.type_match
                    reasons.append(f"Type matches: {cap.type.value}")

            if request.tags:
                weight_sum += w.tag_match
                cap_tags = set(cap.tags or [])
                matched = [t for t in request.tags if t in cap_tags]
                if matched:
                    ratio = len(matched) / len(request.tags)
                    total += w.tag_match * ratio
                    reasons.append(f"{len(matched)}/{len(request.tags)} tags matched")

            if request.min_level:
                weight_sum += w.level_match
                if meets_capability_level(cap.level, request.min_level):
                    diff = abs(_LEVEL_ORDER[cap.level.value] - _LEVEL_ORDER[request.min_level.value])
                    lscore = max(0.0, 1.0 - diff * 0.3)
                    total += w.level_match * lscore
                    reasons.append(f"Level {cap.level.value} meets {request.min_level.value}")

            if request.input is not None or request.output_schema is not None:
                weight_sum += w.schema_compatibility
                sc = _calculate_schema_compatibility(request, cap)
                total += w.schema_compatibility * sc

            final = total / weight_sum if weight_sum > 0 else 0.0
            if final > 0:
                results.append(CapabilityMatchResult(agent_name=dc.agent_name, capability=cap, score=final, reasons=reasons))

        return sorted(results, key=lambda r: -r.score)

    def _match_any(self, request: CapabilityMatchRequest) -> list[CapabilityMatchResult]:
        results: list[CapabilityMatchResult] = []
        for dc in self._caps:
            cap = dc.capability
            score = 0.5
            reasons: list[str] = []
            if request.type and cap.type.value == request.type:
                score += 0.2
                reasons.append(f"Preferred type: {cap.type.value}")
            if request.tags:
                cap_tags = set(cap.tags or [])
                matched = [t for t in request.tags if t in cap_tags]
                score += (len(matched) / len(request.tags)) * 0.15
                if matched:
                    reasons.append(f"Matched tags: {', '.join(matched)}")
            if request.min_level and meets_capability_level(cap.level, request.min_level):
                score += 0.1
                reasons.append(f"Exceeds level: {cap.level.value}")
            results.append(CapabilityMatchResult(agent_name=dc.agent_name, capability=cap, score=min(1.0, score), reasons=reasons))
        return sorted(results, key=lambda r: -r.score)

    def find_best_match(self, request: CapabilityMatchRequest) -> CapabilityMatchResult | None:
        results = self.match(request)
        return results[0] if results else None

    def find_top_matches(self, request: CapabilityMatchRequest, n: int) -> list[CapabilityMatchResult]:
        return self.match(request)[:n]

    def update_discovered_capabilities(self, discovered: list[DiscoveredCapability]) -> None:
        self._caps = discovered


def create_capability_matcher(discovered: list[DiscoveredCapability], weights: MatchWeights | None = None) -> CapabilityMatcher:
    return CapabilityMatcher(discovered, weights)
