---
schema_version: specification/v1
spec_version: 1.0.0
title: Unified mail connector (multi-source)
bet_id: BET-Y1Q4-T2-04
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-03
last_updated: 2026-09-03
type: ssot
last_updated: 2026-09-03
---

# Unified mail connector (T2-04)

## Intent

专门连接器多源汇聚邮件信号（from/subject/date/snippet）喂 T7-03 雷达站；
本地 .eml 解析零凭证优先。邮件事件汇入 T2-01 总线（normal 优先级）。

## Architecture (KISS)

```
projects/omo/src/omo/mail_connector.py
├─ MailEvent(from_, subject, date, snippet, source) — ≥3 字段契约
├─ parse_eml(path) — 标准库 email.parser (header + 文本正文前 200 字)
│   健壮性: 编码/缺头/坏文件 → skip+count 不中断 (circuit_breaker)
├─ SOURCE_DIRS (单源配置):
│   apple-mail-export: ~/Inbox/mail-inbound/apple/   (Apple Mail 导出 .eml)
│   mailbox-master:    ~/Inbox/mail-inbound/master/  (邮箱大师导出)
│   同一 parse 面复用 (done_when 2)
├─ collect() → events → 追加 .omo/state/pipeline-events.jsonl
│   (topic mesh:mail:signal, priority normal — T2-01 总线 ledger 语义)
└─ main: test_parse (verify) / collect / watch (目录轮询)
```

## Verify (BET contract)

- `uv run python -m omo.mail_connector test_parse` → exit 0
- `make gac-local-gate` → exit 0
