---
title: phase28-e2e-eval-report
type: doc
status: active
---

# P29 E2E-DEMO 评估报告 — 2026-06-05

> 工作问题: 基层医疗机构药品集采政策梳理
> 实际运行: 0.03s · KOS 命中 14 条 · 引用 18 条
> 初稿文件: `/tmp/draft_v1.md`

## 召回率评估

| 指标 | 值 |
|---|---|
| 期望种子数 | 5 |
| 命中数 | 4 |
| 缺失 | CON-health-policy-003 |
| 命中明细 | CON-health-policy-001, CON-health-policy-002, CON-health-policy-004, CON-health-policy-005 |
| **Recall** | **0.80** |
| 等级 | A (优秀) |

## 结构校验

- ✅ 问题摘要节
- ✅ 政策依据节
- ✅ 参考引用节
- 引用数: 18

> 全部校验通过, 无警告.


## 改进建议

| 维度 | 当前 | 建议 |
|---|---|---|
| 召回率 | 0.80 (A) | 维持当前关键词策略, 可考虑扩大种子政策覆盖 |
| 引用数 | 18 | 已经达到 ≥ 3 阈值, 当前 18 条 |
| 结构完整性 | 3/3 | 3/3 全部命中, 维持模板 |

## 调用方法

```bash
# 1. 跑 demo 生成初稿
uv run python scripts/e2e_health_demo.py \
    --question "<工作问题>" \
    --output /tmp/draft.md

# 2. 跑 eval 评估初稿
uv run python scripts/e2e_health_eval.py \
    --draft /tmp/draft.md \
    --expected-policy-ids CON-health-policy-001,CON-health-policy-002,CON-health-policy-003 \
    --output .omo/_delivery/phase28-e2e-eval-report.md
```

## 关联文件

- 评估脚本: `projects/kairon/scripts/e2e_health_eval.py`
- 测试: `projects/kairon/tests/scripts/test_e2e_health_eval.py`
- 评估对象: `projects/kairon/scripts/e2e_health_demo.py`
- 任务 YAML: `.omo/tasks/planned/P29-W0-E2E-EVAL.yaml`
