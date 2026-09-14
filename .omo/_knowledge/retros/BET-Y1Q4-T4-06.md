---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-11
---
# Retro — BET-Y1Q4-T4-06: Cockpit 一键署名外发真实网关与业务消费追踪

- status: delivered (cockpit #140 + 主仓 PR; 真实收件箱 E2E 留 operator)
- window: Y1Q4 · track: T4-OUTCOME · completed: 2026-09-09

## 交付 (在 T10-116 spool 状态机之上)

1. **DLP 风控** — 复用 ecos dlp_broker (T10-01 引擎, DRY 零新轮子): send 前
   scan body, high 命中强制阻断 (`blocked-risk`); `--risk-acknowledge` 显式
   flag 即 circuit_breaker 的"人工确认"。
2. **重放拦截** — body_digest (sha256 channel|to|body) 入 envelope; 同 digest
   已 sent → `blocked-replay`; `--allow-replay` 供合法重发。
3. **单日频次硬熔断** — 计数源 receipt.json, cap 读
   `spine-gateway-policy.yaml` (默认 50/日), 无 flag 可解。
4. **OutboundMessageReceipt** — `outbound-message-receipt/v1` 每次尝试/阻断
   均落凭据 (msg_dir/receipt.json); value 台账 entry 增 digest + receipt 字段。
5. **真实通道** — 内建 smtp (smtplib+EmailMessage) / api (urllib); 凭据
   `~/.config/spine/` 部署配置不入仓; 缺失 fail closed。

## 关键决策

1. **write_surfaces 修正**: 立项臆想的 `projects/spine` 不存在 — T10-116 已
   把 Spine 落在 cockpit 命令空间 (先例)。本 BET 修正 ledger 路径与 verify
   cmd 指向真实落点, 不新建空壳项目 (YAGNI)。
2. **契约收紧**: 原 `channel smtp 无 sender` 静默假装成功 → 改为凭据缺失
   fail closed。既有测试同步更新 (成功路径走 mock builtin), 271 全量回归绿。
3. **DLP 引擎故障 fail-open**: 风控引擎不可用时不瘫痪网关 (receipt 记录
   dlp-unavailable 供审计) — 频次/重放判定是本地状态不依赖引擎, 不受影响。
4. **human_gate 的实现语义**: non_goals "未经夏明星确认不执行外发" —
   网关的每次发送都由人显式调用 `spine send`; agent 侧只 dry-run 入队。
   真实收件箱 E2E 留 operator 执行 (见下)。

## 给 operator 的一键实测 (done_when ①)

```bash
# 1. 部署凭据 (一次性):
mkdir -p ~/.config/spine && cat > ~/.config/spine/smtp.json <<'EOF'
{"host":"smtp.example.com","port":587,"user":"...","password":"...","from_addr":"...","use_tls":true}
EOF
# 2. 审查+一键外发测试邮件至真实收件箱:
cockpit spine send --channel smtp --to <你的真实邮箱> --body "T4-06 网关首封测试邮件"
# 3. 验证 receipt: .omo/state/spine-outbox/msg-*/receipt.json (status=sent)
```

## 避坑沉淀

1. **ledger 契约**: in_progress 即要求 completion_evidence matrix 预置
   (COMPLETION_MATRIX_REQUIRED_STATUSES), candidate 时 lint 不炸、claim 后炸
   — claim 后立即补 matrix 再跑 lint。
2. **value_indicator_policy 缺失 ≠ false**: 不写该字段时 resolve 出的策略
   会让 matrix 派生 blocked — 每个 BET 显式写 value_indicator_policy。
3. **占位符骗不过校验器**: merged_reachable_commit 必须真实 40-hex;
   closeout 前用 origin/main HEAD 过校验, merge 后刷新为最终 squash SHA。
4. **并行分支当停车场常态化**: 提交前必须 `git branch --show-current` +
   `git log origin/main..HEAD` 确认面; 本轮 stash pop 在 retros 撞冲突属
   预期 (resident 持续重写), checkout HEAD 版即可, stash 原样保留。
