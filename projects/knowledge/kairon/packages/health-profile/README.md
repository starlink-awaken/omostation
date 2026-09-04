---
title: README
type: doc
---

# health-profile

Phase 28 北极星场景 C 的数据底座 —— 家庭成员健康档案（HealthProfile）。

## 范围（仅 W1，W4 再做摘要/提醒生成）

- 三个 dataclass：`HealthProfile`、`HealthCheckRecord`、`VaccinationRecord`
- 计算方法：`age_years()` / `last_check()` / `upcoming_vaccinations(window=60d)`
- JSON 持久化：`to_json()` / `from_json()` 双向 roundtrip
- 依赖：仅 `core-models`（workspace）+ `pydantic>=2.0`（预留）+ 标准库

## 快速开始

```python
from datetime import date
from health_profile import HealthProfile, HealthCheckRecord, VaccinationRecord
from health_profile.io import to_json, from_json

xia = HealthProfile(
    member_id="xia-2021",
    name="夏维桢",
    birth_date=date(2021, 9, 1),
    blood_type="A",
)
xia.add_check(HealthCheckRecord(date(2024, 3, 1), 95.0, 14.5, 0.8, 0.8, "半年度体检"))
print(xia.age_years())  # 4
print(xia.upcoming_vaccinations())
```

## 测试

```bash
cd projects/kairon
uv run python -m pytest packages/health-profile/tests/unit/test_health_profile.py -v
```

## 下游接口

W4 健康摘要任务可直接消费 `HealthProfile.last_check()` / `upcoming_vaccinations()`。
