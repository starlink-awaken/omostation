"""健康档案 IO（JSON 持久化，FamilyShared iCloud 同步友好）。"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from typing import Any

from .models import HealthCheckRecord, HealthProfile, VaccinationRecord


def _date_to_iso(d: date) -> str:
    return d.isoformat()


def _datetime_to_iso(dt: datetime) -> str:
    return dt.isoformat()


def profile_to_dict(profile: HealthProfile) -> dict[str, Any]:
    """序列化为 dict（所有日期转 ISO 字符串）。"""
    data = asdict(profile)
    data["birth_date"] = _date_to_iso(data["birth_date"])
    data["created_at"] = _datetime_to_iso(data["created_at"])
    data["updated_at"] = _datetime_to_iso(data["updated_at"])
    for check in data["checks"]:
        check["check_date"] = _date_to_iso(check["check_date"])
    for vacc in data["vaccinations"]:
        vacc["administered_at"] = _date_to_iso(vacc["administered_at"])
        if vacc["next_due"] is not None:
            vacc["next_due"] = _date_to_iso(vacc["next_due"])
    return data


def profile_from_dict(data: dict[str, Any]) -> HealthProfile:
    """从 dict 反序列化为 HealthProfile。"""
    checks_raw = data.get("checks", []) or []
    vaccs_raw = data.get("vaccinations", []) or []
    checks = [
        HealthCheckRecord(
            check_date=date.fromisoformat(c["check_date"]),
            height_cm=float(c["height_cm"]),
            weight_kg=float(c["weight_kg"]),
            vision_left=float(c["vision_left"]),
            vision_right=float(c["vision_right"]),
            notes=c.get("notes", "") or "",
        )
        for c in checks_raw
    ]
    vaccinations = [
        VaccinationRecord(
            vaccine=v["vaccine"],
            dose=int(v["dose"]),
            administered_at=date.fromisoformat(v["administered_at"]),
            next_due=date.fromisoformat(v["next_due"]) if v.get("next_due") else None,
        )
        for v in vaccs_raw
    ]
    return HealthProfile(
        member_id=data["member_id"],
        name=data["name"],
        birth_date=date.fromisoformat(data["birth_date"]),
        blood_type=data.get("blood_type", "未知"),
        allergies=list(data.get("allergies", []) or []),
        checks=checks,
        vaccinations=vaccinations,
        created_at=datetime.fromisoformat(data["created_at"]),
        updated_at=datetime.fromisoformat(data["updated_at"]),
    )


def to_json(profile: HealthProfile) -> str:
    """序列化为 JSON 字符串（ensure_ascii=False，保留中文）。"""
    return json.dumps(profile_to_dict(profile), ensure_ascii=False, indent=2)


def from_json(s: str) -> HealthProfile:
    """从 JSON 字符串反序列化为 HealthProfile。"""
    return profile_from_dict(json.loads(s))


def write_json(profile: HealthProfile, path: str | bytes) -> None:
    """便捷：直接写入文件。"""
    from pathlib import Path

    Path(path).write_text(to_json(profile), encoding="utf-8")  # type: ignore[arg-type]


def read_json(path: str | bytes) -> HealthProfile:
    """便捷：直接从文件读。"""
    from pathlib import Path

    return from_json(Path(path).read_text(encoding="utf-8"))  # type: ignore[arg-type]
