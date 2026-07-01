# 剩余债务清理专项 (DEBT-CLEANUP-2026-07-01)

> **建立**: 2026-07-01 · **状态**: 📋 专项建立, 启动中
> **关联**: 路径 A ([AGENT-ISOLATION-ROLLOUT](AGENT-ISOLATION-ROLLOUT.md)) · auto-PR ([AUTO-PR-REVIEW-ISA](AUTO-PR-REVIEW-ISA.md)) · [GOVERNANCE-MATURITY-ISA](GOVERNANCE-MATURITY-ISA.md)
> **源头**: 2026-07-01 综合 ISA session (ISC-3f→2c→auto-PR ISA→bot治本→路径A→F2 generated治) 后的剩余债盘点

---

## 1. 债务清单 (按优先级)

| ID | 债务 | 优先级 | 阻塞于 | 治法 | 状态 |
|:---|:---|:---|:---|:---|:---|
| **C2** | baseline 写入机制缺 (omo registry 只 browse, 无写命令) | P0 | — | ✅ 方案 C 落地: omo apply_baseline_patches broker + omo baseline write CLI + gen --write subprocess 调 broker (跟 omo_readiness P63 同构). 全链验证: drift 消 + direct_omo_io 合规. omo commit a4650c6 | ✅ done |
| **A1** | dependency-baseline-drift (7 项版本下限落后 derived) | P0 | C2 | ✅ 7 项 patched (apscheduler/click/croniter/pytest×3/ruff → derived), gen --write → omo broker patch. drift 消 (52 deps 对齐) | ✅ done |
| **B1** | 协调并发 agent 切 PR (drift 循环根治) | P0 | 人/agent 协调 | 定规则: 子模块 push 必 bump 主仓, 或全切 PR | 🔴 协调层 |
| **E1** | 配 `ANTHROPIC_API_KEY` GitHub secret | P0 | 用户侧 | repo Settings → Secrets → Actions | 🔴 用户侧 |
| **A2** | gac-gate strict 化 (去 paths 过滤 + `--strict`) | P1 | A1 | A1 治后改 `gac-gate.yml` | 🔴 待 A1 |
| **C1** | auto-bump bot CI 验证 (只升不降, 7c9c5471) | P1 | CI 跑 | 等 CI 跑 commit 7c9c5471 验证逻辑 | 🟡 等 CI |
| **D1** | F3 lane 白名单 (复用 `change-lane-check.classify`) | P1 | F2 (A2) | lane → auto/manual 映射 + 治理红线 | 🔴 待 A2 |
| **D2** | F4 merge 状态机 (approve/blocking 终态) | P1 | F1✅ + F3 | review 状态机 + 四条件 AND 触发 | 🔴 待 D1 |
| **D3** | F5 `gac-worktree merge --auto` | P1 | F4 (D2) | 加 `--auto` flag, 复用 `gh pr merge --auto` | 🔴 待 D2 |
| **D4** | F6 安全边界 (独立 token / 不自审 / 不自合) | P2 | F1✅ + F4 | 贯穿 review + merge | 🔴 待 |
| **A3** | gac-gate required check 绑定 | P2 | Phase 3 (B2) | branch protection required checks | 🔴 待 B2 |
| **B2** | 路径 A 第 4 步: 恢复 blocking + Phase 3 | P0 | B1 + auto-PR 通 | 一次性 `install-hooks` + `gac-branch-protection.sh --set` | 🔴 待 B1 |
| **E2** | 测试 PR 验 F1 advisory review | P1 | E1 | 开低风险 PR 看 AI review comment | 🔴 待 E1 |

## 2. 依赖图 / 启动顺序

```
写入机制 (P0):     C2 gen --write ──→ A1 baseline 更新 ──→ A2 gac-gate strict ──→ D1/D2/D3/D4 auto-PR 闭环
                                                                                              ↓
                                                                                           A3 required
协调层 (P0):        B1 并发 agent 切 PR ──→ B2 恢复 blocking + Phase 3 (闭环)
                              ↑
用户侧 (P0):        E1 配 secret ──→ E2 测试 PR (验 F1)
```

**关键路径**: C2→A1→A2 (F2 闭环) + B1→B2 (路径 A 闭环) + E1→E2 (F1 验证). 三条并行.

## 3. 已落地 (本 session, 不在剩余债)

- ✅ ISC-3f: gov/doc-ssot 归 CI_ONLY (`af2444e3`)
- ✅ 2c blocking 源 (`893f2332`) + 路径 A 第 1 步回退 advisory (`63363f6c`)
- ✅ auto-PR ISA (`a939d287`) + F1 ai-pr-review.yml advisory (`26bb7263`)
- ✅ auto-bump bot 治本 只升不降 (`7c9c5471`)
- ✅ F2 generated 债治 CI skip (`8f3340b0`)
- ✅ untracked 债 (governance-evolution.py + roadmap.yaml) — 并发 agent 自解
- ✅ drift 循环 (4 子模块) — 并发 agent 自解
- 🧠 memory: `auto-bump-bot-downgrade-bug`

## 4. 启动决策 (2026-07-01)

- **C2 先行** (gen --write): A1/A2/F2 的写入机制前置, 机械可治 (加 --write flag), 解 baseline 死结 (omo 无写命令).
- **B1 并行** (协调并发 agent): drift 根治, 但属人/agent 协调层, 非单 session 代码.
- **E1 用户侧** (配 secret): F1 真跑前置, 用户操作.

---

## 变更历史

| 日期 | 变更 |
|:---|:---|
| 2026-07-01 | 建立: 13 项剩余债盘点 (P0×5 / P1×6 / P2×2) + 依赖图 + 启动 C2 |
| 2026-07-01 | **C2 探索发现**: gen --write 直写方向**错** (触发 ssot-guardian direct_omo_io 静态红线, 实测加 write_text→critical / 撤销→消, 已撤销 gen 改动). A1 真实阻塞 = baseline 更新**无合规路径** (omo registry 只 browse 无写 + gen 直写触发红线 = 设计 gap). 待治本路径决策 (omo 写命令 / 白名单 broker) |
| 2026-07-01 | **C2+i 落地** (grill-me 决策 → 实现): 方案 C (扩展 ingress_registry_writes broker) + 策略 a (patch) + 方式 i (subprocess CLI). omo apply_baseline_patches (write+audit+trail) + omo baseline write CLI + cli.py 分发 + gen --write subprocess 调 broker. 全链验证: gen --write rc=0 + drift 消 (52 deps) + direct_omo_io 合规 + contract_gatekeeper 扫 gen PASS. A1 治 (7 项 patched). omo commit a4650c6 |
