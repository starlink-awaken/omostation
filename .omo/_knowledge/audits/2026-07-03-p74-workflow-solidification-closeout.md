---
status: active
lifecycle: audit
owner: governance-team
last-reviewed: 2026-07-03
related:
  - ../../_knowledge/decisions/0130-p74-workflow-solidification.md
  - ../../_knowledge/patterns/p74-workflow-solidification-pattern.md
  - ../../standards/p74-solidification-contract.md
  - ../../../.agents/skills/workflow-silence-detection/SKILL.md
  - 2026-07-02-p0-baseline-recovery-closeout.md
---

# P74 Workflow Solidification — Closeout Report

> **日期**: 2026-07-03 | **PR 链**: PR-89 (`1fef373d`) + PR-90 (`2bc44dd4`) | **状态**: ✅ merged

## 1. 5 阶段路线图完成度

| 阶段 | 目标 | PR | 状态 |
|------|------|-----|------|
| 1. 清场 | 关闭 active run `01ecb268`, compliance 归零 | PR-89 commit 1 | ✅ |
| 2. 鸿沟回收 | 3 个新 diff_check + 4 条 CR-P74-* 规则 | PR-89 commit 1+2 / PR-90 | ✅ |
| 3. 错位路由 | `agent-workflow suggest --from-diff` | PR-89 commit 4 | ✅ |
| 4. 沉默分层 | A1/A2 区分 + `silent_workflow_policy` | PR-89 commit 1 | ✅ |
| 5. 自我演化 | `p74_solidification_report` 内嵌 compliance | PR-89 commit 4 / PR-90 | ✅ |

## 2. GaC 维度变化

| 维度 | 修复前 | 修复后 | delta |
|------|--------|--------|-------|
| X1 (审计链) | 33 | **35** | +2 (CR-P74-RUNTIME-STAMP-POLICY, CR-P74-WORKFLOW-SILENCE) |
| X3 (价值栈) | 20 | **21** | +1 (CR-P74-WORKFLOW-SUGGEST) |
| X4 (一致性) | 65 | **66** | +1 (CR-P74-STATE-PROJECTION-GUARD) |
| meta layer | 44 | **48** | +4 |
| **规则总数** | 147 | **151** | +4 |

## 3. L0 / SSOT / MOF 体系收敛

| 层级 | 文件 | 状态 |
|------|------|------|
| M0 capabilities | `.omo/_truth/registry/mof-capabilities.yaml` | + `p74_tools` 段(4 工具) |
| M0 version | `.omo/_truth/mof-version.yaml` | 0.0.107 → **0.0.108** |
| M1 instances | `projects/ecos/.../m1/governance/GAC-RULE-CR-P74-*.yaml` | 4 个**派生 + commit + push** |
| M2 SSOT | `.omo/_truth/registry/governance-checks.yaml` | 151 规则 |
| M3 meta-meta | `projects/ecos/.../m3.yaml` | + **GacRule** 子类型 (12 字段 schema) |

## 4. ADR / 文档 / Skill 三层冗余

| 层 | 文件 | 行数 |
|----|------|------|
| ADR | `.omo/_knowledge/decisions/0130-p74-workflow-solidification.md` | 167 |
| Pattern | `.omo/_knowledge/patterns/p74-workflow-solidification-pattern.md` | 9 节 |
| Standard | `.omo/standards/p74-solidification-contract.md` | 9 节 (含 decision tree) |
| Skill | `.agents/skills/workflow-silence-detection/SKILL.md` | 116 |

## 5. 三类 P71 鸿沟 — 常态化拦截

| P71 类别 | P74 拦截机制 | 触发入口 |
|----------|------------|---------|
| 类 A (路径错位) | `CR-P74-STATE-PROJECTION-GUARD` + `omo-state-projection-guard.py` | 任何改 `runtime-projections.yaml` 的 PR |
| 类 B (工具未接) | `CR-P74-RUNTIME-STAMP-POLICY` + `omo-runtime-stamp-policy.py` | 任何改 `runtime/**` 的 PR |
| 类 C (僵尸 run) | `CR-P74-WORKFLOW-SILENCE` + `p74_solidification_report` | `agent-workflow compliance` |

## 6. 验证

- `gac-validate.py --gate`: 0 error 0 warning
- `gac-drift.py`: 0 drift
- `make gac-local-gate`: **PASS (26/26 ALL GREEN)**
- `mof-schema-validate.py`: ok
- `gac-m1-sync.py --dry-run`: 0 drift(M3 + M1 + SSOT 完整同步)
- `governance-convergence-lint.py`: 0 ERROR
- `pytest tests/test_agent_workflow.py`: **31/31 PASS**
- `agent-workflow compliance` P74: 1 真 warn/12(`c2g-spec-ingress` 治理信号)

## 7. 长期维护入口

### 7.1 任何 agent 启动时
1. `bootstrap` → 报告 P74 健康
2. `agent-workwork compliance` → 看 `p74_solidification` 段
3. 如有 warn → 读 `.omo/standards/p74-solidification-contract.md` §3 decision tree

### 7.2 任何 PR 触发
- 改 `agent-workflows.yaml` → 触发 `agent-workflow-lint` + 相关 diff_checks
- 改 `bin/agent-workflow.py` → 触发 P74 报告路径
- 改 `runtime-projections.yaml` → 触发 `omo-state-projection-guard`
- 改 `runtime/**` → 触发 `omo-runtime-stamp-policy`

### 7.3 观察期
- 阶段 6+ (observability 阶段): omo state sync 派生 P74 报告进 `.omo/state/runtime/health.yaml`
- 阶段 7+ (后续 P 阶段): 接 cockpit compass 视图 + 告警

## 8. 已知真 warn(c2g-spec-ingress)

`c2g-spec-ingress` workflow 30d 内 0 触发, 是 A2 类沉默(运行层沉默)。
**预期行为**: 该 workflow 仅在外部 spec 触发(BMAD/OpenSpec/pitch)时使用, 不强制人工 start。
**下次触发**: 通过 `c2g bet <pitch.md>` 或 `cockpit compass bet <pitch.md>` 入治理。

## 9. 与既有 P 系列关系

- **P71** (baseline-recovery): 一次性 5 阶段鸿沟修复
- **P72** (follow-up-completion): 阶段路线图执行守门
- **P73** (truth-driven-engineering): SSOT 驱动
- **P74** (workflow-solidification): 常态化机制

P74 是 P71 治本后的**治未病**层, 把 P71 的发现沉淀为 SSOT 层的强制机制。

## 10. 后续待办 (非本 PR 范围)

| 任务 | 优先级 | 依赖 |
|------|--------|------|
| omo state sync 接 P74 派生 (`.omo/state/runtime/health.yaml` 新增 p74 段) | P2 | observability 阶段 |
| cockpit compass 加 P74 视图 | P3 | cockpit entry 扩展 |
| KOS 索引 ADR-0130 + pattern/standard | P3 | kos 知识图谱扩展 |
| 阶段 6+ cron: 每周 P74 报告 + 趋势 | P2 | 触发流程, 防 silent 累积 |

💘 Generated with Crush

Assisted-by: Crush:MiniMax-M3
