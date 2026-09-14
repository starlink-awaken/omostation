---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-01
last-reviewed: 2026-09-01
bet: BET-Y1Q4-T2-02
title: IM 会话感知协议面
symptom: 首测暴露白名单 gate 语义漏洞（可解析指令被关键词闸误杀）
solution: gate 扩展为 @|关键词|指令 三通道命中
type: ephemeral
status: archived
---

# BET-Y1Q4-T2-02 复盘

## 做对了什么

1. **测试先暴露设计漏洞**："催一下回函"（无"催办"关键词但指令明确）被 gate
   误杀——单测首跑就抓到，当场修 gate 语义而不是放宽测试。
2. **红线可断言**：隐私红线（白名单丢弃）和审批红线（pending_approval）
   都是代码可断言的不变量，进了 verify 契约——不是文档口号。
3. 评测集含 5 条对抗例（"通过隧道""写得好"等非指令场景），accuracy 0.96
   是在对抗集上算的，不是纯正例自嗨。

## 踩了什么坑

| 坑 | 修复 |
|----|------|
| 关键词闸误杀可解析指令 | gate 扩展指令命中通道 |
| "方案"等宽泛关键词让闲聊过闸 | 接受（提及方案值得注意），测试预期对齐 |
| F841 args 未使用 | parse_args 不接返回值 |
| workspace python import agora 链拉 ecos 依赖 | 生成卡片用 agora venv，测试用文件加载器 |

## human gate 待办（下一站前置）

真实 IM 接入需要：
1. 企微自建应用凭证（ corp_id + secret + 回调 URL）
2. 飞书机器人 webhook
3. 微信桌面端钩子（itchat 类方案有封号风险，需本人评估）
4. 白名单群组清单最终确认（当前 4 个为占位）

## 模板病计数

T2-02 台账 report 路径 2026-10-05——**第 5 例**。建议专项批量清理。
