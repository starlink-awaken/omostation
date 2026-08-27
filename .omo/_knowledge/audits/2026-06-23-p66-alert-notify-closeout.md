---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# P66 — alert-aggregator 主动通知 + 收口

**日期**：2026-06-23
**阶段**：P66 R1-R3
**目标**：alert-aggregator 升级为事件化 + cockpit 子命令化 (调整后)

---

## 1. 治理全景 (P66 完成)

| 指标 | P65 末 | **P66 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.54 | **v0.0.55** | +1 |
| governance | 100.0 A+ | **100.0 A+** | 持平 |
| 独立 bin 治理工具 | 9 | **9** | 持平 |
| 告警事件化 | 报告 | **报告 + omo event emit** | +1 |
| ADR 数量 | 19 | **20** | +1 (0060) |

---

## 2. 完整落地清单

### R1: cockpit 子命令化 (调整 → 保留 wrapper)

**原本目标**: readiness 升级为 cockpit 子命令 (P65 调整)

**实际**: cockpit 主入口 dispatcher 会拦截未注册子命令, 升级需 dispatcher 重构, 超 P66 范围

**调整**: 沿用 P65 wrapper (`bin/cockpit-readiness.py`), 继续作为 cockpit 集成入口

**P67+ 候选**: cockpit dispatcher 重构 + readiness 升级为子命令

### R2: alert-aggregator --notify 主动通知

**修改**: `bin/alert-aggregator.py` 加 `--notify` 选项

**触发逻辑**:
```python
should_notify = bool(storm_warnings) or total_alerts >= 5
if should_notify:
    # 1. 写 .omo/_log/alert-notifications.jsonl
    # 2. omo event emit governance_alert_aggregated
    # 3. 返回 1 (cron 触发告警)
```

**实测**:
- 健康时: 0 告警, exit=0 ✅
- 模拟 5 次同小时: 触发通知 + jsonl 写入 ✅
- omo 不可用: 静默失败 (沿用 P61 模式)

### R3: ADR-0060 + 收口

- `.omo/_knowledge/decisions/0060-p66-...md` (2 D)
- INDEX 双更新
- 本收口报告

---

## 3. 关键决策

### D-P66-1: --notify 触发条件 = storm || total >= 5
- 防御 alert storm
- 避免每次都 emit (减少噪音)
- omo 不可用静默 (P61 模式)

### D-P66-2: cockpit 集成保持 wrapper 形式
- dispatcher 重构超 P66 范围
- P65 wrapper 已可用, 不破坏现状
- P67+ 评估升级

---

## 4. 影响扩散

```
📂 bin/alert-aggregator.py (P65 → P66 增量)
   + emit_notification() 函数 (55 行)
   + --notify 选项 (argparse)
   + main 末尾接入 (if args.notify)
📂 .omo/_log/alert-notifications.jsonl (新, 异常时写入)
📂 .omo/_knowledge/decisions/0060-p66-...md (新 ADR, 2 D)
📂 .omo/_knowledge/decisions/INDEX.md (+1 行)
📂 .omo/_knowledge/audits/2026-06-23-p66-...md (本收口)
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
.alert-aggregator (cron 6h, 异步或同次)
  ├─ 读 jsonl (24h 窗口)
  ├─ 按类型分组 + 风暴检测
  └─ --notify 模式:
      ├─ 写 alert-notifications.jsonl
      └─ omo event emit governance_alert_aggregated
  ↓
事件总线 (omo event)
  ├─ 实时消费
  └─ dashboard / omo governance 集成
```

---

## 6. mof-version 历史

| 版本 | 日期 | 关键 |
|------|------|------|
| v0.0.54 | 2026-06-23 | P65: cockpit-readiness wrapper + alert-aggregator |
| **v0.0.55** | **2026-06-23** | **P66: alert-aggregator --notify 主动通知** |

---

## 7. 后续候选 (P67+)

| 建议 | 工作量 | 价值 | 时机 |
|------|------:|-----:|------|
| cockpit dispatcher 重构 + readiness 升级子命令 | 中 | 高 | P67 |
| 告警聚合阈值参数化 (--threshold N) | 低 | 中 | P67 |
| 告警聚合主动通知级别 (P0/P1/P2) | 中 | 中 | P67 |
| dashboard 卡片实际 UI 渲染 | 大 | 高 | P68 |
| readiness 快照持久化 | 中 | 中 | P68 |
| 维度权重动态调整 | 大 | 中 | P69 |
| governance-readiness-trend 集成 mof-drift v8 | 中 | 高 | P69 |
| management/ 142 拆 3 类 (大重构) | 大 | 待评估 | P70+ |
| graphify 重生覆盖 1190 M1 节点 | 中 | 中 | P70+ |

---

## 8. 总结

P66 是 P65 **深化**的**事件化**阶段:

- **alert-aggregator --notify**: 从"报告"升级为"事件", omo event emit 实时分发
- **cockpit 调整**: 沿用 wrapper, dispatcher 重构留 P67+
- **20 个 ADR**: P50-P66 完整治理链, ADR 数量级达标

**核心方法论**: "**事件化**" — P60 是落地, P64 是数据可消费化, P65 是 wrapper 集成 + 防御, **P66 是告警事件化**让治理系统形成实时事件流。

---

*P66 R1-R3 完成: 2026-06-23 · governance 100 A+ 持续 · mof-version v0.0.55 · 9 独立 bin 治理工具 · 20 ADR 完整治理链*