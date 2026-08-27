---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# P73 — governance-agent 8 步 + P0 mock 集成 + cron --test 收口

**日期**：2026-06-23
**阶段**：P73 R1-R3
**目标**：3 项候选实施 (8 步闭环 + P0 mock 集成 + cron --test)

---

## 1. 治理全景 (P73 完成)

| 指标 | P72 末 | **P73 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.61 | **v0.0.62** | +1 |
| governance | 100.0 A+ | **100.0 A+** | 持平 |
| 独立 bin 治理工具 | 12 | **12** | 持平 |
| governance-agent 步骤 | 7 | **8** (+P0 mock 触发) | +1 |
| install-governance-agent-cron.sh 命令 | 3 | **4** (+--test) | +1 |
| ADR 数量 | 26 | **27** | +1 (0067) |

---

## 2. 完整落地清单 (3/4 候选)

| 候选 | 实施 | 文件 | 关键 |
|------|------|------|------|
| ✅ governance-agent 8 步 | D1 | scripts/omo/governance-agent.sh | [2.6.5/3] P0 mock 触发 |
| ✅ alert-aggregator P0 集成 | D2 | scripts/omo/governance-agent.sh | P0 检测 + 3 通道 mock |
| ✅ install-governance-agent-cron --test | D3 | scripts/omo/install-governance-agent-cron.sh | 运维 dry-run 验证 |
| ⏸ graphify 重生 | 工具限制 | — | — |

---

## 3. 关键决策

### D-P73-1: 8 步闭环 (P0 自动触发)
- 步骤 [2.6.5/3] 介于 alert-aggregator (2.6) 和 alert-history (2.7) 之间
- 紧接 alert-aggregator 写 jsonl 后, 立即检测 P0
- 自动调 alert-mock-p0-notify

### D-P73-2: P0 集成路径
```
alert-aggregator 写 .omo/_log/alert-notifications.jsonl
  ↓
governance-agent 步骤 2.6 跑完, 步骤 2.6.5 检测 jsonl
  ↓
python3 -c "json 解析 + 1h cutoff"
  ↓
LAST_P0 不为空 → alert-mock-p0-notify --all-channels
  ↓
runtime/logs/p0-notifications.log (3 通道 jsonl)
```

### D-P73-3: cron --test 模式
- 跑 1 次 governance-agent --dry-run
- 不修改 crontab, 不写 alert log
- 运维可验证任务正确性

---

## 4. 8 步完整结构

```
[1/3]   governance-readiness          (P60 5 维评分)
[2/3]   mof-drift                      (P52 v5 + P62 v7 + P70 v8)
[2.5/3] governance-readiness-trend    (P63 + P70 mof-drift 集成)
[2.6/3] alert-aggregator              (P67 阈值 + P68 抑制 + P70 跨级别)
[2.6.5/3] P0 mock                       (P73 增) ← 自动检测 + 触发
[2.7/3] alert-history                  (P68 + P69 ASCII + P70 rich + P71 跨级别 + P72 sup_state)
[2.8/3] dim-weight                     (P71 + P72 IQR 调优)
[3/3]   评估
```

---

## 5. P0 mock 实测

```bash
$ python3 -c "..."  # 注入 P0 通知到 alert-notifications.jsonl
$ bash scripts/omo/governance-agent.sh --include-trend
...
--- [2.6/3] alert-aggregator ---
🚨 告警风暴:
⚠️  low_mean 在 2026-06-24T08 触发 12 次, 告警风暴

🚨 P0 触发检测: P0 test 12 alerts
📤 P72 P0 mock 通知
  Level: P0
  Message: P0 test 12 alerts
  [email ] → oncall@omostation.local                  ✅ delivered
  [sms   ] → +86-xxx-xxxx-xxxx                        ✅ delivered
  [slack ] → #governance-alerts                       ✅ delivered
```

---

## 6. cron --test 实测

```bash
$ bash scripts/omo/install-governance-agent-cron.sh --test
=== governance-agent --test 模式 (dry-run) ===
将执行: .../governance-agent.sh --include-trend --dry-run

--- [3/3] 评估 ---
readiness: 98/100
drift: LOW=1 MEDIUM=0 HIGH=0

✅ 自治治理代理正常, 退出码 0
✅ event emitted: kind=agent_mutation_complete
   log: /Users/xiamingxing/Workspace/.omo/_knowledge/omo-events.jsonl

✅ --test 完成 (未修改 crontab, 未写 alert log)
```

---

## 7. 影响扩散

```
📂 scripts/omo/governance-agent.sh (P72 → P73 +25 行)
   + [2.6.5/3] P0 mock 触发步骤
   + LAST_P0 检测 (python3 inline)
   + 自动调 alert-mock-p0-notify --all-channels
📂 scripts/omo/install-governance-agent-cron.sh (P62 → P73 +10 行)
   + --test 模式 (case 分支)
   + 跑 1 次 dry-run 验证
📂 .omo/_knowledge/decisions/0067-p73-...md (新 ADR, 3 D)
📂 .omo/_knowledge/decisions/INDEX.md (+1 行)
📂 .omo/_knowledge/audits/2026-06-23-p73-...md (本收口)
```

---

## 8. mof-version 历史

| 版本 | 日期 | 关键 |
|------|------|------|
| v0.0.61 | 2026-06-23 | P72: 7 步 + sup_state + IQR + P0 mock |
| **v0.0.62** | **2026-06-23** | **P73: 8 步 + P0 mock 集成 + cron --test** |

---

## 9. 后续候选 (P74+)

| 建议 | 工作量 | 价值 | 时机 |
|------|------:|-----:|------|
| graphify 重生 (需 url 入口) | 中 | 中 | P74 |
| management/ 142 实施拆分 (P75+) | 大 | 中 | P75+ |
| P0 mock 替换真实 SMS/email | 大 | 中 | P75+ |
| 事件驱动 P0 检测 (替代 polling) | 中 | 高 | P74 |
| dim-weight 真实数据调优 (需 30+ 快照) | 低 | 中 | P74 持续 |
| alert-history 加更多维度 (跨日 + 跨类型) | 中 | 中 | P74 |

---

## 10. 总结

P73 是 P72 **深化**的**集成 + 运维**阶段:

- **8 步闭环**: P0 mock 自动触发, 完整数据驱动
- **P0 集成**: alert-aggregator → governance-agent → alert-mock-p0-notify 链路
- **cron --test**: 运维可验证任务
- **3/4 候选实施**: graphify 跳过 (工具限制)

**核心方法论**: "**集成 + 运维**" — P60 是落地, P72 是数据可消费化, **P73 是 P0 mock 工具集成到 governance-agent + cron --test**让治理系统端到端可执行 + 可验证。

---

*P73 R1-R3 完成: 2026-06-23 · governance 100 A+ 持续 · mof-version v0.0.62 · 12 独立 bin 治理工具 · 27 ADR 完整治理链 · 3/4 候选实施*