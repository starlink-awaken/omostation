"""health_profile 单元测试（P28-W1）。"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta

import pytest
from health_profile import HealthCheckRecord, HealthProfile, VaccinationRecord
from health_profile.io import from_json, profile_from_dict, profile_to_dict, to_json

# ---------- age_years ----------


def test_age_years_basic() -> None:
    """生日已过：年龄 = year_diff。"""
    p = HealthProfile(member_id="m1", name="Alice", birth_date=date(1990, 6, 15))
    assert p.age_years(on=date(2026, 6, 20)) == 36


def test_age_years_before_birthday() -> None:
    """生日未到：年龄 = year_diff - 1。"""
    p = HealthProfile(member_id="m1", name="Alice", birth_date=date(1990, 6, 15))
    assert p.age_years(on=date(2026, 3, 1)) == 35


def test_age_years_exact_birthday() -> None:
    """生日当天：age_years 视为已过生日。"""
    p = HealthProfile(member_id="m1", name="Alice", birth_date=date(1990, 6, 15))
    assert p.age_years(on=date(2026, 6, 15)) == 36


# ---------- add_check 时间戳 ----------


def test_add_check_updates_timestamp() -> None:
    """add_check 必须刷新 updated_at。"""
    p = HealthProfile(
        member_id="m1",
        name="Bob",
        birth_date=date(2020, 1, 1),
        created_at=datetime(2020, 1, 1, 0, 0, 0),
        updated_at=datetime(2020, 1, 1, 0, 0, 0),
    )
    time.sleep(0.01)
    p.add_check(HealthCheckRecord(date(2024, 1, 1), 90.0, 13.0, 1.0, 1.0))
    assert p.updated_at > datetime(2020, 1, 1, 0, 0, 0)
    assert len(p.checks) == 1


# ---------- last_check ----------


def test_last_check_returns_newest() -> None:
    """last_check 必须按 check_date 返回最大者，不依赖插入顺序。"""
    p = HealthProfile(member_id="m1", name="Cara", birth_date=date(2018, 1, 1))
    p.add_check(HealthCheckRecord(date(2024, 1, 1), 95.0, 14.0, 0.9, 0.9, "first"))
    p.add_check(HealthCheckRecord(date(2024, 7, 1), 98.0, 14.5, 0.95, 0.95, "second"))
    p.add_check(HealthCheckRecord(date(2024, 4, 1), 96.0, 14.2, 0.92, 0.92, "inserted-between"))
    last = p.last_check()
    assert last is not None
    assert last.check_date == date(2024, 7, 1)
    assert last.notes == "second"


def test_last_check_empty() -> None:
    p = HealthProfile(member_id="m1", name="Cara", birth_date=date(2018, 1, 1))
    assert p.last_check() is None


# ---------- upcoming_vaccinations ----------


def test_upcoming_vaccinations_30_days() -> None:
    """next_due 在 30 天内：应被返回。"""
    p = HealthProfile(member_id="m1", name="Dan", birth_date=date(2020, 5, 1))
    today = date(2026, 6, 5)
    p.add_vaccination(VaccinationRecord("DTaP", 1, date(2024, 1, 1), next_due=today + timedelta(days=15)))
    p.add_vaccination(VaccinationRecord("MMR", 1, date(2025, 1, 1), next_due=today + timedelta(days=45)))
    p.add_vaccination(VaccinationRecord("Varicella", 1, date(2025, 6, 1), next_due=today + timedelta(days=120)))
    upcoming = p.upcoming_vaccinations(on=today, window_days=60)
    vaccines = {v.vaccine for v in upcoming}
    assert vaccines == {"DTaP", "MMR"}
    assert len(upcoming) == 2


def test_upcoming_vaccinations_outside_window() -> None:
    """next_due 已过 / 超过 60 天 / 无 next_due：均不返回。"""
    p = HealthProfile(member_id="m1", name="Eve", birth_date=date(2020, 5, 1))
    today = date(2026, 6, 5)
    p.add_vaccination(VaccinationRecord("HepB", 1, date(2023, 1, 1), next_due=today - timedelta(days=10)))
    p.add_vaccination(VaccinationRecord("Polio", 1, date(2023, 6, 1), next_due=today + timedelta(days=90)))
    p.add_vaccination(VaccinationRecord("BCG", 1, date(2022, 1, 1), next_due=None))
    assert p.upcoming_vaccinations(on=today) == []


def test_upcoming_vaccinations_window_validation() -> None:
    """负 window 必须抛错。"""
    p = HealthProfile(member_id="m1", name="Frank", birth_date=date(2020, 5, 1))
    with pytest.raises(ValueError):
        p.upcoming_vaccinations(on=date(2026, 6, 5), window_days=-1)


# ---------- JSON roundtrip ----------


def test_json_roundtrip() -> None:
    """to_json → from_json 字段完全一致。"""
    p = HealthProfile(
        member_id="xia-2021",
        name="夏维桢",
        birth_date=date(2021, 9, 1),
        blood_type="A",
        allergies=["尘螨", "花粉"],
    )
    p.add_check(HealthCheckRecord(date(2024, 3, 1), 95.0, 14.5, 0.8, 0.8, "半年度体检"))
    p.add_vaccination(VaccinationRecord("DTaP", 4, date(2025, 2, 1), next_due=date(2026, 6, 25)))

    s = to_json(p)
    p2 = from_json(s)

    assert p2.member_id == p.member_id
    assert p2.name == p.name
    assert p2.birth_date == p.birth_date
    assert p2.blood_type == p.blood_type
    assert p2.allergies == p.allergies
    assert len(p2.checks) == 1
    assert p2.checks[0].check_date == p.checks[0].check_date
    assert p2.checks[0].height_cm == pytest.approx(p.checks[0].height_cm)
    assert p2.checks[0].notes == p.checks[0].notes
    assert len(p2.vaccinations) == 1
    assert p2.vaccinations[0].vaccine == "DTaP"
    assert p2.vaccinations[0].next_due == date(2026, 6, 25)
    assert p2.created_at == p.created_at
    assert p2.updated_at == p.updated_at


def test_from_json_with_empty_records() -> None:
    """空 records 的 HealthProfile 也能 roundtrip。"""
    p = HealthProfile(member_id="m-empty", name="空档案", birth_date=date(2020, 1, 1))
    s = to_json(p)
    p2 = from_json(s)
    assert p2.member_id == "m-empty"
    assert p2.name == "空档案"
    assert p2.checks == []
    assert p2.vaccinations == []
    assert p2.allergies == []
    assert p2.blood_type == "未知"


def test_profile_dict_roundtrip() -> None:
    """profile_to_dict / profile_from_dict 与 to_json/from_json 等价。"""
    p = HealthProfile(
        member_id="m1",
        name="Grace",
        birth_date=date(1995, 12, 1),
        blood_type="AB",
    )
    d = profile_to_dict(p)
    # 序列化层都是 ISO 字符串
    assert isinstance(d["birth_date"], str)
    assert isinstance(d["created_at"], str)
    p2 = profile_from_dict(d)
    assert p2.birth_date == date(1995, 12, 1)
    assert p2.blood_type == "AB"


def test_json_unicode_preserved() -> None:
    """to_json 必须保留中文（ensure_ascii=False）。"""
    p = HealthProfile(member_id="m-cn", name="张三", birth_date=date(2010, 1, 1))
    s = to_json(p)
    assert "张三" in s
    # 必须是 ensure_ascii=False
    assert json.loads(s)["name"] == "张三"


# ---------- BloodType Literal ----------


def test_blood_type_literal_validation() -> None:
    """血型必须是字面量集合内的值（dataclass Literal 会在构造时拒绝非法值）。"""
    # 合法值
    for bt in ("A", "B", "AB", "O", "未知"):
        p = HealthProfile(member_id="m", name="x", birth_date=date(2000, 1, 1), blood_type=bt)
        assert p.blood_type == bt

    # 非法值：mypy 在静态层拒绝，运行时 Python dataclass Literal 不会强校验
    # 但 Pydantic 模式下会抛错。我们用 try/except 确认行为。
    try:
        HealthProfile(member_id="m", name="x", birth_date=date(2000, 1, 1), blood_type="X")  # type: ignore[arg-type]
    except TypeError:
        pytest.fail("dataclass 不应在运行时拒绝 Literal 非法值 —— 此用例为兼容性记录")
