"""HealthProfile demo —— Phase 28 W1 底座验收。

执行：
    cd projects/kairon
    uv run python scripts/health_profile_demo.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

# 让 kairon workspace 包可被 import（uv run 已把 src 挂上去，但保险起见显式加 path）
_KAIRON_PKGS = Path(__file__).resolve().parent.parent / "packages"
for _pkg in ("health-profile/src",):
    p = _KAIRON_PKGS / _pkg
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from health_profile import HealthCheckRecord, HealthProfile, VaccinationRecord
from health_profile.io import from_json, to_json

TODAY = date(2026, 6, 5)


def build_xia() -> HealthProfile:
    """构造夏维桢的健康档案（出生 2021-09-01，3 次体检 + 2 个疫苗）。"""
    xia = HealthProfile(
        member_id="xia-2021",
        name="夏维桢",
        birth_date=date(2021, 9, 1),
        blood_type="A",
        allergies=["尘螨"],
    )

    # 3 次体检（半年一次）
    xia.add_check(
        HealthCheckRecord(
            check_date=date(2023, 9, 1),
            height_cm=92.0,
            weight_kg=13.0,
            vision_left=0.7,
            vision_right=0.7,
            notes="2 岁体检",
        )
    )
    xia.add_check(
        HealthCheckRecord(
            check_date=date(2024, 3, 1),
            height_cm=95.0,
            weight_kg=14.5,
            vision_left=0.8,
            vision_right=0.8,
            notes="半年度体检",
        )
    )
    xia.add_check(
        HealthCheckRecord(
            check_date=date(2024, 9, 1),
            height_cm=98.0,
            weight_kg=15.2,
            vision_left=0.85,
            vision_right=0.85,
            notes="3 岁体检",
        )
    )

    # 2 个疫苗（其中一个 next_due 在 30 天内）
    xia.add_vaccination(
        VaccinationRecord(
            vaccine="DTaP",
            dose=4,
            administered_at=date(2024, 2, 15),
            next_due=TODAY + timedelta(days=20),  # 25 天后到期
        )
    )
    xia.add_vaccination(
        VaccinationRecord(
            vaccine="MMR",
            dose=1,
            administered_at=date(2024, 8, 20),
            next_due=TODAY + timedelta(days=180),  # 半年后到期
        )
    )

    return xia


def main() -> None:
    print("=" * 60)
    print("Phase 28 W1 — HealthProfile Demo (夏维桢)")
    print("=" * 60)

    xia = build_xia()

    print(f"\n[档案] member_id={xia.member_id}  name={xia.name}")
    print(f"[档案] birth_date={xia.birth_date}  blood_type={xia.blood_type}")
    print(f"[档案] allergies={xia.allergies}")
    print(f"[年龄] 当前 ({TODAY}) 年龄 = {xia.age_years(TODAY)} 岁")

    last = xia.last_check()
    print(f"\n[最近体检] {last.check_date}  身高 {last.height_cm}cm  体重 {last.weight_kg}kg")  # type: ignore[reportOptionalMemberAccess]
    print(f"[最近体检] 视力 L={last.vision_left} R={last.vision_right}  notes={last.notes!r}")  # type: ignore[reportOptionalMemberAccess]

    upcoming = xia.upcoming_vaccinations(on=TODAY, window_days=60)
    print(f"\n[未来 60 天疫苗] 共 {len(upcoming)} 条")
    for v in upcoming:
        days_left = (v.next_due - TODAY).days if v.next_due else None
        print(f"  - {v.vaccine} 第 {v.dose} 剂  next_due={v.next_due}  距今 {days_left} 天")

    # JSON 持久化 + roundtrip 验证
    out = Path("/tmp/health_profile_xia.json")
    payload = to_json(xia)
    out.write_text(payload, encoding="utf-8")
    print(f"\n[JSON] 写入 {out}  ({len(payload)} chars)")

    # roundtrip
    xia2 = from_json(payload)
    assert xia2.member_id == xia.member_id
    assert len(xia2.checks) == len(xia.checks)
    assert len(xia2.vaccinations) == len(xia.vaccinations)
    assert xia2.last_check().check_date == xia.last_check().check_date  # type: ignore[reportOptionalMemberAccess]
    print("[JSON] roundtrip OK  (字段一致)")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
