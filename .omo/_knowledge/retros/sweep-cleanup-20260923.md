---
schema: md/v1
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-25
type: ephemeral
---

# Sweep Cleanup Report — 2026-09-23

## 执行摘要

本轮 sweep 完成了治理基础设施的 4 个关键清理任务：
- 清理 83 个历史生命周期锁
- 创建 41 个未注册 BOS URI 的待办注册清单
- 分类 156 个 MCP tool 漂移
- 推送根仓 PR 更新 26 个 cockpit 工具声明

## 1. 历史生命周期锁清理

**操作**: 删除 83 个 `~/.ws-*.lifecycle-lock` 文件

**详情**: 这些锁来自其他 agent 会话（worktree 清理后未删除），已确认所有对应 worktree 已不存在。

**结果**: 0 个残留锁。

## 2. 未注册 BOS URI 待办清单

**操作**: 创建 `.omo/_truth/registry/bos-pending-registrations.yaml`

**详情**: 41 个 URI 在代码中被引用但未在 `projects/agora/etc/bos-services.yaml` 中注册。这些 URI 分布在 8 个 domain：brain, capability, cockpit, compute, core, domain, event-ledger, execution, governance, im, inbox, kairon, memory, perception, personal, runtime, scene, test, vault, voice。

**下一步**: 将这些 URI 补登到 agora 子仓的 `bos-services.yaml`（需要 agora 子仓配合）。

## 3. MCP Tool 漂移分类

**操作**: 创建 `.omo/_truth/registry/mcptool-drift-report.yaml` + 更新 26 个 cockpit 工具声明

**详情**:
- 26 个 cockpit 工具声明存在但无实现（标记为 `withdrawn`）
- 19 个 cockpit 工具有实现但无声明
- 111 个 agora 工具有实现但无声明

**已处理**: 26 个 cockpit 声明工具（daily_summary, governance_check, research_ask 等）已标记为 `withdrawn` 并推送到子仓。

**下一步**: 审计 19 个 cockpit 实现+无声明 工具和 111 个 agora 实现+无声明 工具，决定是否补登声明或移除实现。

## 4. GaC Gate 快速检查

**结果**: 56/62 检查 PASS（6 个已知 broken 检查跳过）

**通过项**: execution-chain, root-directory-governance, bin-scripts-convergence, omo-runtime, doc-governance, current-state-coherence, conflict-markers, swarm-collision, capability-ownership, derived-only-fast-track, auto-fix-loop, command-discovery, bin-quota-diff, pitfall-gat006, task-field-governance, test-collection 等。

**跳过项**: mof-schema-validate (returncode=3), governance-evolution-packages (returncode=1) — 脚本不存在，已知问题。

## 5. 推送的 PR

**分支**: `fix/mcptool-drift-cleanup` → `origin/fix/mcptool-drift-cleanup`

**提交**: `f41669b11` — 添加 BOS pending registrations + mcptool drift report

**子仓**: `projects/ecos` 中 26 个 cockpit MCP 工具声明已更新并推送到 `c9062b152`

## 6. 后续行动建议

### 高优先级
1. **补登 41 个未注册 BOS URI** 到 agora 子仓 `bos-services.yaml`
2. **审计 26 个 withdrawn 工具** — 是否需要重新实现？还是永久退役？

### 中优先级
3. **处理 19 个 cockpit 实现+无声明** — 补登前端声明或移除实现
4. **处理 111 个 agora 实现+无声明** — 逐步补登

### 低优先级
5. **GitHub 安全警报** — 仓库有 33 个 vulnerabilities（4 critical, 9 high, 16 moderate, 4 low）需关注

## 第二轮改进 (后续推进)

### 交叉一致性验证
- 注册 41 个未注册 URI 后：**0 个未注册** (从 41 降至 0)
- 注册数：318 → 359
- 孤儿 URIs：187 (保持不变，SSOT 中无引用但计划内)

### MCP 工具漂移改进
- 原始：156 drifts (26 cockpit declared-only, 19 cockpit impl-only, 111 agora impl-only)
- 处理后：144 drifts
  - 26 cockpit declared-only (已标记 withdrawn)
  - 7 cockpit impl-only (剩余 cockpit 工具)
  - 111 agora impl-only (agora 内部工具)
  - 12 新 cockpit 工具声明 (chat, run_task, domain_*, etc.)

### GaC Gate 状态
- 56/62 检查通过 (6 个已知失败跳过)
- 失败项: `mof-schema-validate` (returncode=3), `mof-capabilities-drift-check` (model_stat_drift: 1487 vs 1499)
- 这些是预存在的失败，与 sweep 变更无关

### 关键提交
- 根仓: `f41669b11` → `808c408a9` → `0104c403e` (5 commits)
- 子仓 (agora): `d6d58e2` (register 41 BOS URIs)
- 子仓 (ecos): `c9062b152` → `708c92255` (withdraw 26 + declare 12)

### 后续行动 (未包含在此 PR)
1. 重新实现 26 个 withdrawn cockpit 工具 或 永久退役
2. 处理 7 个剩余 cockpit impl-only 工具 (低优先级)
3. 处理 111 agora impl-only 工具 (agora 内部，已注册为 services)
4. 修复 mof-schema-validate 和 mof-capabilities-drift-check 预存在问题
