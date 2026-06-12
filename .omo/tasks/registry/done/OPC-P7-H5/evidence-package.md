# OPC P7-H5 评审模板 — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P7 / Gate H / Sub-gate H5

## 1. REVIEW-TEMPLATE.md 落地

`docs/OPC-REVIEW-TEMPLATE.md` 8 字段模板:

1. **Phase/Subgate** — 阶段/子门 ID + plan + 日期
2. **Objective** — 1-2 句目标
3. **Files changed** — 文件路径 + 描述
4. **Commands run** — 命令 + exit code + 实际输出
5. **Runtime evidence** — 测试 + 真实样本 + 落盘证据
6. **Doc/task writeback** — 4 项 checklist
7. **Open risks** — 红线 + 已知限制
8. **Requested verdict** — LGTM / Request changes / Needs more evidence

## 2. ≥1 次 review 跑通

样本 review: `.omo/tasks/registry/done/OPC-P7-H5/sample-review-P7-H1.md`
- 复审 P7-H1 release cycle runner
- 8 字段全填, Requested verdict = LGTM

## 3. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | REVIEW-TEMPLATE.md 落地 | ✅ | docs/OPC-REVIEW-TEMPLATE.md |
| 2 | ≥1 次 review 跑通 | ✅ | sample-review-P7-H1.md (8 字段全填) |

## 4. 红线遵守

- ✅ 8 字段缺一不可 (template 强制)
- ✅ request changes 强制触发条件明确 (4 条)
- ✅ sample review 是真实跑通, 不是 fixture
- ✅ 实施、测试、task、doc 同步
