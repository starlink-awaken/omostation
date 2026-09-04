---
status: accepted
lifecycle: spec
owner: resident
created: 2026-08-25
last-reviewed: 2026-08-25
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-14
type: ssot
last_updated: 2026-09-03
---

# Resident 告警外发渠道接线 (alert webhook 接线 + forwarder 修复)

> 日期：2026-08-25
> 状态：accepted
> BET：BET-Y1Q3-T10-14
> 上游：resident 体系价值兑现优化轮（T6-14 复盘「接线完整、价值未兑现」后四项之一）

## 背景与问题

resident 常驻体系的告警链路（`bin/ssot/alert-forwarder.py` 增量读 observability 事件 →
`bin/ssot/alert-connectors.py` 按 severity/domain 路由 → 渠道 webhook）存在两个阻断问题，
导致告警无法外发到人：

1. **连字符文件名无法 import**：`alert-forwarder.py` 用 `from alert_connectors import ...`
   导入 `bin/ssot/alert-connectors.py`（连字符文件名非法模块名），任何一次调用都会
   `ModuleNotFoundError`，告警链路整体不可达。
2. **契约方法错误**：旧代码调用 `conn.send(...)`，但 `AlertConnector` 基类契约只有
   `deliver(alert) -> ConnectionReceipt`（含 `result_state`/`receipt_id`/`provider`），
   无 `send()` 方法 → `AttributeError`。

## 目标

1. **修复 alert-forwarder.py**：用 `importlib.util.spec_from_file_location` 按路径加载
   `alert-connectors.py`（绕开连字符文件名），并改调 `conn.deliver({...})` 契约方法，
   按 `receipt.result_state == "delivered"` 判定成功。
2. **渠道声明就绪（先只接线不配 URL）**：`alert-channels.yaml` 声明 `alert-wecom` 渠道
   （`url_ref: env://ALERT_WECOM_WEBHOOK`、routes=critical/governance+runtime、enabled=true），
   凭据以 opaque 引用不落盘。未配 URL 时 fail-closed（返回 `failed url not configured`，
   exit=1 不崩），不产生误报成功。
3. **回执事件**：`_emit_receipt()` 写 `governance:alert_delivered` /
   `governance:alert_delivery_failed` 到 observability events.jsonl，告警送达状态可审计。

## 非目标

- 不配置真实 webhook URL（用户决定「先只接线不配 URL」，激活仅需设置
  `ALERT_WECOM_WEBHOOK` 环境变量）。
- 不改 `alert-connectors.py` 的渠道实现（`WeComWebhookConnector.deliver` 已正确）。
- 不改 omo 侧 `projects/omo/src/omo/resident/alert.py`（已是正确参照实现，cron 走
  `omo.cli resident alert`）。

## 验收

- [ ] `bin/ssot/alert-forwarder.py` 不再出现 `ModuleNotFoundError` / `AttributeError`
- [ ] `alert-connectors.py list` 展示 4 channel 且 `url_configured=NO`
- [ ] `alert-connectors.py send --channel alert-wecom` fail-closed（exit=1，写 failed 回执）
- [ ] `alert-forwarder.py --dry-run` 正常路由事件不崩
