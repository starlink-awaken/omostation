---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# P68 — 告警抑制时间窗 + 告警历史趋势报告 收口

**日期**：2026-06-23
**阶段**：P68 R1-R3
**目标**：抑制噪音 + 历史可见

---

## 1. 治理全景 (P68 完成)

| 指标 | P67 末 | **P68 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.56 | **v0.0.57** | +1 |
| governance | 100.0 A+ | **100.0 A+** | 持平 |
| 独立 bin 治理工具 | 9 | **10** | +1 (alert-history) |
| 告警返回码 | 0/1 | **0/1/2** | +1 (抑制) |
| 告警抑制 | 无 | **60min 同级别** | +1 |
| ADR 数量 | 21 | **22** | +1 (0062) |

---

## 2. 完整落地清单

### R1: 告警抑制时间窗 (D-P68-1)

**修改**: `bin/alert-aggregator.py` 加 `is_suppressed()` + `--suppression-minutes N`

**逻辑**:
- 读 alert-notifications.jsonl 最近 50 条
- 找同级别 + ts 在 suppression_minutes 内
- 找到 → 抑制, 返回 2
- 没找到 → 正常, 返回 1

**参数**: `--suppression-minutes 60` (默认 60min)

**返回码**:
- 0: P3 不触发
- 1: 正常触发
- 2: 抑制

**实测**: 6 个 low_mean 连续 2 次 → 第 2 次 exit=2, 抑制

### R2: 告警历史趋势报告 (D-P68-2)

**新工具**: `bin/alert-history.py` (130 行)

**功能**:
- 读 alert-notifications.jsonl 最近 N 天 (默认 7)
- 按天统计 + 按级别 + 按类型
- 高峰日检测 (P0+P1 >= 3)
- 双格式 (text/json)

**实测**: 3 个 P1 跨 5 天 → 3 天显示

### R3: ADR-0062 + 收口

- `.omo/_knowledge/decisions/0062-p68-...md` (2 D)
- INDEX 双更新
- 本收口报告

---

## 3. 关键决策

### D-P68-1: 三态返回码 (0/1/2)
- 工业实践
- cron 可区分 (0=健康, 1=告警, 2=抑制)

### D-P68-2: 抑制 = 同级别时间窗
- 避免噪音
- 跨级别不抑制 (P0 → P1 仍通知)

### D-P68-3: 趋势报告简化版
- 按天/级别/类型
- 高峰日 P0+P1 >= 3 标记
- 后续可加图表

---

## 4. 影响扩散

```
📂 bin/alert-aggregator.py (P67 → P68 增量 +30 行)
   + is_suppressed() 函数
   + --suppression-minutes 参数
   + 三态返回码 (0/1/2)
📂 bin/alert-history.py (新, 130 行)
   + 跨 N 天趋势
   + 按级别/类型/天统计
   + 高峰日检测
📂 .omo/_knowledge/decisions/0062-p68-...md (新 ADR, 2 D)
📂 .omo/_knowledge/decisions/INDEX.md (+1 行)
📂 .omo/_knowledge/audits/2026-06-23-p68-...md (本收口)
```

---

## 5. 完整闭环 (P68 后)

```
governance-agent (cron 6h)
  ├─ [1/3] governance-readiness (5 维评分)
  ├─ [2/3] mof-drift (8 维度)
  ├─ [2.5/3] governance-readiness-trend (历史 + --alert)
  ├─ [2.6/3] alert-aggregator (P0/P1/P2/P3 级别)
  │       └─ is_suppressed() 抑制 (60min 同级别)
  └─ [3/3] 评估
       ├─ readiness >= 90? ✅
       ├─ drift LOW <= 5? ✅
       └─ alert P0/P1/P2 → omo event emit (or 抑制)

alert-history (独立工具, 7d 趋势)
  └─ P0+P1 频率 + 高峰日
```

---

## 6. mof-version 历史

| 版本 | 日期 | 关键 |
|------|------|------|
| v0.0.56 | 2026-06-23 | P67: 告警阈值参数化 P0/P1/P2/P3 + 5 步闭环 |
| **v0.0.57** | **2026-06-23** | **P68: 告警抑制时间窗 + alert-history 趋势报告** |

---

## 7. 后续候选 (P69+)

| 建议 | 工作量 | 价值 | 时机 |
|------|------:|-----:|------|
| 告警聚合抑制标记写入 jsonl (精确统计 suppression_rate) | 低 | 中 | P69 |
| alert-history 加趋势图 (ASCII 柱状) | 中 | 中 | P69 |
| 告警级别 P0 触发短信/邮件 (P0 需即时响应) | 大 | 中 | P70 |
| readiness 快照持久化 (git LFS / 独立存储) | 中 | 中 | P70 |
| 维度权重动态调整 | 大 | 中 | P71 |
| governance-readiness-trend 集成 mof-drift v8 | 中 | 高 | P71 |
| management/ 142 拆 3 类 (大重构) | 大 | 待评估 | P72+ |
| graphify 重生覆盖 1190 M1 节点 | 中 | 中 | P72+ |

---

## 8. 总结

P68 是 P67 **深化**的**噪音防御 + 历史可见**阶段:

- **告警抑制**: 三态返回码, 工业级防御
- **历史趋势**: 7d 频率, 高峰日检测
- **10 独立 bin 工具**: alert-history 加入治理工具链
- **22 个 ADR**: P50-P68 完整治理链

**核心方法论**: "**抑制 + 可见**" — P60 是落地, P66 是事件化, P67 是分级, **P68 是抑制和趋势**让治理系统长期可观测。

---

*P68 R1-R3 完成: 2026-06-23 · governance 100 A+ 持续 · mof-version v0.0.57 · 10 独立 bin 治理工具 · 22 ADR 完整治理链*