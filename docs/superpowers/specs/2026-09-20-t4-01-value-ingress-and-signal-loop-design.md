---
schema_version: specification/v1
spec_version: 1.0.0
title: 真实业务信号感知与价值凭证闭环采样 (BCOS W5 Value Ingress)
bet_id: BET-Y2Q1-T4-01
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-20
last-reviewed: 2026-09-20
implementation_authorized: true
value_indicator_policy: true
risk_level: L2
human_gate: true
type: ssot
---

# 真实业务信号感知与价值凭证闭环采样 (BCOS W5 Value Ingress)

## 1. 背景与核心问题

1. **算力就绪而价值空转**：`omlxc` 与 `aetherforge` 本地异构算力中枢已在 MBP M5 Max、Mac mini M4、Y7000P 三物理机就绪，但系统当前业务价值证明（`value_proof_readiness`）依然处于 `NOT_PROVEN`（合格样本 0/30），缺乏夏明星真实消费并签署的有效凭证。
2. **外部信号流缺少自主循环**：`mail_daemon` 与 `signal_poller` 已具备感知能力，需持续借助本地算力（含 Bearer 鉴权与二级兜底）进行真实邮件任务提取与日报汇总。
3. **权威收据签发与价值入库机制未贯通**：虽然底层已有 `value-operator-doctor.py --issue-authority-receipt` 与 `value-recorder.py`，但此前未能在真实业务场景中串联。

## 2. 交付范围 (Scope)

1. **接入与调度强化**：完善 AetherForge Bearer API Key 鉴权与 `mail_daemon.py` 运行时兼容性，支持本地与局域网平滑兜底。
2. **业务草稿生成与人机署名流水线**：在公文审阅（`document-review`）或待办邮件场景中，驱动生成真实草稿，支持夏明星审阅修改并记录 Diff。
3. **权威收据绑定与 v2 证据入库**：通过 `DefaultPrincipalAuthority` 为夏明星（`principal:xiamingxing`）签发权威收据，调用 `value-recorder.py record` 生成合格的 v2 价值证据，使 `qualifying_samples` 从 0 突破。

## 3. 非目标 (Non-goals)

- 不进行非法的证据合成伪造或历史数据回溯填充（坚持 `do not backfill` 原则）。
- 不破坏现有 11 个架构门禁与 SFOP 八律。
- 不引入外部未授权依赖。

## 4. 验收标准 (Acceptance Criteria)

1. `python3 bin/ssot/value-recorder.py validate` 执行通过，成功记录至少 1 条符合规范的 v2 价值合格记录（绑定已冻结基准 `value-recorder-baseline-20260919-unique-exec`、合法 receipt_digest、净节约时间 $\ge 60$ 秒）。
2. `mail_daemon.py` 在有未读邮件时能够稳定执行分类与任务提取，无崩溃或阻断。
3. 台账 lint 检查通过：`uv run --with pyyaml python bin/plan/bet-ledger.py lint`。

## 5. 验证命令 (Verification Commands)

```text
python3 bin/ssot/value-recorder.py validate
uv run --with pyyaml python bin/plan/bet-ledger.py lint
git diff --check
```
