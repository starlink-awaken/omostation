---
id: ADR-0400
lifecycle: spec
owner: '@Builder'
last_updated: '2026-08-09'
---

# ADR-0400: Definition of Done — 任务完成验证门禁 (防虚假完成)

- status: accepted
- date: 2026-08-08
- owner: governance-team
- supersedes: 无 (新机制)
- related:
  - `.omo/debt/gap-items/` (能力缺口台账)
  - `bin/_archive/2026-08-conv3/gap-verify.py` (清零率验证)
  - `bin/_archive/2026-08-conv3/task-verify.py` (完成验证门禁)

---

## Context

上次规划"39/39 tasks 100%完成"，但深度复盘发现实际功能实现度仅~43%。
根因: **完成 = 代码存在**，而非**功能可验证**。stub 也标记完成，dry-run 通过但无 live
证据，数据流断裂 3 处未发现。

## Decision

**Definition of Done (DoD) 四级标准**，任何任务标记 `completed/resolved` 前必须满足：

| 级别 | 标准 | 验证方式 |
|------|------|---------|
| L1 | 代码存在 | 文件存在 |
| L2 | dry-run 通过 | 命令可执行返回 0 |
| L3 | 真实数据流过 | evidence 文件存在 |
| L4 | 端到端闭环 | 状态机完整走通 + reflection 产出 |

**机制保障** (不靠自觉):
1. **任务模板**: 每个 task 必须声明 `do_d` + `evidence_refs` + `verification_cmd`
2. **task-verify 门禁**: `make task-verify` 检查 completed 任务是否有 evidence 文件，
   缺失 → 降级为 `unverified`，CI 红灯
3. **gap-verify 清零率**: `make gap-verify` 输出 resolved/total，进度 = 清零率
4. **stub 不算完成**: 含 stub/TODO 标记的函数必须显式标注 `lifecycle_state: open` 或
   `status: stub`，禁止标记 completed

## Consequences

- **正面**: 所有"完成"声明有据可查，杜绝虚假完成
- **负面**: 标记完成成本略增（需产出 evidence 文件）
- **约束**: 依赖用户环境的 live 验证任务，标 `needs_env`，不在自动任务中强求

## Follow-ups

- [ ] 将 DoD 模板推广到所有 task 创建入口
- [ ] 将 task-verify 接入 CI workflow
- [ ] 定期审计历史 completed 任务的 evidence 完整性
