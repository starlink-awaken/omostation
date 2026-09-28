---
schema: md/v1
status: active
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-28
type: retro
schema_version: retrospective/v1
title: "BET-Y2Q4-T4-04 Closeout Retro — 业务第二单：真实纪要 → 决议行动包"
bet_id: BET-Y2Q4-T4-04
created: "2026-09-28"
run_id: 20260928T105629Z-project-doc-change-d07a9de1
---

# BET-Y2Q4-T4-04 Closeout Retro

> **TL;DR**: 业务第二单交付：市政府会议纪要 144 号（"三医"信息化，4 大类 15 项）
> → 决议行动包（全量映射 + 房山区视角 5 条 + OCR 缺口 4 处显式标注 + 修订派发节），
> 落 principal Documents 域 `_drafts/`（零正文入仓）。输入自提取模式首跑成功：
> principal 只说"从 documents 提炼"，真实输入由 agent 实勘发现并确认。

## 计划 vs 实际

| 项 | 结果 |
|---|---|
| 输入实勘 | ✅ 卫健委域发现 144 号纪要 OCR 文本（147 行），早于 principal 指定——授权"自提取"消除了候选①的最大摩擦 |
| 15 项映射 | ✅ 逐项牵头/会同/页码锚点 |
| 房山区视角 | ✅ 5 条（超 ≥3 门槛）：区属医院接入/区级影像平台停建信号/AI 区级覆盖/数据质量/互联网+护理 |
| OCR 缺口 | ✅ 4 处显式标注（含首页批示区乱码——可能改变优先级，已提请对照原件） |
| 零正文入仓 | ✅ git grep 命中 0 |

## 失败与反思

1. **忘 claim 就开铸**——本 bet 的 spec 先写在了未 claim 的路径上（Write 会创建目录），
   铸造时才发现无 git 仓。散目录 mv 走 → claim → 归位。教训：**claim 是一切的第一步**，
   spec 起草也应发生在 worktree 内。
2. **grep tail -1 选 run 的脆弱性再现**——BET_NOT_FOUND 因 grep 到并发 run 的
   stale 引用；合 main 后按精确 run id 重试即过。run 选择应记 id 于 claim 前变量。

## 价值路径

行动包待 principal 修订/派发（报告留槽）——派发/采用即业务价值计量起点；
"修订记录 + 人工基线"是第二期对比的基线数据。
