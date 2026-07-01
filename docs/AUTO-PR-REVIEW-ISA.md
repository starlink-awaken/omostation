---
task: "AI PR review + 分级 auto-merge 闭环"
slug: 20260701-auto-pr-review-merge
effort: E3
effort_source: explicit
phase: observe
progress: 0/33
mode: interactive
started: 2026-07-01T02:00:00Z
updated: 2026-07-01T02:00:00Z
---

# Auto PR Review + 分级 Auto-merge ISA

> **Tier**: E3 · **创建**: 2026-07-01 · **关联**: [AGENT-ISOLATION-ROLLOUT](AGENT-ISOLATION-ROLLOUT.md) Phase 2c/3 · [GOVERNANCE-MATURITY-ISA](GOVERNANCE-MATURITY-ISA.md)
> **状态**: 📋 OBSERVE/PLAN (方案待 review, 未 EXECUTE)

---

## 1. Problem

direct push main 即将被 **2c blocking 守卫 + Phase 3 branch protection** 消灭, 全走 PR (worktree claim→submit→merge). 但 PR review + merge **全人工 = 瓶颈**:

1. 并发 agent 走 PR 会卡 (等人工 merge), direct push 的"效率"没了, PR 反而拖慢
2. 低风险变更 (docs/submodule bump/普通 code) 占多数, 却要人工逐个 merge = 浪费
3. 无 AI 语义 review — GaC gate 只验规则 (语法/SSOT/drift), 验不了"这段改动合不合理/有没有坑"

**根因**: PR 流程没有 auto 闭环 — 低风险变更该无人值守, 高风险变更才该人工. 现在一刀切人工.

## 2. Vision

push `work/*` 分支 → 开 PR → **秒级 AI review comment** + **GaC gate strict 并行跑** → 低风险 lane (`docs`/`submodule_pointer`/`code`/`governance_code`/`config`) 满足条件 **auto squash merge** + worktree auto release; `governance_state`/`runtime_snapshot`/架构变更 AI 标红, 人工 30 秒拍板.

**euphoric surprise**: 从 push 到 main 落地, 低风险变更**全程零人工 < 5 分钟**; 治理变更 AI 精准标红, 人工只兜底该兜的. PR 不再是瓶颈, 反而是质量加速器.

## 3. Out of Scope

- **不替换 GaC gate** — AI review 是语义补充, 规则兜底永远靠 gate (gac-validate/drift/ssot/mof-*)
- **不 auto merge `governance_state` / `runtime_snapshot` lane** — 治理状态 + 运行时快照人工兜底 (不可逆/敏感)
- **不引入第三方 SaaS** (coderabbit/codeac) — 用 `claude-code-action` (Anthropic 官方), 治理上下文靠 GaC gate
- **不强制人工 required review** — `required_approving_review_count: 0`, 靠 AI + gate + lane 分级 (单人仓库)
- **不做 multi-repo/workspace** — 单 workspace (17 子模块的子模块内部 PR 不在此 scope, 见 SUBMODULE-PR-STRATEGY 方案 A')
- **不 auto merge 架构变更** — `ARCHITECTURE.md`/`LAYER-INDEX.md` (5+4+1) 即使落在 docs lane 也强制人工

## 4. Constraints

- 5+4+1 架构不变 (L0-L4 + I0 + X1-X4)
- **GaC gate 是 required CI** (`gac-gate.yml` 已有, PR 必跑 strict)
- **`change-lane-check.classify` 是 lane 分类 SSOT** — 复用, 不重写分类逻辑 (DRY)
- gh CLI 2.95.0+ (gac-worktree.sh submit/merge 依赖)
- `claude-code-action` (Anthropic 官方 GitHub Action)
- `ANTHROPIC_API_KEY` (GitHub Actions secret, 不入库)
- 并发 agent 场景 (多 agent 同时开 PR, review bot 须独立)
- post-commit L0 萃取 commit 级触发 (PR squash merge 是服务端 commit; 派生文件须已在 worktree commit 时进 PR)

## 5. Goal

PR 开启 → **GaC gate (strict) + AI 语义 review 并行** → 满足「gate 绿 ∧ AI 非 blocking ∧ lane ∈ auto 白名单 ∧ reachability PASS」的低风险变更 **auto squash merge**; `governance_state`/`runtime_snapshot`/架构变更**回退人工**. PR 闭环低风险无人值守, 人工只兜底高风险.

## 6. Criteria (ISC)

### F1 — AI review workflow (claude-code-action)

- [ ] ISC-1: `.github/workflows/ai-pr-review.yml` 存在且 `actionlint` PASS
- [ ] ISC-2: triggers = `pull_request: [opened, synchronize, reopened]` (新 PR + 新 commit + 重开)
- [ ] ISC-3: review step 用 `anthropics/claude-code-action` (非自建 agent runner)
- [ ] ISC-4: review 输出为 PR review comment (GitHub API 可见, 非 log 埋没)
- [ ] ISC-5: review 区分 **blocking** (`REQUEST_CHANGES`) vs **advisory** (`COMMENT`)
- [ ] ISC-6: `ANTHROPIC_API_KEY` 从 `secrets.` 读 (probe: workflow 无明文 key)
- [ ] ISC-7: **Anti**: bot 自身触发的 PR (author == `github-actions[bot]`) `[skip]` review (防自审)
- [ ] ISC-8: review step `timeout-minutes: 10`, 超时不卡 PR (graceful 降级 advisory)

### F2 — GaC gate required CI

- [ ] ISC-9: `gac-gate` 在 branch protection / required checks 列表 (PR 必须过)
- [ ] ISC-10: PR CI 跑 `make gac-local-gate --strict` (全套, 非 scoped)
- [ ] ISC-11: GaC gate 红 → `gh pr view --json mergeStateStatus` ≠ `CLEAN` (阻断 merge)

### F3 — auto-merge lane 白名单 (复用 classify)

- [ ] ISC-12: GitHub repo `auto-merge` 已 enable (squash 模式)
- [ ] ISC-13: `docs` lane → auto-merge 候选
- [ ] ISC-14: `submodule_pointer` lane (reachability PASS) → auto 候选
- [ ] ISC-15: `code` lane (普通 `.py`/`.ts`/`.sh`/`.json`/`.yaml`) → auto 候选
- [ ] ISC-16: `governance_code` lane (`bin/gac*`/`.githooks/`/gate 脚本) → auto 候选 (GaC gate 自验)
- [ ] ISC-17: `config` lane (`Makefile`/`.github/workflows/`) → auto 候选
- [ ] ISC-18: `governance_state` lane (`.omo/`) → ❌ **不 auto** (人工兜底)
- [ ] ISC-19: `runtime_snapshot` lane (`runtime/`/`system_health.yaml`) → ❌ **不 auto** (人工)
- [ ] ISC-20: `ARCHITECTURE.md` / `LAYER-INDEX.md` 变更 (5+4+1 架构) → ❌ **强制人工** (即使落 docs lane)
- [ ] ISC-21: 白名单判定脚本复用 `change-lane-check.classify` (probe: 不存在重复分类逻辑)
- [ ] ISC-22: **Anti**: `governance_state` lane 的 PR 永不 auto-merge (硬红线, 即使 gate 绿 + AI approve)

### F4 — merge 状态机

- [ ] ISC-23: AI review `APPROVE` → 终态, 后续 push 不重开 blocking (除非新 commit)
- [ ] ISC-24: AI `REQUEST_CHANGES` → auto-merge 阻断 (state ≠ CLEAN)
- [ ] ISC-25: 新 commit push (`synchronize`) → 重触发 review (防 stale approve 漏新问题)
- [ ] ISC-26: auto-merge 触发 = `GaC 绿` ∧ `AI 非 blocking` ∧ `lane ∈ 白名单` ∧ `reachability PASS` (四条件 AND)
- [ ] ISC-27: 任一条件红 → 回退人工 (auto 不触发, PR 等人工)

### F5 — gac-worktree merge --auto

- [ ] ISC-28: `gac-worktree.sh merge` 新增 `--auto` flag
- [ ] ISC-29: `--auto` = `gh pr merge --squash --auto --delete-branch` (等条件满足自动合)
- [ ] ISC-30: 无 `--auto` 保持现状 (手动 `gh pr merge --squash`, 立即合)
- [ ] ISC-31: merge 操作落日志 (PR # / commit sha / lane / `auto|manual` / 时间)

### F6 — 安全 / 边界

- [ ] ISC-32: review + merge 用独立 `GITHUB_TOKEN` (非 agent 个人 token, 权限最小化)
- [ ] ISC-33: **Anti**: bot 不能 auto-merge **自己开的 PR** (`author == bot → 强制人工`, 防自合)

> **Anti 汇总**: ISC-7 (不自审) / ISC-22 (治理不 auto) / ISC-33 (不自合) — 三道红线防 AI review 系统自循环.

## 7. Test Strategy

```yaml
- isc: ISC-1
  type: static
  check: workflow 文件存在 + actionlint PASS
  threshold: 0 error
  tool: actionlint .github/workflows/ai-pr-review.yml

- isc: ISC-5
  type: contract
  check: review 输出含 event REQUEST_CHANGES 或 COMMENT
  threshold: 二值可分
  tool: gh api repos/:owner/:repo/pulls/:pr/reviews --jq '.[].state'

- isc: ISC-13..ISC-20
  type: unit
  check: lane → auto|manual 映射正确
  threshold: 8 lane 全覆盖
  tool: python3 -m pytest tests/test_auto_merge_lanes.py

- isc: ISC-22
  type: anti-probe
  check: governance_state PR 即使全绿也不 auto
  threshold: 0 次 auto-merge
  tool: 模拟 .omo/ PR → 断言 mergeStateStatus 不自动 CLEAN

- isc: ISC-26
  type: integration
  check: 四条件 AND 触发 auto-merge
  threshold: 缺任一不触发
  tool: tests/integration/auto-merge-conditions.sh (mock CI/review/lane/reachability)

- isc: ISC-33
  type: anti-probe
  check: bot-authored PR 不 auto
  threshold: 0 次
  tool: gh pr list --author github-actions[bot] --json mergeableState
```

## 8. Features

```yaml
- name: F1 AI review workflow
  description: claude-code-action 跑 AI 语义 review, 输出 PR comment + blocking/advisory 标记
  satisfies: [ISC-1..8]
  depends_on: []
  parallelizable: true   # 与 F2/gate 并行跑

- name: F2 GaC gate required
  description: 确认 gac-gate 是 PR required check (gate 已有, 补 required 绑定)
  satisfies: [ISC-9..11]
  depends_on: []
  parallelizable: true

- name: F3 auto-merge lane 白名单
  description: 复用 change-lane-check.classify, lane → auto|manual 映射 + 架构/治理红线
  satisfies: [ISC-12..22]
  depends_on: [F2]        # gate 绿才有 auto 意义
  parallelizable: false

- name: F4 merge 状态机
  description: review approve/request-changes 状态机 + 四条件 AND 触发
  satisfies: [ISC-23..27]
  depends_on: [F1, F3]    # 需 review + lane 判定
  parallelizable: false

- name: F5 gac-worktree merge --auto
  description: merge 子命令加 --auto, 复用 gh pr merge --auto
  satisfies: [ISC-28..31]
  depends_on: [F4]
  parallelizable: false

- name: F6 安全边界
  description: 独立 token + 不自审 + 不自合 + 不 auto 治理
  satisfies: [ISC-32, ISC-33, ISC-7, ISC-22]
  depends_on: [F1, F4]    # 贯穿 review + merge
  parallelizable: false
```

### 依赖图

```
基础 (并行):   F2 GaC gate required
                  |
              F3 lane 白名单 ─────┐
                  |               |
执行:         F1 AI review ──────┤
                  |               |
              F4 merge 状态机 ◄───┘
                  |
              F5 gac-worktree --auto
                  |
安全贯穿:     F6 (独立 token + 不自审/自合/治理)
```

---

## 推进计划

| 顺序 | feature | 预估 | 前置 | 风险 |
|:---|:---|:---|:---|:---|
| **第 1 步** | F2 GaC gate required (确认) | 小 | 无 | 低 |
| 并行 | F1 AI review workflow | 中 | 无 | 中 (API key/成本) |
| 第 2 步 | F3 lane 白名单 | 中 | F2 | 低 (复用 classify) |
| 第 3 步 | F4 merge 状态机 | 中 | F1+F3 | 中 (状态边界) |
| 第 4 步 | F5 gac-worktree --auto | 小 | F4 | 低 |
| 贯穿 | F6 安全边界 | 小 | F1+F4 | 低 |

**当前**: OBSERVE/PLAN 完成, 待用户 review → EXECUTE (先 F2 确认 gate required + F1 advisory 试跑两周).

---

## 关联决策 (Decisions 预填)

- **2026-07-01**: review bot 选 `claude-code-action` 而非自建 agent runner — 省维护, 治理上下文 GaC gate 兜底 (AI 不懂的规则 gate 懂). 自建留作 F1-v2 若 claude-code-action 不够.
- **2026-07-01**: auto-merge 按 lane 分级而非"全 auto/全人工" — `governance_state`/`runtime_snapshot` 人工, 其余 auto. 复用 `change-lane-check.classify` (DRY, 不重写分类).
- **2026-07-01**: 0 required human review — 单人仓库, 靠 AI + gate + lane 三层. 避免"等人工"瓶颈 (这正是要消灭的).
- **2026-07-01**: F1 先 advisory 跑两周再转 blocking — 验证 AI review 质量 (false-positive 率) 前不阻断 merge.

---

## 与硬隔离 (Phase 2c/3) 的关联

**本 ISA 是 install 2c + Phase 3 的安全前置**:

- 有 auto PR (本 ISA) → 并发 agent 走 PR 不卡 (auto review + auto merge) → 硬隔离上了不瘫
- 无 auto PR → 硬隔离上了, 并发 agent 全卡死 (等人工 merge)

**正确顺序**: 先落地本 ISA (auto PR review + merge) → 再 `make install-hooks` (2c blocking) → 再 Phase 3 branch protection. 此时 PR 通道已 auto, 硬隔离有逃生通道.
