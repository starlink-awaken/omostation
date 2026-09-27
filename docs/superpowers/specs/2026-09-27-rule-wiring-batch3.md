---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-27
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: 规则接线批次三 — 孤儿接线 + 债务值域迁移 + 处置落档
bet_id: BET-Y2Q4-T10-06
---

# BET-Y2Q4-T10-06 — 规则接线批次三

## 目标

1. **孤儿执行器接线（3 条）**：bin/gac/mcp-tool-data-complete.py、bin/ssot/check-cross-repo-consistency.py、
   bin/gac/timeout-audit.py 全部本地 rc=0 实测通过，接入 .github/workflows 治理检查步骤
   （脚本名进入可执行语料 → 规则 wired）。
2. **CR-DEBT-GATE-ENUM-01 实现 + 迁移**：check-debt-closure-discipline.py 增加 gate_level
   值域校验（{gate,watchlist,none}，锚 CR-DEBT-GATE-ENUM-01）；存量 20 条违反项
   （P0/P1/P2）按自然语义映射迁移（P0→gate / P1→watchlist / P2→none），修复
   review 队列 rank=99 使高严重度债务反而最后被看的原始缺陷。
3. **d 类 8 条处置注释落档**：L4-FRESHNESS（macOS launchd 依赖，ubuntu CI 不可接，
   留待 mac 专用 lane）、EVIDENCE-DECLARED（收窄至 complete D0 口径）、L2-TASK-DELIVERABLE、
   L0-SSOT-PATH-NORM、X1/X2-POLICIES-SSOT（并入 SH-4 决策）、GIT-STAGE-SUBMODULE-PIN
   （收窄至 staged-gitlink 可检口径）。
4. coverage 复跑记录；SEC×4 / AGE×5 幻影处置留 owner 表态（另呈报）。

## 红线

- 接线只加步骤不改既有 CI 步骤；新步骤失败会红（三脚本已实测 rc=0）；
- 债务迁移逐条留痕（git diff 可见 20 条值域变更），不做静默批量改写；
- 声明条目不删除。

## 验收（done_when 摘要）

1. workflow 新步骤含 3 脚本，coverage wired +3；
2. debt 值域校验生效（CR-DEBT-GATE-ENUM-01 接线）+ 20 条迁移完成、校验通过；
3. 8 条处置注释落 governance-checks.yaml + 批次三文档；
4. coverage 复跑记录 + 债务 history 追加；
5. retro 固化（含 SEC/AGE 幻影 owner 待决清单）。
