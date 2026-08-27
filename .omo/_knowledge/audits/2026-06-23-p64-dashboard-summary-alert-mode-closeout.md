---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# P64 — dashboard 数据源 + 异常自动告警 收口

**日期**：2026-06-23
**阶段**：P64 R1-R3
**目标**：dashboard 卡片数据源 + readiness-trend --alert 自动告警

---

## 1. 治理全景 (P64 完成)

| 指标 | P63 末 | **P64 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.52 | **v0.0.53** | +1 |
| governance | 100.0 A+ | **100.0 A+** | 持平 |
| mof-drift 维度 | 8 | **8** | 持平 |
| governance readiness | 96/100 A+ L4 | **96/100 A+ L4** | 持平 (稳态) |
| 独立 bin 治理工具 | 6 | **7** | +1 (dashboard summary) |
| 自治代理 flags | 3 | **3+1** | +1 (--alert) |
| readiness 快照 | 6 | **10** | +4 |
| ADR 数量 | 17 | **18** | +1 (0058) |

---

## 2. 完整落地清单

### R1: dashboard-readiness-summary 工具 (D-P64-1)

**新工具**: `bin/dashboard-readiness-summary.py` (175 行)

**功能**:
- 加载 10 快照
- 输出 4 类卡片 (summary / dimensions / alerts / history)
- 双格式: JSON (默认) / text
- 输出目标: stdout / --output file

**实测**:
```
📊 governance readiness 摘要
  Score: 96/100  Grade: A+ L4 稳态治理
  Snapshots: 10  Trend: stable
  --- 5 维度 ---
  frontmatter           25/25  (100.0%)
  drift_low             18/20  (90.0%)
  commit_closure        18/20  (90.0%)
  adr_index             20/20  (100.0%)
  governance_score      15/15  (100.0%)
```

### R2: --alert 自动告警 (D-P64-2)

**修改**: `bin/governance-readiness-trend.py` 加 `--alert` 选项

**逻辑**:
- 异常检测: low_mean / high_volatility / sudden_drop
- --alert 模式触发:
  1. 写 `.omo/_log/readiness-alerts.jsonl`
  2. 调 `omo event emit governance_readiness_alert`
  3. 返回非 0 exit code

**实测**: 健康时 mean=95.9, stdev=0.32, exit=0 (无告警)

### R3: ADR-0058 + 收口

- `.omo/_knowledge/decisions/0058-p64-...md` (2 D)
- INDEX 双更新
- 本收口报告

---

## 3. 关键决策

### D-P64-1: dashboard 数据源独立 bin 工具
- 沿用 P58/P62/P63 模式: 独立 bin 工具而非 linter 维度
- 4 卡片标准化 (summary/dimensions/alerts/history)
- 第三方消费方 (cockpit / dashboard UI) 可直接解析

### D-P64-2: --alert 沿用 P61 事件总线
- 异常触发 omo event emit (P61 自治代理同模式)
- 静默失败 (omo 不可用时不阻断)
- 写 jsonl 持久化 (历史可追溯)

---

## 4. 影响扩散

```
📂 bin/dashboard-readiness-summary.py (新, 175 行)
   + 加载快照 + 4 卡片构建 + JSON/text 双格式
📂 bin/governance-readiness-trend.py (P63 → P64)
   + --alert 选项 (D-P64-2)
   + emit_alert() 函数 (异常时 omo event + jsonl)
📂 .omo/_log/readiness-alerts.jsonl (异常时新增, 健康时无)
📂 .omo/_knowledge/decisions/0058-p64-...md (新 ADR, 2 D)
📂 .omo/_knowledge/decisions/INDEX.md (+1 行)
📂 .omo/_knowledge/audits/2026-06-23-p64-...md (本收口)
```

---

## 5. 闭环验证

```
governance-agent.sh --include-trend --alert (未来集成)
  ↓
governance-readiness.py  → 写 readiness-*.json
  ↓
governance-readiness-trend.py --alert
  ├─ 异常检测 (low_mean / high_volatility / sudden_drop)
  ├─ 写 .omo/_log/readiness-alerts.jsonl (历史)
  ├─ omo event emit governance_readiness_alert (事件)
  └─ exit code 0/1 (cron 告警)
  ↓
dashboard-readiness-summary.py (cockpit / 第三方)
  ↓
dashboard 卡片渲染 (P65+)
```

---

## 6. mof-version 历史

| 版本 | 日期 | 关键 |
|------|------|------|
| v0.0.52 | 2026-06-23 | P63: readiness 历史快照 + trend 报告 + agent 3 flags |
| **v0.0.53** | **2026-06-23** | **P64: dashboard 数据源 + --alert 自动告警** |

---

## 7. 后续候选 (P65+)

| 建议 | 工作量 | 价值 | 时机 |
|------|------:|-----:|------|
| dashboard 卡片实际 UI 渲染 (cockpit integration) | 大 | 高 | P65 |
| 告警聚合 (避免 alert storm) | 中 | 中 | P65 |
| readiness 快照持久化 (git LFS / 独立存储) | 中 | 中 | P66 |
| 维度权重动态调整 (基于历史相关性) | 大 | 中 | P66 |
| governance-readiness-trend 集成 mof-drift v8 | 中 | 高 | P67 |
| management/ 142 拆 3 类 (大重构) | 大 | 待评估 | P68+ |
| graphify 重生覆盖 1190 M1 节点 | 中 | 中 | P68+ |

---

## 8. 总结

P64 是 P63 **深化**的**可消费化**阶段:

- **dashboard 数据源**: 结构化 JSON 4 卡片, 第三方可直接消费
- **--alert 自动告警**: 异常时 omo event + jsonl 持久化 + 非 0 exit
- **闭环完整**: readiness → snapshot → trend → alert → dashboard 形成时间序列
- **决策面**: 18 个 ADR 形成 P50-P64 完整治理链

**核心方法论**: "**数据可消费化**" — P60 是 6 层落地, P63 是时间序列化, P64 是结构化输出让外部消费。

---

*P64 R1-R3 完成: 2026-06-23 · governance 100 A+ 持续 · mof-version v0.0.53 · readiness 96/100 A+ L4 稳态 · 7 独立 bin 治理工具 · 10 快照*