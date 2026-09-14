---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-03
last-reviewed: 2026-09-03
bet: BET-Y1Q4-T2-04
title: 统一邮箱连接器
symptom: 手写 B64 fixture 错值; 垃圾字节流被宽容解析成空壳邮件
solution: fixture 用 base64 库生成; 空 From+Subject 判无效
type: ephemeral
status: archived
---

# BET-Y1Q4-T2-04 复盘

## 做对了什么

1. **零凭证优先**：Apple Mail/邮箱大师都走本地导出文件——IMAP 凭证通道
   后置另议，隐私红线不碰。
2. **同一 parse 面**：双源只是目录配置差异，解析逻辑单点（done_when 2
   的"复用"是结构性保证而非约定）。
3. 事件直接落 T2-01 总线 ledger——雷达站二次打标有数据面可接。

## 踩了什么坑

| 坑 | 修复 |
|----|------|
| 手写 B64 值错（解出"关键学重新赤电话"） | fixture 一律 base64 库生成, 禁止手写 |
| 垃圾字节流被 email.parser 宽容成空壳 | from+subject 双空判无效 (circuit_breaker) |
| RFC 2047 相邻 encoded-word 缺空格 | fixture 补空格 |

## 后续

- radar 站消费 mesh:mail:signal 事件做邮件打标（阶段 2 顺手项）
- watch 模式挂 launchd 或并入 pipeline supervisor 第三通道（待真实邮件量评估）
