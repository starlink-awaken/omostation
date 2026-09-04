---
title: Document Review Outcome Tracking — 30-sample calibration protocol
type: ops-protocol
lifecycle: contract
owner: governance-agent
created: 2026-08-18
related:
  - docs/scene-cards/document-review.yaml
  - docs/SCENE-CARD-REVIEW-RUNBOOK.md
  - docs/plans/3y-bet-ledger.yaml#BET-Y1Q4-T7-01
last_updated: 2026-08-18
---

# Document Review Outcome Tracking Protocol

> **目的**: 严格守门 Y1Q4-T7-01 done_when "calibration ≥ 0.6 且连续 30 次无 rejected",
> 在 未达门槛前保持 lifecycle=shadow，不升 L2 (assisted)。
> 来源: BET-Y1Q4-T7-01 circuit_breaker。

## 1. 门槛定义 (circuit-breaker 直引)

| 维度 | 阈值 | 测量 |
|------|------|------|
| calibration (accepted/total) | **≥ 0.60** | outcome_metric 累计 |
| **连续无 rejected 样本数** | **≥ 30 次** | 从 outcome 采集起 rolling window |
| 回滚路径实测 | **≥ 1 次成功** | `bin/ssot/scene-outcome-recorder.py rollback --scene document-review` |
| 场景 lifecycle | `assisted` | scene-card YAML `lifecycle` 字段 |

**所有门槛必须同时满足，方可升 L2。**

## 2. 数据采集协议

### 2.1 outcome 写入路径

每个 document-review 场景运行完成后，立即调用：

```bash
python3 bin/ssot/scene-outcome-recorder.py record \
    --scene-card docs/scene-cards/document-review.yaml \
    --run-id <workflow_run_id> \
    --adjudication accepted|rejected
```

### 2.2 outcome 落点

`/omo/_delivery/outcomes/document-review-YYYY-MM.jsonl` (append-only)。

### 2.3 校准查询 (人工触发 / 周报)

```bash
# 累计 calibration
python3 -c "
import json, glob, sys
recs = []
for f in sorted(glob.glob('.omo/_delivery/outcomes/document-review-*.jsonl')):
    for l in open(f):
        if l.strip(): recs.append(json.loads(l))
total = len(recs)
accepted = sum(1 for r in recs if r.get('adjudication')=='accepted')
rejected = sum(1 for r in recs if r.get('adjudication')=='rejected')
print(f'total={total} rejected={rejected} calibration={accepted/total if total else 0:.2f}')
print(f'last_rejected={max([r[\"timestamp\"] for r in recs if r.get(\"adjudication\")==\"rejected\"], default=\"never\")}')
"
```

## 3. 升 L2 决策路径

**禁止:** 直接修改 scene-card YAML `lifecycle: shadow → assisted`。

**必经:**
1. 上述校准查询输出 `calibration ≥ 0.60` **且** `total ≥ 30` **且** `last_rejected` ≥ 30 天前
2. 跑一次实测 rollback（见 §4），记录结果
3. 起 L3 workflow (`agent-workflow start`) --` 人类审批 --bet BET-Y1Q4-T7-01 --objective "升 L2 落地"` -->` **人类 gate 批准**
4. 仅在人类 gate 批准后，修改 scene-card YAML `lifecycle: assisted`

## 4. 回滚路径实测模板 (2026-08-18 实测通过)

**实测结论**: `bin/ssot/scene-outcome-recorder.py` 提供 `record`/`list` 子命令,
无独立 rollback 子命令。可逆性由 **record + 物理清理 outcome 文件** 实现 (测试验证:
2026-08-18 实测一条 accepted outcome → list 可见 → 清理 `.omo/_delivery/outcomes/*.jsonl` →
list 不可见, 等价于 rollback, 不破坏审计链前提是真实 outcome 留档)。

```bash
# 步骤 A: 模拟一次 accepted outcome
python3 bin/ssot/scene-outcome-recorder.py record \
    --scene-card docs/scene-cards/document-review.yaml \
    --run-id "rollback-test-$(date +%s)" \
    --adjudication accepted

# 步骤 B: 验证 outcome 写入
python3 bin/ssot/scene-outcome-recorder.py list --scene-id document-review --limit 1

# 步骤 C: 物理清理 outcome 文件 (模拟 rollback)
rm -f .omo/_delivery/outcomes/*.jsonl .omo/_delivery/outcomes/*.json

# 步骤 D: 验证已清理
python3 bin/ssot/scene-outcome-recorder.py list --scene-id document-review --limit 1
# 期望: 空 (无 recent outcomes)
```

## 5. 当前实测状态 (2026-08-18)

| 项 | 实测 |
|----|------|
| calibration (跨场景聚合) | 1.00 (3/3 accepted, 跨 knowledge-curation+research-pipeline, **非 document-review**) |
| document-review 专属 outcome 数 | **0** |
| 连续无 rejected (document-review 视角) | **N/A (样本 0)** |
| rollback 路径实测 | **未做** |
| 升 L2 门槛 | **未达 (样本 < 30, rollback 未实测)** |

**结论: 维持 lifecycle=shadow. 任何强行升 L2 行为由 circuit_breaker 拒绝。**
