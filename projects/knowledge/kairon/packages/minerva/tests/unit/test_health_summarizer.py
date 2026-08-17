"""minerva.health_summarizer 单元测试（P28-W4）。"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from health_profile import HealthCheckRecord, HealthProfile, VaccinationRecord
from health_profile.io import to_json
from minerva.health_summarizer.renderer import render
from minerva.health_summarizer.rules import (
    HealthAlert,
    check_allergy_season,
    check_checkup_due,
    check_growth_curve,
    check_vaccination,
    check_vision_change,
)
from minerva.health_summarizer.scanner import scan_profiles

TODAY = date(2026, 6, 5)


def _make_profile(
    *,
    name: str = "夏维桢",
    member_id: str = "xia-2021",
    birth: date = date(2021, 9, 1),
    allergies: list[str] | None = None,
    checks: list[HealthCheckRecord] | None = None,
    vaccinations: list[VaccinationRecord] | None = None,
) -> HealthProfile:
    p = HealthProfile(
        member_id=member_id,
        name=name,
        birth_date=birth,
        allergies=list(allergies or []),
    )
    for c in checks or []:
        p.add_check(c)
    for v in vaccinations or []:
        p.add_vaccination(v)
    return p


# ---------- scanner ----------


def test_scan_profiles_empty_dir(tmp_path: Path) -> None:
    """目录存在但无 *.json → 返回空列表。"""
    assert scan_profiles(tmp_path) == []


def test_scan_profiles_nonexistent_dir(tmp_path: Path) -> None:
    """目录不存在 → 返回空列表（不抛错，stderr 警告）。"""
    assert scan_profiles(tmp_path / "nope") == []


def test_scan_profiles_skips_invalid_json(tmp_path: Path) -> None:
    """混合：有效 JSON + 损坏文件 → 只读有效文件。"""
    good = _make_profile(name="小明")
    (tmp_path / "xia.health.json").write_text(to_json(good), encoding="utf-8")
    (tmp_path / "broken.json").write_text("{ not valid json", encoding="utf-8")
    profiles = scan_profiles(tmp_path)
    assert len(profiles) == 1
    assert profiles[0].name == "小明"


def test_scan_profiles_reads_health_named_files(tmp_path: Path) -> None:
    """文件名后缀 .health.json 也能被识别（glob *.json）。"""
    p = _make_profile(name="小红")
    (tmp_path / "xia.health.json").write_text(to_json(p), encoding="utf-8")
    profiles = scan_profiles(tmp_path)
    assert profiles[0].member_id == "xia-2021"


# ---------- rules: vaccination ----------


def test_check_vaccination_within_window() -> None:
    """next_due 在窗口内 → 产出 HealthAlert，severity 正确分级。"""
    p = _make_profile(
        vaccinations=[
            VaccinationRecord(
                vaccine="DTaP",
                dose=4,
                administered_at=TODAY - timedelta(days=180),
                next_due=TODAY + timedelta(days=5),  # 紧急
            ),
            VaccinationRecord(
                vaccine="MMR",
                dose=1,
                administered_at=TODAY - timedelta(days=300),
                next_due=TODAY + timedelta(days=20),  # 即将
            ),
        ]
    )
    alerts = list(check_vaccination(p, TODAY, window_days=60))
    assert len(alerts) == 2
    severities = sorted(a.severity for a in alerts)
    assert severities == ["soon", "urgent"]
    assert all(a.category == "vaccination" for a in alerts)


def test_check_vaccination_outside_window() -> None:
    """next_due 超出窗口 / 已过期 → 不产出提醒。"""
    p = _make_profile(
        vaccinations=[
            VaccinationRecord(
                vaccine="X",
                dose=1,
                administered_at=TODAY - timedelta(days=400),
                next_due=TODAY - timedelta(days=10),  # 已过期
            ),
            VaccinationRecord(
                vaccine="Y",
                dose=1,
                administered_at=TODAY - timedelta(days=200),
                next_due=TODAY + timedelta(days=200),  # 超出 60 天
            ),
        ]
    )
    assert list(check_vaccination(p, TODAY, window_days=60)) == []


# ---------- rules: checkup ----------


def test_check_checkup_due_severity_urgent() -> None:
    """上次体检 >12 个月 → urgent。"""
    p = _make_profile(
        checks=[
            HealthCheckRecord(
                check_date=TODAY - timedelta(days=400), height_cm=95, weight_kg=14, vision_left=1.0, vision_right=1.0
            )
        ]
    )
    alerts = list(check_checkup_due(p, TODAY))
    assert len(alerts) == 1
    assert alerts[0].severity == "urgent"
    assert alerts[0].category == "checkup"


def test_check_checkup_due_severity_soon() -> None:
    """上次体检 6-12 个月 → soon。"""
    p = _make_profile(
        checks=[
            HealthCheckRecord(
                check_date=TODAY - timedelta(days=240), height_cm=95, weight_kg=14, vision_left=1.0, vision_right=1.0
            )
        ]
    )
    alerts = list(check_checkup_due(p, TODAY))
    assert len(alerts) == 1
    assert alerts[0].severity == "soon"


def test_check_checkup_due_within_window_no_alert() -> None:
    """上次体检 <6 个月 → 不提醒。"""
    p = _make_profile(
        checks=[
            HealthCheckRecord(
                check_date=TODAY - timedelta(days=90), height_cm=95, weight_kg=14, vision_left=1.0, vision_right=1.0
            )
        ]
    )
    assert list(check_checkup_due(p, TODAY)) == []


# ---------- rules: vision / allergy / growth ----------


def test_check_vision_change_detects_drop() -> None:
    """最近 2 次视力下降 >0.1 → info。"""
    p = _make_profile(
        checks=[
            HealthCheckRecord(
                check_date=TODAY - timedelta(days=180), height_cm=95, weight_kg=14, vision_left=0.9, vision_right=0.9
            ),
            HealthCheckRecord(
                check_date=TODAY - timedelta(days=10), height_cm=98, weight_kg=15, vision_left=0.7, vision_right=0.95
            ),
        ]
    )
    alerts = list(check_vision_change(p, TODAY))
    assert len(alerts) == 1
    assert alerts[0].severity == "info"
    assert "左眼" in alerts[0].detail


def test_check_vision_change_no_drop() -> None:
    """视力稳定或上升 → 不提醒。"""
    p = _make_profile(
        checks=[
            HealthCheckRecord(
                check_date=TODAY - timedelta(days=180), height_cm=95, weight_kg=14, vision_left=0.7, vision_right=0.7
            ),
            HealthCheckRecord(
                check_date=TODAY - timedelta(days=10), height_cm=98, weight_kg=15, vision_left=0.8, vision_right=0.85
            ),
        ]
    )
    assert list(check_vision_change(p, TODAY)) == []


def test_check_allergy_season_spring() -> None:
    """3 月 + 有 allergies → info 提醒。"""
    p = _make_profile(allergies=["尘螨", "花粉"])
    alerts = list(check_allergy_season(p, date(2026, 4, 15)))
    assert len(alerts) == 1
    assert "春季" in alerts[0].title
    assert "尘螨" in alerts[0].detail


def test_check_allergy_season_winter_no_alert() -> None:
    """1 月（无季节） → 不提醒。"""
    p = _make_profile(allergies=["尘螨"])
    assert list(check_allergy_season(p, date(2026, 1, 15))) == []


def test_check_allergy_season_empty_allergies() -> None:
    """allergies 为空 → 即便春季也不提醒。"""
    p = _make_profile(allergies=[])
    assert list(check_allergy_season(p, date(2026, 4, 15))) == []


def test_check_growth_curve_normal() -> None:
    """身高/体重接近中位数 → 不提醒。"""
    p = _make_profile(
        birth=date(2021, 6, 1),  # 即将 5 岁
        checks=[HealthCheckRecord(check_date=TODAY, height_cm=105, weight_kg=17, vision_left=1.0, vision_right=1.0)],
    )
    assert list(check_growth_curve(p, TODAY)) == []


def test_check_growth_curve_deviation() -> None:
    """身高偏差 >30% → info 提醒。"""
    # 4 岁中位身高 ~76cm，体重 ~11.5kg；故意取极端值触发 >30% 偏差
    p = _make_profile(
        birth=date(2021, 6, 1),
        checks=[HealthCheckRecord(check_date=TODAY, height_cm=50, weight_kg=5, vision_left=1.0, vision_right=1.0)],
    )
    alerts = list(check_growth_curve(p, TODAY))
    assert len(alerts) == 1
    assert alerts[0].severity == "info"
    assert "身高" in alerts[0].detail


# ---------- renderer ----------


def test_render_separates_urgent_soon_info() -> None:
    """三种 severity 都被渲染到对应分桶。"""
    alerts = [
        HealthAlert(
            severity="urgent",
            category="vaccination",
            member_id="m1",
            member_name="夏维桢",
            title="A",
            detail="a",
        ),
        HealthAlert(
            severity="soon",
            category="checkup",
            member_id="m1",
            member_name="夏维桢",
            title="B",
            detail="b",
        ),
        HealthAlert(
            severity="info",
            category="vision",
            member_id="m2",
            member_name="爸爸",
            title="C",
            detail="c",
        ),
    ]
    md = render(alerts, today=TODAY)
    assert "## 🔴 紧急（7 天内）" in md
    assert "## 🟡 即将（30 天内）" in md
    assert "## ⚪ 一般（参考）" in md
    assert "**夏维桢**" in md
    assert "**爸爸**" in md
    assert "minerva.health_summarizer" in md


def test_render_empty_alerts_shows_placeholder() -> None:
    """空提醒列表 → 友好占位。"""
    md = render([], today=TODAY)
    assert "家庭健康待办" in md
    assert "_当前无待办健康事项。_" in md
    # 不应出现任何分桶
    assert "🔴" not in md
    assert "🟡" not in md
    assert "⚪" not in md
