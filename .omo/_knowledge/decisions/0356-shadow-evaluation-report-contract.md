---
id: ADR-0356
title: Manifest-bound Shadow Evaluation 报告与激活边界
status: ACCEPTED
date: 2026-08-03
owner: governance-team
lifecycle: spec
last_updated: 2026-08-03
---

# ADR-0356: Manifest-bound Shadow Evaluation 报告与激活边界

## 背景

KEMS 已有候选预测器、脱敏评测 manifest 和 acceptance 计算，但如果只有一次性命令输出，无法证明输入样本、评测集、场景和模型版本
属于同一轮可复现的影子评测。另一方面，当前仍没有真实低风险消费者形成完整的 receipt、outcome feedback、双人标注和 adjudication，
因此不能把离线候选结果误报成真实准确率或生产能力。

## 决策

1. 在 Kairon 增加独立的 `kems.shadow-evaluation-report.v1` 编排脚本，不改动既有候选预测器和 acceptance 核心函数。
2. 每次运行必须提供 `run_id`、`scenario_id`、候选模型标识、脱敏数值输入和 `kems.evaluation-manifest.v1`。
3. manifest 必须是 `redaction_status=verified`，样本必须 `annotation_status=adjudicated`，且全部属于请求场景；输入 `case_id` 必须与
   manifest 的 `sample_id` 集合精确一致。
4. 报告只写入 manifest SHA、输入 SHA、样本 ID、指标、基线、策略和控制面，不写入原文、OCR、prompt、模型自由文本、凭据或未声明字段。
5. 报告固定保持 `activation=forbidden`、`provider_invocation=false`、`workflow_run_creation=false`、`automatic_promotion=false`，
   并要求 `blocked_until_omo_approval`。`shadow_pass` 只代表离线指标达标，不代表生产放行。
6. 真实业务上线前，必须由低风险消费者提供连续真实回执，并经过双人标注、adjudication、脱敏 manifest 和 OMO 人工审批；本 ADR 不降低该闸门。

## 影响

- M6 获得可重复、可审计的影子评测报告能力。
- M2 的真实样本缺口仍然公开，fixture 只能用于契约测试，不能作为生产准确率。
- Workflow Mesh 的准入、任务状态、外部资源路由和 provider 激活不受预测报告直接影响。
- 后续若要开放小范围辅助决策，必须新增 ADR，提供人工复核、回滚、置信度和连续评测证据。

## 验证

```bash
cd projects/kairon
PYTHONPATH="packages/kos/src:scripts" uv run --no-project --with pytest pytest tests/scripts/test_kems_shadow_evaluation.py tests/scripts/test_kems_predict_candidate.py -q
uv run --no-project --with ruff ruff check scripts/kems_shadow_evaluation.py tests/scripts/test_kems_shadow_evaluation.py
```
