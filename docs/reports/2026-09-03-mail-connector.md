---
schema_version: report/v1
lifecycle: history
type: delivery-report
owner: governance-team
created: 2026-09-03
last_updated: 2026-09-03
bet: BET-Y1Q4-T2-04
---

# 统一邮箱连接器（交付报告）

## 交付概要

| 项 | 结果 |
|----|------|
| 多源连接器 | `mail_connector.py` — apple-mail-export / mailbox-master 双源目录，**同一 parse 面复用** |
| 结构化事件 | MailEvent(from/subject/date/snippet/source) ≥3 字段契约 ✅ |
| 中文头解码 | RFC 2047 B64 encoded-word 正确解码（实测"关于数字医疗试点推进"）✅ |
| 总线汇入 | pipeline-events.jsonl（topic mesh:mail:signal, priority normal — T2-01 ledger 语义）✅ |
| circuit_breaker | 坏文件/空壳邮件 skip+count 不中断 ✅ |
| watch 模式 | 30s 轮询 + 增量去重 |
| verify | `test_parse` 5 检查全绿 exit 0 ✅ |

## 零凭证设计

Apple Mail 导出 .eml / 邮箱大师导出均走本地文件（无 IMAP/无授权码）；
IMAP 通道为后续可选扩展（凭证制另议）。

## 工程小坑（入档）

1. 手写 B64 fixture 编码错值（"关键学重新赤电话"乌龙）——fixture 一律 `base64.b64encode` 生成
2. `email.parser` 对垃圾字节流宽容解析成空壳邮件——空 From+Subject 判无效补 circuit_breaker
3. RFC 2047 相邻 encoded-word 必须空格分隔
