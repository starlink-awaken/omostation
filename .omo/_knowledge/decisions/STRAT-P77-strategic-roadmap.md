---
status: draft
lifecycle: strategy-decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - ../../../.omo/_knowledge/decisions/0163-p76-phase9a-commit-assist-hook.md (Phase 9A 上游)
  - ../../../.omo/_knowledge/decisions/0162-p76-phase8-real-engineering.md (P76 Phase 8 上游)
  - STRAT-P76-strategic-roadmap.md (上一路线图, 已 100% closed)
supersedes:
  - STRAT-P76 (P77 接替 P76 路线图目标)
---

# STRATEGY-DECISION: P77 战略路线图 — 12 周 5 phase 跨仓一致性 + 演化护栏

> **For agentic workers**: 本文档是 DRAFT 状态 (2026-07-07), 等用户授权 — 我先把方案完整写出, 等明确启动信号执行.

## 0. TL;DR

| 字段 | 值 |
|------|---|
| **决策 ID** | STRAT-P77 |
| **基线 (起点)** | P76 100% closed + governance 85.7 (X-Plane 临时 ruff errors 引起 — 需 reset) |
| **核心目标 (W1-12)** | 跨仓一致性自动 verifier (A) + 演化护栏形式化 (C) 组合 |
| **W1 提案** | Phase 1 跨仓一致性 detector; Phase 2 演化护栏 catalog; Phase 3-5 治本 |
| **NOT IN P77** | gbrain god module 真拆 (太专项); Foundry web dashboard (体验优化) |

## 1. P76 闭包 + 当前态势 (R step)

### 1.1 P76 完成盘点 (12 周 + 8 阶段 + 8 ADR + 8 task closed)

| Phase | Week | 关键产物 | ADR |
|-------|------|---------|-----|
| 1 | W1-2 | 入口解锁 + M1 0/0/0 + god-module SOP | ADR-0155 |
| 2 | W3-5 | CR-LAYER-CALL-DIRECTION + 9 violations 真证据 | ADR-0156 |
| 3 | W6-8 | CR-META-METRIC-DEBT-FEATURE + ratio 0.688 | ADR-0157 |
| 4 | W9-11 | X 扩展晋升 + CR-SUBMODULE-BUMP-AUTO 17/17 | ADR-0158 |
| 5 | W12 | 收敛面 + 知识殿堂雏形 | ADR-0159 |
| 6 | W13 | Knowledge Foundry radar_cron 9-deck | ADR-0160 |
| 7 | W14 | LLM-assisted commit + foundry cron + 5 task closes + mesh 决议 | ADR-0161 |
| 8 | W15 | aetherforge L0 + QuotaEngine + c2g path + dead paths + 3 task closes | ADR-0162 |
| 9A | W16+ | commit-assist pre-commit 集成 | ADR-0163 |

**40 原则沉淀 (P76-1..5/2-1..5/3-1..5/4-1..5/5-1..5/6-1..5/7-1..5/8-1..4) + 9A-1..5**

### 1.2 系统债扫描 (S step - 现状负面)

| 债 | 来源 | 优先级 | ROI |
|----|------|--------|-----|
| 跨仓一致性 (aetherforge/omo/c2g 各自 M1 不一致) | P76 Phase 8 痛点 (跨仓 PR 易生 stitch-up) | 🔴 高 | A: 跨仓自动 verifier |
| GaC 规则回退 (X-Plane 临时 157 → P76 161) | worktree reset 反复 | 🟡 中 | C: 演化护栏 |
| ruff errors 98 处 (X-Plane 引入) | X-Plane ruff scope 改了 | 🟡 中 | C (附属) |
| governance 85.7 (down from 100) | 上面三个债共同 | 🟡 中 | C 治本 |
| gbrain 5 god module >1300L | P76 Phase 1 SOP 起步 | ⚫ 低 | 推到 P78 |
| web dashboard | 体验 | ⚫ 低 | 推到 P78 |
| 多仓 conflict 自动化 | 跨 agent 协作 | ⚫ 低 | 推到 P78 |

## 2. WHAT — P77 5 phase 路线图

### Phase 1 (W1-2) 跨仓一致性 detector

**目标**: 自动检测 aetherforge / omo / c2g / cockpit 仓内的 M1 yaml 与 BOS URI registry 是否一致

**产物**:
- `bin/ssot/check-cross-repo-consistency.py` (新)
  - 读 projects/*/src/*/ssot/registry/*.yaml (各仓 SSOT)
  - 读 projects/agora/etc/bos-services.yaml
  - diff: URI 引用 / M1 实例 vs 各仓声明
  - 输出 mismatch table, threshold=3 不一致就 fail
- ADR-0164 收口
- 跑 1 周累积 violations baseline

**风险**: 各仓 M1 schema 可能未对齐, 需先做 schema 调研

### Phase 2 (W3-4) 演化护栏 catalog

**目标**: 把 P76 沉淀的 40 原则形式化, 加 GaC rules

**产物**:
- `.omo/standards/p77-principles.md` (从 ADR-0155..0163 提取 40 原则, 分类)
- 5 个新 GaC 规则:
  - `CR-PRINCIPLE-ENFORCEMENT` (governance audit 每月跑的 dry-run)
  - `CR-CROSS-REPO-REGISTRY-CONSISTENT` (与 Phase 1 detector 配对)
  - `CR-PR-DESCRIPTION-NON-EMPTY` (防止空 PR body)
  - `CR-WORKTREE-CLEAN-BEFORE-PR` (防 worktree reset 残留)
  - `CR-RUFF-SCOPE-STABLE` (防止 X-Plane 改变 ruff scope)
- ADR-0165 收口

**风险**: 原则"形式化"可能把活的 wisdom 变成死的 checklist. 治本: 原则给"上下文", 不是 checkbox.

### Phase 3 (W5-6) 跨仓一致性 Phase 2: 行动化

**目标**: Phase 1 detector 的 violations 治本

**产物**:
- 修复实际不一致 (mismatch table 触发)
- 增 CR-CROSS-REPO-... 为 hard 守门
- ADR-0166

**风险**: 一致性修复可能要改多个仓的 SSOT, 跨仓 PR 风险高

### Phase 4 (W7-9) GaC rules +9A LLM hook 真升级

**目标**: 把 Phase 9A 的 advisory hook 升为有默认值

**产物**:
- bin/commit-assist.py 加 `--tier=auto` (默认 aetherforge 网关), 失败 fallback ollama, 再 fallback heuristic
- .githooks/prepare-commit-msg-commit-assist 改用 --tier=auto
- ADR-0167

**风险**: 网慢/网关挂 → fail-silent 机制已就绪 (P76-7-3), 风险低

### Phase 5 (W10-12) P77 收口 + P78 proposal

**目标**: 闭合当前 5 phase + 沉淀原则

**产物**:
- STRAT-P77 → ACCEPTED historical-strategy
- 治理 score 回升 100
- 新一轮债务 list → P78 候选
- ADR-0168

## 3. NEXT — P78 入口 (候选按 ROI)

| 候选 | ROI |
|------|-----|
| gbrain 5 god module >1300L 真拆 | 中 (Phase 1 SOP 续) |
| cockpit-ui vs cockpit 接口契约形式化 | 中 (反向警示 #2 已延 2 季度) |
| Knowledge Foundry metrics-archive (3 月累积 ledger → 趋势分析) | 中 |
| LLM-assisted commit pre-push hook (Phase 9A 续) | 低 |

## 4. 沉淀原则 (P77 草拟 — 实施时 L 修正)

| # | 原则 | 含义 |
|---|------|------|
| P77-1 | **consistency-by-tool** | 跨仓一致性靠自动 verifier 守护, 不靠 review memory |
| P77-2 | **principle-formalization-with-context** | 原则形式化要保留"上下文", 不变成死的 checkbox |
| P77-3 | **worktree-rotation-safe** | 任何运行时操作要 worktree clean-aware (不被 X-Plane 反复 clean) |
| P77-4 | **baseline-replay** | 每个 phase 收口重放 baseline, 防回退 (例如 100 → 85.7) |
| P77-5 | **xer-multi-agent-coordination** | 跨 agent 协作要在 文档 / SSOT 显式声明, 不靠 "应该都知道" |

## 5. 不在本 STRAT 范围 (反向警示)

| NOT IN P77 | 原因 |
|------------|------|
| ❌ 重写 agora (3.x 稳定) | 与 "稳定当先" 原则冲突 |
| ❌ 重写 cockpit-ui monorepo split | 反向警示 #2 (拖 2 季度, 但与 LLM-assisted commit 路线无 strong correlate) |
| ❌ 动 L0 SSB (与 ADR-0133 冲突) | L0 不变层原则 |
| ❌ 强加 ontology kind 到 toolbox | 反向警示 #4 (deliberate exception 清单才是答案) |
| ❌ gbrain god module 真拆 | 推到 P78 (单仓专项, 不在 P77 cross-repo 主题) |
| ❌ Knowledge Foundry web dashboard | 推到 P78 (体验优化, 非债务治本) |

## 6. 验证清单

- [ ] 用户授权本 STRAT + 启动 Phase 1
- [ ] 5 个 ADR (0164-0168) 全部写, 全部 ACCEPTED
- [ ] 治理 score 期末回升 100 A+
- [ ] STRAT-P77 → ACCEPTED historical-strategy (末尾)

## 7. 现状 (启动 P77 之前的真实状态)

> 这部分诚实登记, 不打包装饰:

- governance: **85.7 B** (X-Plane ruff errors 引起的临时下降; 启动 Phase 2.5 治本之前需先 reset)
- GaC rules: **157** (X-Plane worktree reset 退回; P76 落地的 161 现工作中)
- planned tasks: 0 (P76 fully closed, true)
- 9A hook: merged @ dfcf7f44 (tested, 已工作)
- foundry cron: alive (P76 Phase 7.2 verified)

P77 如启动 **优先 task**: 重置 governance 100 / GaC 161 (做这之前 launch commit-assist 在 scoring 90+ 时不会被反映)

---

*最后更新: 2026-07-07 · P77 战略路线图 DRAFT · 等用户授权*
