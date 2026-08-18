from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class KeyResult:
    kr_id: str
    description: str
    target: float
    current: float = 0.0
    unit: str = "%"


@dataclass
class Objective:
    obj_id: str
    title: str
    key_results: list[KeyResult] = field(default_factory=list)
    owner: str = ""
    period: str = ""


class OKRFramework:
    def __init__(self) -> None:
        self._objectives: dict[str, Objective] = {}

    def create_objective(self, title: str, owner: str = "", period: str = "") -> Objective:
        oid = uuid.uuid4().hex[:12]
        obj = Objective(obj_id=oid, title=title, owner=owner, period=period)
        self._objectives[oid] = obj
        return obj

    def add_key_result(self, obj_id: str, description: str, target: float, unit: str = "%") -> KeyResult:
        obj = self._require(obj_id)
        kr_id = uuid.uuid4().hex[:8]
        kr = KeyResult(kr_id=kr_id, description=description, target=target, unit=unit)
        obj.key_results.append(kr)
        return kr

    def update_progress(self, obj_id: str, kr_id: str, value: float) -> None:
        obj = self._require(obj_id)
        for kr in obj.key_results:
            if kr.kr_id == kr_id:
                kr.current = value
                return
        raise KeyError(f"KeyResult {kr_id} not found in objective {obj_id}")

    def get_objective(self, obj_id: str) -> Objective | None:
        return self._objectives.get(obj_id)

    def get_objective_progress(self, obj_id: str) -> float:
        obj = self._require(obj_id)
        if not obj.key_results:
            return 0.0
        ratios = []
        for kr in obj.key_results:
            if kr.target == 0:
                ratios.append(1.0 if kr.current >= 0 else 0.0)
            else:
                ratios.append(min(kr.current / kr.target, 1.0))
        return sum(ratios) / len(ratios)

    def list_objectives(self, owner: str | None = None) -> list[Objective]:
        if owner is None:
            return list(self._objectives.values())
        return [o for o in self._objectives.values() if o.owner == owner]

    def get_at_risk_objectives(self, threshold: float = 0.3) -> list[Objective]:
        result: list[Objective] = []
        for obj in self._objectives.values():
            if obj.key_results and self.get_objective_progress(obj.obj_id) < threshold:
                result.append(obj)
        return result

    def get_dashboard(self) -> dict[str, object]:
        items: list[dict[str, float | str | int]] = []
        for obj in self._objectives.values():
            progress: float = self.get_objective_progress(obj.obj_id)
            items.append(
                {
                    "obj_id": obj.obj_id,
                    "title": obj.title,
                    "owner": obj.owner,
                    "period": obj.period,
                    "progress": progress,
                    "key_results_count": len(obj.key_results),
                }
            )
        total = len(items)
        avg = sum(float(v["progress"]) for v in items) / total if total else 0.0
        return {
            "total_objectives": total,
            "average_progress": avg,
            "objectives": items,
        }

    def _require(self, obj_id: str) -> Objective:
        obj = self._objectives.get(obj_id)
        if obj is None:
            raise KeyError(f"Objective {obj_id} not found")
        return obj
