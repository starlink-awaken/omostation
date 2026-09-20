---
status: superseded
lifecycle: planning
owner: governance-team
last-reviewed: 2026-09-19
superseded-by: docs/OMOSTATION-FORWARD-PLAN-v2.md
type: roadmap
---

# OMOSTATION-FORWARD-PLAN — 后 3 年路线图 (2026H2 - 2029H1) [SUPERSEDED]

> **Status**: SUPERSEDED by [v2](OMOSTATION-FORWARD-PLAN-v2.md) (2026-09-20)
> v1 完成度: §A 短期 3/3 (A1/A2/A3), §B 中期 4/4 (B1.1/1.2/1.3/B2), §C 3/4 (C2.2 done, C3 done, C1 持续监测)
> 本文档保留作历史快照; 新方向看 v2.

## 状态: 当前 (2026-09-19)

- **总 BET**: 425 (全部 done, 100%)
- **窗口**: Y1H1 / Y1H2 100%, Y3H1 / Y3H2 100%
- **main HEAD**: `a79ab630c` (含 STRATEGIC-3YEAR-PLAN-COMPLETION)
- **持续 commit 速率**: 9 月 18-19, 50+ commits (其他 agent 在 hardening)

## 短期目标 (2026-09 ~ 2026-12, 3 个月)

### A1. 治理预算自动化 (P0)

**当前**: `auto-bump-doc-governance-budget.py` 只处理 `legacy-omo-knowledge-enums`.
**目标**: 扩展到所有 budget exception (5 个).

```bash
# 现状 budget 列表
grep -E "  - id: legacy" .omo/_truth/registry/document-governance.yaml
# legacy-omo-knowledge-enums (rule: invalid_metadata, surface: omo-knowledge)
# legacy-omo-knowledge-frontmatter (rule: missing_frontmatter, surface: omo-knowledge)
# legacy-omo-truth-frontmatter (rule: missing_frontmatter, surface: omo-truth-docs)
# legacy-omo-standards-frontmatter (rule: missing_frontmatter, surface: omo-standards)
# concurrent-plans-orphan-docs (rule: orphan_document, surface: docs-discoverable)
```

**完成判据**:
- `auto-bump-doc-governance-budget.py --dry-run` 能识别全部 5 个 budget
- 自动匹配 rule + surface (不只 omo-knowledge)
- bump amount 自动按 budget 大小比例缩放

### A2. 跨 repo 流程模板化 (P1)

**当前**: 5+ 种 closeout 工作流 (PR #3585, #3703, #3715, #3730, #3753, #3766, #3768, #3791, #3805, #3823, #3958)
**目标**: 标准化 closeout 5 步 SOP

```yaml
# docs/SOPs/ledger-closeout-sop.md
phases:
  - claim-check:
      tool: bin/gac/gac-worktree.sh claim <bet-id>
      verify: claim-check exit 0
  - implement:
      surface: <bet done_when paths>
      tests: pytest + smoke
      retro: .omo/_knowledge/retros/<bet-id>.md
  - closeout:
      ledger: status flip + done_at + CE matrix
      scripts: bin/_registry/scripts/ 登记 (若新增)
      lint: bet-ledger.py + doc-governance + script-registry
  - commit-push:
      amend: --amend --no-edit
      force-with-lease: 必
      rebase: origin/main 必先
  - merge:
      pr: gh pr create (auto --admin for protected branch)
      closeout: --squash --delete-branch
```

### A3. pre-commit auto-fix-loop 与 closeout PR 冲突解决 (P1)

**当前**: 提交 closeout PR 时, auto-fix-loop 修改 retro 文件 frontmatter (last-reviewed, status), 与本地 ledger 不同步产生额外 diff
**目标**: 让 pre-commit 钩子在 closeout branch 上跳过

```yaml
# .githooks/pre-commit 增加:
skip_fix_loop_branch:
  - "agent/governance-agent/.*-closeout"
  - "feat/.*-closeout"
  
# 检测 branch name 包含 'closeout' / 'retro' / 'ledger' 时:
# export SKIP_FIX_LOOP=1
# 跳过 .omo/_knowledge/retros/ 自动修复
```

## 中期目标 (2027 H1, 3-6 个月)

### B1. AI 驱动治理深化 (P2)

- `auto-fix-loop` 扩展到所有 retro 字段 (不只 frontmatter)
- `bin/ssot/claim-suggester.py` 根据 git log 自动建议 candidate BETs
- `bin/ssot/health-predict.py` 提前 7 天预测 ledger drift

### B2. 跨 repo 标准化 (P2)

- 单一 `bin/closeout-pr.sh` 跨 omostation + 所有子模块
- `bin/mof/cross-repo-status.py` 统一报告 dashboard
- 各子模块统一 retro 模板 (`.omo/_knowledge/retros/<bet>.md`)

## 长期目标 (2027 H2 ~ 2029, 1-3 年)

### C1. 三年终局门

按原计划, 2027-12-31 评估:
- 连续 12 周每周产出 ≥ 3 条被采纳的建议 ✓ (待证)
- Y1 冗余清零 (gbrain/kairon/omo 等核心去重) ✓ 已完成
- Persona 心智镜像可用 ✓ (T6-30 完成)
- Routine 自动托管 (Y3H1-T5-02) ✓ 已完成

### C2. 探索性目标 (滚动添加)

- **场景自适应**: 17+ 现有场景卡 + 自动生成新场景
- **Agent 联邦**: 多 agent 协同任务分配 (T7-06 等)
- **隐私保护**: 个人数据端侧处理 (T6-25 + T6-29)
- **跨域学习**: 学术 + 工程双线知识沉淀

### C3. 评估与调整

每季度评估:
- 完成率 (当前 100% 已达)
- 实际价值 (用户采用率)
- 战略匹配 (3 年终局门)

## 不在范围内

- 替代码添功能 (本期纯持续维护)
- 替架构做大改动 (架构已稳定)
- 新建独立产品 (在 omstation 治理范围内)

## 关联

- `docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md` (前 3 年, 已完成)
- `.omo/_knowledge/summaries/strategic-3year-plan-completion-2026-09-18.md` (完成 retro)
- `.omo/_knowledge/patterns/` (P97-P105, 11 个沉淀)
EOF
