---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# P60 — P43-P59 治理方法论内化提案 (L/X/M 三层 + Workflow Skills)

**日期**：2026-06-23
**作者**：omostation 治理 Agent
**基础**：P43-P59 系统性深度复盘
**目标**：把方法论沉淀内化为机器可执行规则 + 决策工作流

---

## 0. 落地设计原则

### 0.1 三层架构对齐

```
┌─────────────────────────────────────────────────────────┐
│ L4 自我层 (l4-kernel)                                     │
│   → 决策智能 (KEMS 六面 / Cards Plane / DomainHealth)      │
├─────────────────────────────────────────────────────────┤
│ L3 入口层 (cockpit) + L2 引擎面 (omo)                      │
│   → 命令执行 (omo CLI / omo lint / cockpit CLI)           │
├─────────────────────────────────────────────────────────┤
│ L1 运行时 + L0 协议 (ecos)                                 │
│   → 强制约束 (L0-constraints / X1-X4 rules)                │
├─────────────────────────────────────────────────────────┤
│ X 横切框架 (model-driven + c2g + bus + omo-debt)          │
│   → 模型驱动 + 战略入口 + 事件总线                         │
├─────────────────────────────────────────────────────────┤
│ M0 模型层 (model-driven)                                  │
│   → M3 标准 + M2 schema + M1 实例 三层桥接                │
└─────────────────────────────────────────────────────────┘
```

### 0.2 内化的两条路径

```
路径 A: 规则内化 (确定性)
├─ L0 约束 (强制)
├─ X1-X4 规则 (强制 + 软引导)
└─ CI/pre-commit 钩子 (强制执行)

路径 B: 智能内化 (启发式)
├─ L4-kernel capability (可注册)
├─ Workflow Skill (可触发)
└─ Agent prompt 注入 (决策引导)
```

---

## 1. 落地清单 (12 项 · 4 类别)

### 类别 1：L0 强制约束增量 (5 项)

把 P43-P59 沉淀的硬规则写入 `L0-constraints.yaml`:

#### L0-CR-GOV-CLOSED-LOOP-01 (新)

```yaml
- id: CR-GOV-CLOSED-LOOP-01
  name: 强制闭环原则 (mandatory commit)
  description: |
    P59 暴露的核心问题: mof-version 记录后未 git commit, 导致知识萃取引擎失效。
    规则: 任何 mof-version bump 必须伴随至少 1 个 git commit 在同一会话内提交。
    检测: post-commit hook 触发后 mof-version 增量, 反向校验 git log。
  severity: error
  enforcement: pre-commit + cron (5min)
  introduced_by: P60
```

#### L0-CR-GOV-FRONTMATTER-SCHEMA-01 (新)

```yaml
- id: CR-GOV-FRONTMATTER-SCHEMA-01
  name: frontmatter 4 字段契约
  description: |
    .omo/_knowledge/ 任何 .md 必须含 status + lifecycle + owner + last-reviewed 4 字段。
    P56 100% 覆盖是基础, 新文件必须达标。
  severity: warn
  enforcement: omo lint doc-lifecycle
  introduced_by: P56
```

#### L0-CR-GOV-DOC-CATEGORY-01 (新)

```yaml
- id: CR-GOV-DOC-CATEGORY-01
  name: 文档 4 类生命周期 (ssot/contract/pattern/history)
  description: |
    .omo/ 文档必须按 4 类分类, status 必填 (active/deprecated/archived/experimental)。
    历史文档 status: archived + lifecycle: history 必带。
  severity: warn
  enforcement: omo lint doc-lifecycle
  introduced_by: P45
```

#### L0-CR-GOV-DIMENSION-SATURATION-01 (新)

```yaml
- id: CR-GOV-DIMENSION-SATURATION-01
  name: linter 维度饱和预警
  description: |
    当 omo lint 维度 ≥ 15 时, 新增能力应以独立 bin 工具形式实现, 不得再增 linter 子命令。
    P57 ADR-0053 记录此铁律。
  severity: warn
  enforcement: linter-developer-guide
  introduced_by: P57
```

#### L0-CR-GOV-COMMIT-FREQUENCY-01 (新)

```yaml
- id: CR-GOV-COMMIT-FREQUENCY-01
  name: commit 频率与文件改动同步
  description: |
    工作 tree 累积未提交 > 100 文件触发警告, > 500 触发 error。
    防止 P59 类失闭环事件再次发生。
  severity: warn (100) / error (500)
  enforcement: pre-commit + health check
  introduced_by: P59
```

---

### 类别 2：X1-X4 规则新增 (3 项)

#### X1-AUD-COMMIT-LOOP (新)

```yaml
rule_id: X1-AUD-COMMIT-LOOP
title: 强制闭环审计
target: .omo/_truth/mof-version.yaml
freshness:
  mechanism: git-commit-mof-version-correlation
  threshold_days: 1
  action: escalate
notes: |
  mof-version.yaml 中每条 history entry 必须有对应的 git commit。
  P59 治理闭环修复后, 此规则持续维护。
```

#### X2-FRESH-COMMIT-FATIGUE (新)

```yaml
rule_id: X2-FRESH-COMMIT-FATIGUE
title: 工作 tree 累积预警
target: .omo/_knowledge/
freshness:
  mechanism: git-working-tree-accumulation
  threshold_days: 1
  action: warn (100 files) / escalate (500 files)
notes: |
  检测 .omo/_knowledge/ 累积未提交修改, 防止 P59 失闭环。
```

#### X4-CONS-DRIFT-VS-GOVERNANCE (新)

```yaml
rule_id: X4-CONS-DRIFT-VS-GOVERNANCE
title: 漂移 vs 治理评分一致性
target: bin/mof-drift + omo governance
freshness:
  mechanism: cross-tool-consistency
  threshold_days: 1
  action: warn
notes: |
  mof-drift LOW 计数应与 governance score 反向相关 (drift 越少, 治理越好)。
  偏离时报警, 可能存在统计口径不一致。
```

---

### 类别 3：M0 model-driven 桥接 (3 项)

#### M3-STAGE-GOVERNANCE-MAINTENANCE (新)

```python
# projects/model-driven/src/model_driven/mof/m3_extended.py
# P60: 新增阶段定义 — 治理维护 (GOVERNANCE_MAINTENANCE)

STANDARD_STAGES = {
    ...
    "GOVERNANCE_MAINTENANCE": {
        "id": 8,  # 紧接 P57 SELF_CORRECTION
        "name": "Governance Maintenance",
        "description": "持续治理维护, 含 frontmatter / drift / 闭环审计",
        "objectives": [
            "维护 frontmatter 覆盖率 ≥ 95%",
            "监控 mof-drift LOW 维度 ≤ 5",
            "强制 git commit 与 mof-version 同步",
        ],
        "gates": [
            "GATE-GOV-FRONTMATTER-COVERAGE",
            "GATE-GOV-DRIFT-LOW-COUNT",
            "GATE-GOV-COMMIT-CLOSURE",
        ],
        "duration_days": 7,
        "owner_role": "governance-agent",
    },
}
```

#### M2-SCHEMA-GOVERNANCE-DECISION (新)

```yaml
# projects/ecos/src/ecos/ssot/mof/m2/governance_decision.yaml
type: governance_decision
schema:
  required:
    - decision_id  # GOVD-YYYY-NNN
    - decision_type  # dimension_saturation / commit_closure / category_assignment
    - rationale  # 必填, 含 WHY/WHAT/NEXT 3 段
    - alternatives_considered  # 至少 1 项
    - consequences  # positive / negative / neutral
    - evidence  # 引用 .omo/_knowledge/audits/...
  state_machine:
    - proposed
    - accepted
    - superseded
    - deprecated
  validation_rules:
    - "rationale 必含 '## WHY' '## WHAT' '## NEXT' 3 段标题"
    - "alternatives_considered 至少含 1 个 rejected 选项"
```

#### M1-实例 GOVERNANCE-MAINTENANCE-PHASE (新)

```yaml
# projects/ecos/src/ecos/ssot/mof/m1/governance/GOVERNANCE-MAINTENANCE-PHASE.yaml
id: GOVERNANCE-MAINTENANCE-PHASE
type: governance_phase
m3_parent: GOVERNANCE_MAINTENANCE
status: active
phase_range: P60-P99
description: |
  P60+ 持续治理维护阶段, 沿用 P43-P59 沉淀方法论。
  核心机制: RISE 循环 + 维度饱和律 + 闭环纪律。
gates:
  - id: GATE-GOV-FRONTMATTER-COVERAGE
    threshold: "knowledge/ frontmatter ≥ 95%"
    check_command: "omo lint doc-lifecycle"
  - id: GATE-GOV-DRIFT-LOW-COUNT
    threshold: "mof-drift LOW ≤ 5"
    check_command: "bin/mof-drift"
  - id: GATE-GOV-COMMIT-CLOSURE
    threshold: "git status --short | wc -l ≤ 50"
    check_command: "git status --short"
evidence:
  - "P59 收口: governance 100 A+ 持续"
  - "P56 收口: frontmatter 689/689 = 100%"
```

---

### 类别 4：Workflow Skills (1 个, 复合)

#### Skill: governance-phase-orchestrator

```yaml
skill_name: governance-phase-orchestrator
trigger_keywords:
  - "治理"
  - "收敛"
  - "P 阶段"
  - "phase closure"
  - "governance cycle"
description: |
  自动化 P 阶段治理流程: 调研 → 方案 → 执行 → 收口。
  适用场景: agent 收到 governance-related 任务时, 自动激活。

workflows:
  - name: rise-cycle
    steps:
      - name: R (Research)
        actions:
          - "git status --short | wc -l  # 检查闭环"
          - "bin/mof-drift  # 看 LOW 维度"
          - "omo governance  # 看总分"
          - "omo lint doc-lifecycle  # 看 frontmatter"
        output: governance-snapshot.yaml

      - name: I (Investigate)
        actions:
          - "分析 snapshot 中异常项"
          - "查 .omo/_knowledge/decisions/ ADR 历史"
          - "评估影响范围与优先级"
        output: investigation-report.md

      - name: S (Strategize)
        actions:
          - "列出 ≥3 个可选方案 (选项 A/B/C)"
          - "评估每个方案的风险 / 收益 / 工作量"
          - "选择最低风险最高价值方案"
        output: strategy-decision.md (含 GOVD- 编号)

      - name: E (Execute)
        actions:
          - "执行批量兜底 (frontmatter / status 转换)"
          - "写 README 标注职责"
          - "更新 ADR INDEX"
          - "bin/mof-version record"
          - "git add . && git commit -m '...'"
        output: phase-closure artifacts

      - name: C (Closeout)
        actions:
          - "写收口报告到 .omo/_knowledge/audits/"
          - "omo governance 验证 100 A+"
          - "更新 TodoList"
        output: 收口报告 + mof-version bump

  - name: commit-closure-recovery
    description: "P59 类失闭环事件的自动恢复流程"
    trigger: "git status --short | wc -l > 100"
    steps:
      - "评估改动是否分多个 phase 可分批提交"
      - "按 phase 维度 git add + commit"
      - "每个 commit 必含语义描述"
      - "最后 commit 写收口报告"
```

---

## 2. L4 Kernel 集成 (Capability 注册)

### 2.1 新增 capability

```python
# projects/l4-kernel/src/l4_kernel/registry.py

# P60 新增 6 个 capability
governance_capabilities = {
    "gov.frontmatter_audit": {
        "domain": "governance",
        "kems_faces": ["document", "evidence", "metrics"],
        "handler": "omo_lint.doc_lifecycle",
        "trigger": "omo lint doc-lifecycle",
    },
    "gov.drift_monitor": {
        "domain": "governance",
        "kems_faces": ["metrics", "signal"],
        "handler": "bin.mof_drift",
        "trigger": "bin/mof-drift",
    },
    "gov.commit_closure": {
        "domain": "governance",
        "kems_faces": ["evidence", "metrics", "signal"],
        "handler": "l4.governance.commit_closure_check",
        "trigger": "git status --short | wc -l > 100",
    },
    "gov.dimension_saturation": {
        "domain": "governance",
        "kems_faces": ["signal", "card"],
        "handler": "l4.governance.dimension_saturation_check",
        "trigger": "linter_dimension_count >= 15",
    },
    "gov.adr_index_integrity": {
        "domain": "governance",
        "kems_faces": ["document", "evidence"],
        "handler": "l4.governance.adr_index_check",
        "trigger": "omo audit (adrs check)",
    },
    "gov.rise_cycle": {
        "domain": "governance",
        "kems_faces": ["document", "evidence", "metrics", "signal", "card", "metric"],
        "handler": "l4.governance.rise_cycle_orchestrator",
        "trigger": "agent receives governance task",
    },
}
```

### 2.2 DomainHealth 集成

```python
# projects/l4-kernel/src/l4_kernel/health.py

# P60 新增 governance_domain_health
def compute_governance_health() -> GovernanceHealth:
    return GovernanceHealth(
        frontmatter_coverage=get_frontmatter_coverage(),  # ≥ 95%
        drift_low_count=get_drift_low_count(),  # ≤ 5
        commit_closure=get_commit_closure_status(),  # 工作 tree < 50
        dimension_saturation=get_dimension_count(),  # ≤ 15
        adr_index_integrity=check_adr_index(),  # 无 UNLISTED
        governance_score=get_governance_score(),  # 100 A+
    )
```

---

## 3. c2g 战略入口集成

### 3.1 brainstorm → bet → broker 流程

```
c2g brainstorm "治理收敛"
   ↓ Pitch (Upstream + Appetite)
c2g broker
   ↓ TASK-*.yaml (planned → pending)
omo broker ingress-task
   ↓ mof-version bump + commit
omo governance 验证
   ↓ score 100 A+
git push origin main
```

### 3.2 brainstorm 模板 (治理专用)

```yaml
# c2g brainstorm template for governance tasks
template:
  name: governance-convergence
  required_fields:
    - upstream:  # 治理痛点
        - governance_score_drop
        - drift_increase
        - frontmatter_decay
        - commit_closure_breakdown
    - appetite:  # 投入意愿
        - small: 1-3 commits (轻量)
        - medium: 5-15 commits (中量)
        - large: 20+ commits (大重构)
    - target_metrics:  # 目标量化
        - frontmatter_coverage: 100
        - drift_low_count: ≤ 5
        - governance_score: 100 A+
```

---

## 4. Cockpit CLI 集成 (人类入口)

### 4.1 新增子命令

```bash
# 治理就绪度评估
cockpit governance readiness
# 输出: 5 维度评分 + 改进建议

# 启动 RISE 循环
cockpit governance rise-cycle <phase-name>
# 自动执行 R → I → S → E → C 5 步

# 健康度快查
cockpit governance status
# 输出: governance score / drift count / frontmatter / commit closure

# 历史回放
cockpit governance history <phase-name>
# 输出: P 阶段决策链 + ADR 引用 + 收口报告

# 失闭环预警
cockpit governance check-closure
# 输出: 工作 tree 累积 / mof-version vs commit 配对
```

### 4.2 Dashboard 卡片

```yaml
# cockpit dashboard 新增 3 张卡片
cards:
  - id: governance_score
    title: "Governance Score"
    source: "omo governance"
    refresh: 1h
    target: 100

  - id: drift_status
    title: "Drift Status"
    source: "bin/mof-drift"
    refresh: 6h
    target: low ≤ 5

  - id: commit_closure
    title: "Commit Closure"
    source: "git status --short | wc -l"
    refresh: 30min
    target: ≤ 50
```

---

## 5. Agent Prompt 注入 (Decision Guidance)

### 5.1 CLAUDE.md 增量

```markdown
## 治理纪律 (P60+)

### 强制闭环原则 (P59 教训)
- 任何文件修改后立即 `git add . && git commit`
- `bin/mof-version record` 必须与 commit 同步
- 工作 tree 累积 > 100 文件触发自动警告

### RISE 循环 (P43-P59 方法论)
- **R**esearch: 先调研, 再动手
- **I**nvestigate: 找根因, 不修表面
- **S**trategize: 至少 3 方案, 选最低风险
- **E**xecute: 批量兜底 + frontmatter + 收口
- (新增) **C**ommunicate: 写收口报告 + commit 闭环

### 软分层原则
- 物理位置不重要, frontmatter 是机器可读契约
- 不动路径原则: 优先 frontmatter 化, 再考虑真迁移
- 双指针可追溯: 真迁移时原位 + 新位双向引用

### 维度饱和律 (P57 ADR-0053)
- linter 维度 ≥ 15 时, 新能力用独立 bin 工具
- 拒绝做什么 = 有效治理

### 治理债务识别
- 结构债: 目录错位 / 命名冲突 / 断链
- 语义债: frontmatter 缺失 / status 混乱
- 时序债: 累积未提交 / 未归档 / 未清理
```

### 5.2 启动时注入

```python
# projects/cockpit/src/cockpit/injector.py

GOVERNANCE_PROMPT = """
## 治理决策提醒 (P60+)

检测到 governance 相关任务时, 自动激活 governance-phase-orchestrator skill。

执行步骤:
1. R: 读 .omo/state/system.yaml + .omo/_knowledge/decisions/INDEX.md
2. I: 查 mof-drift + omo governance + omo lint doc-lifecycle
3. S: 至少 3 方案 (轻量 / 中量 / 大重构), 选最低风险
4. E: 批量兜底 → README → frontmatter → mof-version → commit
5. C: 收口报告 → governance 验证 → TodoList 完成

P59 教训: commit 闭环不可省略!
"""
```

---

## 6. 实施路径 (4 周)

### Week 1: L0/X1-X4 规则落地 (确定性)

```
Day 1-2: L0-constraints.yaml 增量 5 条
Day 3: X1-X4 规则增量 3 条
Day 4: 注册到 omo lint / X2 freshness
Day 5: pre-commit + CI 验证
```

### Week 2: M0 桥接 (模型层)

```
Day 1-2: M3-STAGE-GOVERNANCE-MAINTENANCE
Day 3: M2-SCHEMA-GOVERNANCE-DECISION
Day 4: M1 实例 GOVERNED-MAINTENANCE-PHASE
Day 5: mof-derive / mof-bridge-sync 验证
```

### Week 3: L4 Kernel + Workflow Skill (智能层)

```
Day 1-2: l4-kernel 6 capability 注册
Day 3: governance-phase-orchestrator skill 设计
Day 4: SKILL.md 落地 + 测试
Day 5: cockpit CLI 集成 (governance readiness / rise-cycle)
```

### Week 4: 验证 + 收口

```
Day 1-3: 跑一遍 P60 测试 phase, 验证 RISE 循环可执行
Day 4: governance 就绪度评分 ≥ 90
Day 5: ADR-0054 记录 + 收口报告
```

---

## 7. 验证标准

### 7.1 实施完成标志

- [ ] 5 条 L0 约束 + 3 条 X1-X4 规则已注册, CI 拦截有效
- [ ] M3/M2/M1 三层桥接完整, mof-derive 验证通过
- [ ] L4 kernel 6 capability 已注册, DomainHealth 集成
- [ ] governance-phase-orchestrator skill 可触发并完成 RISE 5 步
- [ ] cockpit governance 子命令 4 个可执行
- [ ] 跑一次 P60 测试, RISE 循环自动完成
- [ ] ADR-0054 记录内化决策

### 7.2 治理指标

| 指标 | 当前 (P59) | P60 目标 |
|------|----------:|--------:|
| governance score | 100 A+ | **100 A+ 持续** |
| L0 约束覆盖 | ~30 | **+5 = 35** |
| X1-X4 规则 | 8 | **+3 = 11** |
| omo lint 维度 | 15 | **15 (饱和)** |
| 独立 bin 治理工具 | 2 | **+1 governance-readiness** |
| L4 governance capability | 4 | **+6 = 10** |
| Workflow skill | 0 | **+1 governance-phase-orchestrator** |

---

## 8. 长期演化 (3-6 个月)

### 8.1 自治治理代理

```
# 未来: governance-agent (自动触发)
cron: every 6h
actions:
  - 运行 5 维度 governance readiness 检查
  - 如 frontmatter < 95%, 自动批量补
  - 如 drift LOW > 5, 自动分析原因
  - 如 commit closure breakdown > 100, 自动警告
  - 任何自动动作需 mof-version + commit 闭环
```

### 8.2 治理可移植性 (OmniFrame)

```
把 P43-P60 治理模式抽象为开源框架:
├─ 6 平面架构 (control/truth/knowledge/delivery/state/...)
├─ frontmatter 4 字段契约
├─ X1-X4 治理规则
├─ L0 强制约束
├─ RISE 循环 workflow
└─ commit 闭环纪律

适用: 任何 monorepo / 长期演进项目
```

---

## 9. 关键决策总结

### D-P60-1: 双路径内化 (规则 + 智能)
- **规则内化** (L0/X1-X4): 确定性约束, CI 强制
- **智能内化** (L4/Skill/Prompt): 启发式引导, agent 自主
- 两者互补: 规则兜底, 智能优化

### D-P60-2: L4 capability 而非新增 L4 模块
- l4-kernel 已 19 域, 不再新增域
- governance 作为"跨域 capability"注册
- 沿用 KEMS 六面 + DomainHealth 集成

### D-P60-3: M0 桥接而非 M0 扩展
- model-driven 是横切面框架, 不承载治理逻辑
- M3 增 GOVERNANCE_MAINTENANCE 阶段, M2 增 schema, M1 增实例
- 遵循 P14-P15 model-driven bridge 模式

### D-P60-4: skill 而非 prompt 注入
- governance-phase-orchestrator 是 workflow skill
- 可在 agent 启动时自动加载
- 与现有 superpowers 系列 skill 一致

### D-P60-5: cockpit 子命令而非独立 CLI
- cockpit 是 L3 唯一人类入口
- governance 子命令统一管理
- 与 agora/omo/runtime CLI 解耦

---

## 10. mof-version 历史 (含本提案)

```
v0.0.1   - v0.0.40  P43-P52 治理收敛主体
v0.0.41  - v0.0.46  P53-P58 知识面深度收敛
v0.0.47            P59 git commit 闭环恢复
v0.0.48 (P60)      治理方法论内化提案 (本报告)
v0.0.49+ (P61+)    落地实施 (L0/X/M/L4/cockpit)
```

---

## 11. 立即可执行 (P60 收口)

1. 写入 ADR-0054 (本提案决策记录)
2. 提交本报告到 .omo/_knowledge/audits/
3. mof-version v0.0.47 → v0.0.48
4. 创建 5 个 L0 约束草案到 .omo/_truth/ 备审
5. 创建 governance-phase-orchestrator skill 草案到 skills/

---

*最后更新: 2026-06-23 · omostation P60 提案 · 治理方法论内化路径设计*

💘 Generated with Crush

Assisted-by: Crush:MiniMax-M3