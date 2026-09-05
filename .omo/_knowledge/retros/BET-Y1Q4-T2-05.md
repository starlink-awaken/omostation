---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-02
last-reviewed: 2026-09-02
bet: BET-Y1Q4-T2-05
title: 管线 supervisor 常驻化
symptom: _run 截断致 OCR JSON 解析失败; resident-status 卡 ledger/watermark 初始化
solution: 全量捕获+前导剥离; heartbeat 角色实例补齐部署态
type: ephemeral
status: archived
---

# BET-Y1Q4-T2-05 复盘

## 做对了什么

1. **纯编排层设计**：supervisor 不实现任何站点逻辑，全部 subprocess 调归属
   CLI——五站各自的 venv/依赖/verify 契约零侵入，降级语义在编排层统一。
2. **Mac mini 远程嵌入首战**：晨报条目经 embed node (T3-02 P3) 向量化成功
   ——双机算力分工从架构图变成运行时事实。
3. **降级语义全程实测**：坏文件→degraded 续跑→state alerts→pulse health
   捕获——三段链路一次验证到底（不是纸面 circuit_breaker）。
4. launchd 三守护（morning/embed-node/resident-daemon）+ tailscale 心跳
   ——常驻化的运维面一步到位。

## 踩了什么坑

| 坑 | 修复 |
|----|------|
| _run 截尾 300 字符丢 JSON 头 | OCR 站全量捕获 + find("{") 前导剥离 |
| resident-status "ledger sqlite missing" | 实为首次跑 daemon 前旧日志误导; ledger 本在 |
| resident-status "daemon never ticked" (rc=2) | status 要 heartbeat watermark——起 --role heartbeat 实例补齐部署态 |
| uv venv 首建吞 stdout | 排除后确认 JSON 输出纯净 |

## 待观察（真实闸门）

1. 连续 3 天 07:30 自动晨报（launchd 已挂, morning_runs 逐日记录）
2. 中继抖动下 embed 远程/本地降级切换频率（backend 字段可统计）

## 部署知识沉淀

- resident daemon 常驻 = 主 daemon (KeepAlive) + heartbeat 角色实例（watermark
  供 status 探活）——单 daemon 不写 status 期望的 watermark，这个部署形态值得
  进 resident 体系文档。
