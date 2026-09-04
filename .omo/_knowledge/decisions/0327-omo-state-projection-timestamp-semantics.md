---
id: ADR-0327
title: OMO 状态投影的时间戳语义与业务变更判定
status: archived
type: decision
owner: architecture-governance
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../standards/doc-ssot-contract.md
  - 0326-external-activation-preflight.md
---

# ADR-0327: OMO 状态投影的时间戳语义与业务变更判定

## 背景

OMO 状态投影每次运行都会刷新 `system.yaml` 中的运行时间字段。若直接比较序列化结果，
即使健康分、阶段和任务计数都没有变化，也会产生虚假的 projection change 和同步证据，
污染 Workflow Mesh 的运营统计。

## 决策

1. `normalize_system_yaml()` 将 `health_score_generated_at`、
   `governance_feedback_last_run` 和 `updated_at` 视为运行元数据，从语义比较面排除。
2. 这些字段仍可写入投影文件；本 ADR 只规定变更判定，不改变运行态字段的保存、审计或事件语义。
3. 健康分、阶段、任务计数等业务字段继续参与语义比较。业务字段变化必须生成 canonical
   projection 写入，并创建对应的 state sync evidence。
4. 回归测试必须同时覆盖 timestamp-only no-op 和 semantic-change detected，防止为了消除噪声
   而误吞真实状态变化。

## 验证

```bash
cd projects/omo
PYTHONPATH=src uv run --no-project --with pytest --with pyyaml python -m pytest -q \
  tests/test_omo_ingress_state.py tests/test_omo_governance_data.py
/opt/homebrew/bin/ruff check src/omo/omo_ingress_state.py tests/test_omo_ingress_state.py
```

定向测试结果：4 passed。完整 OMO 测试在隔离 worktree 中仍受既有环境前置条件影响，失败项
集中在缺失 `bus-foundation`、子进程 `PYTHONPATH`、跨日系统日期和既有 CLI 路径假设，未涉及
本 ADR 的状态投影逻辑。
