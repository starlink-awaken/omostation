---
schema_version: report/v1
lifecycle: history
type: deep-retrospective
owner: governance-team
created: 2026-08-31
last_updated: 2026-08-31
adr: ADR-0443
scope: multi-agent collaboration failure modes (session 2026-08-30/31, ADR-443 v1-v7)
---

# 多 agent 协作事故深度复盘（deep retro，非点修）

> 数据集：ADR-443 v1-v6 六轮迭代的完整事故日志。环境：单机多 agent（Claude ×N
> 并行），共享一个 git 仓 + 多 worktree + 主树默认落点。

## 一、事故全清单（14 起，按根因四类）

### A 类：共享可变状态（6 起，占比最高）
| # | 事故 | 损耗 | 现有防护 | 结果 |
|---|------|------|----------|------|
| A1-A3 | `git add -A` 误 stage 子仓 side-branch 指针（cockpit/omlxc/omo）| ~15min | 三层 gate 全拦 | 零污染，已规则化（CR-GIT-STAGE-SUBMODULE-PIN，v3）|
| A4 | worktree 被并行 agent merge 污染（ws-t1069）| ~30min | 无 | 接受 merge 因祸得福（带入 registry 同步）|
| A5 | 主树分支频繁易主（4 次：real-scenario → convergence-wave2 → mof-kems-final → main）| 每次需探测 | 无 | 被迫换 worktree 推送 |
| A6 | 共享 index 死锁：pre-push 检查 staged 含并行 agent 变更 | ~20min | 无 | worktree 绕行 |

### B 类：流程竞态（3 起）
| # | 事故 | 损耗 | 现有防护 | 结果 |
|---|------|------|----------|------|
| B1 | PR 合并后同名分支重建丢交付（#2736 二段提交）| 发现+恢复 ~30min | 无 | v2 恢复+测试钉死 |
| B2 | PR 被关闭+分支连坐删除（#2795）| ~40min | 无 | 内容已进 main（路径未完全追溯）|
| B3 | PR 关闭竞态（#2751，后 reopen 正常合并）| ~15min | 无 | 正常落地 |

### C 类：异步可见性（4 起）
| # | 事故 | 损耗 | 防护 | 结果 |
|---|------|------|------|------|
| C1 | 并行 agent 未登记脚本卡全局 validate ×2 | ~20min | 无（validate 是全局口径）| 顺手代登记（元数据占位）|
| C2 | 新脚本未同步 capability-registry → CI drift | ~30min | drift check（CI 层，push 后才发现）| sync 补上 |
| C3 | main 高速前进 → CONFLICTING | ~20min | 无 | rebase 解决 |
| C4 | bench quota 基线与活跃数漂移 ×3 | 每次 ~10min | gac-validate（有报错但需人手 bump）| SCRIPT-BASELINE-SYNC 契约执行 |

### D 类：自身流程（1 起）
| # | 事故 | 处置 |
|---|------|------|
| D1 | ruff format 残留 ×2（删行后/重构后）| 本地 diff-scoped 预跑（已固化习惯）|

## 二、成本核算

六轮总摩擦 ≈ **4.5 小时**（A 类 65min / B 类 85min / C 类 80min / 处理切换开销 40min），
占六轮总时长约 25%。**A 类（共享可变状态）是最大单一损耗源**。

## 三、长解（分层，非点修）

| 层 | 方案 | 状态 |
|----|------|------|
| **L1 物理隔离** | 每 agent 专属 worktree 强制化；主树不再做工作落点（只做只读基线+运行时区）| 🔶 事实已如此但无强制——建议 ADR 化"主树只读纪律" |
| **L2 锁协议** | 主树/worktree 纳入 gac-worktree claim 管理（工具已有，覆盖面缺主树）| 🔶 扩展 claim 范围 |
| **L3 gate 适配多 agent** | ① pre-push 检查 own-commit-range（origin/main..HEAD）而非共享 staged ② validate 增 per-diff 模式 ③ 关闭 PR 不删分支（branch protection 设置）| ❌ 未做——v8 候选 |
| **L4 流程契约** | main 直推需带 PR 追溯标记；quota 基线 bump 自动化（新脚本登记时自动）| ❌ 未做——quota 自动化最易先落 |

## 四、两个已固化成果（本轮治理的存量）

1. CR-GIT-STAGE-SUBMODULE-PIN 规则（A 类主犯已规则化，v3）
2. 本报告 + p96 pattern（模式库沉淀）

## 五、v8+ 入口

1. quota 基线自动 bump（登记时联动——C4 根除）
2. pre-push own-range 模式（A6 根除，需 gate 变更评审）
3. branch protection：PR 关闭不删分支（B2 根除，GitHub 设置层）
4. 主树只读 ADR（A4/A5 根除的制度化）
