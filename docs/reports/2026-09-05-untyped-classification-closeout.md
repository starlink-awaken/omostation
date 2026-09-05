---
title: BET-Y1Q4-T10-04 收尾报告 — 知识文档 type 批量分类
type: report
owner: governance-team
last_updated: 2026-09-05
bet: BET-Y1Q4-T10-04
---

# BET-Y1Q4-T10-04 收尾报告

> 生成: 2026-09-05 | owner: governance-team | 状态: done

## 1. 任务与结果

BET-Y1Q4-T10-04「知识文档 type 批量分类 — UNTYPED 软信号清零收口」：
目标 UNTYPED 1939 → <300，实际 **1939 → 125**（main 终验，超额完成）。

## 2. 执行记录

| 步骤 | 命令 | 结果 |
|------|------|------|
| 机制扩展 | `generate-docs-index.py --classify <rules.yaml>` | 新增批量分类模式（零新增 bin 脚本） |
| 首轮分类 | 规则 17 条 | 1503 文件 |
| 第二轮补漏 | 规则追加至 35 条 | +125 文件 |
| 总计 | 1628 文档 frontmatter 赋 type | UNTYPED 1939 → 213 (worktree) |
| 主线终验 | `/tmp/verify-main` 挂 origin/main 跑 `--check` | **UNTYPED 125**（含并行子模块融合） |
| 合并 | PR #3155 | `80ec49a2` (CI 33/33 PASS) |

## 3. 分类口径

- 长期知识（decisions/design/management/patterns/superpowers 等 9 目录）→ `type: ssot` + owner/last-reviewed 补全（与 --fix 同口径，已有值不重复写）
- 时点产物（audits/retros/sediment/summaries/decision-proposals/tasks/_archive 等 14 目录）→ `type: ephemeral` + `status: archived`（避开 EXPIRED 硬阻塞）
- 工具产物/镜像（.codebase-memory/.subtrees）→ 扫描器 IGNORE_DIRS 排除（#3133 前置）
- 子模块/沙箱散点（~125 残余）→ 保持 untyped，子模块自行治理

## 4. 波及修复 (合并途中暴露的存量问题)

1. **7 个 SKILL.md name/description 丢失**（#3097 补过、被后续并行 PR 冲掉）→ 补回，check-agent-skills 39/39 PASS
2. **capability-registry drift**（skills 12→31，含 19 个新 skill 首次注册）→ 重生成同步
3. **omo gitlink 回退拦截**（add -A 误裹 worktree 旧检出）→ gitlink-ancestry 拦截后恢复前进指针 `dad7c212`（含 portfolio-projection-control snapshot 修复 #142）
4. **mutation-surfaces stale**（gitlink 落后致 CI 挂）→ gitlink 恢复后 pass: surfaces=32

## 5. done_when 达成情况

1. ✅ doc-index UNTYPED 软信号 < 300（基线 1939）→ **125**
2. ✅ doc-index 硬阻塞维持 0 → PASS
3. ✅ 分类规则表落盘 → `docs/plans/2026-09-05-untyped-classification-rules.md` + `.yaml`

## 6. 遗留

- 子模块散点 ~125 个 untyped（projects/knowledge 36、omlxc 34、cockpit-ui 21 等）由各子模块自行治理
- resident agents 持续生成的新 sediment/retro 文件默认 untyped——增量的 type 赋值建议在 resident workflow 模板里固化（后续小改进）
