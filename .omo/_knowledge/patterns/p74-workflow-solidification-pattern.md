---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-07-03
related:
  - p71-baseline-recovery-pattern.md
  - p72-follow-up-completion-pattern.md
  - p73-truth-driven-engineering-pattern.md
  - ../decisions/0129-state-projection-plane-phase3.md
---

# P74 — Workflow Solidification Pattern (固化工作流模式)

> **适用范围**: 对 registry 已登记但未被实际触发、或被反复触发但缺乏专属流程的 workflow,进行系统性固化与回收。

## 0. 触发场景

任一即触发 P74 评估:

1. **沉默 workflow**:registry 登记 ≥ 1 周,无 `agent_workflow_start` 事件。
2. **错位 workflow**:实际做的事 ≥ 3 次,却走通用 `project-code-change` 而非专属 workflow。
3. **僵尸 run**:status 中 `active_runs > 0` 但 `last_closeout` 已 ≥ 24h(失忆或中断)。
4. **声明/执行鸿沟残留**:某文件被声明受治理(`claim_policy.required_paths`)但 `diff_checks` 无对应 gate。

## 1. 现状诊断(P74 输入)

### 1.1 矩阵盘点

对每个 workflow 取:

- `lanes` (`agent-workflows.yaml`)
- `closeout_required` 实际可执行的命令
- 最近 30 天 `agent_workflow_start` 事件计数
- 最近 30 天 `agent_workflow_closeout` 计数
- 平均 duration(从 `start` 到 `closeout` 的 `updated_at - created_at`)
- 失忆率(`status: ok` 但 24h 内无 closeout 的比例)

### 1.2 集成盘点

每个 `internal_integrations` × `external_patterns`:

- `status` (integrated / optional_adapter)
- `health` (PASS / WARN / FAIL)
- `degrade_to` 是否被声明

### 1.3 路径漂移盘点

`git log --diff-filter=A --name-only --since="<window>"` 提取新增 SSOT/工具/脚本路径,与 `claim_policy.required_paths` 做差集。

## 2. 固化分类(P74 处理)

| 类型 | 诊断特征 | 固化策略 |
|------|----------|----------|
| **A. 沉默 workflow** | 登记但无 start 事件 | 拆 3 子情况: (a1) 名称误导→改名/合并 (a2) 流程太重→拆 phase (a3) 实际无人需要→登记为 `deprecated` |
| **B. 错位 workflow** | 反复走 project-code-change | 提取专属 workflow + 专属 `diff_checks` + 强制 `allowed_lanes` |
| **C. 僵尸 run** | active 超 24h, evidence 空 | (c1) 同 actor → 续 verify/closeout (c2) 异 actor → observer-agent 介入,按 lock/ledger 决策 halt/escalate |
| **D. 鸿沟残留** | 新路径未注册 | 走 `governance-state-mutation` 流程,加进 `claim_policy.required_paths` + `diff_checks` |

## 3. 当前诊断结果(2026-07-03 快照)

### 3.1 Workflow 利用矩阵

| Workflow | Lanes | Start(30d) | Closeout(30d) | 类别 |
|----------|-------|------------|---------------|------|
| project-code-change | code, gov_code, config | 7 | 6 | 高频 ✅ |
| project-doc-change | docs, gov_code, config | 0 | 0 | **A 沉默** |
| governance-state-mutation | gov_state, docs, runtime_snapshot | 0 | 0 | **A 沉默** |
| c2g-spec-ingress | gov_state, docs | 0 | 0 | **A 沉默** |
| mof-model-change | gov_code, gov_state, docs | 0 | 0 | **A 沉默** |
| mof-state-bridge-audit | gov_code, gov_state | 0 | 0 | **A 沉默** |
| external-adapter-sync | docs, gov_code, gov_state | 0 | 0 | **A 沉默** |
| submodule-pointer-close | submodule_pointer, config | 0 | 0 | **A 沉默** |
| handoff-resume | 全 lanes | 0 | 0 | **A 沉默**(预期内,压缩才用) |
| observer-audit | gov_code, gov_state | 0 | 0 | **A 沉默** |
| state-sync | gov_state, docs, runtime_snapshot | 0 | 0 | **B 错位**(实际派生高频但走 project-code-change) |
| governance-audit | docs, gov_code, gov_state | 0 | 0 | **A 沉默** |

**结论**:12 个 workflow 中 11 个是沉默的。仅 `project-code-change` 在用。

### 3.2 B 错位深挖:`state-sync` 实际被绕道

最近 7 个 closeout 的工作内容(含本会话 dirty 文件)显示:

- `omo state sync` 派生文件(`BRIEF.md` / `.omo/state/*.yaml` / `.omo/_control/*.json`)→ 走 `project-code-change`
- `gen-service-configs.py` GHA schedule_ref 校验(P4 治本)→ 走 `project-code-change`
- `projects/runtime` / `projects/omo` 子模块脏指针 → 走 `project-code-change`

这些应该走 `state-sync` / `governance-state-mutation` / `submodule-pointer-close`,但被错位路由。

### 3.3 C 僵尸 run 现状

- `20260703T105647Z-project-code-change-01ecb268`:8h+ 前 verify fail(`agent-workflow-tests` + `ssot-guardian` 双 fail),**两个 fail 已自动恢复**(本会话重跑均 PASS),但 run 仍 active。

### 3.4 D 鸿沟残留

新增未注册:

- `.omo/_truth/registry/runtime-projections.yaml` (P0 元递归新增 SSOT)
- `bin/gen-service-configs.py` (阶段4 元递归新增工具)
- `.omo/state/runtime/*.yaml` (新增派生目录)
- `runtime/.watch-dispatch-stamps.json` (新增 runtime 戳)

## 4. P74 修复路线图(分 5 阶段)

### 阶段 1 — 清场(P74 §0 类 C)

**目标**:把 `01ecb268` 跑 verify → closeout,compliance 归零。

```bash
uv run --with pyyaml python bin/agent-workflow.py \
  verify 20260703T105647Z-project-code-change-01ecb268 --from-diff --execute
uv run --with pyyaml python bin/agent-workflow.py \
  closeout 20260703T105647Z-project-code-change-01ecb268
uv run --with pyyaml python bin/agent-workflow.py compliance
```

**验收**:compliance `findings: []`。

### 阶段 2 — 鸿沟回收(P74 §0 类 D)

把 §3.4 的新路径收口:

1. `runtime-projections.yaml` 加进 `claim_policy.required_paths.tiers[core-governance-required]`。
2. `bin/gen-service-configs.py` 加进 `diff_checks`,触发 `gac-local-gate` + 自定义 `gha-schedule-ref-validate`(P4 复发拦截)。
3. `.omo/state/runtime/**` 加进 `state-sync` 的 `allowed_paths`(在 `bin/agent-workflow.py` 显式声明)。
4. `runtime/.watch-dispatch-stamps.json` 决定:.gitignore 或受治理。

**验收**:`agent-workflow lint` 通过 + `gac-local-gate` 通过 + `bin/gen-service-configs.py` 改动必触发 schedule_ref 校验。

### 阶段 3 — 错位路由纠正(P74 §0 类 B)

定义 3 个高频错位的标准输入:

| 触发物 | 应走 workflow | 入口命令 |
|--------|---------------|----------|
| `.omo/state/**` / `.omo/_control/**` / `BRIEF.md` 改动 | `state-sync` | `omo state sync` 后由 `state-sync-agent` 接管 |
| `.omo/_truth/**` / `bin/gac-*.py` / `bin/ssot-*.py` 改动 | `governance-state-mutation` | `governance-agent` |
| `projects/*` 子模块 SHA 推进 | `submodule-pointer-close` | `release-agent` |

实现路径:`diff_checks` 按 glob pattern 自动判定建议 workflow,`agent-workflow start --suggest` 用 advisory 模式提示。

**验收**:下次同样的改动,`--suggest` 输出预期 workflow 名字。

### 阶段 4 — 沉默 workflow 激活(P74 §0 类 A)

对 8 个沉默 workflow 分类处理:

| Workflow | 处置 | 理由 |
|----------|------|------|
| handoff-resume | 保留沉默 | 预期行为,压缩才用 |
| observer-audit | 接入 `bootstrap` 自动跑 | 沉默但价值高,顺手做 |
| mof-state-bridge-audit | 接入 gac-local-gate | 已有 check,但缺显式 workflow 触发 |
| 其他 5 个 | 保留沉默 + 加 `last_triggered` 字段 | 等真实场景再激活 |

**验收**:`observer-audit` 在 `make gac-local-gate` 输出中可见。

### 阶段 5 — 自我演化(P74 闭环)

写入 SSOT:`.omo/_truth/registry/agent-workflows.yaml::workflows[*].last_health_check`,由 `state-sync` 定期刷新。

新增 `governance-audit` workflow 接 `agent-workflow observe` + `compliance`,定期产出 P74 评估报告(7 天一次)。

## 5. 防复发机制(对应 P71 4 GaC 规则 + 1 新规则)

| 规则 ID | 触发 | 拦截点 |
|---------|------|--------|
| CR-X1-EVIDENCE-RUNNABLE | workflow closeout_required 命令不可执行 | agent-workflow lint |
| CR-L0-BOS-DOMAIN-NORM | 新增 SSOT 未声明 lane | claim_policy 校验 |
| CR-META-BIN-NAMING | `bin/*.py` 未声明 owner | diff_checks 自动注册 |
| CR-META-BIN-ORPHAN | 工具无 caller | runtime invoke 计数 = 0 → fail |
| **CR-WORKFLOW-SILENT** (新) | workflow 30d 内 0 触发 | observer-audit weekly 报警 |

## 6. 与 P71/P72/P73 关系

- **P71** (baseline recovery):治本,一次性的 5 阶段声明/执行鸿沟修复。
- **P72** (follow-up completion):阶段路线图执行守门。
- **P73** (truth-driven engineering):以 SSOT 为唯一真源的工作模式。
- **P74** (workflow solidification):**常态化机制**,把 P71/P72 的发现沉淀为 workflow 层级的固化结构。

## 7. 风险与回滚

| 阶段 | 风险 | 回滚 |
|------|------|------|
| 1 | 误关合规 run | closeout 不删 run record,只改 status;observer-audit 可恢复 |
| 2 | 强加 lint 卡死开发 | `--strict` 仅 CI;pre-commit 默认 advisory |
| 3 | 误判 workflow | `--suggest` 仅 advisory,不强制 |
| 4 | observer-audit 噪声 | 默认 weekly,可关 |

## 8. 立即执行项(P74 阶段 1)

按本会话上下文,阶段 1 已经具备执行条件:

1. `verify 01ecb268 --from-diff --execute`(8h 前 fail 已自然恢复)
2. `closeout 01ecb268`
3. `compliance` 确认清零
4. 列出 dirty 文件 commit plan,等用户确认

阶段 2-5 需要用户确认是否继续,并明确每个阶段的范围。