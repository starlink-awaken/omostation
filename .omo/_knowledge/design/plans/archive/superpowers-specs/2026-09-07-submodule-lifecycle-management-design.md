---
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-07
last-reviewed: 2026-09-07
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q4-T10-129
type: ssot
last_updated: 2026-09-07
---

# Submodule Lifecycle Management — 指针漂移检测、分支清理、Tags 管理

> 日期：2026-09-07
> 状态：accepted
> BET：BET-Y1Q4-T10-129

## 背景与问题

仓库有 16+ 个子模块（通过 `.subtrees/` worktree 隔离管理）。当前痛点：

1. **指针漂移无检测**：主仓 `git submodule update` 后无 CI 级别一致性门禁（`check-submodule-consistency.py` 不存在）
2. **远程僵尸分支堆积**：历史 agent worktree 产生的远程分支未定期清理（`branch-ttl-gate.py` 已存在但缺子模块场景适配）
3. **子模块健康无报告**：无周期性健康报告输出

已存在的相关资产：
- `bin/gac/branch-ttl-gate.py`（主仓分支 TTL，需扩展到子模块）
- `bin/gac/generate-submodule-health-report.py`（来自未合入的分支 `agent/governance-agent/bet129-submodule`，需验证并适配）

## 架构选择

### 交付物 1: `bin/gac/check-submodule-consistency.py`

用途：CI 级子模块指针一致性门禁。

功能：
- 读取 `.gitmodules` 获取所有子模块路径
- 对每个子模块执行 `git diff HEAD -- <submodule-path>` 检查指针是否漂移
- 输出 JSON 格式报告（通过/失败 + 漂移明细）
- 支持 `--fail-on-drift` 标志返回非零退出码
- 支持 `--json` 输出供 CI 消费

不做什么：
- 不自动修复漂移（由人类或 ADR 决定）
- 不修改子模块源码

### 交付物 2: `bin/gac/branch-ttl-gate.py` 扩展

当前 `branch-ttl-gate.py` 只扫描主仓远程分支。扩展方向：
- 添加 `--submodules` 标志，递归扫描每个子模块的远程分支
- 检测已合入对应子模块 main 的过期分支
- 输出待清理列表（dry-run 默认，`--execute` 才删除）

### 交付物 3: `docs/submodule-health.md`

子模块健康报告，包含：
- 每个子模块的当前指针 commit + 最新远程 HEAD 的差距
- 远程分支数量（含过期标记）
- Tags 数量
- 最近 5 条 commit 摘要

由 `bin/gac/generate-submodule-health-report.py` 生成（适配现有实现或重写）。

## 验收标准

1. **[check-submodule-consistency.py 通过]**
   - 验证方式：`python3 bin/gac/check-submodule-consistency.py --fail-on-drift`
   - 证据类型：exit 0（主仓指针一致时）

2. **[branch-ttl-gate.py 子模块支持]**
   - 验证方式：`python3 bin/gac/branch-ttl-gate.py --submodules --dry-run`
   - 证据类型：exit 0，输出包含子模块分支扫描结果

3. **[submodule-health.md 存在且非空]**
   - 验证方式：`test -s docs/submodule-health.md`
   - 证据类型：exit 0

4. **[gac-local-gate 通过]**
   - 验证方式：`make gac-local-gate`
   - 证据类型：exit 0
