"""Trust Layer — entity confidence scoring for KOS."""

import logging

_log = logging.getLogger(__name__)

SOURCE_AUTHORITY = {
    "official_docs": 1.0,
    "peer_reviewed": 0.9,
    "established_media": 0.7,
    "blog": 0.5,
    "social_media": 0.3,
    "unknown": 0.2,
}


class TrustLayer:
    def __init__(self) -> None:
        self.scores: dict[str, float] = {}

    def score_entity(self, entity_id: str, source_type: str, cross_validated: bool = False, age_days: int = 0) -> dict:
        base = SOURCE_AUTHORITY.get(source_type, 0.2)
        if cross_validated:
            base = min(1.0, base + 0.1)
        if age_days > 730:
            base *= 0.8  # -20% for >2 years
        elif age_days > 365:
            base *= 0.9  # -10% for >1 year
        self.scores[entity_id] = round(base, 2)
        return {"entity_id": entity_id, "trust": base, "source": source_type, "cross_validated": cross_validated}

    def get_score(self, entity_id: str) -> float:
        return self.scores.get(entity_id, 0.2)

    def propagate(self, graph: dict[str, list[str]], steps: int = 2) -> dict[str, float]:
        for _ in range(steps):
            new = dict(self.scores)
            for node, neighbors in graph.items():
                if neighbors:
                    avg = sum(self.scores.get(n, 0.2) for n in neighbors) / len(neighbors)
                    new[node] = round(self.scores.get(node, 0.2) * 0.8 + avg * 0.2, 2)
            self.scores = new
        return dict(self.scores)

    def filter(self, min_score: float = 0.3) -> dict[str, float]:
        return {k: v for k, v in self.scores.items() if v >= min_score}

    def stats(self) -> dict:
        if not self.scores:
            return {"total": 0}
        return {
            "total": len(self.scores),
            "avg_trust": round(sum(self.scores.values()) / len(self.scores), 2),
            "high_trust": sum(1 for v in self.scores.values() if v >= 0.7),
        }
