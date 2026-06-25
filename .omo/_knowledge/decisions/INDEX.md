---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# Architecture Decision Records — 索引

> 全部 ADR 文件位于本目录 `.omo/_knowledge/decisions/`
> 制度启用: 2026-06-05 (Phase 28 W3) · MADR 风格

---

## 索引表

| # | 标题 | Status | Date | Authors | 文件 |
|---|------|--------|------|---------|------|
| 0001 | agora 路由表精简策略 | ACCEPTED | 2026-06-05 | omostation P28-W3 | 0001-agora-routes-deferred.md |
| 0002 | kairon-assistant / kairon-voice 首批归档 | ACCEPTED | 2026-06-05 | omostation P28-W3 | 0002-pkg-archive-p28-w2.md |
| 0003 | P28 TECH-RADAR 实施绕过 agora | ACCEPTED | 2026-06-05 | omostation P28-W3 | 0003-tech-radar-bypass-agora.md |
| 0004 | kaironcloud-billing 归档（W6 评估） | ACCEPTED | 2026-06-05 | omostation P28-W6 | 0004-kcb-archived.md |
| 0005 | P29 架构升级（kairon 31 包 → L1 工程层） | ACCEPTED | 2026-06-05 | omostation P29 | 0005-architecture-p29-upgrade.md |
| 0006 | kairon 17 包合并到 14 包（方向 C — 3 组瘦包合并，砍 data-pipeline） | ACCEPTED | 2026-06-06 | omostation P31-W0 | 0006-kairon-package-merge.md |
| 0007 | 多仓库统一版本发布策略（VERSION + CHANGELOG + release.sh） | ACCEPTED | 2026-06-07 | omostation P34-W3 | 0007-multi-repo-release.md |
| 0008 | in_progress 任务列表清理原则（4 类分类：completed / pending / cancelled / 删） | ACCEPTED | 2026-06-07 | omostation P37-W1 | 0008-task-cleanup-policy.md |
| 0050 | gbrain 53 TODOs 4 类决策（keep/fix/close/planned） | ACCEPTED | 2026-06-23 | omostation P50 | 0050-gbrain-53-todos-4-cat.md |
| 0051 | gbrain TODOs v5 终极收敛（unknown=0, any TODO=planned, extends 0050） | ACCEPTED | 2026-06-23 | omostation P52 | 0051-gbrain-todos-v5-unknown-zero.md |
| 0052 | P54-P55 知识面深度收敛（设计契约区建立 + frontmatter 100% + 断链 SSOT 修复） | ACCEPTED | 2026-06-23 | omostation P56 | 0052-p54-p55-knowledge-convergence.md |
| 0053 | P56 frontmatter 100% + doc-lifecycle 100/100（linter 维度饱和评估，暂不增量） | ACCEPTED | 2026-06-23 | omostation P57 | 0053-p56-frontmatter-100-and-doc-lifecycle.md |
| 0054 | P60 治理方法论内化（L0/X1-X4/M0/L4/Skill/cockpit 6 层落地） | ACCEPTED | 2026-06-23 | omostation P60 | 0054-p60-governance-internalization.md |
| 0055 | P61 readiness 修复 + mof-drift v6 + 自治治理代理（readiness 95/100 A+ L4） | ACCEPTED | 2026-06-23 | omostation P61 | 0055-p61-readiness-drift-agent.md |
| 0056 | P62 readiness 5 档优化 + mof-drift v7 stale_governance + install 脚本（readiness 96/100 A+ L4） | ACCEPTED | 2026-06-23 | omostation P62 | 0056-p62-readiness-thresholds-stale-governance.md |
| 0057 | P63 readiness 历史快照 + trend 报告 + governance-agent --dry-run/--snapshot-only/--include-trend | ACCEPTED | 2026-06-23 | omostation P63 | 0057-p63-readiness-snapshot-trend-agent-flags.md |
| 0058 | P64 dashboard-readiness-summary 4 卡片 + readiness-trend --alert 自动告警 (omo event emit) | ACCEPTED | 2026-06-23 | omostation P64 | 0058-p64-dashboard-summary-alert-mode.md |
| 0059 | P65 cockpit-readiness wrapper + alert-aggregator 避免 alert storm (9 独立 bin 工具) | ACCEPTED | 2026-06-23 | omostation P65 | 0059-p65-cockpit-integration-alert-aggregator.md |
| 0060 | P66 alert-aggregator --notify 主动通知 (omo event emit aggregated, 20 个 ADR) | ACCEPTED | 2026-06-23 | omostation P66 | 0060-p66-alert-aggregator-notify.md |
| 0061 | P67 告警阈值参数化 P0/P1/P2/P3 + governance-agent 集成 alert-aggregator (5 步) | ACCEPTED | 2026-06-23 | omostation P67 | 0061-p67-alert-thresholds-and-agent-integration.md |
| 0062 | P68 告警抑制时间窗 (60min 同级别) + alert-history 趋势报告 (10 独立 bin) | ACCEPTED | 2026-06-23 | omostation P68 | 0062-p68-alert-suppression-and-history.md |
| 0063 | P69 抑制标记精确统计 (双 jsonl) + alert-history ASCII 柱状图 (23 个 ADR) | ACCEPTED | 2026-06-23 | omostation P69 | 0063-p69-alert-suppression-tracking-and-chart.md |
| 0064 | P70 跨级别抑制 (高→低) + rich 颜色 + dashboard 6 卡片 + 快照持久化 + mof-drift v8 趋势 | ACCEPTED | 2026-06-23 | omostation P70 | 0064-p70-cross-level-rich-dashboard-snapshots-drift.md |
| 0065 | P71 governance-agent 6 步 + alert-history 跨级别 + dim-weight 动态权重 (25 个 ADR) | ACCEPTED | 2026-06-23 | omostation P71 | 0065-p71-six-step-cross-level-dim-weight-mgmt-eval.md |
| 0066 | P72 governance-agent 7 步 + alert-history sup_state + dim-weight IQR 调优 + P0 mock 通知 | ACCEPTED | 2026-06-23 | omostation P72 | 0066-p72-seven-step-iqr-p0-mock.md |
| 0067 | P73 governance-agent 8 步 + P0 mock 集成 + install-governance-agent-cron --test (27 个 ADR) | ACCEPTED | 2026-06-23 | omostation P73 | 0067-p73-eight-step-p0-mock-cron-test.md |
| 0068 | P74 p0-event-listener 事件驱动 + dim-weight percentile 调优 + alert-history 多维扩展 (28 ADR) | ACCEPTED | 2026-06-23 | omostation P74 | 0068-p74-event-driven-p0-listener-dim-weight-percentile-alert-history-extended.md |
| 0069 | P75 management 142 frontmatter 分类 + alert-history 9 维深化 + graphify-local-extract wrapper (29 ADR) | ACCEPTED | 2026-06-23 | omostation P75 | 0069-p75-management-categorize-alert-history-graphify-wrapper.md |
| 0070 | P76 p0-event-listener --watch 实时 + install-governance-agent-cron --status-json (30 个 ADR) | ACCEPTED | 2026-06-23 | omostation P76 | 0070-p76-real-time-listener-and-cron-status-json.md |
| 0071 | P77 management 144 物理迁移 (workflows/playbooks/guides, 简化版双指针, 16 bin) | ACCEPTED | 2026-06-23 | omostation P77 | 0071-p77-management-144-physical-migration.md |
| 0072 | P78 cross-submodule-check + management INDEX + alert-history 自动洞察 (17 bin, 32 ADR) | ACCEPTED | 2026-06-23 | omostation P78 | 0072-p78-cross-submodule-management-index-anomaly.md |
| 0073 | P79 dim-weight 真实调优 (30 快照) + graphify --report-only + inotify 评估 (33 ADR) | ACCEPTED | 2026-06-23 | omostation P79 | 0073-p79-dim-weight-graphify-inotify-evaluation.md |
| 0074 | P80 dim-weight 集成 readiness + cross-submodule-events 路由 (7×3) + cron 评估 (34 ADR) | ACCEPTED | 2026-06-23 | omostation P80 | 0074-p80-tuned-weights-events-cron-evaluation.md |
| 0075 | P81 watchdog 集成 + dashboard UI 渲染 + z-score 洞察 + management 跨子目录引用检查 (35 ADR) | ACCEPTED | 2026-06-23 | omostation P81 | 0075-p81-watchdog-dashboard-zscore-crossref.md |
| 0076 | P82 cross-ref scope-aware + status-aware 升级 (active:0, archived:43 符合预期) + 删孤立 workflows/INDEX.md (36 ADR) | ACCEPTED | 2026-06-23 | omostation P82 | 0076-p82-cross-ref-scope-status-aware.md |
| 0077 | P83 governance-history + drift-history 洞察 + cross-ref gitignore 感知 (active:0, archived:23 + 20 gitignored, 24 bin) | ACCEPTED | 2026-06-25 | omostation P83 | 0077-p83-history-insight-gitignore-aware.md |
| 0078 | P84 M2 coverage 修正 (69 噪音→2 真孤儿) + X2 freshness check (9 rules) + DEBT-EVIDENCE rule target 修正 (26 bin) | ACCEPTED | 2026-06-25 | omostation P84 | 0078-p84-mof-coverage-x2-freshness.md |
| 0079 | P85 X2 rule lint + adr-coverage + COMMIT-FATIGUE rule 修正 (37 ADRs 100% 健康, 28 bin) | ACCEPTED | 2026-06-25 | omostation P85 | 0079-p85-x2-rule-lint-adr-coverage.md |

---

## 命名规则

`NNNN-<kebab-case-title>.md`，编号 4 位 zero-padded 全局递增。

- 0001-0099: Phase 28 期间决策
- 0100-0999: 后续 Phase 决策
- 1000+: 长生命周期核心架构决策

## Status 状态机

```
   PROPOSED ──> ACCEPTED ──> DEPRECATED
                    │
                    └──> SUPERSEDED by ADR-NNNN
```

| Status | 含义 |
|--------|------|
| `PROPOSED` | 提案中，待评审；尚未落地实施 |
| `ACCEPTED` | 已接受并实施；当前生效 |
| `DEPRECATED` | 仍有效但不再推荐用于新场景；旧系统维持 |
| `SUPERSEDED` | 已被新 ADR 替代（必须填 `Superseded by: ADR-NNNN`） |

---

## 主题分类

### L0 — 路由/网关（agora）

- ADR-0001: agora 路由表精简策略（L1 包按需注册）
- ADR-0003: P28 TECH-RADAR 实施绕过 agora（W1 演示豁免）

### L1 — 包治理（kairon 31 包）

- ADR-0002: kairon-assistant / kairon-voice 首批归档
- ADR-0005: P29 架构升级（kairon 31 包 → L1 工程层）
- ADR-0006: kairon 17 包合并到 14 包（方向 C，3 组：llm-gateway-kernel / sot-bridge / protocols-layer）— **ACCEPTED**

### L2 — 治理与发布

- ADR-0007: 多仓库统一版本发布（VERSION + CHANGELOG + release.sh，6 项目共享 omostation-X.Y.Z）— **ACCEPTED**
- ADR-0008: in_progress 任务列表清理原则（4 类：completed / pending / cancelled / 删）— **ACCEPTED**

### L3 — 治理增强 (P50+)

- ADR-0050: gbrain 53 TODOs 4 类决策（keep/fix/close/planned + 根仓 0 行 gbrain 代码）— **ACCEPTED** | 2026-06-23 | omostation P50 | 0050-gbrain-53-todos-4-cat.md
- ADR-0051: gbrain TODOs v5 终极收敛（unknown 19→0, any TODO = planned, extends ADR-0050; 2 LOW 信息维度保留）— **ACCEPTED** | 2026-06-23 | omostation P52 | 0051-gbrain-todos-v5-unknown-zero.md
- ADR-0052: P54-P55 知识面深度收敛（design/specs/ 契约区建立 + plans-archive/dbo-archive 迁移 + memtheta 真迁移 + frontmatter 100% 全覆盖 + 断链 SSOT 修复）— **ACCEPTED** | 2026-06-23 | omostation P56 | 0052-p54-p55-knowledge-convergence.md

---

## 维护责任

- **新增 ADR**: 任何 Phase 收尾时由治理 Agent 触发（参考 `README.md` 维护规则）
- **冲突处理**: 编号冲突时由人类审批
- **过期判定**: 每个 Phase 入口处审阅已 `ACCEPTED` 的 ADR，决定是否需 `DEPRECATED`
  或 `SUPERSEDED`

---

## 相关文件

- 模板与规则: [`README.md`](./README.md)
- 候选收集任务: `P28-W1-ADR-COLLECT`（已完成）
- 制度化任务: `P28-W3-ADR-SETUP`（本批 ADR 的来源）

---

*最近更新: 2026-06-23 · Owner: governance-team · 0050/0051 状态 ACCEPTED (P50/P52)*
