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
| 0131 | (保留) | — | — | — | — |
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

*最近更新: 2026-07-06 · Owner: governance + eCOS team · M4 元模型方案 ADR-0132 PROPOSED (L0/M0/MOF 统一,14 周 5 阶段 38 里程碑)*
