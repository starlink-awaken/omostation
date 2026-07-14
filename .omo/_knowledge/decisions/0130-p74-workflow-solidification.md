---
status: active
lifecycle: architecture
owner: governance-team
last-reviewed: 2026-07-03
related:
  - 0128-state-generation-concurrency.md
  - 0129-state-projection-plane-phase3.md
  - ../../standards/p74-solidification-contract.md
  - ../patterns/p74-workflow-solidification-pattern.md
  - ../../_truth/registry/agent-workflows.yaml
  - ../../_truth/registry/mof-capabilities.yaml
  - ../../../projects/ecos/src/ecos/ssot/mof/m3.yaml#GacRule
  - ../../../projects/ecos/src/ecos/ssot/mof/m1/governance/GAC-RULE-CR-P74-STATE-PROJECTION-GUARD.yaml
  - ../../../projects/ecos/src/ecos/ssot/mof/m1/governance/GAC-RULE-CR-P74-RUNTIME-STAMP-POLICY.yaml
  - ../../../projects/ecos/src/ecos/ssot/mof/m1/governance/GAC-RULE-CR-P74-WORKFLOW-SILENCE.yaml
  - ../../../projects/ecos/src/ecos/ssot/mof/m1/governance/GAC-RULE-CR-P74-WORKFLOW-SUGGEST.yaml
---

# ADR-0130: P74 Workflow Solidification — 常态化工作流沉默治理

## 1. 背景与问题定位

### 1.1 观察事实

`agent-workflows.yaml::workflows` 登记 N 个 workflow,但 `agent_workflow_start` 事件中 30 天内只有 `project-code-change` 真正触发(`bootstrap` + `status` 报告)。其余 workflow 都"声明存在但沉默"。

### 1.2 与 P71 关系(声明/执行鸿沟)

P71 识别 3 类鸿沟:
- **类 A — 路径错位**:Git-ignored SSOT 声明在 X、实际写 Y。
- **类 B — 工具未接**:工具存在但 0 caller。
- **类 C — 僵尸 run**:失忆会话留下的 active run。

**P74 是 P71 的常态化扩展**:

| P71 类 | P74 对应 |
|--------|----------|
| 类 A(路径错位) | `omo-state-projection-guard` (CR-P74-STATE-PROJECTION-GUARD) |
| 类 B(工具未接) | `omo-runtime-stamp-policy` (CR-P74-RUNTIME-STAMP-POLICY) |
| 类 C(僵尸 run) | `p74_solidification_report` 内嵌 compliance (CR-P74-WORKFLOW-SILENCE) |

P71 是"一次性 5 阶段修复";P74 是"每次提交后自动验证,防复发"。

### 1.3 与 ADR-0128 / 0129 关系

- ADR-0128 解决了"状态生成并发"(单写者 broker)
- ADR-0129 解决了"运行时投影面分离"(canonical/legacy 分离)
- ADR-0130 解决"工作流维度治理"(沉默 workflow 检测 + 主动触发)

三者递进:0128 → 0129 → 0130 形成"状态面 → 投影面 → 治理面"的完整治理层。

## 2. 决策

### 2.1 决策 1:三层冗余的长期维护机制

| 层 | 机制 | 文件 |
|----|------|------|
| 检测层 | `bin/agent-workwork compliance --json` 输出 `p74_solidification` 段 | `bin/agent-workflow.py` |
| 规则层 | `governance-checks.yaml` 加 4 条 `CR-P74-STATE-PROJECTION-GUARD` / `CR-P74-RUNTIME-STAMP-POLICY` / `CR-P74-WORKFLOW-SILENCE` / `CR-P74-WORKFLOW-SUGGEST` 规则 | `.omo/_truth/registry/governance-checks.yaml` |
| 文档层 | pattern 抽象 + standards 操作契约 + skill 触发式引导 | `.omo/_knowledge/patterns/p74-*.md` + `.omo/standards/p74-*.md` + `.agents/skills/workflow-silence-detection/` |

**为何 3 层冗余**:
- 检测层保证"能跑出结果"(类 B 治本)
- 规则层保证"X1-X4 维度显式覆盖"(GaC 合规)
- 文档层保证"agent/人都能发现"(P73 truth-driven)

### 2.2 决策 2:沉默的两层定义(A1 + A2)

| 层 | 含义 | 处置 |
|----|------|------|
| **A1 检查层沉默** | workflow 路径无 `diff_checks` 触发 | 通过 `doctor_checks` 接入即可 |
| **A2 运行层沉默** | workflow 路径无 `agent_workflow_start` 事件 | 不强制触发;保持 "P74 设计正确的沉默" |

**A2 治标策略**:通过 `agent-workflow suggest --from-diff` advisory 引导。

### 2.3 决策 3:主动触发接 omo state sync

P74 报告通过 `omo state sync` 派生,产物进 `.omo/state/runtime/health.yaml`。任何 agent 读 SSOT 即知 P74 健康。

**为何不发明 cron**:
- omo state sync 已是单写者,加进去是既定流程扩展
- 避免元递归(防止"守护 watcher 自己 silent")

### 2.4 决策 4:命名收敛(omo- 前缀)

`bin/state-projection-guard.py` → `bin/gac/omo-state-projection-guard.py`
`bin/runtime-stamp-policy.py` → `bin/gac/omo-runtime-stamp-policy.py`

归类:OMO 治理域(`omo-` 前缀),符合 `.omo/standards/bin-tool-naming.md` 的命名空间约束。在 ADR-0115 Phase X 引用本 ADR。

**2026-07-07 更新**: 这两个工具已内化到 omo CLI:
- `bin/gac/omo-state-projection-guard.py` → `omo lint projection-guard`
- `bin/gac/omo-runtime-stamp-policy.py` → `omo lint stamp-policy`

原 bin/ 脚本保留作为 backward-compat wrapper。

## 3. 实施细节

### 3.1 文件清单

| 类型 | 路径 | 性质 |
|------|------|------|
| ADR | `.omo/_knowledge/decisions/0130-p74-workflow-solidification.md` | 本文件 |
| Pattern | `.omo/_knowledge/patterns/p74-workflow-solidification-pattern.md` | 抽象模式 |
| Standard | `.omo/standards/p74-solidification-contract.md` | 操作契约 |
| Skill | `.agents/skills/workflow-silence-detection/SKILL.md` | agent 触发入口 |
| SSOT | `.omo/_truth/registry/agent-workflows.yaml` (diff_checks + silent_workflow_policy) | 路由声明 |
| SSOT | `.omo/_truth/registry/runtime-projections.yaml` (state field) | 投影面状态 |
| Rule | `.omo/_truth/registry/governance-checks.yaml` (+4 P74 CR) | GaC 维度覆盖 |
| Tool | `projects/omo/src/omo/omo_lint_projection.py` | CR-P74-STATE-PROJECTION-GUARD 实现 |
| Tool | `projects/omo/src/omo/omo_lint_stamp.py` | CR-P74-RUNTIME-STAMP-POLICY 实现 |
| Tool | `bin/agent-workflow.py` (+ suggest + p74_solidification_report) | CR-P74-WORKFLOW-SILENCE 实现 |

### 3.2 关键约束

- **0 新增顶层 SSOT 文件**(已有 SSOT 文件扩展)
- **0 新增 executor**(`ci_gate` 已存在)
- **0 新增 cron**(复用 omo state sync)
- **0 违反 doc-ssot-contract**(全指针,无硬编码)
- **0 新增独立 watcher agent**(避免元递归)

## 4. 后果

### 4.1 正面

- P71 三类鸿沟有常态化拦截机制
- GaC X1 + X4 维度各 +1 覆盖
- agent / 人类都能通过 skill/INDEX 发现 P74
- omo state sync 派生机制扩展,无新基础设施

### 4.2 风险与缓解

| 风险 | 缓解 |
|------|------|
| omo state sync 改坏现有派生 | `--include-p74` flag 默认 off,observability 阶段验证 |
| suggest advisory 误报 | 仅 advisory,不影响 start 命令 |
| governance-checks.yaml 加 3 规则总数变 | `gac-validate` 自动验证;X1 +1, X4 +1 平衡 |
| P74 pattern 文档仍可能过期 | 全部指针到 SSOT;`last-reviewed` 字段强制刷新 |

### 4.3 与既有架构的兼容性

| 既有机制 | 接入方式 |
|---------|---------|
| `agent-workflow compliance` | 扩展输出 `p74_solidification` 段 |
| `gac-local-gate` 26 checks | 复用 `ci_gate` executor,不增 gate 数量 |
| `omo state sync` 派生 | P74 报告作为新派生字段 |
| `bootstrap` 命令 | 可加 P74 摘要(可选,见 phase 6) |
| `INDEX.md` (knowledge / registry) | 自动反映新 ADR/standard |

## 5. 验证标准

PR 合并前必须满足:

1. `gac-validate.py --gate` 0 error 0 warning
2. `gac-drift.py` 0 drift
3. `make gac-local-gate` PASS (≥ 26 checks)
4. `pytest tests/test_agent_workflow.py` 31/31 PASS
5. `agent-workflow compliance --json` 输出 `p74_solidification` 段
6. `bin/gac/omo-state-projection-guard.py` 4 projections OK
7. `bin/gac/omo-runtime-stamp-policy.py` 0 orphan

## 6. 后续(可选,observability 阶段再考虑)

- `bootstrap` 命令加 P74 摘要
- `cockpit compass` 加 P74 视图
- KOS 知识图谱索引 ADR-0130 + 相关 pattern/standard

## 7. ADR 链

- 上游:ADR-0106 (GaC 总决策)
- 上游:ADR-0115 (bin 命名)
- 上游:ADR-0128 (状态生成并发)
- 上游:ADR-0129 (运行时投影面)
- **本 ADR(ADR-0130)**
- 下游:无