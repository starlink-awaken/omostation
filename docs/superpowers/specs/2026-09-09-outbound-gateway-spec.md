---
schema_version: specification/v1
spec_version: 1.0.0
title: Cockpit 一键署名外发真实网关 — 风控/重放/频次熔断/回执/真实通道
bet_id: BET-Y1Q4-T4-06
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-09
---


# T4-06: 外发真实网关增量 (在 T10-116 spool 状态机之上)

## 现状 (T10-116 已交付, 本 BET 不重做)

spool 原子状态机 (queued→sent/failed) + 可插拔 `--sender` 钩子 + value 台账
原子追加 + review diff 工作台 + dry-run。**真实引擎缺口**: 风控/重放/频次/
回执/真实通道全部缺失; 立项 write_surfaces 臆想的 `projects/spine` 不存在
(实际落点是 cockpit 命令空间, 本 spec 修正之)。

## 增量设计 (KISS — 全部挂在 cmd_spine_send 现有流上)

1. **DLP 风控 (复用 ecos dlp_broker, 不造新轮子)**
   send 前对 body 跑 `dlp_broker.scan()`; 命中 `risk == "high"` → 强制阻断
   (envelope `status: blocked-risk`), `--risk-acknowledge` 显式 flag 即
   circuit_breaker 的"人工确认"语义。非 high 命中仅告警不阻。

2. **重放拦截**
   `body_digest = sha256(channel|to|body)`; 扫 spool 历史 envelope, 存在同
   digest 且 `status == "sent"` → 阻断 (`blocked-replay`); `--allow-replay`
   显式放行 (收件人未收到的合法重发)。

3. **单日频次熔断 (硬, 无 flag 可解)**
   数 spool 内当日 (本地日期) `status == "sent"` 的消息数, ≥ policy cap →
   阻断 (`blocked-cap`)。policy: `.omo/_truth/registry/spine-gateway-policy.yaml`
   `daily_send_cap: 50`。

4. **OutboundMessageReceipt 形式化**
   每次 send 尝试写 `msg_dir/receipt.json` (schema `outbound-message-receipt/v1`:
   msg_id/channel/to/body_digest/status/reason/sent_at/provider_ref);
   value 台账 entry 增加 `body_digest` + `receipt` 字段。

5. **真实通道 (凭据不入仓, fail closed)**
   - `--channel smtp`: `~/.config/spine/smtp.json` {host,port,user,password,
     from_addr,use_tls} — stdlib smtplib + EmailMessage; 配置缺失 → 明确报错
     指引 (不入队不发送)。
   - `--channel api`: `~/.config/spine/api.json` {url, headers} — urllib POST
     JSON {to, body, msg_id}。
   - 原有 `--sender` 可插拔钩子保留, 优先级: 显式 `--sender` > channel 内建。

## 安全边界 (non_goals 强化)

- 不在未经夏明星确认前执行外发: 发送动作永远由人显式调用 `spine send`
  (agent 侧只能 dry-run 入队); `--risk-acknowledge`/`--allow-replay` 均为
  人工显式 flag, agent 不得代传。
- 凭据只存在 `~/.config/spine/` (deployment config), 仓库零凭据。

## 验收

- pytest: 风控阻断/acknowledge 放行、重放拦截/allow 放行、频次熔断硬阻断、
  receipt 落盘、smtp 配置缺失 fail closed、状态机兼容 (原 4 测试不回归)。
- 真实收件箱 E2E (done_when ①): 留 operator 人工执行一条 `spine send
  --channel smtp --to <真实收件箱>` 完成一键确认外发 — 这是 human_gate 的
  运行时体现, 不由 agent 代跑。
