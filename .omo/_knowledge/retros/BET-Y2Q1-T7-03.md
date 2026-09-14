---
status: active
lifecycle: history
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
title: BET-Y2Q1-T7-03 retrospective
type: doc
bet_id: BET-Y2Q1-T7-03
---

# BET-Y2Q1-T7-03 retrospective

## Q1. What was intended?

执行场景卡存储归一选项 A (夏明星 2026-09-05 拍板): 单一 SSOT 归一到 docs/scene-cards, 消灭与 .omo/_truth/scenarios 的双存储口径分裂。

## Q2. What happened?

- 3 张生命周期卡 (inbox-to-decision/meeting-to-delivery/research-to-insight) 迁入 docs/scene-cards 并 v2 合规 (schema v2 + bet + falsifier), validate --all 63→66 全 PASS
- 侦察发现 scenarios 店是混货: knowledge-capture-search 实为 scenario contract (phase-16, authorization: scenario-contract-only) → 迁 .omo/_truth/contracts/ 与 candidates 收集器语义对齐; research-pipeline-legacy 已 superseded → 归档 .omo/_archive/scenarios/
- 消费方改址 9 处: scene-card-review (3 path) / candidates DEFAULT_DIR / current-state-coherence / playbook / candidate-schema / scene-shadow-activate skill / WORKFLOW-MESH / knowledge-curation / v2-research-pipeline
- PR #3226 CI 33/33 PASS 合并 (7494bb12)

## Q3. What changed during implementation?

- 首版 sed 只换了路径尾段, 留下 .omo/_truth/scene-cards 错误父路径 — 自查抓出后二次修正。教训: 多段路径常量别用 sed 切段替换。
- CI capability-registry drift 两次: 首次是分支落后 #3227 的 registry 基线 (夹层 gitlink bump), rebase 后本地复现真实漂移 (skill 变更), 重同步修复。RTK 环境的 grep 是 rtk grep 别名, 多文件用法报 usage — 用 \grep 绕开。

## Q4. 遗留与跟进 (不阻塞)

1. **omo 子模块 phase15/16 的 scenarios 引用本就是死链** (指向不存在的 .omo/_truth/scenarios/research-pipeline.yaml) — 迁移前已断, 未扩战线修 omo, 应由 omo 侧清理或立小 BET
2. **ecos registry scene-cards.yaml 是第四家存储** (scene-card-review.py 头部 SSOT 注记指向它) — 归一它超出本 BET 范围, 建议与 ecos 团队对齐后另立
3. calibration 字段 (0.65) 随卡迁入 docs/scene-cards, review 工具的同源读取已打通 — calibration 与 lifecycle 的 tier 语义统一可在后续小迭代固化

## 相关

- spec: docs/superpowers/specs/2026-09-05-scene-card-store-unification-spec.md (选项 A + 决策记录)
- 提案: docs/plans/2026-09-05-scene-card-store-unification-proposal.md
- 前置: BET-Y2Q1-T7-02 (shadow 试验记录, #3215)
