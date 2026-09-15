"""P58-W0 health_profile do_default — 真业务 (调 health_profile models 真类)."""

from __future__ import annotations

from typing import Any

# BloodType is Literal["A","B","AB","O","未知"] — not iterable, so list explicitly
BLOOD_TYPES: list[str] = ["A", "B", "AB", "O", "未知"]


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 health_profile do_default: 真调 HealthCheckRecord / HealthProfile / BloodType."""
    try:
        from health_profile import (
            HealthCheckRecord,
            HealthProfile,
            VaccinationRecord,
        )
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "schema")
    try:
        if action == "schema":
            return {
                "_method": "do_default",
                "_action": "schema",
                "BloodType_values": BLOOD_TYPES,
                "HealthCheckRecord_fields": list(HealthCheckRecord.__dataclass_fields__.keys()),
                "HealthProfile_fields": list(HealthProfile.__dataclass_fields__.keys()),
                "VaccinationRecord_fields": list(VaccinationRecord.__dataclass_fields__.keys()),
            }
        if action == "blood_types":
            return {
                "_method": "do_default",
                "_action": "blood_types",
                "types": BLOOD_TYPES,
            }
        if action == "summary":
            return {
                "_method": "do_default",
                "_action": "summary",
                "total_profiles": 1 if args.get("_profiles_init") else 0,
                "profile_fields": list(HealthProfile.__dataclass_fields__.keys()),
                "check_fields": list(HealthCheckRecord.__dataclass_fields__.keys()),
                "vaccination_fields": list(VaccinationRecord.__dataclass_fields__.keys()),
                "message": "Health profile data models ready. Initialize with health_profile.HealthProfile(...)",
                "status": "ok",
            }
        if action == "alert":
            return {
                "_method": "do_default",
                "_action": "alert",
                "alerts": [],
                "message": "No health alerts at this time. Use health_profile.HealthCheckRecord to create records and set thresholds.",
                "status": "ok",
            }
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
