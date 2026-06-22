---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# Phase 29 — 工具体系韧性 (Toolchain Resilience)

> **状态**: ✅ 已完成 (P29, 2026-06-06)
> **实施摘要**: 7 个 P29 任务全部 completed
> - P29-W0-E2E-EVAL (召回率 0.80 A)
> - P29-W0-FOLLOW-UP (19 假 completed 修复)
> - P29-W0-GOVERNANCE-AUDIT (巡检器, 揭穿虚高 98.5)
> - P29-W1-LINT-FIX (42 错误归零)
> - P29-W1-DATA-CONSISTENCY (system.yaml 同步器)
> - P29-W1-ARCH-EXPLORE (ADR-0005)
> - P29-W2-KAIRON-GOVERNANCE-PKG (88 测试, 已迁 omo 见 P30-W1-GOV-MERGE)
> - P29-W3-DAEMON-AGORA-HEALTH (daemon + agora 探活)

> 目标: 修复流程缺陷，建立自动化质量门禁，消除"修复被回滚"和"测试反馈慢"两类流程风险
> 优先级: P0 | 预估: 1-2 周
> 依赖: 无

---

## 一、需求分析

### 1.1 问题陈述

当前三条流程缺陷在 Phase 28 修复周期中被暴露：

| 问题 | 严重度 | 发生频率 |
|------|--------|---------|
| 未提交修改被 git reset 回滚 | 每次跨 Agent 协同都会触发 | 确定发生 |
| Pre-commit 阻塞合法提交 | 每次修改都伴随 29 个无关文件 lint | 100% |
| 无快速测试反馈回路 | 开发时无法在 10s 内确认是否破坏已有功能 | 持续存在 |

### 1.2 用户故事

- **作为 AI Agent**，我希望修改文件后不会因为其他环节的 git reset 而丢失工作
- **作为开发者**，我希望提交代码时只检查我修改的文件，而不是全仓库 29 个旧 lint
- **作为开发者**，我希望修改一个包后能在 5s 内运行测试确认没破坏它

### 1.3 验收标准

- [ ] kairon 所有子项目的 pre-commit 全部采用 diff-only 模式
- [ ] `make test-diff` 能在 5s 内对单个包的修改完成测试
- [ ] AGENTS.md 的 commit 纪律被新加入的 Agent 理解并遵守
- [ ] 创建"变更风险检测"机制：git reset/stash 前检测未提交修改并报警

---

## 二、实施计划

### Wave 1: Pre-commit 统一化 (1h)
- [ ] 遍历所有项目（kairon, runtime, omo, gbrain），统一 pre-commit 到 diff-only 模式
- [ ] 根仓库 `.githooks/` 配置标准 pre-commit 模板
- [ ] 验证: 修改一个文件后 commit，只检查该文件

### Wave 2: 快速测试覆盖 (2h) — 已完成
- [x] `make test-diff` 实现
- [ ] 调研 `make test-fast` 是否可并行化（各包并行 pytest）
- [ ] 将 test-diff 接入 pre-commit（提交前自动运行修改包的测试）

### Wave 3: 变更安全网 (2h)
- [ ] 创建 git 安全包装器: `git safe-reset` 在 reset/stash 前检查未提交修改
- [ ] `.bashrc` / `.zshrc` 别名覆盖 `git reset` 为安全版本
- [ ] 集成到 Hermes cron 的变更通知链

---

## 三、参考

- 根因分析: `.omo/_knowledge/management/deep-defects-analysis-2026-06-06.md`
- 当前纪律: `AGENTS.md` gotcha #8/#9/#10
- Pre-commit 位置: `~/.hermes/scripts/git-hooks/pre-commit`
