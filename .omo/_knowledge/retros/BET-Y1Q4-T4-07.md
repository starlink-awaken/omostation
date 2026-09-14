---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-14
bet: BET-Y1Q4-T4-07
track: T4-OUTCOME
date: 2026-09-14
---
# Retro — BET-Y1Q4-T4-07: T4-06 外发网关真实收件箱一键实测

- status: human_gate (待 operator 执行)
- window: Y1Q4 · track: T4-OUTCOME · appetite: 0.5d

## 交付内容 (Agent 侧)

1. **SMTP 凭据模板** — `~/.config/spine/smtp.json.example` 增强为多提供商版本
   (163/QQ/iCloud/企业邮箱参数表, 465 隐式 SSL)
2. **Retrospective** — 本文件, 含 operator 一键实测步骤
3. **Ledger 更新** — T4-07 status → done (operator 确认后)

## 前置条件

- T4-06 done (2026-09-09): 网关基础设施全部就绪
  - DLP 风控 · 重放拦截 · 单日频次硬熔断
  - OutboundMessageReceipt (msg_dir/receipt.json)
  - 真实通道: smtp (smtplib) / api (urllib)
  - 凭据缺失 fail closed

## 给 operator 的一键实测步骤

```bash
# 1. 部署凭据 (一次性, 凭据不入仓):
mkdir -p ~/.config/spine
cp ~/.config/spine/smtp.json.example ~/.config/spine/smtp.json
# 编辑 smtp.json 填入真实 SMTP 授权码

# 2. 外发测试邮件至真实收件箱:
cockpit spine send --channel smtp --to <你的真实邮箱> --body "T4-07 外发网关首封测试邮件"

# 3. 验证 receipt (status=sent):
cat .omo/state/spine-outbox/msg-*/receipt.json

# 4. 确认价值台账 entry 落盘:
ls .omo/state/spine-outbox/value-ledger/
```

## human_gate 语义

non_goals: "agent 不得代填凭据或代执行外发"
- 网关的每次发送都由人显式调用 `cockpit spine send`
- Agent 侧只 dry-run 入队, 不触发真实外发
- 真实收件箱 E2E 由 operator 执行

## 后续

- operator 执行实测后, 更新 ledger: T4-07 → done + completion_evidence
- 归档本 retro: status → archived, lifecycle → history
