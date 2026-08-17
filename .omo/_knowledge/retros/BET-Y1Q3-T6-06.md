---
id: BET-Y1Q3-T6-06
type: retro
status: completed
date: 2026-08-17
run_id: 20260817T012454Z-project-doc-change-167575da
workflow_id: project-doc-change
bet_id: BET-Y1Q3-T6-06
north_star_ref: docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
commit: 064ebef83
scope:
  - .omo/_knowledge/patterns
  - .agents/skills
---

# BET-Y1Q3-T6-06 Retro: 文档治理减负 — 知识沉淀入库

## 目标
近期连续多轮 submodule-pointer 交付/closeout 中沉淀了大量可复用实操经验，
以 pattern + SEMA skill 形式入库，避免同类坑重复踩。

## 产出
1. `.omo/_knowledge/patterns/submodule-pointer-closeout-playbook.md` (SSP-CLOSEOUT)
   - verify/closeout 用 `--file` 限定 gitlink 面，避开 `.omo/**` 并发漂移误伤
   - `verify --json` 需过滤前导 `^warning:` 行再解析
   - 子模块 worktree 移除必须 `--force`
   - squash 合并后分支「非祖先 != 未入库」判定 (`git show <sha>:<path>` 验证)
   - gh 在子目录查询必须 `--repo starlink-awaken/<sub>.git`
2. `.agents/skills/workflow:submodule-pointer-close/SKILL.md` — SEMA 自动结晶
   技能包入库，与 workflow:bet-execution / workflow:mini 同路径先例对齐。
3. 4 个僵尸 active run 清理（compliance WARN 清零）:
   - b775a96f (landing plan 被 supersede) → failed
   - 5f273a08 (omlxc→7485d096 已覆盖) → ok
   - 4b48c154 (T6-05 文档已落地) → ok
   - 30bcb40a (lint 修复 #1624 已合入) → ok

## 验证
- verify: doc-ssot-lint / project-layer-index / omo-state-projection-guard 全 PASS
- ssot-guardian / gac-local-gate 的 FAIL 为并发 agent 既有子模块指针漂移
  (cockpit/omo/scripts)，与本次新增文档无关
- compliance: continue (4 个 WARN 清零)

## 沉淀
- Pattern id 命名沿用 `P<NN>` 外的自由 id 形式 (`SSP-CLOSEOUT`)，与既有
  `P75` 并存，frontmatter 校验通过
