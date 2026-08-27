"""健康提醒规则 — 5 条儿童家庭健康常识规则。

每条规则签名为 (profile, today, **kwargs) -> Iterator[HealthAlert]。
- 紧急（urgent）: 7 天内必须处理
- 即将（soon）: 30 天内处理
- 一般（info）: 60-90 天参考
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from health_profile.models import HealthProfile

Severity = Literal["urgent", "soon", "info"]
Category = Literal["vaccination", "checkup", "vision", "allergy", "growth"]


@dataclass
class HealthAlert:
    """单条健康提醒。"""

    severity: Severity
    category: Category
    member_id: str
    member_name: str
    title: str
    detail: str
    action_by: date | None = None
    extra: dict = field(default_factory=dict)


# ---------- 1. 疫苗临近 ----------


def check_vaccination(profile: HealthProfile, today: date, window_days: int = 60) -> Iterator[HealthAlert]:
    """未来 window_days 天内 next_due 的疫苗。"""
    for v in profile.vaccinations:
        if v.next_due is None:
            continue
        delta = (v.next_due - today).days
        if delta < 0 or delta > window_days:
            continue
        if delta <= 7:
            severity: Severity = "urgent"
        elif delta <= 30:
            severity = "soon"
        else:
            severity = "info"
        yield HealthAlert(
            severity=severity,
            category="vaccination",
            member_id=profile.member_id,
            member_name=profile.name,
            title=f"{v.vaccine} 第 {v.dose} 剂 即将接种",
            detail=f"距 {v.next_due.isoformat()} 还有 {delta} 天",
            action_by=v.next_due,
        )


# ---------- 2. 体检超期 ----------


def check_checkup_due(profile: HealthProfile, today: date, window_days: int = 60) -> Iterator[HealthAlert]:
    """学龄前儿童：上次体检 >6 个月提醒，>12 个月紧急。"""
    last = profile.last_check()
    if last is None:
        # 从未体检过（新生儿的合理情况）
        if profile.age_years(today) >= 1:
            yield HealthAlert(
                severity="soon",
                category="checkup",
                member_id=profile.member_id,
                member_name=profile.name,
                title="尚未建立体检档案",
                detail="建议尽快安排首次儿童保健体检",
                action_by=today,
            )
        return
    months_since = (today - last.check_date).days / 30.0
    if months_since >= 12:
        severity = "urgent"
        title = "体检超期超过 12 个月"
        detail = f"上次体检 {last.check_date.isoformat()}，已过 {months_since:.0f} 个月，请尽快安排"
    elif months_since >= 6:
        severity = "soon"
        title = "体检即将超期（6 个月）"
        detail = f"上次体检 {last.check_date.isoformat()}，已过 {months_since:.0f} 个月，建议预约"
    else:
        return  # 6 个月内，无需提醒
    yield HealthAlert(
        severity=severity,  # type: ignore[arg-type]
        category="checkup",
        member_id=profile.member_id,
        member_name=profile.name,
        title=title,
        detail=detail,
        action_by=last.check_date,
    )


# ---------- 3. 视力变化 ----------


def check_vision_change(profile: HealthProfile, today: date, window_days: int = 60) -> Iterator[HealthAlert]:
    """最近 2 次体检视力下降 >0.1 → 一般提醒。"""
    if len(profile.checks) < 2:
        return
    sorted_checks = sorted(profile.checks, key=lambda c: c.check_date, reverse=True)
    latest = sorted_checks[0]
    previous = sorted_checks[1]
    left_drop = previous.vision_left - latest.vision_left  # 正值=下降
    right_drop = previous.vision_right - latest.vision_right
    if left_drop <= 0.1 and right_drop <= 0.1:
        return
    worse_eye = []
    if left_drop > 0.1:
        worse_eye.append(f"左眼 {previous.vision_left:.2f}→{latest.vision_left:.2f}")
    if right_drop > 0.1:
        worse_eye.append(f"右眼 {previous.vision_right:.2f}→{latest.vision_right:.2f}")
    yield HealthAlert(
        severity="info",
        category="vision",
        member_id=profile.member_id,
        member_name=profile.name,
        title="视力较上次下降",
        detail=" / ".join(worse_eye) + "，建议关注用眼习惯，必要时复查",
        action_by=today,
    )


# ---------- 4. 季节过敏 ----------


def check_allergy_season(profile: HealthProfile, today: date, window_days: int = 60) -> Iterator[HealthAlert]:
    """春/秋季（3-5 月、9-11 月）+ 成员 allergies 列表非空 → 一般提醒。"""
    if not profile.allergies:
        return
    month = today.month
    if month in (3, 4, 5):
        season = "春季"
    elif month in (9, 10, 11):
        season = "秋季"
    else:
        return
    yield HealthAlert(
        severity="info",
        category="allergy",
        member_id=profile.member_id,
        member_name=profile.name,
        title=f"{season}过敏高发期",
        detail=f"已知过敏原: {', '.join(profile.allergies)}，注意防护与用药储备",
        action_by=today,
    )


# ---------- 5. 生长曲线偏差 ----------


def check_growth_curve(profile: HealthProfile, today: date, window_days: int = 60) -> Iterator[HealthAlert]:
    """最近一次体检身高/体重与 WHO 中位数偏差 >30% → 一般提醒。"""
    last = profile.last_check()
    if last is None:
        return
    age = profile.age_years(today)
    if age <= 0 or age > 18:
        return
    # 简化的 WHO 中位数近似（仅用于偏差判断，精度足够筛选异常）
    median_height = 50.0 + age * 6.5  # 1岁~75cm, 5岁~105cm, 10岁~130cm
    median_weight = 3.5 + age * 2.0  # 1岁~5.5kg, 5岁~13.5kg
    height_dev = abs(last.height_cm - median_height) / median_height
    weight_dev = abs(last.weight_kg - median_weight) / median_weight
    if height_dev <= 0.30 and weight_dev <= 0.30:
        return
    issues = []
    if height_dev > 0.30:
        issues.append(f"身高 {last.height_cm}cm 偏离同龄中位数 {height_dev:.0%}")
    if weight_dev > 0.30:
        issues.append(f"体重 {last.weight_kg}kg 偏离同龄中位数 {weight_dev:.0%}")
    yield HealthAlert(
        severity="info",
        category="growth",
        member_id=profile.member_id,
        member_name=profile.name,
        title="生长曲线偏离较多",
        detail="；".join(issues) + "，建议咨询儿科或儿保科",
        action_by=last.check_date,
    )


# ---------- 规则注册表 ----------

ALL_RULES: list[Callable[[HealthProfile, date, int], Iterator[HealthAlert]]] = [
    check_vaccination,
    check_checkup_due,
    check_vision_change,
    check_allergy_season,
    check_growth_curve,
]
