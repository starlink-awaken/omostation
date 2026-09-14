---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y2Q1-T7-02
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
---

# T7-02 shadow 试验记录机制设计

## 1. 目标

打通 shadow → assisted 的试验证据断层：
- journey-runner 完成的 run 必须落盘到 `.omo/_knowledge/workflow-mesh/shadow-scene-trials.jsonl` (含 `journey_id/run_id/mode/scene_ids`)
- scene-card-lifecycle Check4 从"文件级存在性"升级为"按 scene_id 精确匹配"
- 三类试验日志任一含本 scene 条目即过 (`trial_recorded=true`)

## 2. In scope

1. `bin/ssot/journey-runner.py`：
   - 完成的 run 自动追加 `.omo/_knowledge/workflow-mesh/shadow-scene-trials.jsonl`
   - `mode` 字段诚实区分 `dry_run` / `live`
   - 记录失败不阻断主流程 (stderr 告警后继续)
2. `bin/ssot/scene-card-lifecycle.py` Check4：
   - 旧逻辑：`*.jsonl` 文件存在即 `trial_recorded=true`
   - 新逻辑：解析每个 jsonl，按本卡的 `scene_id` 字段匹配；任一含本场景条目即过
3. `tests/test_journey_runner_validate.py`：覆盖 4 类场景 (empty / dry-run / live / 多 scene)

## 3. Out of scope

- 不自动升级任何场景卡 (transition 仍需人工命令)
- 不改 internal/external 准入试验工具 (proposal_only 语义不变)
- 不触碰 `.omo/_truth/scenarios` 第三套卡存储 (另行归一立项 Y2Q1-T7-03)

## 4. 验收

1. `journey-runner run --journey admin-notification-workflow --dry-run` → exit 0 + jsonl 追加一条
2. `scene-card-lifecycle check --scene-card admin-classify.yaml` → `trial_recorded=true` + `ready=true`
3. 未跑 trial 的其他场景卡 (e.g. project-supervision) 仍 `ready=false`
4. `pytest tests/test_journey_runner_validate.py -q` → 4/4 PASS
