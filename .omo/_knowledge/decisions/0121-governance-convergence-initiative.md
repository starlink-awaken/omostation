---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-07-02
---

# ADR-0121: Governance Convergence Special Initiative (GCSI) — 治理收敛专项

- **Status**: PROPOSED
- **Date**: 2026-07-02
- **Authors**: governance-team (基于 ADR-0119/0120 + P71 + 系统性健康审计)
- **Supersedes**: 无 (扩展 ADR-0119, 补充 ADR-0120 遗留项)
- **Related**:
  - [ADR-0119: 系统性优化 Roadmap](0119-systemic-optimization-roadmap-2026h2.md) (S0/S1/S2/S3)
  - [ADR-0120: Runtime 健康监控语义修正](0120-runtime-health-semantics-fix.md) (Layer 3 GaC 规则未注册)
  - [P71 Baseline Recovery Pattern](../patterns/p71-baseline-recovery-pattern.md) (Class D 扩展)
  - [系统性健康审计 2026-07-01](../audits/2026-07-01-systemic-health-audit.md) (8 维度 7.2/10)
  - [P0 Baseline Recovery Closeout](../audits/2026-07-02-p0-baseline-recovery-closeout.md) (反馈回路停摆 29h)
  - [ENGINEERING-OPTIMIZATION-ROADMAP](../../../docs/ENGINEERING-OPTIMIZATION-ROADMAP.md)

## Context and Problem Statement

### 现状: 治理碎片化与收敛缺口

2026-07-01 系统性健康审计 (7.2/10) + 2026-07-02 P0 baseline recovery + ADR-0120 runtime health fix
暴露了一个深层模式: **治理工具和规则不断产生, 但缺乏收敛机制, 导致"声明绿/执行红"持续复发**。

具体表现 (5 类碎片化):

#### 碎片 1: 规则注册与执行脱节
- ADR-0120 Layer 3.0 定义了 3 条 GaC 规则 (CR-X1-FRESHNESS-SEMANTIC 等), **但未注册到 governance-checks.yaml**
- ADR-0115 Phase 3 计划接入 9 个 check-* 工具到 gac-local-gate, **但未执行**
- P71 Phase 4 要求"每根因→1 条 GaC 规则", 但 P0 recovery 新增的 4 条规则中, **2 条待加** (CR-L0-SSOT-PATH-NORM, CR-META-CI-SKIP-MATRIX)

#### 碎片 2: 健康分数计算不可信
- `health_score: 80` (system.yaml) 与 `evidence_health_score: 78.9` (evidence-smoke.py) **两套独立计算, 互不同步**
- health_score 的 `service_online_ratio: 0.33` 在 ADR-0120 修复前是错的 (误报导致), 修复后仍为 0.33 (未重新计算)
- 8 个 governance-evolution initiative **全部 active 但进度为空 (?%)**

#### 碎片 3: 反馈回路停摆
- evidence-smoke.py 报告: `回路存活: False (29.0h 停摆)`
- 治理最后一次运行: `2026-06-30T23:01:30Z` (超过 29 小时前)
- 没有自动机制在治理操作后触发 evidence-smoke 验证

#### 碎片 4: SSOT 多源未收敛
| 事实类型 | 来源 1 | 来源 2 | 冲突 |
|----------|--------|--------|------|
| 服务健康 | system_health.yaml | 实时 launchctl/lsof | ADR-0120 修复前不一致 |
| 端口注册 | port-registry.yaml | matrix.yaml port 字段 | agora-gateway:7422 矛盾 (已修) |
| 规则数 | governance-checks.yaml | AGENTS.md gac.rules_count | 需手动同步, 易漂移 |
| 健康分数 | system.yaml health_score | evidence-smoke score | 两套算法, 无对账 |

#### 碎片 5: 工具覆盖盲区
- bin/ 85 个工具仅 9% 有测试 (ADR-0119 S2-1~S2-3 未执行)
- 新增的 `matrix-consistency-lint.py` **无测试**
- `evidence-smoke.py` 无测试, 其输出的 `evidence_health_score` 是治理决策依据但无回归保护

### 根因: 缺乏"治理收敛层"

当前治理体系有"产生"机制 (ADR/pattern/rule/standard 不断创建) 和"执行"机制 (gac-local-gate/CI/pre-commit),
但缺少**收敛层** — 即确保声明被注册、注册被执行、执行被验证、验证反馈回声明的闭环。

```
当前 (开环):
  产生 → 执行 → (断裂) → 产生 → 执行 → ...
                    ↑
              声明/执行鸿沟在此产生

目标 (闭环):
  产生 → 注册 → 执行 → 验证 → 反馈 → 产生
    ↑                                    │
    └────────── 收敛层 ──────────────────┘
```

## Decision Drivers

* 治理工具和规则的"声明绿/执行红"必须被自动检测, 不能依赖人工发现
* health_score 必须单一可信源, 不能两套算法各算各的
* 反馈回路必须自动运转, 不能 29h 停摆无人知
* SSOT 多源冲突必须有 lint 拦截 (matrix-consistency-lint 是好的开始, 但只覆盖了 1 个维度)
* 与 ADR-0119 S2 路线对齐, 不另起炉灶
* 工时可控 (2-3 周), 不阻塞 VISION-ROADMAP 产品迭代

## Considered Options

### 方案 A: 逐项修复 (碎片化应对)

按碎片 1-5 逐个修, 每个独立 PR。

**优点**: 每个 PR 小, 易 review
**缺点**: 治标不治本 — 修了碎片 1 (规则注册), 下次新增规则还会忘记注册; 修了碎片 3 (回路停摆), 但回路本身的设计未改

### 方案 B: Governance Convergence Special Initiative (GCSI) — 推荐

建立"治理收敛层", 4 个收敛维度各自闭环, 统一专项管理:

1. **Rule Convergence** (规则收敛): 规则定义→注册→执行→drift 检测, 自动闭环
2. **Score Convergence** (分数收敛): health_score 单一 SSOT + evidence-smoke 对账
3. **Loop Convergence** (回路收敛): 治理操作→自动触发 evidence-smoke→反馈→自动重评
4. **SSOT Convergence** (数据收敛): 多源事实对账 lint, 覆盖所有已知碎片

**优点**: 根治"声明/执行鸿沟"复发; 与 P71 Class D (语义错配) 对齐; 统一管理避免碎片化
**缺点**: 跨多子模块 + 主仓, 需要协调; 工时 ~2-3 周

### 方案 C: 等待 ADR-0119 S2 自然覆盖

ADR-0119 S2 已定义 state-freshness-check + initiative 进度填充, 等 S2 执行时一并修。

**优点**: 零额外规划
**缺点**: S2 未覆盖规则注册闭环、分数对账、SSOT 多源冲突; S2 工时 3-4 周, 执行时才发现缺口会延期

## Decision Outcome

**Chosen option: "方案 B — GCSI 治理收敛专项", because 根治碎片化复发且与 ADR-0119 互补而非冲突。**

### Consequences

* Good: "声明/执行鸿沟"有自动检测; health_score 单一可信; 反馈回路自动运转; SSOT 冲突有 lint 拦截
* Bad: 4 个收敛维度需跨子模块协调; 部分改动涉及 omo state schema (已在 ADR-0120 改过一次)

### Confirmation

1. 新增 GaC 规则后 `gac-drift` 自动检测是否注册 (Rule Convergence)
2. `evidence-smoke.py` 与 `system.yaml` health_score 差异 < 5 分 (Score Convergence)
3. 治理操作后 evidence-smoke 自动触发, 回路存活: True (Loop Convergence)
4. `bin/governance-convergence-lint.py` 0 ERROR (SSOT Convergence, 覆盖 4 维度)

---

## 实施方案

### 维度 1: Rule Convergence (规则收敛, P0, ~4h)

> **目标**: 规则定义→注册→执行→drift 检测自动闭环。新增规则必须注册, 否则 gac-drift 报红。

#### 1.1 补注册 ADR-0120 定义的 3 条规则

**文件**: `.omo/_truth/registry/governance-checks.yaml`

```yaml
# ADR-0120 Layer 3.0 — 3 条规则 (此前定义但未注册)
- id: CR-X1-FRESHNESS-SEMANTIC
  dimension: X1
  layer: meta
  check_type: audit_chain
  severity: error
  description: "freshness_seconds producer/consumer 语义一致性"
  executor: bin/governance-convergence-lint.py --rule freshness-semantic

- id: CR-L0-MATRIX-PORT-CONSISTENCY
  dimension: L0
  layer: meta
  check_type: ssot_lint
  severity: warn
  description: "matrix.yaml port 与 port-registry.yaml 一致性"
  executor: bin/matrix-consistency-lint.py

- id: CR-L0-MATRIX-LAUNCHD-COVERAGE
  dimension: L0
  layer: meta
  check_type: ssot_lint
  severity: error
  description: "daemon 类型服务必须有 launchd_label 或 docker_container"
  executor: bin/matrix-consistency-lint.py
```

#### 1.2 补注册 P71 遗留的 2 条规则

```yaml
# P71 Phase 4 — 2 条待加规则
- id: CR-L0-SSOT-PATH-NORM
  dimension: L0
  layer: meta
  check_type: ssot_lint
  severity: error
  description: "SSOT 路径与 broker 写入路径一致 (防 dependency-baseline 类路径错位)"
  executor: bin/governance-convergence-lint.py --rule ssot-path-norm

- id: CR-META-CI-SKIP-MATRIX
  dimension: X4
  layer: meta
  check_type: registry_integrity
  severity: warn
  description: "CI_SKIP_CHECKS ∪ CI_ONLY_CHECKS 覆盖所有 CI 不适用项"
  executor: bin/governance-convergence-lint.py --rule ci-skip-matrix
```

#### 1.3 规则注册闭环 lint

**文件**: `bin/governance-convergence-lint.py` (新建, GCSI 核心工具)

```python
def check_rule_registration():
    """R-GOV-1: 所有 ADR 中定义的 CR-* 规则必须在 governance-checks.yaml 注册."""
    # 扫描 .omo/_knowledge/decisions/*.md 中引用的 CR-* 规则 ID
    # 对比 governance-checks.yaml 中已注册的规则
    # 未注册的 → ERROR
```

### 维度 2: Score Convergence (分数收敛, P1, ~3h)

> **目标**: health_score 单一可信源, evidence-smoke 与 system.yaml 对账。

#### 2.1 健康分数统一计算

**文件**: `projects/omo/src/omo/omo_state_schema.py`

当前 system.yaml 的 `health_score: 80` 来自 `compass_radar_composite` (外部源), 与 evidence-smoke 的 78.9 独立计算。

**方案**: 在 `_sync_system_yaml_runtime_summary` (scheduler.py) 中, 调用 evidence-smoke 的分数作为 `health_score_evidence` 字段, 与 `health_score` 并列输出。当两者差异 > 5 分时, 在 system.yaml 标记 `health_score_divergence: true`。

```python
# scheduler.py _sync_system_yaml_runtime_summary
data["health_score_evidence"] = evidence_score  # from evidence-smoke
data["health_score_divergence"] = abs(data.get("health_score", 0) - evidence_score) > 5
```

#### 2.2 分数对账 lint

**文件**: `bin/governance-convergence-lint.py`

```python
def check_score_convergence():
    """R-GOV-2: health_score 与 health_score_evidence 差异 < 5."""
    # 读 system.yaml 的 health_score 和 health_score_evidence
    # 差异 > 5 → WARN
```

#### 2.3 initiative 进度填充 (ADR-0119 S2-7 对齐)

**文件**: `.omo/_truth/registry/governance-evolution-roadmap.yaml`

8 个 initiative 全部 active 但进度 ?%。每个补充 `progress` 和 `last_evaluated` 字段。

### 维度 3: Loop Convergence (回路收敛, P1, ~3h)

> **目标**: 治理操作后自动触发 evidence-smoke, 反馈回路不再停摆。

#### 3.1 post-closeout 自动触发

**文件**: `bin/agent-workflow.py` (closeout 命令)

在 `closeout` 成功后, 自动运行 `evidence-smoke.py` 并更新 `system.yaml` 的反馈回路时间戳。

```python
# agent-workflow.py closeout 后
subprocess.run(["python3", "bin/evidence-smoke.py", "--quiet"], ...)
# 更新 system.yaml: governance_feedback_last_run = now
```

#### 3.2 回路存活检测 lint

**文件**: `bin/governance-convergence-lint.py`

```python
def check_feedback_loop():
    """R-GOV-3: 治理反馈回路存活 (最后运行 < 6h)."""
    # 读 system.yaml 的 governance_feedback_last_run
    # 超过 6h → WARN; 超过 24h → ERROR
```

#### 3.3 cron-service 定时触发 (ADR-0119 S2-5 对齐)

在 cron-service 的定时任务中增加 evidence-smoke 定期运行 (每 4h), 确保即使无 closeout 也能触发回路。

### 维度 4: SSOT Convergence (数据收敛, P2, ~4h)

> **目标**: 多源事实对账 lint, 覆盖所有已知碎片。

#### 4.1 governance-convergence-lint.py 完整实现

**文件**: `bin/governance-convergence-lint.py` (新建, 统一收敛 lint)

整合 matrix-consistency-lint + 新增 4 维度对账:

| 规则 | 校验内容 | 数据源 A | 数据源 B |
|------|----------|----------|----------|
| R-GOV-1 | ADR 引用的 CR-* 规则已注册 | decisions/*.md | governance-checks.yaml |
| R-GOV-2 | health_score 与 evidence 对账 | system.yaml | evidence-smoke |
| R-GOV-3 | 反馈回路存活 | system.yaml timestamp | now() |
| R-GOV-4 | 端口注册一致 | matrix.yaml port | port-registry.yaml |
| R-GOV-5 | gac.rules_count 与实际一致 | AGENTS.md | governance-checks.yaml count |
| R-GOV-6 | 服务类型与 launcher 一致 | matrix.yaml type+launchd_label | matrix-consistency-lint R1 |

#### 4.2 纳入 GaC gate

**文件**: `bin/gac-local-gate.py`

```python
CHECKS = (
    ...
    # GCSI: 治理收敛 lint (ADR-0121)
    ("governance-convergence", ["bin/governance-convergence-lint.py"]),
)
```

### 测试覆盖 (ADR-0119 S2 对齐)

| 工具 | 测试文件 | 覆盖路径 |
|------|----------|----------|
| matrix-consistency-lint.py | tests/test_matrix_consistency.py | R1-R5 全覆盖 |
| governance-convergence-lint.py | tests/test_governance_convergence.py | R-GOV-1~6 全覆盖 |
| evidence-smoke.py | tests/test_evidence_smoke.py | 分数计算 + BOS resolve |

---

## 执行顺序

```
维度 1 (P0, Rule Convergence, ~4h)
  ├─ 1.1 注册 ADR-0120 的 3 条规则
  ├─ 1.2 注册 P71 的 2 条规则
  ├─ 1.3 新建 governance-convergence-lint.py (R-GOV-1)
  └─ gac-validate --gate (139→144 规则, 0 error)
       │
       ▼
维度 2 (P1, Score Convergence, ~3h)
  ├─ 2.1 scheduler.py: health_score_evidence + divergence 标记
  ├─ 2.2 governance-convergence-lint: R-GOV-2 分数对账
  └─ 2.3 initiative 进度填充 (8 个)
       │
       ▼
维度 3 (P1, Loop Convergence, ~3h)
  ├─ 3.1 agent-workflow.py closeout 后触发 evidence-smoke
  ├─ 3.2 governance-convergence-lint: R-GOV-3 回路存活
  └─ 3.3 cron-service 定时 evidence-smoke (每 4h)
       │
       ▼
维度 4 (P2, SSOT Convergence, ~4h)
  ├─ 4.1 governance-convergence-lint: R-GOV-4~6 多源对账
  ├─ 4.2 gac-local-gate 接入 governance-convergence
  └─ 测试覆盖 (3 个测试文件)
       │
       ▼
验证: gac-local-gate 14/14 + evidence-smoke 回路存活 + convergence-lint 0 ERROR
```

## 验证清单

| # | 验证项 | 命令 | 预期 |
|---|--------|------|------|
| V1 | GaC 规则数 | `gac-validate --gate` | 144 (139+5), 0 error |
| V2 | 规则注册闭环 | `governance-convergence-lint.py --rule registration` | 0 ERROR (ADR 引用的 CR-* 全注册) |
| V3 | 分数对账 | `governance-convergence-lint.py --rule score` | health_score 与 evidence 差异 < 5 |
| V4 | 回路存活 | `governance-convergence-lint.py --rule loop` | 最后运行 < 6h |
| V5 | SSOT 一致 | `governance-convergence-lint.py` | 0 ERROR, ≤3 WARN |
| V6 | GaC gate | `make gac-local-gate` | 14/14 PASS (含 governance-convergence) |
| V7 | evidence-smoke | `python3 bin/evidence-smoke.py` | 回路存活: True |
| V8 | initiative 进度 | `governance-evolution.py status --json` | 8 个 initiative 有 progress % |
| V9 | 测试 | `pytest tests/test_governance_convergence.py tests/test_matrix_consistency.py` | 全绿 |

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|------|------|------|
| governance-checks.yaml 规则注册格式错 | gac-validate --gate 验证 | revert governance-checks.yaml |
| scheduler.py 分数对账引入新 bug | 保留现有 health_score 不变, 仅新增 health_score_evidence | revert scheduler.py |
| cron-service 定时 evidence-smoke 增加负载 | 4h 间隔, evidence-smoke < 3s | 移除 cron job |
| convergence-lint 误报 | WARN 不阻断, 仅 ERROR 阻断 | 从 gac-local-gate 移除 |

## 与现有 Roadmap 的关系

| GCSI 维度 | ADR-0119 | P71 | ADR-0120 |
|-----------|----------|-----|----------|
| 维度 1 Rule | S2-1~S2-3 (测试覆盖) | Phase 4 (规则化) | Layer 3.0 (3 条规则未注册) |
| 维度 2 Score | S2-7 (initiative 进度) | — | — |
| 维度 3 Loop | S2-5/S2-6 (freshness check) | Phase 5 (元治理递归) | — |
| 维度 4 SSOT | — | Phase 2 (SSOT 路径) | Layer 3.1 (matrix-consistency-lint) |

GCSI 不替代 ADR-0119 S2, 而是补充其未覆盖的"收敛层" — 确保规则注册闭环、分数对账、回路自动运转。

## References

- [ADR-0119: 系统性优化 Roadmap](0119-systemic-optimization-roadmap-2026h2.md)
- [ADR-0120: Runtime 健康监控语义修正](0120-runtime-health-semantics-fix.md) (Layer 3.0 GaC 规则待注册)
- [ADR-0115: bin/ 治理工具集重整](0115-bin-governance-rationalize.md) (Phase 3 待执行)
- [P71 Baseline Recovery Pattern](../patterns/p71-baseline-recovery-pattern.md)
- [系统性健康审计](../audits/2026-07-01-systemic-health-audit.md) (7.2/10, A+B+D 短板)
- [P0 Baseline Recovery Closeout](../audits/2026-07-02-p0-baseline-recovery-closeout.md) (回路停摆 29h)
- [ENGINEERING-OPTIMIZATION-ROADMAP](../../../docs/ENGINEERING-OPTIMIZATION-ROADMAP.md)
- [governance-checks.yaml](../../_truth/registry/governance-checks.yaml)
- [governance-evolution-roadmap.yaml](../../_truth/registry/governance-evolution-roadmap.yaml)
