---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-07-03
related:
  - ../../../.agents/skills/governance-ssot-edit/SKILL.md
  - ../../../docs/AGENT-ISOLATION-ROLLOUT.md
  - p72-follow-up-completion-pattern.md
  - p71-baseline-recovery-pattern.md
---

# P73 Truth-Driven Engineering Pattern — eCOS 多迁移/并发/声明执行鸿沟下的工程纪律

> **Generated**: 2026-07-03 (post-PR #60 GaC executor enum 5源对齐)
> **SSOT**: 本轮实战 + memory `path-migration-lookup-protocol` / `concurrent-pr-flushes-worktree` / `existence-check-already-exists` / `debt-system-healthy`
> **Purpose**: 抽象"在多次迁移 + 多 agent 并发 + 声明/执行鸿沟的 eCOS 里做工程"的纪律, 防"凭路径直觉错判 / 被并发静默冲掉 / 信声明假绿 / 单源改漏源"

## 1. 模式识别 (4 类 eCOS 工程陷阱)

| 陷阱 | 症状 | 本轮案例 |
|------|------|---------|
| **D1** 凭路径直觉判存在性 | 报"X 零实现/不存在/悬空" 其实文件已迁移或运行时写面未创建 | 连续 3 轮把 debt(空=运行时写面正常) / task(卡 ingress delivery) / GaC(3 drift 非 129) 判错 |
| **D2** 信声明健康假绿 | health_score=100 但真实 evidence_health=78.9, gap 全在盲区 | compass_radar 合成 100 掩盖反馈回路停摆 50.7h |
| **D3** 单源改多源字段 | 改一处 enum/registry 漏其他源 → drift 复发 | GaC executor 5 源, F-14 (PR#59) 只补 1/5 (PRESENCE), 漏 executor_enum + EXECUTOR_ENUM |
| **D4** 工作树裸奔 | 未 commit 改动被并发 PR 合并/checkout 静默还原 | PR #59 合并冲掉我对 gac-drift.py + governance-checks.yaml 的改, gac-drift 重新红 |

## 2. 标准应对 (4 纪律)

### 纪律 1: 证据驱动, 5 位置查询法 (治 D1)
判断"不存在 / 零实现 / 悬空 ref"前**必查 5 位置**:
1. **ADR** — `.omo/_knowledge/decisions/*.md` 含 `migrate`/`physical-migration`/`superseded`/`convergence`
2. **archive** — `.omo/_archive/legacy-*` + 顶层 `_archived/` (搬家的旧物)
3. **`_control/`** — `.omo/_control/<name>-dashboard/` (治理 dashboard 迁移落点, 如 debt-dashboard)
4. **mutation-surfaces.yaml** — 声明的写面**运行时按需创建**, 空=正常非 drift (如 .omo/debt/)
5. **ingress delivery** — `runtime/omo/_delivery/` + `change-log/mutations.jsonl` (artifact 可能未投影到正式体系)

工具: `rg -l <id> .omo/ runtime/ projects/ docs/` (不只 .omo/tasks) + 读相关 ADR。

### 纪律 2: 真实 vs 声明健康双量 (治 D2)
- 声明源: `.omo/state/system.yaml::health_score` (compass_radar 合成)
- 真实源: `bin/gac/evidence-smoke.py` (量化 BOS 鸿沟 + dirty + 反馈回路三维度)
- **gap > 10 即有盲区**。review 健康/架构必跑 evidence-smoke, 不信单方 health=100。

### 纪律 3: 多源对齐逐核 (治 D3)
改 enum/registry/规则类字段, 逐个核全部源。GaC executor **5 源**:
1. `governance-checks.yaml::gac.rules` (规则 SSOT)
2. `governance-checks.yaml::gac.schema.executor_enum` (schema enum)
3. `bin/gac/gac-drift.py::EXECUTOR_ENUM` (drift 检测器)
4. MOF M1 `GAC-RULE-CR-*.yaml` (`gac-m1-sync.py --sync` 派生)
5. `bin/gac/gac-executor.py::EXECUTOR_PRESENCE` (存在性映射)

**别信"已修"** — 并发方也会漏源 (F-14 补一半证明)。改完跑 `gac-drift` + `gac-bootstrap` + `gac-executor` 三验证全绿才算闭环。

### 纪律 4: 改完立即 commit/PR (治 D4)
共享工作树 (eCOS auto-commit + 多 agent), 未 commit 改动会被并发 git 操作静默还原。
- 改完**立即** pathspec commit (`git commit <files>`) 只含目标文件, 不带并发 staged
- 立即 push + 开 PR, 防工作树裸奔
- 验证后**再跑 `git diff --stat`** 确认改动还在 (防静默还原骗你"已绿")
- 详见 governance-ssot-edit skill (`.agents/skills/governance-ssot-edit/SKILL.md`, agent 可触发)

## 3. 何时用

- 改 governance SSOT / registry / enum / GaC 规则
- 报"系统零实现 / 架构有缺口 / 某功能缺失"前
- CI 红 / health 异常 / drift 排查
- 多 agent 并发期任何工作树改动

## 4. 实证 (PR #60, 2026-07-03)

GaC executor enum drift 修复全走通 4 纪律:
- **纪律1**: 5 位置排查发现 F-14 是不完整修复 (只补 ⑤ 漏 ②③)
- **纪律3**: 5 源对齐 (我补 executor_enum ② + EXECUTOR_ENUM ③, F-14 补 PRESENCE ⑤, M1 ④ 派生, rules ① 原对)
- **纪律4**: 首次改动被 PR#59 冲掉 → 重新应用 + 立即 PR #60 → 持久闭环, merged (3bd4edc)
- **纪律2**: evidence-smoke 78.9 vs health 100 的 gap 定位到反馈回路停摆 (非债务, debt 真实 100)

## 5. 反模式 (别干)

- ❌ 凭 `.omo/<dir>/` 不存在就报"零实现" (纪律1)
- ❌ 只看 health_score=100 就判系统健康 (纪律2)
- ❌ 改一个 enum 文件就收工, 不核其他源 (纪律3)
- ❌ 工作树改完不 commit, 裸奔等"下次再提" (纪律4)
- ❌ 信并发方/旧 memory 的"已修 N 缺口", 不重新核真实数据 (纪律3, 本轮推翻 memory 的"129 缺口"实为 3 drift)

## 6. 关联

- **操作流程 (agent 可触发)**: `.agents/skills/governance-ssot-edit/SKILL.md` (端到端步骤, agent 可触发)
- **并发根治**: `docs/AGENT-ISOLATION-ROLLOUT.md` (worktree+branch protection 终态, 本 pattern 纪律4 是临时防护)
- **同系列**: p71 (baseline 恢复) / p72 (follow-up 完成)
- **配套 memory**: `path-migration-lookup-protocol` / `concurrent-pr-flushes-worktree` / `existence-check-already-exists` / `debt-system-healthy` / `ci-red-multitrack-tasks`
