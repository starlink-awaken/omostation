---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0074: P80 dim-weight 集成到 readiness + 跨子仓 event 联动订阅器 + cron 评估

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P80
- **Extends**: ADR-0073 (P79 dim-weight 调优 + graphify report + inotify 评估)
- **Superseded by**: (无)

## Context and Problem Statement

P79 收口后, P80 调研 5 项候选, 实施 3 项:

1. **dim-weight 集成到 readiness 计算** (P79 调优结果应用)
2. **跨子仓 omo event 联动订阅器** (ecos/agora/cockpit 路由)
3. **governance-agent cron 完整安装测试** (实际安装评估)

跳过 2 项:
- graphify 实际扫描 (P81+ 需 OPENAI_API_KEY)
- dashboard 卡片 UI 渲染 (P81+ 评估)

## Decision

### D1: dim-weight 集成到 readiness (P80 R1)

**修改**: `bin/governance-readiness.py` 加 `USE_TUNED_WEIGHTS=1` 环境变量支持

**逻辑**:
```python
if os.environ.get("USE_TUNED_WEIGHTS") == "1":
    # 调 bin/dim-weight.py --format json 拿调优权重
    # 加权总分 = sum(score * weight/100)
    # 输出 "⚖️  P80 调优权重" + "📊 加权总分"
    # 用加权总分替代原始总分
```

**实测**:
- 默认 (无 USE_TUNED_WEIGHTS): total=93 (P60 原始权重)
- 启用调优: total=15.7 (frontmatter=0, drift=24, commit=76 加权)
- 反映波动维度的真实重要性

**vs 默认权重**:
- 默认 25/20/20/20/15 → 均匀
- 调优 0/24/76/0/0 → 集中在波动维度
- 33 快照下 commit_closure 突出 (高波动)

### D2: 跨子仓 omo event 联动订阅器 (P80 R2)

**新工具**: `bin/cross-submodule-events.py` (165 行)

**功能**:
- 读 .omo/_knowledge/omo-events.jsonl
- 按 event kind 路由 (ROUTES 表)
- 7 种 kind × 3 子仓路由
- `--stats` 统计
- `--watch` 实时 tail
- `--kind <name>` 过滤

**路由表**:
| kind | 路由 |
|------|------|
| governance_alert | ecos:audit-check |
| governance_alert_aggregated | ecos:audit-batch |
| ssot_audit_divergence_found | ecos:flag |
| ssot_guardian_run | ecos:heartbeat |
| tasks_registry_index_updated | agora:registry-sync |
| agent_mutation_complete | agora:notify |
| agent_ssb_update | cockpit:event-bus |

**实测** (44 历史事件):
- 25 ssot_guardian_run → ecos:heartbeat
- 7 governance_alert_aggregated → ecos:audit-batch
- 4 agent_mutation_complete → agora:notify
- 1 ssot_audit_divergence_found → ecos:flag
- 1 tasks_registry_index_updated → agora:registry-sync
- 4 agent_mutation_intent (no route)
- 2 governance_alert_suppressed (no route)

### D3: governance-agent cron 完整安装评估 (P80 R3)

**结论**: 沙箱禁用 `crontab` 命令 (安全考虑), 实际安装需在生产环境

**已完成** (跨 P62-P80):
- `install-governance-agent-cron.sh` 5 命令 (install/--uninstall/--test/--status/--status-json)
- 干测试 (`--test`) 跑通
- 状态查询 (`--status`) 跑通
- JSON 输出 (`--status-json`) 跑通

**P81+ 待办**:
- 实际 `crontab -e` 安装 (需生产环境)
- 与 cockpit dashboard 集成 cron 状态
- 实时 cron 触发 governance-agent

## Consequences

### Positive

- **dim-weight 集成**: 调优权重应用, 反映真实重要性
- **跨子仓 event 联动**: 7 种 kind 路由, 44 事件可追溯
- **cron 5 命令完善**: install/test/status/status-json/uninstall

### Negative

- **crontab 命令沙箱禁用**: 实际安装需生产环境
- **agent_mutation_intent/suppressed 无路由**: P81+ 补 ROUTES

### Neutral

- **不增 linter 维度**: 沿用 P58 独立 bin 工具
- **不增 mof-drift 维度**: 8 维度持续

## Compliance

### 验证指标

| 指标 | P79 末 | **P80 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.68 | **v0.0.69** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 17 | **18** | +1 (cross-submodule-events) |
| readiness 调优模式 | 默认 | **USE_TUNED_WEIGHTS=1 可选** | +1 |
| 跨子仓 event 路由 | 0 | **7 kind × 3 子仓** | +7 |
| ADR 数量 | 33 | **34** | +1 (0074) |

### 关联 ADR

- **ADR-0073**: P79 dim-weight 调优 (P80 集成结果)
- **ADR-0070**: P76 governance-agent cron (P80 完善)
- **ADR-0072**: P78 跨子仓联动 (P80 订阅器扩展)

### 关联 L0 规则

- `X2-FRESH-COMMIT-FATIGUE` — cron 干测试稳定, 待生产实装
- `CR-GOV-CLOSED-LOOP-01` — 跨子仓 event 即 commit 闭环

## Notes

本 ADR 记录 P80 3 项候选实施:
- ✅ dim-weight 集成到 readiness (USE_TUNED_WEIGHTS=1)
- ✅ 跨子仓 event 联动订阅器 (7 kind × 3 子仓)
- ✅ cron 完整安装评估 (5 命令完善, 待生产实装)
- ⏸ graphify 实际扫描 (P81+ 需 OPENAI_API_KEY)
- ⏸ dashboard 卡片 UI 渲染 (P81+)

后续 P81+ 候选:
- graphify 实际扫描 (需 OPENAI_API_KEY)
- 跨子仓 event 联动生产实装 (agent_mutation_intent 等补 ROUTES)
- cockpit dashboard 集成 cron 状态
- inotify/watchdog 安装 (Linux/跨平台)
- alert-history 加 LSTM/ML 洞察
- dashboard 卡片实际 UI 渲染

---

*最后更新: 2026-06-23 · P80 · omostation 治理方法论持续深化*