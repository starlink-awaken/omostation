---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# P69 — 抑制标记精确统计 + alert-history ASCII 趋势图 收口

**日期**：2026-06-23
**阶段**：P69 R1-R3
**目标**：抑制率真实统计 + 趋势图可视化

---

## 1. 治理全景 (P69 完成)

| 指标 | P68 末 | **P69 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.57 | **v0.0.58** | +1 |
| governance | 100.0 A+ | **100.0 A+** | 持平 |
| 独立 bin 治理工具 | 10 | **10** | 持平 |
| 告警 jsonl | 1 | **2 (notifications + suppressions)** | +1 |
| 抑制率 | 0 (hardcoded) | **真实统计** | +1 |
| 趋势可视化 | 表格 | **ASCII 柱状图** | +1 |
| ADR 数量 | 22 | **23** | +1 (0063) |

---

## 2. 完整落地清单

### R1: 抑制标记精确统计 (D-P69-1)

**修改**: `bin/alert-aggregator.py` `emit_notification()` 抑制分支

**逻辑**:
```python
if suppressed:
    # 写 alert-suppressions.jsonl (P69 新增)
    suppress_payload = {
        "timestamp": ..., "level": level,
        "total_alerts": agg["total_alerts"],
        "suppression_minutes": suppression_minutes,
        "prev_record_ts": prev_record["timestamp"],
        "storm_count": len(storm_warnings),
    }
    append to .omo/_log/alert-suppressions.jsonl
    return 2
```

**双 jsonl 分工**:
- `alert-notifications.jsonl`: 实际触发的通知
- `alert-suppressions.jsonl`: 抑制记录 (P69 新)

### R2: alert-history ASCII 趋势图 + 抑制率 (D-P69-2)

**修改**: `bin/alert-history.py`

**新增**:
- `load_suppressions()` 函数
- `analyze_history()` 接受 suppressions 参数
- `render_ascii_bar()` 函数 (40 字符柱状)
- 主函数读双 jsonl

**报告新增**:
- 抑制记录数
- 抑制率 (%)
- 按天 ASCII 柱状图

**实测**: 5 个通知 + 5 个抑制 → 50% 抑制率, 5 天柱状图

### R3: ADR-0063 + 收口

- `.omo/_knowledge/decisions/0063-p69-...md` (2 D)
- INDEX 双更新
- 本收口报告

---

## 3. 关键决策

### D-P69-1: 双 jsonl 分工
- notifications (触发) + suppressions (抑制)
- 互不污染, 精确统计

### D-P69-2: ASCII 柱状图
- 终端友好, 不依赖第三方库
- 40 字符宽, 适应标准终端

### D-P69-3: 抑制率真实计算
- suppression_count / (total + suppression_count)
- 替换 P68 的 hardcoded 0

---

## 4. 影响扩散

```
📂 bin/alert-aggregator.py (P68 → P69 增量 +25 行)
   + 抑制分支写 alert-suppressions.jsonl
   + prev_record_ts 字段
   + storm_count 字段
📂 bin/alert-history.py (P68 → P69 增量 +50 行)
   + load_suppressions() 函数
   + analyze_history(suppressions) 参数化
   + render_ascii_bar() 函数
   + 抑制率真实计算
📂 .omo/_log/alert-suppressions.jsonl (新, 抑制时写入)
📂 .omo/_knowledge/decisions/0063-p69-...md (新 ADR, 2 D)
📂 .omo/_knowledge/decisions/INDEX.md (+1 行)
📂 .omo/_knowledge/audits/2026-06-23-p69-...md (本收口)
```

---

## 5. alert-history 实测示例

```
============================================================
📊 P69 告警历史趋势报告 (最近 7 天)
============================================================
📁 通知记录数: 5
📈 总通知数: 5
🔕 抑制记录: 5
📊 抑制率: 50.0%

--- 按级别 ---
  P1         5

--- 按类型 ---
  low_mean                   30

--- 按天 (最近 7d ASCII 柱状图) ---
  2026-06-19  ████████████████████████████████████████ 1 {'P1': 1}
  2026-06-20  ████████████████████████████████████████ 1 {'P1': 1}
  2026-06-21  ████████████████████████████████████████ 1 {'P1': 1}
  2026-06-22  ████████████████████████████████████████ 1 {'P1': 1}
  2026-06-23  ████████████████████████████████████████ 1 {'P1': 1}
```

---

## 6. mof-version 历史

| 版本 | 日期 | 关键 |
|------|------|------|
| v0.0.57 | 2026-06-23 | P68: 告警抑制时间窗 + alert-history 趋势报告 |
| **v0.0.58** | **2026-06-23** | **P69: 抑制标记精确统计 + ASCII 柱状图** |

---

## 7. 后续候选 (P70+)

| 建议 | 工作量 | 价值 | 时机 |
|------|------:|-----:|------|
| ASCII 柱状图加颜色 (rich 库集成) | 中 | 中 | P70 |
| 跨级别抑制 (P0→P1 仍抑制, P0→P3 不抑制) | 低 | 中 | P70 |
| alert-history 集成到 dashboard 卡片 | 中 | 中 | P70 |
| P0 触发短信/邮件 | 大 | 中 | P71 |
| readiness 快照持久化 | 中 | 中 | P71 |
| 维度权重动态调整 | 大 | 中 | P72 |
| governance-readiness-trend 集成 mof-drift v8 | 中 | 高 | P72 |
| management/ 142 拆 3 类 (大重构) | 大 | 待评估 | P73+ |
| graphify 重生覆盖 1190 M1 节点 | 中 | 中 | P73+ |

---

## 8. 总结

P69 是 P68 **深化**的**精确化 + 可视化**阶段:

- **抑制率真实计算**: 双 jsonl 分工, 50% 抑制率精确统计
- **ASCII 柱状图**: 终端友好可视化, 不依赖第三方库
- **10 独立 bin 工具**: 工具链成熟
- **23 个 ADR**: P50-P69 完整治理链

**核心方法论**: "**精确化 + 可视化**" — P60 是落地, P66 是事件化, P68 是抑制, **P69 是抑制率精确化和 ASCII 趋势图**让治理数据可量化、可视化。

---

*P69 R1-R3 完成: 2026-06-23 · governance 100 A+ 持续 · mof-version v0.0.58 · 10 独立 bin 治理工具 · 23 ADR 完整治理链*