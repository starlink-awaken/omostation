---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-28
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: "L1+L2 — KOS 检索前置机制 + 纪要 144 号区级 5 项落实准备"
bet_id: BET-Y2Q4-T4-07
---

# BET-Y2Q4-T4-07 — L1 KOS 检索前置 + L2 纪要区级项落实准备

## 授权链

联动地图（workspace-documents-linkage-map-2026-10-07.md）→ principal 批准第一梯队（L1+L2）。

## L1 交付物：KOS 检索前置

1. CLAUDE.md Step A 增补：BET spec 起草前先跑 KOS 检索（强制步骤）；
2. agent-workflow.py start 输出末尾追加一行 KOS 检索命令提示（纯 echo，不改逻辑）；
3. BET spec 模板增补「KOS 先例」节。

## L2 交付物：纪要 144 号区级 5 项落实准备

产出 5 份落实准备文件（principal Documents 域 `@工作文档/卫健委/_drafts/`）：

| 项 | 准备内容 | 转办科室 |
|---|---|---|
| ① 区属医院接入预约挂号统一平台 | 进度跟踪模板（9 月底时限已过需确认实际状态） | 医政科 |
| ② AI 病历生成"区级覆盖" | 产品比选评估框架（参照协和模式+144 号要求） | 信息科 |
| ③ 数据质量治理 | 治理方案框架（西城经验+采集标准） | 公卫科 |
| ④ 互联网+护理试点 | 试点方案框架（社区机构为重点） | 社卫科 |
| ⑤ 影像平台政策留档 | 政策分析笔记（144 号"不再建设区级"对房山区的影响） | 信息科 |

每份准备文件带 144 号原文锚点 + 建议下一步动作 + 转办科室。零外发。

## 红线

- 5 份准备文件只落 Documents 域，仓库零正文；
- agent-workflow.py 修改仅追加 echo 行不改逻辑；
- CLAUDE.md 修改最小化（追加一段不重构）。

## 验收

1. CLAUDE.md 含 KOS 检索强制步骤；
2. agent-workflow.py start 输出含 KOS 提示（echo 行）；
3. 5 份准备文件落 _drafts/（各带 144 号锚点+转办科室）；
4. lint 0 / gate PASS。
