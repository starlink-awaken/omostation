# Autopilot Implementation Plan: P44 W5 — review-queue 闭环

> **Date**: 2026-06-16
> **Stage**: Autopilot Phase 1 — Planning
> **Spec**: `.omc/autopilot/spec.md`

---

## 0. Plan Validation

| 标准 | 状态 |
|------|:----:|
| Goals 范围收敛 | ✅ (1 目标, 3 worker 并行) |
| 验收可验证 | ✅ (5 文件 + 5 状态流转) |
| 复用已有资产 | ✅ (W4 review-queue + items) |
| 风险可缓解 | ✅ (3 风险) |
| Out of scope 明确 | ✅ (5 项目不改) |

**总评**: 🟢 进 Phase 2

---

## 1. Execution Strategy (3 worker 并行)

| Worker | 任务 | 范围 |
|--------|------|------|
| worker-1 | Goal 1 review | 5 review-queue YAML 走实际 review + 写 verdict |
| worker-2 | approved debt close | approved debts 改 items YAML status=closed + evidence |
| worker-3 | 文档 + 战略 | P44 W5 复盘 + 战略 SSOT 更新 |

Lead 收口: commit + cleanup

---

## 2. Worker-1: 5 review-queue 走 review

### 步骤
1. 读 5 review-queue YAML + 对应 items YAML
2. 对每个 review-queue:
   - 读 debt 字段: id/title/severity/owner/source_file
   - 读 items YAML: 完整内容
   - 评 verdict: approved / rejected / needs-changes
   - 写新字段: verdict / reviewer / reviewed_at / reason / next_action
3. 5 个全改完
4. 验证 5 review-queue 全含 verdict 字段
5. commit (但 lead 接管)

### 验收
- [ ] 5 review-queue 全含 verdict
- [ ] reviewer=team-lead
- [ ] reason 填全

---

## 3. Worker-2: approved debt close

### 步骤
1. 读 5 review-queue (worker-1 改完的)
2. 筛 verdict=approved 的 debt
3. 对每个 approved:
   - 读对应 .omo/debt/items/DEBT-*.yaml
   - 改 status=closed + closed_at + evidence
4. 验证: items YAML status 流转一致
5. commit (但 lead 接管)

### 验收
- [ ] approved debts: items YAML 改 status=closed
- [ ] closed_at + evidence 填全

---

## 4. Worker-3: 文档 + 战略

### 步骤
1. 读 5 review-queue (改完的)
2. 写 P44 W5 复盘: `.omo/_knowledge/management/retrospective-2026-06-16-p44-w5.md`
3. 更新战略 SSOT: `.omo/_knowledge/management/strategic-governance-p42.md` (BET-REVIEW-QUEUE 状态 ✅)

---

## 5. Sequencing

3 worker 并行。

---

*Plan: 老王 · 2026-06-16 · 1 目标 · 3 worker 并行*
