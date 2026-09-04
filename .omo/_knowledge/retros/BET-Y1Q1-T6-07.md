---
title: BET-Y1Q1-T6-07 retro — 战略收敛 r3 剩余件
type: retro
owner: governance-agent
created: 2026-08-17
bet: BET-Y1Q1-T6-07
related:
  - /Users/xiamingxing/Downloads/AGENT-BRIEF-STRATEGY-CONVERGENCE-REMAINDER.md
  - .omo/_knowledge/decisions/0413-gbrain-kairon-merge-disposition.md
  - .omo/_knowledge/decisions/0414-physical-multihost-tension-resolution.md
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q1-T6-07 复盘 — 战略收敛第三轮派工

## Q1 做了什么

按 r3 派工指令四项：D3 决策补档 + D5 张力 ADR + 6 文档内容级重读 +
chain-bind 旁路/误报核查（第 4 项核查部分完成，修复项见打假）。

## Q2 证据

| 指令项 | 产出 | 证据 |
|---|---|---|
| D3 | ADR-0413 (PROPOSED) | 实施事实链全部入档 (#1600/test_loc/去重闭环/回滚 tag)；「不可逆」重判为高成本可逆；REJECTED ALTERNATIVES 三条 |
| D5 | ADR-0414 (PROPOSED, amends 0225/0226) | 张力实测 (0225/0226 grep '0247'=0 次, G-DEL.1 仍 2<4 BLOCKED)；方案 a (PARKED-DEFERRED) + 方案 b 否定理由 |
| 6 文档重读 | 全部 last-reviewed: 2026-08-17 + content-reviewed | 逐条见下 §「文档重读明细」 |
| chain-bind 旁路 | 核查完成 | root wrapper exit=1+显式报错 ✅；`python -m omo.workflow.cli` 拦截但 **exit 0 静默** ❌（缺口收窄为 exit code 不诚实）；cockpit delegates 到 wrapper ✅ 闭环 |

## Q3 打假（与指令假设不符的事实）

1. **指令假设 D3「本轮未开」——实际已实施完毕**（#1600 merged 2026-08-16，
   按用户授权链：grill 十问 C / /plan 批次 6 / 全面推进指令）。本轮正确动作
   是补决策档（ADR-0413），非重新决策。**授权链事实与派工指令的时点差**是本轮最重要的语境修正。
2. **指令假设 registry 计数 200/196 不一致——实测两处均 223 且与 live 一致**
   （前轮已修）。第 6 份文档只需复核标记。
3. **指令假设 SYSTEM-INDEX-DESIGN「1 件 vs 5 文件」矛盾待裁——实测四件
   INDEX-*.md 全存在**：两者都被实施，矛盾是头部表述不准确而非方案未落地。
4. **chain-bind「绕过 wrapper 仍可开工」的描述已过时**：omo 底层 CLI 已接
   同一 chain_bind 硬门（拦截实测有效、无产物）。真实残余缺口是**拦截时
   exit 0 静默**（非显式 exit 1）——类型从「旁路」降级为「静默失败」。

## Q4 文档重读明细（6 份逐条）

| 文档 | 判断 | 动作 |
|---|---|---|
| PANORAMA.md | 仍被 3 入口引用, knowledge 路径已随 T6-01 修好, 战略部分 superseded | 保留 + review-note 声明定位 |
| FUNCTIONAL-CAPABILITY-MAP.md | §11 域数错误 (9 → 实测 **16**) | 订正为 16 域表 + 5 规范域/16 实测域双口径注 |
| USER-JOURNEY-SOP.md | 内容仍有效但断链场景卡体系 | 保留 + 补 scene-cards/journey-specs 交叉引用节 |
| SYSTEM-INDEX-DESIGN.md | 头部自相矛盾 | 修正: 两方案皆实施 (5 件全存在), 正文留作设计史 |
| STRATEGY-INDEX.md | 缺 08-03 后 6 项 | 补台账/AGENT-BRIEF/MILESTONES/ADR-0413/0414 |
| project-registry.yaml | 计数已一致 (223=223=实测) | 复核标记 + _last_updated |

## Q5 遗留与移交

1. **chain-bind exit 0 静默拦截**：`python -m omo.workflow.cli start`（无 bet）
   应 exit 1 + stderr 显式拒绝。涉及 omo 子仓 `workflow/cli.py` start 分支
   的 return-code 链路（该分支代码 return 1 但实际 exit 0 — 疑 runpy/入口
   包装吞码）。**本轮未修**原因：属 omo 子仓变更，与本轮 governance 面拆分
   不同类，且复现根因需 30min+ 调试 — 留专项，不静默（指令第 4 项 done_when
   的「要么修复要么说明为何不修」以此条满足说明义务）。
2. **missing-bet 误报修正**（perception 扫描范围）：核查 `inject_perception`
   时未及完整复现，与上一条同批留专项。
3. **D0 tag 条款入 AGENT-BRIEF**：§8.5.2 已含指针纪律（bump 后必验
   ls-tree），tag 推远端验证条款与现有「tag 的 ref 不会脱离历史」论述合并
   待下轮 BRIEF 修订时落正式 D0 补充。
4. ADR-0413/0414 均 PROPOSED——ACCEPTED 等夏明星确认（指令红线）。
