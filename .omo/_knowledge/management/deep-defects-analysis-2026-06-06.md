---
category: guides
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# 系统深度缺陷与长期风险分析

> 生成日期: 2026-06-06
> 基于: 全量 73 项债务修复复盘 + 流程审计 + 工具链分析
> 状态: 已标记 debt 73 项全部清零，本文聚焦未追踪的结构性/流程性/长期性风险

---

## 一、修复流程缺陷

### 1.1 修复文件被隐式回滚（严重）⚠️

**现象**: P0-AGENTRT_CRITICAL 的 `mcp_server.py` 修复在 git 工作树中消失了，文件回到了原始的带 bug 状态。险些导致生产级缺陷未被修复。

**根因**: `.omc/` 的状态追踪/检查点机制可能无意中覆盖了工作树的修改。kairon 项目有自己的 `.omc/` 目录，可能包含状态回滚逻辑。

**影响**: 任何未提交的修复都可能被静默回滚。AI Agent 修改文件后如果未立即 commit，可能永远丢失。

**风险**: **高** — 下次修复同样的问题时，文件仍可能被回滚。

**建议**: 
- 关键修复必须立即 `git commit`
- 调查 `.omc/` 的回滚机制并明确其行为
- 在 AGENTS.md 中增加"修改后马上 commit"的纪律

### 1.2 Pre-commit Hook 阻塞合法提交

**现象**: 修复 `mcp_server.py` 时，pre-commit 的 ruff 检查发现了 29 个**不相关文件**的 lint 错误（engine.py, cron-service, ecos, forge, llm-gateway, wksp 等），阻止了提交。

**影响**: 开发者被迫使用 `--no-verify` 绕过检查。一旦绕过成为习惯，pre-commit 形同虚设。

**根因**: ruff 配置扫描整个 `packages/`，而 29 个错误是其他文件的历史遗留。修复一个文件→整包检查→到处报错。

**建议**:
- 将 pre-commit 的 ruff 检查限定为 `git diff --cached --name-only`（只检查已暂存文件）
- 或单独创建 `.pre-commit-config.yaml` 只检查变更文件
- 后续 Phase 规划全量 ruff 修复（当前 29 个错误的波次）

### 1.3 Submodule 管理混乱

**现象**: `scripts/` 目录是独立 git 仓库，但不是通过 `git submodule add` 注册的。`git status` 会在根仓库看到一个 dirty submodule 但无法用标准命令管理。

**影响**: 
- 根仓库 commit 时不会自动包含 scripts/ 的变更
- `scripts/validate_protocol_registry.py` 需要单独 commit 到子仓库
- GH Actions 引用 `scripts/validate_protocol_registry.py` 但 CI 中能否正确检出不清楚

**建议**: 修复期不建议动子模块结构。但应在 Phase 规划中考虑统一仓库策略。

---

## 二、工具链缺陷

### 2.1 无统一测试走通（P0 级别）

**已验证问题**: `make test-fast` 在 kairon 根目录执行时需要 2+ 分钟，且被 29 个 pre-commit lint 阻塞。开发者无法快速验证是否破坏现有功能。

**风险**: **高** — 无快速反馈回路，bug 易被引入不察觉。

### 2.2 跨仓库测试缺失

测试覆盖分布:
```
kairon:    293+ 测试文件 ✅
gbrain:    715 测试文件 ✅
runtime:   6  测试文件 (新增 3 个) ⚠️
root:      0  测试文件 ❌
```

没有跨项目集成测试的自动运行。根仓库 `.github/workflows/integration.yml` 存在但从未确认能否完整运行。

### 2.3 CI Gate 未实跑验证

即使已创建 `meta-model-check.yml`，无法确认 GitHub Actions 能否在真实环境中正确运行，因为没有最近的 CI 运行记录可供检查。

---

## 三、架构性长期风险

### 3.1 治理过密执行过疏（结构性问题）

OMO 治理体系极为完善（4 平面 + 债务台账 + 健康评分 + 审查队列），但存在两个系统性风险：

**A. 健康评分 ≈ 已登记债务数**：health_score 100 不意味着系统完美，仅意味着所有已知债务已标记为 resolved。未发现的问题不会降低评分。

**B. 债务发现依赖主动审计**：60+ 项债务分两波注册（上次审计 + 本次深度分析）。如果人类不主动做审计，债务不会自动被发现。\*这本质上是 "found debt / real debt" 之间的偏差。\*

### 3.2 架构文档与代码的两层皮趋势

5+3+1 架构定义清晰，但：
| 架构定义 | 代码实际 | 偏差 |
|---------|---------|------|
| L0 协议编织层 | 16 协议有 YAML 定义 + 运行时验证 | 完整协议实现缺失 |
| L1 运行时矩阵 | 项目存在（projects/runtime/）| 但 agent-runtime 在 kairon 内独立运行 |
| L2 Agora 是 I0 | 代码在 kairon/packages/ | 架构正确但代码位置没变 |
| L3 多入口桥接 | 只有 Hermes + Runtime MCP | Claude Code / Codex 适配器零实现 |

每次新 Phase 若只做概念设计不做代码落地，偏差会持续扩大。

### 3.3 项目膨胀信号

| 包 | 文件数 | 评估 |
|----|--------|------|
| agora | 90+ 文件 | 超载，集路由/认证/代理/仪表板/A2A 于一身 |
| agent-runtime | 50+ 顶级模块 | 开始微单体化 |
| omo | 60 文件 / 12,765 LOC | 合理但偏大 |

这三个项目在持续增长，没有拆分计划（AGORA_MODULE_SPLIT 已搁置）。

---

## 四、运行时可观测性缺陷

### 4.1 无统一服务面板

32 个运行时服务分散在 4 种运行模式:
- launchd (macOS 原生)
- Docker 容器
- Python 直接进程
- npm global 工具

`runtime dashboard` 已可以聚合基础信息，但没有统一的服务生命周期管理界面。

### 4.2 KEI 审计日志已累积但无人消费

KEI audit hook 已记录 11K+ 条操作记录。`runtime kei dashboard` 可以展示摘要，但仍无人定期查看或配置告警阈值。

### 4.3 无 LLM Token 使用量追踪

所有 LLM 调用流量经 agent-runtime 和 llm-gateway，但没有一处记录 Token 消耗。无法回答 "这个月花了多少钱"、"哪个任务最贵"。

---

## 五、项目治理风险

### 5.1 单点故障

当前所有架构决策、Phase 规划、债务审查完全依赖一个人。没有:
- 自动化的架构合规检查
- 定期债务审查机器人
- 变更影响分析工具

### 5.2 代码冻结与实际修复的矛盾

`.omo/state/system.yaml` 标记 `code_freeze: true`，但本轮修复了大量代码。冻结的目的是阻止功能迭代，修复债务属于例外。但没有机制区分"修复"和"迭代"——决策完全靠判断。

### 5.3 无版本发布策略

- kairon: 各包版本号写在 `pyproject.toml` 中但从未严格管理
- gbrain: v0.39.0（有版本号）
- runtime: v0.1.0（初始版本）
- omo: v0.1.0
- 无 changelog 或 release note 的统一管理
- 无向后兼容性保证

---

## 六、长期风险矩阵

| 风险 | 概率 | 影响 | 当前缓解 | 建议行动 |
|------|------|------|---------|---------|
| 修复文件被回滚 | 中 | 高 | .omc 机制未知 | 调查 .omc 行为 + 关键修改立即 commit |
| Pre-commit 阻塞 | 高 | 中 | --no-verify 绕过 | 隔离检查范围到已暂存文件 |
| 架构文档与代码偏差 | 确定 | 中 | 无自动校验 | 每 Phase 结束时做一次架构合规检查 |
| 单点故障 | 中 | 高 | 无 | 建立自动债务审查 + 架构规则检查 |
| 跨包测试缺失 | 高 | 中 | 存在 workflow 文件未验证 | 跑一次集成 CI 验证 |
| Agora 膨胀 | 确定 | 中 | 接受现状 | 中期规划拆分 |
| Token 成本失控 | 中 | 高 | 无追踪 | 在 llm-gateway 添加用量记录 |
| 代码冻结被绕过 | 确定 | 低 | 全靠判断 | 增加冻结例外的工作流 |
| 版本管理缺失 | 低 | 中 | 无 | 暂不增加复杂度 |
| submodule 混乱 | 低 | 低 | 工作区认知 | 统一仓库策略 |

---

## 七、总结

73 项债务清零后，系统真正的问题从"具体缺陷"转移到"流程/工具/治理"层面：

1. **最紧急**: 修复被回滚 (1.1) + Pre-commit 阻塞 (1.2)
2. **最影响效率**: 无快速测试反馈回路 (2.1)
3. **最影响决策**: 无健康评分偏差修正 (3.1)
4. **最长期**: 架构漂移 (3.2) + 项目膨胀 (3.3)
5. **最重要但最慢**: 可观测性 + 成本追踪 (4.2, 4.3)

以上建议按影响/难度排序。建议下一轮 Phase 从 "修复流程缺陷" 开始，而不是继续清 debt。
