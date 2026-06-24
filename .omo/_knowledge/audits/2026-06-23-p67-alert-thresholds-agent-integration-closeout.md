---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# P67 — 告警阈值参数化 + governance-agent 集成 收口

**日期**：2026-06-23
**阶段**：P67 R1-R3
**目标**：告警灵活化（阈值参数 + 级别）+ 代理完整闭环

---

## 1. 治理全景 (P67 完成)

| 指标 | P66 末 | **P67 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.55 | **v0.0.56** | +1 |
| governance | 100.0 A+ | **100.0 A+** | 持平 |
| 告警级别 | 2 档 | **4 档 (P0/P1/P2/P3)** | +2 |
| 独立 bin 治理工具 | 9 | **9** | 持平 |
| governance-agent 步骤 | 4 | **5** | +1 (alert-aggregator) |
| ADR 数量 | 20 | **21** | +1 (0061) |

---

## 2. 完整落地清单

### R1: alert-aggregator 阈值参数化 + 级别 (D-P67-1)

**修改**: `bin/alert-aggregator.py` (P66 → P67 增量 +50 行)

**新参数**:
- `--storm-threshold N` (默认 3)
- `--total-threshold N` (默认 5)

**级别判定 (P0/P1/P2/P3)**:
```
P0 (critical): storm + total > total_threshold * 2
P1 (high):     storm + total > total_threshold
P2 (medium):   storm || total > total_threshold
P3 (low):      其余 (默认)
```

**notify 触发**: P0/P1/P2 → omo event emit, P3 → 不触发

**实测**: 8 个 low_mean → P1 触发通知

### R2: governance-agent.sh 集成 alert-aggregator (D-P67-2)

**修改**: `scripts/omo/governance-agent.sh` (P66 → P67 增量 +9 行)

**集成逻辑**:
```bash
if [ "$INCLUDE_TREND" = true ] && [ -f .omo/_log/readiness-alerts.jsonl ]; then
    python3 bin/alert-aggregator.py
fi
```

**触发条件**:
- --include-trend flag
- readiness-alerts.jsonl 存在

**实测**: governance-agent --include-trend --dry-run 跑通, 5 步完整

### R3: ADR-0061 + 收口

- `.omo/_knowledge/decisions/0061-p67-...md` (2 D)
- INDEX 双更新
- 本收口报告

---

## 3. 关键决策

### D-P67-1: 阈值参数化（避免 hardcoded）
- 不同环境 (dev/staging/prod) 需调整
- 沿用 P62 readiness 5 档思路

### D-P67-2: P0/P1/P2/P3 工业级分级
- 告警按严重度排序
- 便于响应优先级
- 工业实践（P0=立刻, P1=1h 内, P2=4h 内, P3=24h 内）

### D-P67-3: governance-agent 5 步闭环
- 1. governance-readiness
- 2. mof-drift
- 2.5. governance-readiness-trend
- 2.6. alert-aggregator (新)
- 3. 评估

---

## 4. 影响扩散

```
📂 bin/alert-aggregator.py (P66 → P67 增量 +50 行)
   + --storm-threshold / --total-threshold 参数
   + P0/P1/P2/P3 级别判定
   + emit_notification 带 level 字段
📂 scripts/omo/governance-agent.sh (P66 → P67 +9 行)
   + [2.6/3] alert-aggregator 步骤
📂 .omo/_knowledge/decisions/0061-p67-...md (新 ADR, 2 D)
📂 .omo/_knowledge/decisions/INDEX.md (+1 行)
📂 .omo/_knowledge/audits/2026-06-23-p67-...md (本收口)
```

---

## 5. 完整闭环 (P67 后)

```
governance-agent (cron 6h)
  ├─ [1/3] governance-readiness
  ├─ [2/3] mof-drift
  ├─ [2.5/3] governance-readiness-trend
  ├─ [2.6/3] alert-aggregator (P67 增)
  └─ [3/3] 评估
       ├─ readiness >= 90?
       ├─ drift LOW <= 5?
       └─ alert P0/P1/P2 → omo event emit
```

---

## 6. mof-version 历史

| 版本 | 日期 | 关键 |
|------|------|------|
| v0.0.55 | 2026-06-23 | P66: alert-aggregator --notify 主动通知 |
| **v0.0.56** | **2026-06-23** | **P67: 告警阈值参数化 P0/P1/P2/P3 + governance-agent 5 步闭环** |

---

## 7. 后续候选 (P68+)

| 建议 | 工作量 | 价值 | 时机 |
|------|------:|-----:|------|
| 告警级别 P0 触发 omo event 含 P0 标记 | 低 | 中 | P68 |
| 告警抑制时间窗 (避免 1h 内重复 P0) | 低 | 中 | P68 |
| 告警聚合历史趋势 (跨 7d 频率) | 中 | 中 | P68 |
| readiness 快照持久化 (git LFS / 独立存储) | 中 | 中 | P69 |
| 维度权重动态调整 | 大 | 中 | P69 |
| governance-readiness-trend 集成 mof-drift v8 | 中 | 高 | P70 |
| management/ 142 拆 3 类 (大重构) | 大 | 待评估 | P71+ |
| graphify 重生覆盖 1190 M1 节点 | 中 | 中 | P71+ |

---

## 8. 总结

P67 是 P66 **深化**的**参数化 + 闭环**阶段:

- **阈值参数化**: 工业实践, 不同环境可调整
- **P0/P1/P2/P3 分级**: 响应优先级明确
- **governance-agent 5 步闭环**: 完整评估 + 告警聚合
- **21 个 ADR**: P50-P67 完整治理链

**核心方法论**: "**参数化 + 分级**" — P60 是落地, P66 是事件化, **P67 是告警参数化和工业级分级**让治理系统适配不同环境。

---

*P67 R1-R3 完成: 2026-06-23 · governance 100 A+ 持续 · mof-version v0.0.56 · 9 独立 bin 治理工具 · 21 ADR 完整治理链*