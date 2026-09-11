---
schema_version: specification/v1
spec_version: 1.0.0
title: 移动端与桌面端本地离线安全沙箱与主权凭据金库
bet_id: BET-Y1Q4-T10-05
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-11
last-reviewed: 2026-09-11
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-11
decision_ref: decision://accepted/BET-Y1Q4-T10-05
---

# 本地离线安全沙箱与主权凭据金库（BET-Y1Q4-T10-05）

## 背景（Context）

邮件/公文/签名私钥目前缺乏本地隔离托管边界，断网环境下 Spine 拟草与署名能力无保障。
本 spec 为 BET-Y1Q4-T10-05 建立契约：以 Mac 本地 Secure Enclave + 本地文件系统构建零泄漏沙箱与凭据金库，
ledger `goal/done_when/verify` 为准，`write_surfaces` 收敛到 `config/security/`、`bin/security/vault.py` 与 retro。

## 目标（Goal）

在 Mac 本地 Secure Enclave 与本地文件系统中构建零泄漏安全沙箱与凭据金库，
实现邮件/公文/签名私钥的本地隔离托管，断网环境下依然支持全功能安全运算与拟草。

## 非目标（Non-Goals）

- 不上传凭据至任何公有云密钥管理服务。
- 不做跨设备同步/远端备份，本 bet 只做单机本地闭环。
- 不替代 OS 级钥匙串审计与合规认证，只做应用层隔离与凭据托管。

## 完成标准（Done When）

1. 完成 Local Secure Vault 零明文存储实现（落盘无明文凭据）。
2. 断网离线状态下全套 Spine 拟草与署名演练通过。
3. 集成测试覆盖防注入与权限隔离。
4. 凭据校验失败时自动锁定沙箱并触发警告（circuit_breaker 生效）。

## 验证（Verify）

- `PYTHONPATH=bin python -m security.test_offline_sandbox` → exit 0。
- `make gac-local-gate` → exit 0。
- `uv run --with pyyaml python bin/plan/bet-ledger.py lint` → exit 0（结构合法）。

## 决策引用（Decision Ref）

- `decision://accepted/BET-Y1Q4-T10-05`（2026-09-11 UTC 用户授权补 spec 绑定，可审计）
