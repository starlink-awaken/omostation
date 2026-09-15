"""健康档案数据模型（P28-W1 底座，W4 再做摘要/提醒）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

BloodType = Literal["A", "B", "AB", "O", "未知"]


@dataclass
class HealthCheckRecord:
    """单次体检记录。"""

    check_date: date
    height_cm: float
    weight_kg: float
    vision_left: float  # 视力（左眼，0.0–2.0）
    vision_right: float  # 视力（右眼，0.0–2.0）
    notes: str = ""


@dataclass
class VaccinationRecord:
    """疫苗接种记录。"""

    vaccine: str
    dose: int
    administered_at: date
    next_due: date | None = None


@dataclass
class HealthProfile:
    """家庭成员健康档案。"""

    member_id: str
    name: str
    birth_date: date
    blood_type: BloodType = "未知"
    allergies: list[str] = field(default_factory=list)
    checks: list[HealthCheckRecord] = field(default_factory=list)
    vaccinations: list[VaccinationRecord] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now())
    updated_at: datetime = field(default_factory=lambda: datetime.now())

    def add_check(self, record: HealthCheckRecord) -> None:
        """追加一次体检，并刷新 updated_at。"""
        self.checks.append(record)
        self.updated_at = datetime.now()

    def add_vaccination(self, record: VaccinationRecord) -> None:
        """追加一次疫苗接种，并刷新 updated_at。"""
        self.vaccinations.append(record)
        self.updated_at = datetime.now()

    def age_years(self, on: date | None = None) -> int:
        """计算当前年龄（完整年份）。"""
        on = on or date.today()
        years = on.year - self.birth_date.year
        if (on.month, on.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years

    def last_check(self) -> HealthCheckRecord | None:
        """返回最近一次体检记录（按 check_date 排序）。"""
        if not self.checks:
            return None
        return max(self.checks, key=lambda c: c.check_date)

    def upcoming_vaccinations(self, on: date | None = None, window_days: int = 60) -> list[VaccinationRecord]:
        """返回 next_due 在 on 之后、且落在 [0, window_days] 窗口内的疫苗。"""
        if window_days < 0:
            raise ValueError(f"window_days must be >= 0, got {window_days}")
        on = on or date.today()
        out: list[VaccinationRecord] = []
        for v in self.vaccinations:
            if v.next_due is None:
                continue
            delta = (v.next_due - on).days
            if 0 <= delta <= window_days:
                out.append(v)
        return out
