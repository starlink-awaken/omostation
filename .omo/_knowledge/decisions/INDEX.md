---
status: active
lifecycle: index
owner: governance-team
last-reviewed: 2026-06-29
note: "P45 曾标记 archived, 但 ADR 索引仍活跃维护, 2026-06-29 恢复 active"
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
| 0080 | P86 pre-commit 集成 4 工具 (x2-rule-lint/mof-m2-coverage/adr-coverage/dashboard) + governance dashboard (29 bin, 26 hooks) | ACCEPTED | 2026-06-25 | omostation P86 | 0080-p86-precommit-integration-dashboard.md |
| 0081 | P87 god-module 拆解 roadmap + X2 rule 交互式添加 + dashboard 扩展 9 工具 (31 bin) | ACCEPTED | 2026-06-25 | omostation P87 | 0081-p87-god-module-roadmap-x2-rule-add.md |
| 0082 | P88 omo_lint 拆解 (1560→1257L, -19.4%) + X2 rule template standard + gov-trend-report (32 bin, 10 dashboard) | ACCEPTED | 2026-06-25 | omostation P88 | 0082-p88-omo-lint-split-x2-template-trend.md |
| 0083 | P89 rule-history-insight (8/9 fresh) + adr-drift-check (109 历史 issues) + dashboard 12 工具 (34 bin) | ACCEPTED | 2026-06-25 | omostation P89 | 0083-p89-rule-history-adr-drift.md |
| 0084 | P90 X2-FRESH-OMO-LINT-SIZE rule + adr-drift-classify + governance dashboard cron + dashboard 13 工具 (35 bin) | ACCEPTED | 2026-06-25 | omostation P90 | 0084-p90-x2-rule-adr-classify-cron.md |
| 0085 | P91 install-dashboard-cron + X2-FRESH-GOV-DASHBOARD (11 rules) + gov-history-stats + .yaml 修 (36 bin, 14 dashboard) | ACCEPTED | 2026-06-25 | omostation P91 | 0085-p91-cron-install-gov-stats.md |
| 0086 | P92 adr-trend-insight (44 ADRs 100% frontmatter) + install-dashboard-cron 推入 scripts/ + 6 类别趋势深化 (37 bin, 15 dashboard) | ACCEPTED | 2026-06-25 | omostation P92 | 0086-p92-adr-trend-scripts-install.md |
| 0087 | P93 adr-drift-auto-fix (32 P50+, 30/94% auto-fix) + gov-history-stats --compare (+2.2 delta) (38 bin, 16 dashboard) | ACCEPTED | 2026-06-25 | omostation P93 | 0087-p93-adr-drift-auto-fix-compare.md |
| 0088 | P94 adr-drift-apply (19 SUBDIR touch 待) + 13 god-module list (24252L excess) + REAL_BUG 修 (40 bin, 18 dashboard) | ACCEPTED | 2026-06-25 | omostation P94 | 0088-p94-adr-apply-god-module-bugfix.md |
| 0089 | P95 adr-drift-apply --apply (20 files) + adr-typo-fix (新) + pyyaml 修 + 7 步 roadmap (41 bin, 19 dashboard) | ACCEPTED | 2026-06-25 | omostation P95 | 0089-p95-adr-apply-typo-fix-7step.md |
| 0090 | P96 adr-typo-real-fix (真 Levenshtein, 6/8 ratio 1.0) + venv-yaml-check + X2-FRESH-ADR-DRIFT (12 rules) (43 bin, 21 dashboard) | ACCEPTED | 2026-06-25 | omostation P96 | 0090-p96-typo-levenshtein-venv-x2.md |
| 0091 | P97 TYPO apply (12 实际修复, 19→11 -42%) + apply/rollback 集成测试 + X2-FRESH-ADR-TYPO (13 rules) (44 bin, 22 dashboard) | ACCEPTED | 2026-06-25 | omostation P97 | 0091-p97-typo-apply-rollback-test-x2.md |
| 0092 | P98 3 ASPIRATIONAL + 1 REAL_BUG + 4 TYPO + regex bug 修 (P50+ 19→2 -89%, 44 bin, 22 dashboard) | ACCEPTED | 2026-06-25 | omostation P98 | 0092-p98-adr-drift-final-fixes.md |
| 0093 | P99 ADR-0092 self-ref 清 (P50+ 6→3 -50%) + omo_lint 兑现路径 P100-P103 (4 步) + 53 ADR + 22 dashboard | ACCEPTED | 2026-06-25 | omostation P99 | 0093-p99-selfref-omo-lint-roadmap.md |
| 0094 | P100 omo_lint schemas 子模块拆分 (1269→800L, 兑现 11 轮推迟) | ACCEPTED | 2026-06-25 | omostation | 0094-p100-omo-lint-schemas-split.md |
| 0095 | P101 omo_lint yaml-bypass 子模块拆分 (800→731L, 校正 P102-P103 | ACCEPTED | 2026-06-25 | omostation | 0095-p101-omo-lint-yaml-bypass-split.md |
| 0096 | P102 omo_lint surfaces 子模块拆分 (731→594L, <600L ideal 达成) | ACCEPTED | 2026-06-25 | omostation | 0096-p102-omo-lint-surfaces-split.md |
| 0097 | P103 omo_lint mutation-ledger 子模块拆分 (594→544L, ADR-0093 | ACCEPTED | 2026-06-25 | omostation | 0097-p103-omo-lint-mutation-ledger-split.md |
| 0098 | P104 omo_governance_surfaces snapshots 子模块拆分 (1762→1244 | ACCEPTED | 2026-06-25 | omostation | 0098-p104-governance-surfaces-snapshots-split.md |
| 0099 | P105 omo_governance_surfaces ingress-check 子模块拆分 (1244→ | ACCEPTED | 2026-06-25 | omostation | 0099-p105-governance-surfaces-ingress-split.md |
| 0100 | P106 omo_governance_surfaces 4 子模块化 (1022→763L, <800L w | ACCEPTED | 2026-06-25 | omostation | 0100-p106-governance-surfaces-4-submodules.md |
| 0101 | P107 omo_governance_surfaces 6 子模块化 (763→556L, <600L id | ACCEPTED | 2026-06-25 | omostation | 0101-p107-governance-surfaces-6-submodules.md |
| 0102 | P108 omo_governance_surfaces 8 子模块化 (556→443L, 黄金值 400- | ACCEPTED | 2026-06-25 | omostation | 0102-p108-governance-surfaces-8-submodules.md |
| 0103 | P109 治理赋能三件套 (验证模板 + 智能化 + TS 工具) | ACCEPTED | 2026-06-25 | omostation | 0103-p109-governance-tooling-trio.md |
| 0104 | P110 omo_ingress_task_lifecycle 3 子模块化 (1530→614L, <800 | ACCEPTED | 2026-06-25 | omostation | 0104-p110-ingress-task-lifecycle-3-submodules.md |
| 0105 | Phase 0 BOS Contract Linter (mof-contract-lint) 落地 | ACCEPTED | 2026-06-25 | omostation | 0105-phase0-bos-contract-linter.md |
| 0106 | GaC 治理即代码架构 (Governance-as-Code) | ACCEPTED | 2026-06-26 | omostation | 0106-gac-governance-as-code.md |
| 0107 | Phase 3 BOS Contract Linter v0.3 (mof-contract-agent) | ACCEPTED | 2026-06-25 | omostation | 0107-phase3-bos-contract-linter.md |
| 0108 | P110-A ecos domain_manager 2 子模块化 (1914→1406L) | ACCEPTED | 2026-06-25 | omostation | 0108-p110a-ecos-domain-manager-split.md |
| 0109 | P110-B omo_governance_surfaces build_report 子模块化 (443→2 | ACCEPTED | 2026-06-25 | omostation | 0109-p110b-build-report-split.md |
| 0110 | P110-C Phase 1 BOS Contract Linter 强制接入 (3 交付物) | ACCEPTED | 2026-06-25 | omostation | 0110-p110c-phase1-enforcement.md |
| 0111 | P110-D TS AST 工具升级 (ts-morph 替代, 10 TS god-module 解锁) | ACCEPTED | 2026-06-25 | omostation | 0111-p110d-ts-ast-tool-upgrade.md |
| 0112 | P111 修复 dashboard 退化 (2 工具退出码语义 + ADR 0108 duplicate) | ACCEPTED | 2026-06-25 | omostation | 0112-p111-dashboard-fix.md |
| 0113 | Phase 2 BOS Contract Linter v0.2 (--explain + --impact) | ACCEPTED | 2026-06-25 | omostation | 0113-phase2-bos-contract-linter.md |
| 0114 | L4 自我层 GaC 强约束豁免 | ACCEPTED | 2026-06-29 | omostation | 0114-l4-gac-exemption.md |
| 0115 | P52 model-driven LifecycleStage 7→8 阶段 (P60 GOVERNANCE_MAINTENANCE) | SUPERSEDED | 2026-06-30 | governance-team | 0115-p52-model-driven-8-stages.md |
| 0116 | Tier 1 渐进式修复 vs Tier 2 真治本 (Meta-Reflection) | ACCEPTED | 2026-06-30 | governance-team | 0116-p52-meta-tier1-vs-tier2.md |
| 0117 | 撤销 P60 GOVERNANCE_MAINTENANCE 阶段 (P52 真治本) | ACCEPTED | 2026-06-30 | governance-team | 0117-p52-undo-p60-stage-8.md |
| 0118 | 根仓 dev-deps 统一 — 部分真治本 + P3 follow-up | PARTIAL | 2026-06-30 | governance-team | 0118-p52-partial-root-dev-deps.md |
| 0119 | Workspace 系统性优化 Roadmap (2026 H2) — 3 阶段 S0/S1/S2/S3 | ACCEPTED | 2026-07-01 | governance-team | 0119-systemic-optimization-roadmap-2026h2.md |
| 0120 | Runtime 健康监控语义修正与 SSOT 一致性加固 (freshness uptime/staleness 分离 + matrix lint) | PROPOSED | 2026-07-02 | governance-team | 0120-runtime-health-semantics-fix.md |
| 0121 | Governance Convergence Special Initiative (GCSI) — 治理收敛专项 (规则/分数/回路/SSOT 4 维收敛) | PROPOSED | 2026-07-02 | governance-team | 0121-governance-convergence-initiative.md |
| 0122 | 系统审计 follow-up 路线图 (18 项 S0 落地: GaC-RULE M1 sync + governance-checks 注册) | ACTIVE | 2026-07-02 | governance-team | 0122-system-audit-followup-plan.md |
| 0123 | bin/ 治理工具集重整 (命名归一 + 孤立工具接入 gate) | PROPOSED | 2026-07-02 | governance-team | 0123-bin-governance-rationalize.md |
| 0124 | S1 阶段完结复盘 — 5 PR + 1 修 + 1 cleanup (P72 follow-up pattern) | ACTIVE | 2026-07-02 | governance-team | 0124-s1-followup-retrospective.md |
| 0125 | S2 阶段 S1 部分复盘 — F-2 + ADR-0115 Phase 2/4 (5 commit, 1 PR) | ACTIVE | 2026-07-02 | governance-team | 0125-s2-followup-retrospective.md |
| 0126 | S2 阶段深度分析 (2026-07-03) — 当前状态 + 后续建议 | ACTIVE | 2026-07-03 | governance-team | 0126-s2-final-analysis.md |
| 0127 | Code Review: S2 阶段主仓 PR + 后续 (2026-07-03) | ACTIVE | 2026-07-03 | governance-team | 0127-code-review-s2.md |
| 0128 | 多 Agent 并发下治理状态生成的架构收敛 | PROPOSED | 2026-07-03 | governance-team | 0128-state-generation-concurrency.md |
| 0129 | 运行时投影面分离（ADR-0128 Phase 3 治本设计） | PROPOSED | 2026-07-03 | governance-team | 0129-state-projection-plane-phase3.md |
| 0130 | P74 工作流常态化治理 (Workflow Solidification) | ACTIVE | 2026-07-03 | governance-team | 0130-p74-workflow-solidification.md |
| 0131 | (保留) | — | — | — | 0131-reserved.md |
| 0132 | L0 / M0 / MOF 统一元模型 (M4 升级) | ACCEPTED | 2026-07-06 | governance + eCOS team | 0132-l0-mof-m4-metamodel.md |
| 0133 | L0-constraints v2 派生面 — 双轨切单轨 | ACCEPTED | 2026-07-06 | governance + eCOS team | 0133-l0-constraints-v2-cutover.md |
| 0134 | meta_model ↔ m3.yaml 双轨桥接受 (M3-meta ACCEPTED) | ACCEPTED | 2026-07-06 | governance + eCOS team | 0134-m3-meta-cutover.md |
| 0135 | 派生面统一收口 (ADR-0129 范式 enforcement) | ACCEPTED | 2026-07-06 | governance-team | 0135-derived-plane-unification.md |
| 0136 | P5 phase — m3.yaml 扩展 4 gap 治本 | ACCEPTED | 2026-07-06 | governance + eCOS team | 0136-m3-yaml-extension-p5.md |
| 0137 | 派生面落点纠偏 — 跟随 SSOT 源所在子模块 | ACCEPTED | 2026-07-06 | governance + eCOS team | 0137-derived-plane-relocation.md |
| 0138 | 元元模型类目提升至 m3.yaml 主流 (Round 2b) | ACCEPTED | 2026-07-06 | governance + eCOS team | 0138-meta-element-promotion.md |
| 0139 | model-driven 8 阶段复活评估 — 拒回 (Round 2c) | ACCEPTED | 2026-07-06 | governance + eCOS team | 0139-model-driven-8stage-revival-rejected.md |
| 0140 | M4 Health Score 量化与派生面落地 (Round 3b) | ACCEPTED | 2026-07-06 | governance + eCOS team | 0140-m4-health-score.md |
| 0141 | M2BaseSchema 抽象基类 + check_5 (Round 3a) | ACCEPTED | 2026-07-06 | governance + eCOS team | 0141-m2-base-schema.md |
| 0142 | M4 决策速查表 (Round 4b) | ACCEPTED | 2026-07-06 | governance-team | 0142-decisions-quick-ref.md |
| 0143 | 45 m2 schema date → datetime 迁移 (Round 4c) | ACCEPTED | 2026-07-06 | governance + eCOS team | 0143-m2-date-migration.md |
| 0144 | M4 Cron Hook (Round 4d) | ACCEPTED | 2026-07-06 | governance-team | 0144-m4-cron-hook.md |
| 0145 | MCPTOOL 集合占位识别 (Round 4a) — 100/100 Health Score | ACCEPTED | 2026-07-06 | governance + eCOS team | 0145-mcptool-collection-skip.md |
| 0146 | 8 阶段反向 ADR 稳定性声明 (Round 5a) | ACCEPTED | 2026-07-06 | governance + eCOS team | 0146-8stage-stability-declaration.md |
| 0147 | MCPTOOL M1 Adder Guide (Round 5b) | ACCEPTED | 2026-07-06 | governance + eCOS team | 0147-mcptool-adder-guide.md |
| 0148 | Round-Trip 流程文档化 (Round 5c) | ACCEPTED | 2026-07-06 | governance + eCOS team | 0148-round-trip-playbook.md |
| 0149 | P71 Baseline 防重做 (Round 5d) | ACCEPTED | 2026-07-06 | governance-team | 0149-p71-baseline-no-replay.md |
| 0150 | Submodule PR 反向 Review (Round 5e) | ACCEPTED | 2026-07-06 | governance-team | 0150-submodule-pr-reverse-review.md |
| 0151 | 子模块 gitignore 守门 (Round 5f) | ACCEPTED | 2026-07-06 | governance-team | 0151-submodule-hygiene-gate.md |
| 0152 | M4 5 GaC 规则追加 (Phase 1) | ACCEPTED | 2026-07-06 | governance + eCOS team | 0152-m4-gac-rules.md |
| 0153 | M4 4 工具入 agent-workflows (Phase 2b) | ACCEPTED | 2026-07-06 | governance + eCOS team | 0153-m4-agent-workflows-tools.md |
| 0154 | M4 OMO cron 集成 (Phase 4) | ACCEPTED | 2026-07-06 | governance-team | 0154-m4-omo-cron-integration.md |
| 0155 | P76 Phase 1 收口 (积压清理) | ACCEPTED | 2026-07-07 | governance-team | 0155-p76-phase1-cleanup.md |
| 0156 | P76 Phase 2 分层调用方向契约硬化 | ACCEPTED | 2026-07-07 | governance-team | 0156-p76-phase2-call-direction.md |
| 0157 | P76 Phase 3 元治全自 + debt-closed-per-feature | ACCEPTED | 2026-07-07 | governance-team | 0157-p76-phase3-self-meta.md |
| 0158 | P76 Phase 4 X 扩展晋升 + submodule 对称 | ACCEPTED | 2026-07-07 | governance-team | 0158-p76-phase4-promotion.md |
| 0159 | P76 Phase 5 收敛面+演化平台 + 全路线收口 | ACCEPTED | 2026-07-07 | governance-team | 0159-p76-phase5-foundry.md |
| 0160 | P76 Phase 6 Knowledge Foundry 真正集成 (radar_cron) | ACCEPTED | 2026-07-07 | governance-team | 0160-p76-phase6-foundry-runtime.md |
| 0161 | P76 Phase 7 follow-up 治本 (LLM+cron+tasks+mesh-router) | ACCEPTED | 2026-07-07 | governance-team | 0161-p76-phase7-llm-cron-tasks-mesh.md |
| 0162 | P76 Phase 8 4 项真工程 follow-up 治本 | ACCEPTED | 2026-07-07 | governance-team | 0162-p76-phase8-real-engineering.md |
| 0163 | P76 Phase 9A commit-assist pre-commit-msg hook (advisory) | ACCEPTED | 2026-07-07 | governance-team | 0163-p76-phase9a-commit-assist-hook.md |
| 0164 | P77 Phase 1 跨仓一致性 (cross-repo consistency) | ACCEPTED | 2026-07-07 | governance-team | 0164-p77-phase1-cross-repo-consistency.md |
| 0165 | P77 Phase 2 演化护栏 catalog (15 原则形式化 + 5 新 GaC rules) | ACCEPTED | 2026-07-07 | governance-team | 0165-p77-phase2-evolution-guardrails.md |
| 0166 | P77 Phase 3 跨仓 unregistered 治本 (threshold 0 + 26 unregistered 补登 + 升 hard) | ACCEPTED | 2026-07-07 | governance-team | 0166-p77-phase3-cross-repo-remediation.md |
| 0167 | P77 Phase 4 跨仓 port-registry 一致性 (load bug 修 + yaml comment strip + 6 端口对齐) | ACCEPTED | 2026-07-07 | governance-team | 0167-p77-phase4-port-registry-consistency.md |
| 0168 | P77 Phase 5 跨仓端口硬编码扫描 (5 port 补登 + 7 port-context pattern + 5 LEGACY_OK_PORTS) | ACCEPTED | 2026-07-07 | governance-team | 0168-p77-phase5-hardcoded-ports.md |
| 0169 | P77 Phase 6 commit-assist E2E 验收 (19 测试 + heuristic bug 修) | ACCEPTED | 2026-07-07 | governance-team | 0169-p77-phase6-commit-assist-e2e.md |
| 0170 | P77 Phase 7 端口 env var 重构 (25 env var 映射 + root repo 迁移) | ACCEPTED | 2026-07-07 | governance-team | 0170-p77-phase7-env-var-port-migration.md |
| 0171 | 宪法 Wave 1 — 治理规则 severity 分层 (red/gray, executor 推导, 159 red + 12 gray) | ACCEPTED | 2026-07-08 | governance-team | 0171-constitution-wave1-severity-classification.md |
| 0172 | P78 端口注册表收敛 (deprecated 清理 + transport 字段) | ACCEPTED | 2026-07-08 | governance-team | 0172-p78-port-registry-convergence.md |
| 0173 | P78 Phase 2 基线重放 + Foundry v2 (10-deck) | ACCEPTED | 2026-07-08 | governance-team | 0173-p78-phase2-baseline-foundry-v2.md |
| STRAT-P79 | P79 2026H2 治理巩固 + Foundry 运营化路线图 (5 phase) | PROPOSED | 2026-07-08 | governance-team | STRAT-P79-strategic-roadmap.md |
| 0174 | P79 Phase 1 Foundry v2 cron 集成 (10-deck) | ACCEPTED | 2026-07-08 | governance-team | 0174-p79-phase1-foundry-v2-cron.md |
| 0175 | P79 Phase 2 Health 100 (bare ports 分类 + env var 迁移) | ACCEPTED | 2026-07-08 | governance-team | 0175-p79-phase2-health-100.md |
| 0176 | P79 Phase 3 跨仓零残留 (ecos 结构化对齐) | ACCEPTED | 2026-07-08 | governance-team | 0176-p79-phase3-cross-repo-zero-residual.md |
| 0177 | P79 Phase 4 文档刷新 (ARCHITECTURE.md port-registry) | ACCEPTED | 2026-07-08 | governance-team | 0177-p79-phase4-docs-refresh.md |

| 0178 | P79 Phase 5 收官 (SOP + GaC 173 冻结 + 结项) | ACCEPTED | 2026-07-08 | governance-team | 0178-p79-phase5-closeout.md |
| 0179 | runtime 探测假阳性根治本 (launcher-zombie + import 断裂 + self-heal 死循环) | ACCEPTED | 2026-07-10 | governance-team | 0179-runtime-probe-false-positive-treatment.md |
| 0180 | bus-foundation 全面落地 (P7x rollout: topics SSOT + dormant-adapter gate + P74) | ACCEPTED | 2026-07-13 | governance-team | 0180-bus-foundation-rollout.md |
| 0181 | metaos × ecos 方案 C — 三平面契约化 (Phase 1–4) | ACCEPTED | 2026-07-14 | governance-team + eCOS | 0181-metaos-ecos-scheme-c-planes.md |
| 0182 | CI / evidence / BOS registry 常态化落地 | ACCEPTED | 2026-07-14 | governance-team | 0182-ci-evidence-bos-landing.md |
| 0183 | Wave 2 C2G+OMO Phase A 数据闭环范围 | ACCEPTED | 2026-07-14 | governance-team | 0183-wave2-c2g-omo-phase-a.md |
| 0184 | Scheme C Phase 5b Container Executor 运行时模型 | ACCEPTED | 2026-07-15 | governance-team | 0184-scheme-c-5b-container-executor.md |
| 0185 | Wave 2 Phase B 预测增强 + 可视化导出 | ACCEPTED | 2026-07-15 | governance-team | 0185-wave2-phase-b-predictive-viz.md |
| 0186 | Scheme C Phase 5c OS 写面 ACL 设计 (design-only) | ACCEPTED | 2026-07-15 | governance-team | 0186-scheme-c-5c-os-acl-design.md |
| 0187 | Scheme C 5c L1 path-acl 只读巡检 | ACCEPTED | 2026-07-15 | governance-team | 0187-scheme-c-5c-l1-path-acl-doctor.md |
| 0188 | Wave 2 Phase C C2G→OMO 治理提案联动 | ACCEPTED | 2026-07-15 | governance-team | 0188-wave2-phase-c-governance-feedback.md |
| 0190 | Wave2 dashboard JSON v1 + cockpit entry | ACCEPTED | 2026-07-15 | governance-team | 0190-wave2-dashboard-json-contract.md |
| 0191 | Cockpit UI Wave2 dashboard 消费 | ACCEPTED | 2026-07-15 | governance-team | 0191-wave2-cockpit-ui-dashboard.md |
| 0192 | Wave2 提案→TaskCenter 闭环 (dry-run plan) | ACCEPTED | 2026-07-15 | governance-team | 0192-wave2-proposal-taskcenter-handoff.md |
| 0193 | Wave2 demo OutcomeTracker seed | ACCEPTED | 2026-07-15 | governance-team | 0193-wave2-demo-outcome-seed.md |
| 0194 | Scheme C 5c setfacl 细粒度设计 (design-only) | ACCEPTED | 2026-07-15 | governance-team | 0194-scheme-c-5c-setfacl-design.md |
| 0189 | Scheme C 5c L2 omo acl plan/apply | ACCEPTED | 2026-07-15 | governance-team | 0189-scheme-c-5c-l2-acl-plan-apply.md |
| 0195 | Architecture Convergence (ISC-2) 声明/执行鸿沟收敛 | ACCEPTED | 2026-07-14 | governance-team | 0195-architecture-convergence-isc2.md |
| 0197 | Wave2 Cockpit 加载演示数据按钮 | ACCEPTED | 2026-07-15 | governance-team | 0197-wave2-demo-seed-ui-button.md |
| 0198 | omo acl apply --yes --acl 命名 ACE 执行 | ACCEPTED | 2026-07-15 | governance-team | 0198-omo-acl-apply-named-ace.md |
| 0199 | omo doctor 纳入 path-acl 日常节奏 | ACCEPTED | 2026-07-15 | governance-team | 0199-omo-doctor-path-acl-rhythm.md |
| 0200 | operating-rhythm 接入 omo-doctor-cron | ACCEPTED | 2026-07-15 | governance-team | 0200-omo-doctor-cron-operating-rhythm.md |
| 0201 | Doctor-cron 状态 API + path-acl 连续 warn 告警 | ACCEPTED | 2026-07-15 | governance-team | 0201-doctor-cron-status-api-alert.md |
| 0202 | 假绿灯防线三件套 (非空守卫/迁移保内容/并发验证纪律) | ACCEPTED | 2026-07-15 | governance-team | 0202-fake-green-prevention.md |
| 0203 | 需求迭代强制走 Agent Workflow | ACCEPTED | 2026-07-15 | governance-team | 0203-requirement-iteration-workflow-mandatory.md |
| 0204 | ADR-0203 可执行闸门 + pre-push 路径 + worktree/ADR 占号 | ACCEPTED | 2026-07-15 | governance-team | 0204-requirement-iteration-enforcement.md |
| 0205 | 5b Docker digest pin + macOS ACL host validation | ACCEPTED | 2026-07-15 | governance-team | 0205-docker-digest-pin-acl-host-validation.md |
| 0206 | omo-acl-ops-window 运维窗口脚本 | ACCEPTED | 2026-07-15 | governance-team | 0206-omo-acl-ops-window.md |
| 0207 | macOS 主机 omo acl apply --acl 实机证据 | ACCEPTED | 2026-07-15 | governance-team | 0207-macos-acl-host-apply-evidence.md |
| 0208 | macOS group ACE via OMO_ACL_GROUP=staff | ACCEPTED | 2026-07-15 | governance-team | 0208-macos-acl-staff-group-ace.md |
| 0209 | ledger events.jsonl trim 元凶未定位 + SSOT 编号虚标反思 | PROPOSED | 2026-07-15 | governance-team | 0209-ledger-trim-and-adr-ssot-renumbering.md |
| 0210 | 三年综合战略方向 — 从"扩图纸"转向"收敛执行面" | ACCEPTED | 2026-07-15 | 夏明星 | 0210-three-year-strategy-execution-convergence.md |
| 0211 | P74 run_frequency 字段落地 + excluded_workflows 字段移除 | ACCEPTED | 2026-07-15 | governance-team | 0211-p74-run-frequency-field-and-excluded-workflows-removal.md |
| 0212 | ledger trim 现象修正：history gap 而非物理 trim | ACCEPTED | 2026-07-15 | governance-team | 0212-ledger-history-gap-not-physical-trim.md |
| 0213 | ADR-0209 附录 A 收口（A2 ledger heal / A4 read-only claim / A6 finding topics） | ACCEPTED | 2026-07-15 | governance-team | 0213-adr-0209-appendix-a2-a4-a6-closeout.md |
| 0214 | P74 silent 治本 D6：diff_checks 覆盖 4 silent workflow | ACCEPTED | 2026-07-15 | governance-team | 0214-p74-silent-diff-checks-coverage.md |
| 0215 | agora-gateway 假绿灯治本（PID 重置 + health_check 落盘） | ACCEPTED | 2026-07-15 | governance-team | 0215-agora-gateway-false-green-pid-health-check.md |
| 0216 | compass 健康刷新：feedback partial smoke + c2g 降级 | ACCEPTED | 2026-07-15 | governance-team | 0216-compass-feedback-partial-smoke.md |
| 0217 | Workflow 卫生：layer-check 误报修复 + 契约对齐 + evidence 愈合 | ACCEPTED | 2026-07-15 | governance-team | 0217-workflow-hygiene-layer-check-and-evidence.md |
| 0218 | Agent Isolation P0 核实生效态 + worktree 卫生固化 | ACCEPTED | 2026-07-15 | 夏明星 | 0218-agent-isolation-p0-verify-and-hygiene.md |
| 0219 | BOS 全量 evidence-smoke 可复现路径 | ACCEPTED | 2026-07-15 | governance-team | 0219-bos-evidence-smoke-full-path.md |
| 0220 | Swarm 协调纪律 M1 收口前置 | ACCEPTED | 2026-07-17 | 夏明星 | 0220-swarm-coordination-discipline-m1-gate.md |
| 0221 | G-DEL.5a 涌现/集体决策 L3 风险评审 | ACCEPTED | 2026-07-18 | 架构师 | 0221-g-del-5a-emergence-collective-decision-risk-review.md |
| 0222 | M1 冲突=0 证据标准扩展（对抗验证等效被动窗） | ACCEPTED | 2026-07-18 | 架构师 | 0222-m1-conflict-zero-evidence-standard-adversarial.md |
| 0223 | 阶段门禁 CI 硬阻断（phase gate enforcing） | ACCEPTED | 2026-07-18 | 架构师 | 0223-phase-gate-ci-enforcement.md |
| 0224 | conflict_count>0 时对抗路径须先溯源 | ACCEPTED | 2026-07-18 | 架构师 | 0224-m1-conflict-count-rootcause-before-adversarial-pass.md |
| 0225 | G-DEL 兑现期门禁维持物理多机口径（方案 A） | ACCEPTED | 2026-07-19 | 架构师 | 0225-g-del-physical-multihost-gate-caliber.md |
| 0196 | omo acl plan --acl 命名 ACE 干跑 | ACCEPTED | 2026-07-15 | governance-team | 0196-omo-acl-plan-named-ace.md |
| STRAT-P76 | P76 战略 5-phase 路线图 (12周) | ACCEPTED | 2026-07-07 | governance-team | STRAT-P76-strategic-roadmap.md |
| STRAT-P77 | P77 战略 12 周 5 phase: 跨仓一致性 + 演化护栏 | DRAFT | 2026-07-07 | governance-team | STRAT-P77-strategic-roadmap.md |

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

### P76 — 策略路线图 (ADR-0155..0163)

- ADR-0155: P76 Phase 1 (积压清理) — **ACCEPTED** | 2026-07-07 | omostation P76 | 0155-p76-phase1-cleanup.md
- ADR-0156: P76 Phase 2 (分层调用契约) — **ACCEPTED** | 2026-07-07 | omostation P76 | 0156-p76-phase2-call-direction.md
- ADR-0157: P76 Phase 3 (元治全自) — **ACCEPTED** | 2026-07-07 | omostation P76 | 0157-p76-phase3-self-meta.md
- ADR-0158: P76 Phase 4 (X扩展晋升) — **ACCEPTED** | 2026-07-07 | omostation P76 | 0158-p76-phase4-promotion.md
- ADR-0159: P76 Phase 5 (收敛面+foundry) — **ACCEPTED** | 2026-07-07 | omostation P76 | 0159-p76-phase5-foundry.md
- ADR-0160: P76 Phase 6 (foundry runtime) — **ACCEPTED** | 2026-07-07 | omostation P76 | 0160-p76-phase6-foundry-runtime.md
- ADR-0161: P76 Phase 7 (LLM/cron) — **ACCEPTED** | 2026-07-07 | omostation P76 | 0161-p76-phase7-llm-cron-tasks-mesh.md
- ADR-0162: P76 Phase 8 (真工程) — **ACCEPTED** | 2026-07-07 | omostation P76 | 0162-p76-phase8-real-engineering.md
- ADR-0163: P76 Phase 9A (commit-assist hook) — **ACCEPTED** | 2026-07-07 | omostation P76 | 0163-p76-phase9a-commit-assist-hook.md

### P77 — 跨仓一致性战略路线图 (ADR-0164..0170)

- ADR-0164: P77 Phase 1 (跨仓一致 detector) — **ACCEPTED** | 2026-07-07 | omostation P77 | 0164-p77-phase1-cross-repo-consistency.md
- ADR-0165: P77 Phase 2 (演化护栏 catalog) — **ACCEPTED** | 2026-07-07 | omostation P77 | 0165-p77-phase2-evolution-guardrails.md
- ADR-0166: P77 Phase 3 (跨仓治本) — **ACCEPTED** | 2026-07-07 | omostation P77 | 0166-p77-phase3-cross-repo-remediation.md
- ADR-0167: P77 Phase 4 (port-registry 一致性) — **ACCEPTED** | 2026-07-07 | omostation P77 | 0167-p77-phase4-port-registry-consistency.md
- ADR-0168: P77 Phase 5 (端口硬编码扫描) — **ACCEPTED** | 2026-07-07 | omostation P77 | 0168-p77-phase5-hardcoded-ports.md
- ADR-0169: P77 Phase 6 (commit-assist E2E) — **ACCEPTED** | 2026-07-07 | omostation P77 | 0169-p77-phase6-commit-assist-e2e.md
- ADR-0170: P77 Phase 7 (端口 env var 重构) — **ACCEPTED** | 2026-07-07 | omostation P77 | 0170-p77-phase7-env-var-port-migration.md

### P78 — 端口注册表收敛 (ADR-0172..0173)

- ADR-0172: P78 (端口注册表收敛) — **ACCEPTED** | 2026-07-08 | omostation P78 | 0172-p78-port-registry-convergence.md
- ADR-0173: P78 Phase 2 (基线重放 + Foundry v2) — **ACCEPTED** | 2026-07-08 | omostation P78 | 0173-p78-phase2-baseline-foundry-v2.md

### P79 — 2026H2 治理巩固 + Foundry 运营化 (STRAT-P79)

- STRAT-P79: P79 战略路线图 (5 phase) — **PROPOSED** | 2026-07-08 | omostation P79 | STRAT-P79-strategic-roadmap.md
- ADR-0175: P79 Phase 2 (Health 100) — **ACCEPTED** | 2026-07-08 | omostation P79 | 0175-p79-phase2-health-100.md
- ADR-0176: P79 Phase 3 (跨仓零残留) — **ACCEPTED** | 2026-07-08 | omostation P79 | 0176-p79-phase3-cross-repo-zero-residual.md
- ADR-0177: P79 Phase 4 (文档刷新) — **ACCEPTED** | 2026-07-08 | omostation P79 | 0177-p79-phase4-docs-refresh.md
- ADR-0174: P79 Phase 1 (Foundry v2 cron 集成) — **ACCEPTED** | 2026-07-08 | omostation P79 | 0174-p79-phase1-foundry-v2-cron.md
- ADR-0178: P79 Phase 5 (收官: SOP + GaC 冻结) — **ACCEPTED** | 2026-07-08 | omostation P79 | 0178-p79-phase5-closeout.md

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

*最近更新: 2026-07-18 · Owner: governance-team · ADR-0221 G-DEL.5a L3 risk review; GaC rules 见 registry*
