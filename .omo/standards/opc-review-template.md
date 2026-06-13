# OPC Phase/Sub-gate Review Template (8 段硬结构)

> 状态: active | 版本: v1.0 | 引入: 2026-06-13
> 关联: `.omo/_control/evolution/config.yaml`, `feedback_8field_review_template_20260612.md`, `feedback_opc_closeout_reviewer_acceptable_20260613.md`
> 适用范围: 所有 OPC Phase / Sub-gate / Self-correction 收口报告

---

## 1. 适用范围

本模板用于 OPC 路线图所有 phase 收口 (P0-P7) / sub-gate 验收 (E1-E4 / F1-F4 / G1-G4 / H1-H5) / self-correction 闭环报告。

**强制要求**: 8 段缺一即 `request changes`, 不得合并段、不得省略段。

---

## 2. 8 段硬结构

### 2.1 Phase

- **Phase 编号** (P0 / P1 / ... / P7)
- **Sub-gate 编号** (F1 / G3 / H5 等)
- **状态** (`not_yet_passed` / `conditionally_passed` / `passed`)

### 2.2 Subgate Objective

- 一句话目标 (用 `SHALL` / `MUST` 强约束表达, 不得写"我们尝试...")
- 与 OPC 路线图 macro-goal 的映射关系 (哪个 vision-roadmap item 受益)

### 2.3 Files (SSOT 列表)

列出所有被变更 / 验证 / 引用的文件, 每条含:
- 相对路径 (从 `~/Workspace` 起)
- 变更类型 (新增/修改/删除)
- 与 sub-gate 的关联 (主文件 / 证据 / 配置)

**禁止**: 写"详见 git log"或"diff 见上"敷衍。

### 2.4 Commands (可复制)

每条命令必须满足:
- 完整可复制 (含 `cd` / `uv` / `pytest` 全路径)
- 含期望输出 (top 5-10 行)
- 含 `2>&1` 转向避免污染

**禁止**: 写"已通过"无命令, 写"测试通过"无 evidence。

### 2.5 Runtime

- **触发窗口**: manual-only / cron-only / mixed
- **cron 表达式** (若 cron-only): `0 2 * * 1`
- **env 变量**: INVOCATION_ID, OPC_TRIGGER, OPC_MODE, OPC_GENERATED_AT, OPC_TODAY
- **锁策略**: fcntl.flock / file lock / advisory

### 2.6 Doc-writeback

- 落盘报告路径 (`.omo/_knowledge/audits/{date}-*.md`)
- L0 模型变更 (`projects/ecos/src/ecos/ssot/mof/m1/...`)
- standards 变更 (`.omo/standards/...`)
- closeout 报告 self-correction discipline 标记

### 2.7 Risks (6 处遗留争议)

- 必含 6 处显式遗留争议, 按 P0/P1/P2/P3 标红黄绿
- 每条含: 描述 / 影响范围 / 何时升级 / 触发再 review 条件
- **禁止**: 写"无遗留"或"全部闭环" (除非真的 0 风险)

### 2.8 Verdict

- **自我验收**: ✅ / 🟡 / ❌
- **第三方验收**: ✅ / 🟡 / ❌
- **passed 前置条件** (若 not_yet_passed): 列出 N 条 P2 必须项
- **Redline 状态**: 5/5 守住打勾, 任一不守即 `request changes`

---

## 3. 5 红线 (违反即 request changes)

| # | 红线 | 守门方式 |
|---|------|---------|
| 1 | `gate_status` 一律维持 `not_yet_passed` | YAML lint + reviewer 一票否决 |
| 2 | `planned/` 任务不得推 `active/` | governance 健康检查 100% |
| 3 | manual 演练仅限 1 次 | evidence type 字段必含 `cron` / `manual` 二选一 |
| 4 | 子仓指针不自动 bump | 根仓只 commit 元数据 (plan/doc/evidence) |
| 5 | 无 §17 证据 / 无 5repos.json / 无 audit 报告 → 不得宣称 passed | `validation_summary` 段 3/3 必填 |

---

## 4. 收口报告交叉引用

- **reviewer-acceptable 模板**: `feedback_opc_closeout_reviewer_acceptable_20260613.md`
- **8 字段 review template 强制标准**: `feedback_8field_review_template_20260612.md`
- **release notes 三件套**: `feedback_release_notes_three_piece_20260612.md`
- **drift 闭环配置**: `.omo/_control/evolution/config.yaml`
- **L0 约束 7 条新规**: `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml:opc_cadence_constraints`
- **X4 一致性 3 新规**: `projects/ecos/src/ecos/ssot/mof/m1/governance/GOV-X4-CONSISTENCY.yaml:rules`

---

## 5. 历史触发点

- **2026-06-13**: OPC P5-P7 self-correction closeout, 首次按本模板产出报告, 通过 reviewer 验收
- **2026-06-12**: 8 字段 review template 强制标准 (前身) 引入, 经 OPC P5-P7 8 阶段演练沉淀
