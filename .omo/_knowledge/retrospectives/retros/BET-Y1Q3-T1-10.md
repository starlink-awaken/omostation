---
lifecycle: history
owner: auto-fix-loop
last_updated: 2026-08-24
title: BET-Y1Q3-T1-10 Retro
type: retro
---

# BET-Y1Q3-T1-10 Retro

## 五问

1. **What happened?**  
   resident 常驻 agent 体系 (WP-A~I / ADR-0396) 的感知面在治理/CI/MCP/BOS 四层存在系统性缺口。通过 PR #2047 完成全覆盖。

2. **What went well?**  
   - 3 个 CR-RESIDENT check 工具（status/mof-sync/bos）一次落地并通过 gac-local-gate
   - ci-surfaces.yaml 和 governance-checks.yaml 同步登记
   - agent-workflows registry 新增 resident-runtime-observe workflow
   - docs/architecture/resident-agent-system-v1.md 漂移修复（Agora MCP 声明修正）

3. **What went poorly?**  
   - 台账状态未随 PR #2047 合并自动回写，导致 bet 仍显示 in_progress
   - Agora MCP resident 工具未实现，文档曾声明"已接线"造成漂移

4. **What did we learn?**  
   - PR 合入后必须同步更新 bet 台账状态（防 done 状态滞后）
   - 文档声明必须与实际代码对齐，L0 enforcement 引用不能悬空

5. **What should we do next?**  
   - 如需 Agora MCP resident 工具，新建 bet（运行时能力扩展）
   - 监控 CR-RESIDENT check 工具的 CI 执行率

## 补充复盘 (2026-08-24 回退纠偏后重新 done)

- **回退原因**: done_when 第 5 条 "docs/architecture/resident-agent-system-v1.md 的已接线声明与实际代码一致" 存在漂移 — 文档曾声明 Agora MCP 待接线, 与 tools_resident.py 已实现不符。
- **本次修复 (omo PR #95 + 主仓 PR #2100/#2102)**:
  - status.py `_daemon_snapshot` 只统计五类角色水位, 排除订阅层 `resident-sub.json` — 修复 sub 水位陈旧导致健康体系误判 degraded (status.py:57-71 min(mtime) 缺陷)
  - 新增回归测试 `test_snapshot_daemon_sub_stale_role_fresh_is_recovered`
  - `docs/architecture/resident-agent-system-v1.md` 第 79 行 Agora MCP 状态 "待接线"→"已接线"
  - T1-10 台账 done→candidate→done 全链路 (start run 绑定 + verify + closeout)
- **经验**: 接线类 done_when 的"文档声明与代码一致"必须实测 (tools_resident.py 实现存在 + 注册表登记 + 文档三处对齐), 不能只信文档或只信代码单侧。
