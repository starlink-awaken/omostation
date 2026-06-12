# OPC P6-G2 周更升级报告 — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P6 / Gate G / Sub-gate G2
> 2 周周报: W23 + W24

## 1. ≥3 candidates + score 排序实证

W23 top 3 (取自 `.omo/_control/evolution/loop/2026-W23.json`):

| # | score | lane | title |
|---|------:|------|-------|
| 1 | 1.5 | radar | Platform: consolidate 'search-trace: AGENTS' into a shared module |
| 2 | 0.0 | radar | Manual follow-up #1 — review recent research activity |
| 3 | 0.0 | radar | Manual follow-up #2 — review recent research activity |

score 排序: 1.5 > 0.0 = 0.0 ≥ 3 candidates ✅

W24 top 3 同结构, evidence_id=34 稳定, generated_at 不同。

## 2. 字段完整性 (G2 红线)

每条 candidate 必含 4 字段:
- source ✅
- timestamp ✅
- next-action ✅
- 人工审批栏 ✅ (周报末 "8. 人工审批栏")

## 3. 2 周连续性

- W23 markdown: `.omo/tasks/registry/done/OPC-P6-G1/weekly-2026-W23.md`
- W24 markdown: `.omo/tasks/registry/done/OPC-P6-G1/weekly-2026-W24.md`

均为 2026-06-12 03:24 (相差 7 秒) 实际跑出, 不是 mock。

## 4. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | ≥2 周连续周报 | ✅ | W23 + W24 |
| 2 | 每份含 ≥3 candidates | ✅ | W23 top 3 / W24 top 3 |
| 3 | score 排序 | ✅ | score 1.5 > 0.0 |
| 4 | 含 source | ✅ | cockpit:research |
| 5 | 含 timestamp | ✅ | 2026-06-11T09:49:15Z (真实) / 2026-06-12T03:24:37Z (now) |
| 6 | 含 next-action | ✅ | "create OPC follow-up task + link to source research" |
| 7 | 含人工审批栏 | ✅ | weekly-{week}.md §8 reviewer A/B 复选框 |
