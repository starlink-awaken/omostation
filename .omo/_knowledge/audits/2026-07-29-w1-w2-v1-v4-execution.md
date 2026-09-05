---
status: needs-human
lifecycle: history
owner: governance-team
last-reviewed: "2026-07-29"
type: ephemeral
status: archived
---
# W1/W2/V1-V4 执行记录 (2026-07-29)

> 上位: 用户 W1-W2 + V1-V4 指令 (基于 human-delegated-decisions)
> 红线: 不摘门/不加 || true (W2) · 完整回滚含 runtime submodule (V1) · 综合 D1-D6 退回人类 (V4)

## V2 · required check ✅ (branch protection 已设)

`gh api branches/main/protection`:
- `required_status_checks.contexts: ["phase-gate", "gac-gate"]`
- **gac-gate 已是 required check** (strict + enforce_admins)
- gac-gate.yml job = `gac-gate` (line 18-19), 跑 gac-local-gate --strict

→ check-scenario-growth 在 gac-gate strict → **W19 PR 必被 GitHub blocked** (required check fail).

## W1 · required check 验证 (待 push W19 PR)

- gac-gate required 已设 (V2 确认)
- W19 PR (ADV 形态) push 后 → gac-gate strict 跑 check-scenario-growth → cap/evidence blocking → **PR blocked**
- 🔴 **待人类确认 push** (outward): gh pr create W19 → 观察 GitHub blocked 状态
- (本地 E2 已实测 strict exit 1, GitHub 侧 blocked 需真 PR 验证)

## W2 · main 红处理 (按 baseline, 不摘门)

### CI 红 root cause (找到)
**主仓 runtime submodule pointer 损坏**: `0d48a5591723...` (本地+远程都无, Not a valid object).
CI `actions/checkout` 拉 runtime 0d48a55 → `Direct fetching failed` → checkout exit 128 → gac-gate FAIL.

→ **非 check 门问题, 是 pointer 损坏** (主仓记录 runtime commit, 但该 commit 不存在).

### 本地 check fail (baseline 修)
- check-scenario-growth: 旧 strict 模式 baseline grace 也 blocking (bug) → **修**: baseline 永远 grace (W2 "存量不追溯")
- cap 门 (ADV>77): 系统加到 101 (超 cap 存量) → **修**: cap 门 baseline 化 (超 cap 存量 grace)
- detector 门 (49 > baseline 31): 系统加 18 detector → **重新 baseline** (49)
- ✅ **check-scenario-growth 修后 PASS** (blocking=0, warn=87 grace)
- agent-workflow-doctor: gstack missing (CI ci_skip 不跑, 本地 WARN, 非 CI 红原因)

### W2 修法 (不摘门)
1. ✅ check-scenario-growth baseline 修 (cap/detector/evidence 三层 grace, 存量不阻断)
2. 🔴 CI 红 runtime pointer 损坏 → **修 main pointer 回 f3db619 (runtime HEAD)** + commit + push
   - 本地已 stage (0d48a55 → f3db619, "commits not present" 确认损坏)
   - 🔴 **push main outward, 待人类确认**
3. gstack doctor: CI 不跑 (ci_skip), 本地 WARN (gstack 未装, 标注待装)

## V1 · #592 完整回滚 (实质完成 + 主仓历史 PR)

### 实质回滚 ✅ (runtime 多机已不在)
- #592 (a86cbe7ae) bump runtime pointer f3db619 → 253e3a9 (Agent Registry MVP)
- 当前 HEAD runtime = 0d48a55 (≠253e3a9, #592 后被覆盖)
- runtime 253e3a9 commit: f3db619..253e3a9 = **0 commits** (孤立/不同线)
- 当前 runtime (0d48a55/实际 f3db619) **不含 Agent Registry** (ls-tree 空)
- → **#592 多机代码已不在当前 runtime**, 实质回滚完成

### 主仓历史 revert (走 PR)
- a86cbe7ae revert 冲突 (runtime pointer 非线性: 253e3a9 不是 0d48a55 祖先)
- 完整 revert 需手动解决 pointer + 走 PR (outward)
- 🔴 待人类确认执行 (破坏性 + outward)

### omo state sync (V1 步骤 4)
- system.yaml/system_health.yaml 前面恢复 HEAD (清理 revert 残留)
- 待 commit 后 `omo state sync` 重建

## V3 · ADV 边界标注 ✅

- ADV 51 个 (max 101, 用户说 107 含 GEN-ADV)
- 全部 baseline grace (check-scenario-growth, 不补实现)
- 边界声明: r2-adv25-59-boundary-declaration.md (扩展到 101)

## V4 · 综合 D1-D6 退回人类

🔴 **退回**: p83 longplan line 145 提"19 项决策清单 (含综合 D1-D6)" 但**未列出综合 D1-D6 具体项**.
agent 无法核对未列出的项 (不自行判定"不适用"). **请人类查综合 D1-D6 出自哪份文档**.

## 🔴 红线遵守
- W2: 不摘门/不加 || true (baseline 修, 非绕过)
- V1: 完整回滚 (实质 clean + 主仓 PR)
- V4: 综合 D1-D6 退回 (不自行判定)
- push outward 操作待人类确认 (CI pointer 修 + W19 PR + a86cbe7ae revert)

## 待人类确认 (outward)
1. CI 红 pointer 修: commit main (runtime 0d48a55→f3db619) + push (本地已 stage)
2. W19 PR: push 验证 GitHub blocked
3. a86cbe7ae revert: 主仓历史 revert (走 PR, pointer 手动解决)
4. 综合 D1-D6: 查出自哪份文档 (V4 退回)
