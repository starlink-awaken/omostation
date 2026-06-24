---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# P65 — cockpit 集成 + 告警聚合 收口

**日期**：2026-06-23
**阶段**：P65 R1-R3
**目标**：cockpit 消费 dashboard + 告警风暴防御

---

## 1. 治理全景 (P65 完成)

| 指标 | P64 末 | **P65 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.53 | **v0.0.54** | +1 |
| governance | 100.0 A+ | **100.0 A+** | 持平 |
| mof-drift 维度 | 8 | **8** | 持平 |
| governance readiness | 96/100 A+ L4 | **96/100 A+ L4** | 持平 |
| 独立 bin 治理工具 | 7 | **9** | +2 |
| readiness 快照 | 10 | **10** | 持平 |
| ADR 数量 | 18 | **19** | +1 (0059) |

---

## 2. 完整落地清单

### R1: cockpit-readiness wrapper (D-P65-1)

**新工具**: `bin/cockpit-readiness.py` (60 行)

**功能**:
- 委派到 `bin/dashboard-readiness-summary.py` (P64)
- 自动发现 workspace 根
- 双格式 (json/text)
- 60s timeout

**注**: 原本设计为 cockpit 子命令, 但 cli.py 有 pre-existing ruff 错误, 改 wrapper 形式

**实测**: 10 快照, score=96, alerts=[], stable (JSON 完整)

### R2: alert-aggregator 告警聚合 (D-P65-2)

**新工具**: `bin/alert-aggregator.py` (130 行)

**功能**:
- 读 `.omo/_log/readiness-alerts.jsonl` (P64 --alert 写入)
- 时间窗口过滤 (默认 24h)
- 按类型分组 (low_mean / high_volatility / sudden_drop)
- **告警风暴检测**: 同 1h 内同类型 > 3 次
- 双格式 (json/text)

**实测**:
- 健康时: 0 告警, 无风暴 ✅
- 模拟 5 次同小时: 检测到告警风暴 🚨

### R3: ADR-0059 + 收口

- `.omo/_knowledge/decisions/0059-p65-...md` (2 D)
- INDEX 双更新
- 本收口报告

---

## 3. 关键决策

### D-P65-1: cockpit 集成用 wrapper 而非子命令
- 原因: cli.py pre-existing ruff 错误 (P65 范围外)
- 权衡: wrapper 是过渡方案, 完整集成需 P66+ 修复 cli.py
- 收益: 立即可用, 不破坏 cockpit 子仓

### D-P65-2: 告警聚合 = 1h 内同类型 > 3 抑制
- 防御 alert storm
- 沿用 P64 jsonl 持久化
- 报告形式而非主动通知 (P66+ 评估)

---

## 4. 影响扩散

```
📂 bin/cockpit-readiness.py (新, 60 行) — wrapper
📂 bin/alert-aggregator.py (新, 130 行) — 告警聚合
📂 .omo/_knowledge/decisions/0059-p65-...md (新 ADR, 2 D)
📂 .omo/_knowledge/decisions/INDEX.md (+1 行)
📂 .omo/_knowledge/audits/2026-06-23-p65-...md (本收口)
```

---

## 5. 闭环验证

```
governance-agent.sh (cron 6h)
  ↓
readiness-trend --alert (P64)
  ├─ 异常: omo event emit + jsonl 写入
  └─ 正常: 0 告警
  ↓
alert-aggregator (P65 R2)
  ├─ 读 jsonl (24h 窗口)
  ├─ 按类型分组
  └─ 同 1h > 3 → 抑制报告
  ↓
cockpit-readiness wrapper (P65 R1)
  ↓
dashboard-readiness-summary (P64)
  ↓
4 卡片 JSON (summary/dimensions/alerts/history)
```

---

## 6. mof-version 历史

| 版本 | 日期 | 关键 |
|------|------|------|
| v0.0.53 | 2026-06-23 | P64: dashboard-readiness-summary + --alert 自动告警 |
| **v0.0.54** | **2026-06-23** | **P65: cockpit-readiness wrapper + alert-aggregator 告警聚合** |

---

## 7. 后续候选 (P66+)

| 建议 | 工作量 | 价值 | 时机 |
|------|------:|-----:|------|
| cockpit cli.py pre-existing ruff 错误修复 + 升级为子命令 | 中 | 高 | P66 |
| dashboard 卡片实际 UI 渲染 (cockpit dashboard integration) | 大 | 高 | P66 |
| 告警聚合主动通知 (omo event emit aggregated) | 中 | 中 | P67 |
| readiness 快照持久化 (git LFS / 独立存储) | 中 | 中 | P67 |
| 维度权重动态调整 | 大 | 中 | P68 |
| governance-readiness-trend 集成 mof-drift v8 | 中 | 高 | P68 |
| management/ 142 拆 3 类 (大重构) | 大 | 待评估 | P69+ |
| graphify 重生覆盖 1190 M1 节点 | 中 | 中 | P69+ |

---

## 8. 总结

P65 是 P64 **深化**的**集成 + 防御**阶段:

- **cockpit 集成**: wrapper 形式, 立即可用, P66+ 升级为子命令
- **告警聚合**: 24h 窗口 + 同小时 > 3 抑制, 防御 alert storm
- **9 独立 bin 工具**: P60 1 → P65 9, 治理工具链成熟
- **决策面**: 19 个 ADR 形成 P50-P65 完整治理链

**核心方法论**: "**集成 + 防御**" — P60 是 6 层落地, P64 是数据可消费化, **P65 是 cockpit 集成 + 告警防御**让治理系统闭环运行。

---

*P65 R1-R3 完成: 2026-06-23 · governance 100 A+ 持续 · mof-version v0.0.54 · readiness 96/100 A+ L4 稳态 · 9 独立 bin 治理工具*