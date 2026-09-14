---
schema_version: specification/v1
spec_version: 1.0.0
title: 主动健康连续体征监测、异常预警与就诊咨询闭环场景包设计
bet_id: BET-Y2Q2-T7-03
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-12
---



# T7-03 — 主动健康连续体征监测、异常预警与就诊咨询闭环设计

## 1. 问题

健康域现有 4 张场景卡（`health-intake / visit-prep / visit / archive`，BET-Y1Q3-T7-02）
全部围绕“就诊事件”手工触发：症状出现 → 人工记录 → 就诊准备。缺少一条
**连续体征 → 每日健康分 → 异常预警 → 干预/就诊问答卡** 的自动闭环，
心率/血糖/睡眠的漂移在两次就诊之间无人值守。

## 2. 非目标 (与 ledger non_goals 一致)

- 不替代专业执业医师法律责任：管线只输出**结构化发现**（指标/偏离/持续天数）
  与**建议向医生提问的问题清单**，不做任何诊断断言。
- 不接自动采集源：不连穿戴 API/体检系统（沿用 `health-intake` P1 敏感域约束
  “不接自动采集源，不外发未人审内容”）。输入为本地 JSONL 台账 + Apple Health
  手工导出 CSV 的本地解析适配器（`import_apple_health_csv`），数据不出本机。
- 不引入云端 LLM/外部服务：全确定性本地计算，零模型调用。
- 不向医生/医院外发：`send_email:doctor` 属 L2 强 HITL，本 bet 不碰。

## 3. 设计

### 3.1 体征台账 (`domain/health/vitals.py`)

- `VitalReading`: dataclass —— `date / metric(hr_rest/sleep_hours/fasting_glucose/
  steps) / value / source(manual/apple_health_csv)`。
- `unmeasured` 语义：缺失日期标 `unmeasured`，永不插值伪造（circuit breaker）。
- `PersonalBaseline`: 滚动 14 天窗口均值/标准差（需 ≥7 个有效点，否则 baseline
  状态为 `insufficient` 并降级为固定临床参考区间比较）。

### 3.2 监测管线 (`domain/health/monitor_pipeline.py`)

- `daily_health_score(date, ledger)`: 0–100，由三项偏离度加权（静息心率 40% /
  睡眠 35% / 空腹血糖 25%），缺失项按权重重归一并标记 `partial`。
- `detect_anomalies(...)`: z ≥ 2.0 且连续 ≥2 天 → `anomaly`；单日 z ≥ 3.0 →
  `spike`（当日即卡）。返回结构化 `Finding` 列表。
- `build_intervention_card(finding)`: 生成干预场景卡 payload —— 发现摘要 +
  3–5 个建议向医生提问的问题 + `needs_doctor_visit` 布尔建议（规则：连续异常
  ≥3 天或任一 spike → true）。**同步生成**：同一执行内产出，无队列延迟，
  满足“5 分钟内生成”SLA（本地同步执行，实测毫秒级）。
- `run_daily(date, ledger_path)`: CLI 入口 `--daily`，供 cron 调用。

### 3.3 Apple Health CSV 适配器 (`domain/health/apple_health_csv.py`)

- 解析 Apple Health 手工导出 CSV（`startDate, type, value, unit, detail` 列），映射
  `HKQuantityTypeIdentifierHeartRate → hr_rest`（取每日最小值近似静息）、
  `HKCategoryTypeIdentifierSleepAnalysis → sleep_hours`（detail 为 asleep* 睡眠段
  的 value 小时数求和，在床/清醒段识别后忽略）、
  `HKQuantityTypeIdentifierBloodGlucose → fasting_glucose`（取每日最早值）。
- 未知 type 直接跳过并计数（不中断）。

### 3.4 自测 (`domain/health/test_monitor_pipeline.py`)

- `uv run python -m domain.health.test_monitor_pipeline`（exit 0 = pass，
  与 `research` cartridge 同约定：`sys.path.insert` cartridge dir，CWD 无关）。
- 30 天种子台账（含 6 天注入异常 ground truth）→ 断言：检出 F1 ≥ 0.6
  （assisted 校准门）、每日分 0–100、缺失日标 `unmeasured`、干预卡同步产出、
  CSV 适配器三映射正确。

### 3.5 场景卡 (`docs/scene-cards/personal-health-monitor.yaml`)

- schema `scene-card/v2`，`lifecycle: assisted`（30-sample + calibration ≥ 0.6
  证据见本 spec §3.4 与管线自测输出），`journey_id: health-medical-workflow`
  （复用现有旅程，不新建）。
- 每日定时声明：`.omo/cron/registry.yaml` 新增 `status: proposed` 条目
  `health-daily-summary`（scheduler 编译器明确忽略 proposed，不装机，只留声明）。

## 4. 验收映射 (ledger done_when)

1. 场景卡晋级 assisted → 卡 `lifecycle: assisted` + §3.4 校准证据（F1 ≥ 0.6）。
2. 每日定时自动汇总健康分并与基线对比 → `run_daily --daily` + cron proposed 条目。
3. 异常 5 分钟内生成干预场景卡 → `build_intervention_card` 同步产出 + 自测断言。

## 5. 风险

- 种子台账非真人数据：校准证据标注 `synthetic-seed`，真人 30-sample 积累为后续
  bet（shadow→assisted 的 routine 化不在本 bet 范围）。
- 固定参考区间（静息心率 60–100 等）为通用成人区间，卡片注明“非个体医嘱”。
