# Runbook: 场景执行失败

## 症状
- Journey 执行后 status != succeeded
- 场景产出率为 0

## 排查

### 1. 检查场景状态
```bash
python3 -c "from ecos.observability.scenario_metrics import scenario_summary; print(scenario_summary())"
```

### 2. 检查 journey 定义
```bash
cd projects/ecos
uv run python3 src/ecos/l1/runtime/journey_runner.py  # 列出 journeys
```

### 3. 手动执行旅程
```python
from ecos.l1.runtime.journey_runner import JourneyRunner
r = JourneyRunner()
result = r.execute_journey("intent-to-execution")
print(result)
```

### 4. 检查前置条件
- scene-card status 必须为 pilot/active
- journey-spec 必须有 steps
- 所需能力 (CI/agent workflow) 必须可用

## 预防
- 场景激活前做 dry-run
- 监控 `outcome_metric` 趋势
