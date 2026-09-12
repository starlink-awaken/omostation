---
schema_version: specification/v1
spec_version: 1.0.0
title: 真实邮件/日历多通道 Ingress 自动感知与 LECP 实体分诊管道
bet_id: BET-Y1Q4-T2-06
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-12
last-reviewed: 2026-09-12
risk_level: L1
human_gate: true
type: ssot
last_updated: 2026-09-12
decision_ref: decision://accepted/BET-Y1Q4-T2-06
---

# 真实邮件/日历多通道 Ingress 自动感知与 LECP 实体分诊管道（BET-Y1Q4-T2-06）

## 背景（Context）

当前 omostation 感知通道依赖人工触发与 mock 数据输入，无法自动感知真实外部信号（邮件、日历事件）。
本 spec 为 BET-Y1Q4-T2-06 建立契约：构建本地 daemon/cron 定时探测邮件及日程更新，
统一抽取为 LECP 规范信号并存入主干感知通道（`bos://spine/ingress`），
实现近实时邮件收取与日历行程抓取，摆脱人工触发。

## 目标（Goal）

打通真实外部信号源（IMAP/Exchange/CalDAV/ICS），实现：
1. 本地 daemon 或 cron 定时探测邮件及日程更新
2. 收到新邮件 60s 内自动产出标准 LECP Signal 事件并投递至 `bos://spine/ingress`
3. 集成测试覆盖真实 eml 与 ics 解析

## In scope

1. `projects/spine/src/spine/ingress/` — Python 包，包含邮件解析器（eml）、日历解析器（ics）、LECP 实体分诊器
2. `bin/daemon/mail_ingress.py` — 本地 daemon 入口，定时轮询 + 事件投递
3. LECP 实体分诊：将邮件/日历事件映射到 LECP v3.0 规范（domain, privacy_level, status, payload）
4. 集成测试：使用真实 eml/ics 样本文件验证解析与分诊链路

## Out of scope（non_goals）

- 不直接修改邮件服务器上的未读状态
- 不对外发送任何回复
- 不实现完整的 IMAP IDLE 长连接（首版用定时轮询）
- 不处理附件内容深度解析（仅提取元数据）

## LECP 实体分诊规则

| 来源 | LECP domain | privacy_level | 分诊逻辑 |
|------|-------------|---------------|----------|
| 工作邮件 | p0_work | internal | 发件人域名匹配工作域 |
| 个人邮件 | p3_mind | secret | 默认归类 |
| 日历-会议 | p0_work | internal | 含参会人 > 1 |
| 日历-个人 | p3_mind | secret | 单人造访 |
| 日历-健康 | p1_health | secret | 关键词匹配（医院/体检/医生） |

## 技术方案

### 邮件 Ingress
- 使用 Python `email` 标准库解析 .eml 文件
- 支持 IMAP IDLE 降级为定时轮询（默认 60s 间隔）
- 提取：发件人、收件人、主题、正文（纯文本优先）、日期、Message-ID

### 日历 Ingress
- 使用 `icalendar` 库解析 .ics 文件
- 支持 CalDAV 订阅 URL 与本地 .ics 文件
- 提取：事件 UID、标题、开始/结束时间、地点、描述、参会人

### LECP 信号生成
- 遵循 `protocols/lecp-schema.yaml` v3.0 规范
- entity_id 格式：`evt-{YYYYMMDD}-{source}-{hash}`
- 状态流转：raw → triaged → drafted → signed

## 验收标准（done_when）

- 部署本地 daemon 或 cron 定时探测邮件及日程更新
- 收到新邮件 60s 内自动产出标准 Signal 事件并投递至 `bos://spine/ingress`
- 集成测试覆盖真实 eml 与 ics 解析

## 验证（verify）

- `uv run python -m spine.ingress.test_pipeline` → exit 0
- `make gac-local-gate` → exit 0

## Circuit Breaker

外部信号解析异常时记录告警日志并安全降级，不阻断主干运行。

## write_surfaces

- `projects/spine/src/spine/ingress/`
- `bin/daemon/mail_ingress.py`
- `.omo/_knowledge/retros/BET-Y1Q4-T2-06.md`
