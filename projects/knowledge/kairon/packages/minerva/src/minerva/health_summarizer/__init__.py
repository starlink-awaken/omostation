"""健康摘要器 — 扫描 FamilyShared 健康档案 → 输出家庭可读待办 Markdown。

P28-W4: 北极星场景 C 落地第一步。
- scanner: 扫 *.json 健康档案
- rules: 5+ 条健康提醒规则（疫苗/体检/视力/过敏/生长）
- renderer: 渲染 Markdown（按紧急/即将/一般分桶）
- runner: CLI 入口（支持 cron 调度）
"""

from __future__ import annotations

from minerva.health_summarizer.renderer import DEFAULT_OUTPUT, render
from minerva.health_summarizer.rules import (
    HealthAlert,
    check_allergy_season,
    check_checkup_due,
    check_growth_curve,
    check_vaccination,
    check_vision_change,
)
from minerva.health_summarizer.scanner import DEFAULT_PROFILE_DIR, scan_profiles

__all__ = [
    "DEFAULT_OUTPUT",
    "DEFAULT_PROFILE_DIR",
    "HealthAlert",
    "check_allergy_season",
    "check_checkup_due",
    "check_growth_curve",
    "check_vaccination",
    "check_vision_change",
    "render",
    "scan_profiles",
]
