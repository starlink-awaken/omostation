---
type: ephemeral
status: active
created: 2026-09-03
owner: governance-team
---

# 场景激活 Playbook

> 目标: 将场景维度从 3/10 提升到 6/10
> 策略: Shadow 模式先行 → 积累样本 → 逐步升级

## 当前状态

| 指标 | 数值 |
|------|------|
| Journey Specs | 48 个 (docs/journey-specs/) |
| 活跃场景卡 | 0 |
| 可激活候选 | 多个 (scene-card-candidates.py) |
| 阻塞因素 | 缺少 admission contract 字段 |

## 5 档生命周期

```
draft → shadow → assisted → supervised → routine
 ↑         ↑          ↑           ↑          ↑
无需确认   3-sample   30-sample   事后审查   全自主
```

## 优先激活场景 (Shadow 模式)

### P0 — 立即可激活 (无业务副作用)

| 场景 | Journey | 触发条件 | 预期产出 |
|------|---------|----------|----------|
| inbox-to-decision | inbox-to-decision.yaml | 新消息入收件箱 | 自动分类 + 优先级排序 |
| research-to-insight | research-to-insight.yaml | 研究任务完成 | 知识沉淀 + 关联发现 |
| meeting-to-delivery | meeting-to-delivery.yaml | 会议结束 | 行动项提取 + 任务创建 |

### P1 — 需少量配置

| 场景 | Journey | 触发条件 | 预期产出 |
|------|---------|----------|----------|
| intent-to-execution | intent-to-execution.yaml | NL 意图输入 | 编译为执行 DAG |
| schedule-to-evidence | schedule-to-evidence.yaml | 定时触发 | 证据收集 + 报告生成 |

### P2 — 需业务确认

| 场景 | Journey | 触发条件 | 预期产出 |
|------|---------|----------|----------|
| health-medical | health-medical-workflow.yaml | 健康数据更新 | 健康报告 + 建议 |
| documents-release | documents-accepted-release-journey.yaml | 文档审批通过 | 发布 + 通知 |

## Shadow 模式激活步骤

### Step 1: 创建场景卡 (draft)

```yaml
# docs/scene-cards/<scene-id>.yaml
schema: scene-card/v1
scene_id: <scene-id>
lifecycle: draft
journey_id: <journey-id>
goal: <一句话目标>
trigger: <触发条件>
input_contract: <输入契约>
result_contract: <输出契约>
outcome_metric: <结果指标>
owner: <owner>
```

### Step 2: 升级到 shadow

```bash
# 验证场景卡字段完整
python3 bin/ssot/scene-card-review.py --validate <scene-id>

# 升级到 shadow (无需业务确认)
python3 bin/ssot/scene-card-review.py --promote <scene-id> --to shadow
```

### Step 3: 积累 3 个 sample

```bash
# 运行 journey runner (dry-run)
python3 bin/ssot/journey-runner.py --journey <journey-id> --dry-run

# 验证 sample 质量
python3 bin/ssot/journey-validator.py --journey <journey-id>
```

### Step 4: 升级到 assisted

```bash
# 3-sample 通过后自动升级
python3 bin/ssot/scene-card-review.py --promote <scene-id> --to assisted
```

## 48 个 Journey Spec 清单

### 文档家族 (docs-family)
- documents-accepted-release-journey
- documents-bridge-preflight-journey
- documents-cockpit-convergence-journey
- documents-cockpit-runtime-journey
- documents-concept-weave-journey
- documents-consumer-audit-journey
- documents-consumer-audit-modes-journey
- documents-consumer-tail-journey
- documents-consumer-tokenization-journey
- documents-contract-ocr-journey
- documents-controller-preflight-journey
- documents-convergence-preflight-journey
- documents-domain-sync-journey
- documents-execution-retirement-journey
- documents-family-runtime-journey
- documents-freshness-journey
- documents-guizi-scripts-journey
- documents-guizi-symlinks-journey
- documents-guizi-tools-journey
- documents-guozhuan-symlinks-journey
- documents-guozhuan-tools-journey
- documents-l4-convergence-journey
- documents-learning-control-journey
- documents-learning-helpers-journey
- documents-ocr-cutover-journey
- documents-ocr-preflight-journey
- documents-opc-runtime-journey
- documents-owner-job-journey
- documents-predictor-preflight-journey
- documents-public-runtime-journey
- documents-release-root-journey
- documents-root-control-tools-journey
- documents-root-oneoff-journey
- documents-root-tools-journey
- documents-schedule-cutover-journey
- documents-signals-preflight-journey
- documents-vault-health-journey
- documents-weijian-cleanup-journey
- documents-weijian-control-journey
- documents-weijian-runtime-journey
- documents-workspace-watch-journey
- documents-zcode-config-journey
- documents-zcode-state-journey

### 工作流 (workflow)
- inbox-to-decision
- intake-review-deliver-inbox
- intake-review-deliver-meeting
- intake-review-deliver-oversight
- intent-to-execution
- meeting-to-delivery
- oversight-to-decision
- parallel-approval-test
- research-to-insight
- schedule-to-evidence

### 通知/健康 (notification/health)
- admin-notification-workflow
- health-medical-workflow

### KEMS (知识引擎)
- knowledge-capture-pipeline

## 验证命令

```bash
# 1. 检查 journey spec 有效性
for f in docs/journey-specs/*.yaml; do
  python3 bin/ssot/journey-validator.py --spec "$f"
done

# 2. 列出可激活的候选
python3 bin/ssot/scene-card-candidates.py

# 3. 尝试自动创建 journey
python3 bin/gac/scene-journey-connector.py --auto-create
```

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 场景卡字段不完整 | 使用模板 + validator 前置检查 |
| 业务 owner 未指定 | shadow 模式无需 owner 确认 |
| Journey 执行失败 | dry-run 模式先验证 |
| Sample 质量不足 | journey-validator 前置校验 |

## 下一步

1. 创建 3 个 P0 场景卡 (draft)
2. 验证字段完整性
3. 升级到 shadow
4. 积累 sample
5. 文档化 activation playbook → ADR
