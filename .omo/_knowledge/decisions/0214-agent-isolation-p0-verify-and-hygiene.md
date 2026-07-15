---
status: PROPOSED
lifecycle: decision
owner: 夏明星
last-reviewed: 2026-07-15
related:
  - 0210-three-year-strategy-execution-convergence.md
  - 0202-fake-green-prevention.md
  - ../patterns/p73-truth-driven-engineering-pattern.md
  - ../../../docs/AGENT-ISOLATION-ROLLOUT.md
  - ../../../docs/ARCHITECTURE-ANALYSIS-2026-07-14.md
supersedes: []
---

# ADR-0214: Agent Isolation P0 落地 — 核实生效态 + worktree 卫生固化

> **背景**: 本 ADR 是 ADR-0210 收敛期 P0「启用 Agent Isolation」的落地承载。编号 0214
> 取自 INDEX 最大号（0213）+ 1；0211–0213 已被并发 agent 占用（撞号规则见 ADR-0202 D4）。

## Context and Problem Statement

ADR-0210 把「启用 Agent Isolation」列为收敛期头号 P0，隐含假设是"机制就绪但未启用"。
**2026-07-15 运行时核实推翻了这个假设**——机制其实**大部分已启用**，真正的问题是
「已启用但状态自相矛盾 + 卫生缺失」，这是比"未启用"更隐蔽的声明-执行鸿沟（P73 真相驱动）。

实测证据（2026-07-15，`git worktree list` + hook 检视）：

| 机制 | 声明文档 | 运行时实测 | 判定 |
|------|---------|-----------|------|
| pre-push 守卫 | ROLLOUT ISC-3b 曾写"advisory 未 install" | `.git/hooks/pre-push` **blocking active**（实测 07-04：push main → exit 1，work/* 放行）| ✅ 已生效 |
| per-session worktree | ROLLOUT 称"0 个 per-session" | 实存 3 个（本会话 `work/improvements-round3` + 2 个 `prunable` 孤儿）| ⚠️ 已用但脏 |
| branch protection | ROLLOUT 头部"✅ Phase 3 已落地 07-08" | ARCHITECTURE-ANALYSIS 07-14 仍记录"agent 抢 main" | ❓ 声明冲突未核实 |

**矛盾焦点**：三份文档对同一机制给出三种状态（未启用 / 已启用 / 冲突）。在这种"文档打架"
下，任何"启用"动作都可能是对已生效机制的重复施工或回退。**P0 的正确形态是核实 + 收敛，
不是从零启用。**

## Decision Drivers

- **D1 · 真相优先（P73）**：不信任何单一文档，以 `git worktree list` / hook 实测 / gh API 为准。
- **D2 · 已生效不回退**：pre-push blocking 已 active，误判为"未启用"再去"启用"有回退风险。
- **D3 · 卫生即执行面**：2 个 prunable 孤儿 worktree = 隔离机制在用但生命周期未闭环，
  正是 ADR-0210 M1「零主仓冲突」达标的隐患。
- **D4 · 文档收敛**：三份文档状态打架本身违反 doc-ssot-contract，须归一到单一权威源。

## Considered Options

- **选项 A · 按原假设从零启用**：跑 `gac-branch-protection.sh --set` + install-hooks。
  - 缺点：对已生效机制重复施工；pre-push 已 blocking，可能触发回退叙事（ISC-3b 教训）。
- **选项 B · 核实 + 收敛 + 固化（本 ADR 选定）**：先实测三态归一，再补 worktree 卫生闭环，
  最后把状态写回单一权威源。
  - 优点：符合 P73；不回退已生效机制；直接推进 M1 达标。
- **选项 C · 不动，等周体检**：靠已配的 weekly-strategy-health-check 观察。
  - 缺点：孤儿 worktree 与文档矛盾不会自愈；被动。

## Decision Outcome

**选定选项 B**，分三步（均低破坏、可逆、不改已生效的 blocking 行为）：

### D1 · 核实三态（只读，出证据）
- `git worktree list` → 确认 per-session worktree 实况（已知 3 个，2 prunable）。
- `gh api repos/starlink-awaken/omostation/branches/main/protection` → 确认 ISC-4（200 vs 404）。
  沙箱无 gh/网络时，标记为"待人工在授权环境核实"。
- 检视 `.git/hooks/pre-push` 与源 `.githooks/pre-push` 是否一致（防 install 漂移）。

### D2 · worktree 卫生闭环
- 清理 2 个 `prunable` 孤儿（`git worktree prune` + 确认对应 PR 已合/已弃）。
- 确认 `gac-worktree.sh release` 在正常流程末尾被调用（孤儿说明 release 环节遗漏）。
- 评估把 `git worktree prune` + 孤儿检测纳入 foundry cron（与 gitlink 巡检同一 deck）。

### D3 · 文档状态归一
- 以运行时实测为准，更新 `AGENT-ISOLATION-ROLLOUT.md` 头部状态（消除"未启用/已启用"矛盾）。
- ARCHITECTURE-ANALYSIS 的"agent 抢 main"若已被 pre-push blocking 解决，标注时间戳订正。
- 单一权威源：隔离机制生效态回指 `.omo/state/system.yaml`（若有对应字段则新增）。

**后果**：
- 正面：P0 从"以为要启用"收敛为"核实已生效 + 补卫生"，工作量更小、更贴真相；直接服务 M1。
- 代价：需在授权环境跑 gh API（沙箱受限）；文档订正涉及三份文件的 doc-ssot 校验。
- 不做：不重设已生效的 branch protection；不改 pre-push blocking 逻辑（避免 ISC-3b 回退重演）。

## Confirmation

- **M1 对齐（ADR-0210）**：
  - 并发 agent 主仓冲突 = 0 —— 由 pre-push blocking（已生效）保证，本 ADR 补实测证据。
  - `gac-worktree.sh` claim/release 覆盖率 → 孤儿清零即为覆盖闭环证据。
- **文档收敛**：三份文档状态归一后，`doc-ssot-lint.py` 无冲突。
- **周体检衔接**：weekly-strategy-health-check 增加"孤儿 worktree 数"观测项。
- **工具校验**：`adr-coverage.py` frontmatter 通过；`adr-drift-check.py` 引用路径通过。

---

*ADR-0214 · PROPOSED · 2026-07-15 · 夏明星 · ADR-0210 收敛期 P0 落地承载*
