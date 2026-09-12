---
schema: session-retro/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-12
type: ephemeral
---

# Session 2026-09-04 → 2026-09-12 复盘

> 范围：主仓 a4ffeb414 → dbf0329073（49 commits, 124 files, +4867/-309 行）

## 核心交付（6 PR 全合并）

| PR | 类型 | 核心变更 |
|---|---|---|
| omostation-omo#163 | 架构 | dispatch_backend() + cell CLI 经 Mesh 分发（SFOP 八律第3条） |
| #3620 | 治理 | CR-SFOP-03 自动化检查 |
| #3606 | 运维 | radar 刷新 health.yaml + stale_beats 1→0 |
| #3612 | 知识 | PITFALL-004 UTC 时区陷阱 + foundry registry 登记 |
| #3634 | 治理 | 4 workflow trigger 登记 + drift 归零 |
| #3642 | 治理 | Diff 治理三件套 CI 门禁 + ref fallback |

## 关键教训（已实证）

1. **frontmatter UTC 时区陷阱**：CST 晚间写的 last-reviewed 被 UTC 判 future → gac-gate FAIL → PITFALL-004
2. **ci-surfaces 不加自引用路径**：workflow 的 on.paths 多登记 self-path → trigger-drift
3. **mergeStateStatus = CLEAN/BLOCKED/DIRTY**（非 MERGEABLE）
4. **worktree 创建后立即 submodule update --init**：防指针回退（cockpit-ui 回退 2 次实证）
5. **并发 agent 争用**：主仓被切走用 stash+checkout main 恢复；不替并发 agent 写 retro
6. **Diff 工具 ref fallback**：CI 只有 origin/main，工具已加 _resolve_ref
7. **growth 阈值是猜测**：500/30 需观察是否误杀

## 系统终态

- 治理门禁全绿（SFOP / execution-chain / ci-surfaces drift=0 / meta-doctor stale=0）
- diff-governance 工作流正常运行
- BET 362 done / Y1Q4 77.5%
- 健康度 9/10

## 未做成（并发 agent 区域）

- T10-143 closeout：测试通过但无诚实变更历史写 retro
- T8-24C：测试 0/8 失败，并发 agent in_progress
- proposed cron 清理：并发 agent 刚触碰
- AGENTS.md 经验固化：并发 agent 高频修改该文件，争夺失败
