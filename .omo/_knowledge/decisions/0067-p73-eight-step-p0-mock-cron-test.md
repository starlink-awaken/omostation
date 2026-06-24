---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0067: P73 governance-agent 8 步闭环 + P0 mock 集成 + cron --test 模式

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P73
- **Extends**: ADR-0066 (P72 7 步 + sup_state + IQR + P0 mock)
- **Superseded by**: (无)

## Context and Problem Statement

P72 收口后, P73 调研 4 项候选, 实施 3 项:

1. **governance-agent 8 步** (P72 7 步 + P0 mock 触发步骤)
2. **alert-aggregator P0 触发 alert-mock-p0-notify** (P72 mock 工具接入 P73 集成)
3. **install-governance-agent-cron.sh --test 模式** (P62 install 脚本完善)

跳过 1 项:
- graphify 重生 (工具限制)

## Decision

### D1: governance-agent 8 步闭环 (P73 R1)

**修改**: `scripts/omo/governance-agent.sh` P0 检测

**新增 [2.6.5/3] P0 mock 触发步骤**:
```bash
# 检测最近 alert-notifications.jsonl 是否有 P0 且 1h 内未通知
LAST_P0=$(python3 -c "...json 解析 + 1h cutoff...")
if [ -n "$LAST_P0" ]; then
    python3 bin/alert-mock-p0-notify.py --message "$LAST_P0" --all-channels
fi
```

**8 步完整结构**:
```
[1/3]   governance-readiness
[2/3]   mof-drift
[2.5/3] governance-readiness-trend
[2.6/3] alert-aggregator
[2.6.5/3] P0 mock (P73 增)  ← 自动检测 + 触发
[2.7/3] alert-history
[2.8/3] dim-weight
[3/3]   评估
```

**实测**: P0 触发 → 检测 → mock 通知 3 通道 ✅

### D2: alert-aggregator P0 集成 (P73 R2)

**集成路径**:
```
alert-aggregator (P67 阈值 + P68 抑制 + P70 跨级别)
  ↓
.jsonl 写入 (P64 --alert)
  ↓
governance-agent 步骤 2.6 (检测 jsonl)
  ↓
alert-mock-p0-notify (P72) 3 通道
  ↓
runtime/logs/p0-notifications.log
```

### D3: install-governance-agent-cron.sh --test (P73 R3)

**修改**: `scripts/omo/install-governance-agent-cron.sh`

**新增 --test 模式**:
```bash
./install-governance-agent-cron.sh --test
# 跑 1 次 dry-run, 不修改 crontab, 不写 alert log
```

**实测**:
- ✅ 8 步 governance-agent 跑通
- ✅ readiness 98/100
- ✅ omo event 自动 emit (agent_mutation_complete)
- ✅ 退出码 0

## Consequences

### Positive

- **8 步闭环**: P0 自动检测 + 触发 mock 通知
- **cron --test 模式**: 运维可验证 cron 任务
- **3 通道通知**: email/sms/slack 本地文件
- **P72 mock 工具集成**: 不再孤立

### Negative

- **mock 是 mock**: 实际生产需替换真实 provider
- **P0 检测是 polling**: 不是 event-driven (未来 P74+ 优化)

### Neutral

- **不增 linter 维度**: 沿用 P58 独立 bin 工具
- **不增 mof-drift 维度**: 8 维度持续

## Compliance

### 验证指标

| 指标 | P72 末 | **P73 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.61 | **v0.0.62** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 12 | **12** | 持平 |
| governance-agent 步骤 | 7 | **8** (+P0 mock 触发) | +1 |
| install-governance-agent-cron.sh 命令 | 3 | **4** (+--test) | +1 |
| ADR 数量 | 26 | **27** | +1 (0067) |

### 关联 ADR

- **ADR-0066**: P72 7 步 + sup_state + IQR + P0 mock (P73 直接扩展)
- **ADR-0065**: P71 6 步 + 跨级别
- **ADR-0062**: P62 governance-agent (P73 增强 cron)

### 关联 L0 规则

- `X2-FRESH-COMMIT-FATIGUE` — 8 步闭环避免漂移
- `CR-GOV-CLOSED-LOOP-01` — P0 mock 写入即 commit 闭环

## Notes

本 ADR 记录 P73 3 项候选实施:
- ✅ governance-agent 8 步 (含 P0 mock 触发)
- ✅ alert-aggregator P0 集成
- ✅ install-governance-agent-cron.sh --test
- ⏸ graphify 重生 (P73 跳过)

后续 P74+ 候选:
- graphify 重生 (需 url 入口)
- management/ 142 实施拆分 (P75+)
- P0 mock 替换真实 SMS/email
- 事件驱动 P0 检测 (替代 polling)
- dim-weight 真实数据调优
- alert-history 加更多维度

---

*最后更新: 2026-06-23 · P73 · omostation 治理方法论持续深化*