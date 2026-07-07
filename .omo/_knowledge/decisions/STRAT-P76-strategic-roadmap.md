---
status: ACCEPTED
lifecycle: historical-strategy
owner: governance-team
last-reviewed: 2026-07-07
related:
  - 0155-p76-phase1-cleanup.md
  - 0156-p76-phase2-call-direction.md
  - 0157-p76-phase3-self-meta.md
  - 0158-p76-phase4-promotion.md
  - 0159-p76-phase5-foundry.md
  - ../../../.omo/_knowledge/audits/2026-07-02-system-comprehensive-audit.md
  - ../../../.omo/_knowledge/patterns/p74-workflow-solidification-pattern.md
---

# STRATEGY-DECISION: P76 战略 5-phase 迭代路线图 — **已收口 (2026-07-07)**

> **For agentic workers**: 本文档是 **ACCEPTED historical-strategy** 状态 (2026-07-07)。
> 全部 5 phase 在单一 commit batch 中交付 (commits see git log work/p76-phase1-cleanup)。
> 闭环证据: ADR-0155/0156/0157/0158/0159 + STRAT (本文件) AC 转换。
>
> 实施证据:
> - 12 commits ahead of main
> - 161 GaC rules (+4 新)
> - governance score 100 A+
> - 17 submodules aligned
> - debt-closed-per-feature ratio 0.688
> 路线图快照: 用户原话"启动吧, 制定规划, 完成 phase1-5"

## 0. TL;DR

| 字段 | 值 |
|------|---|
| **决策 ID** | STRAT-P76-2026-07-06 |
| **基线评分** | governance 100.0 A+ · GaC 157 rules 0err · gac-healthcheck ❌ 有红 (legacy-drift + M1 drift) |
| **5 phase 总预算** | 12 周 · 5 个 ADR · 8-12 个 PR |
| **首推动作** | Phase 1 (积压清理 2 周) — 不立新, 只消存量 |
| **冻结区** | debt score < 95 之前 **禁止**新增 L2 引擎或 X 扩展晋升 |

---

## 1. Baseline 自检报告 (R 步)

### 1.1 5 项核心健康指标

| 指标 | 现状 | 目标 | 阶段归属 |
|------|:---:|:---:|:---:|
| `omo governance` | **100.0 A+** | 保持 ≥ 98 | 全程 |
| `gac-validate` rules | **157 规则 0/0** | 保持 0/0 | 全程 |
| `gac-healthcheck` legacy-drift | ❌ **4 missing + 1 ghost** | 0/0 | Phase 1 |
| `gac-healthcheck` M1-instance drift | ❌ **6 missing + 14 extra + 2 expired** | 0/0 | Phase 1 |
| `ssot-guardian` SSOT IO | ❌ **2 violations** (submodule_pointer + direct_omo_io) | 0 | Phase 2 |
| `agent-workflow bootstrap` | ❌ **YAML parse error** (registry 损坏) | 加载成功 | Phase 1 P0 |
| Working tree dirty | 8 files | ≤ 50 | 全程 |

### 1.2 发现的 **P0 隐藏债务** (执行前的真问题)

1. **`.omo/_truth/registry/agent-workflows.yaml` 损坏** — line 1197+ 多个 `- id: mof-bootstrap` 等 sibling workflow 项 indent 错位 (应为 indent 2, 实为 4)。这会让 `agent-workflow.py bootstrap/list/lint` **完全无法运行**, 而该项目治理的"启动第一步"恰是 bootstrap — 形成**死锁入口**。
2. **`scripts` submodule pointer 落后** (492b9e6e), 需 omo broker 写而非手动 bump。
3. **6 个 M1 实例缺 + 14 多 + 2 过期** — registry 跟实际文件不一致。
4. **CR-X4-MCPTOOL-IMPL-DRIFT 1 处 drift** — 规则引用一个已重命名的工具, 需修正 source_ref 或恢复工具名。

> 这 4 项是 **Phase 1 必须先解决的"启动前提"**, 否则后续 phase 全部不可观测。

---

## 2. 战略 WHY (S 步 - 必答第一问)

### 2.1 解决什么问题?

依据 ADR-0142 (M4 决策速查) + 2026-07-02 系统审计 + P74 治理闭环, **当前 omostation 处于"成熟期山脚"**:

- ✅ **不变层 (L0/M0) 已稳**: SSB 签名链 + Stage/Gate 双锚生效, 157 GaC 规则 0/0
- ✅ **入口收敛 (L3) 已稳**: cockpit CLI/MCP/Web 三态统一
- ⚠️ **L2 引擎出现"双向耦合岛"**: runtime ↔ aetherforge ↔ omo 形成小环, agora 5 重依赖
- ⚠️ **元治理"未完整闭环"**: 9 个 check-* 工具 0 caller, 治理面有"幽灵资产"风险

### 2.2 量化数据

- 治理 score **趋势**: 100→97.8 (2.2 点下滑, P43-P71 历史数据)
- planned 任务累积: **16 > 5 阈值**
- god module: **7 文件 > 1500L 全在 gbrain**
- 死链: **4701 broken links / 512 文件**
- 工作树 dirty: 8 files (健康)

---

## 3. 候选方案 (S 步 - 必答第二问, 至少 3 个)

### 方案 A · 极简: 只清债 (1 周)

| 动作 | 内容 |
|------|------|
| F-1 | god module 拆分 SOP + gbrain 第 1 个文件拆解 |
| F-2 | 16 planned 任务收口 |
| F-3 | cross-refs 4701 死链清理 (大头: archive 旧路径) |
| F-4 | M1-instance drift 修复 |
| F-5 | registry yaml 损坏修复 |
| **代价** | 1 周, 零架构变更 |
| **收益** | governance score 推回 100; 入口解锁 |
| **风险** | 不动架构 = L2 引擎耦合继续累积 |

### 方案 B · 中量: 清债 + 分层契约硬化 (3 周) ⭐ 推荐

| Phase | 内容 | 工作量 |
|------|------|---:|
| **P1 积压清理** (W1-W2) | F-1 到 F-5 + 修 agent-workflows.yaml + 6 个 BOS 域加 kind | M |
| **P2 契约硬化** (W3-W5) | CR-LAYER-CALL-DIRECTION GaC 规则 + gbrain 三栈拆分重构图 + 写 ADR-0155 | L |
| **P3 元治全自** (W6-W8) | agent-workflow register --auto + debt_closed_per_feature 指标 | S |
| **P4 演化动力学** (W9-W11) | X 扩展晋升机制 + 主仓-子仓对称修复 | M |
| **P5 收敛面 + 演化平台** (W12) | omostation-bootloader + Knowledge Foundry | XL |
| **代价** | 12 周, 5 个 PR, 5 个 ADR, ~25 commits |
| **收益** | governance score 永远 ≥ 98; 爆炸半径 -70%; 元治理自给 |
| **风险** | P2 中 gbrain 拆分需 freeze gbrain 开发 1-2 月 |

### 方案 C · 大重构: 引擎层全部重写 (未通过)

| 不通过理由 |
|------|
| ADR-0133 evidence-complete 已声明 L0 SSB 重构为 v8 范畴 |
| agora 已稳定 3.x 是当前最强支柱, 拆了风险极大 |
| cockpit-ui 托管稳定, 拆出来增加 2× 同步成本 |
| **评估**: ROI 极低, 已被 ADR 系列黑名单覆盖 |

**→ 选择 方案 B (中量)**。

---

## 4. 12 周路线图 (E 步前导)

### Phase 1 · 积压清理 (W1-W2) — 不立新, 先消存量

| Step | 任务 | 子命令 / 文件 | 预期产出 |
|------|------|--------------|---------|
| 1.0 | **解锁 agent-workflow 入口** | `bin/fix-agent-workflows-yaml.py` (新建) 或手改 | yaml 修复 |
| 1.1 | GaC 健康红 → 全绿 | `gac-m1-sync --sync` + `gac-drift --fix` | 0/0 |
| 1.2 | ssot-guardian 2 violation | omo broker 写 → submodule-pointer bump | 0 violation |
| 1.3 | 16 planned 任务收口 | `omo task close --id <task>` 批量 | planned < 5 |
| 1.4 | 6 单点 BOS 域加 kind | `projects/agora/etc/bos-services.yaml` | 全部有 kind |
| 1.5 | god module 拆分 SOP | `projects/gbrain/docs/SOP-GOD-MODULE-SPLIT.md` | SOP 文档 |
| 1.6 | Phase 1 收口 PR | `.omo/_knowledge/audits/p76-phase1-closeout.md` | closeout |

**关键 ADR**: `ADR-0155-p76-phase1-cleanup.md`

### Phase 2 · 分层契约硬化 (W3-W5)

| Step | 任务 | 预期产出 |
|------|------|---------|
| 2.1 | CR-LAYER-CALL-DIRECTION GaC 规则 | governance-checks.yaml + 1 |
| 2.2 | 跑 1 周 informational 收集 violations | violations report |
| 2.3 | gbrain 三栈拆分重构图 | 设计图 + ADR-0156 |
| 2.4 | 真正拆 gbrain 第 1 个文件 | god module -1 |
| 2.5 | Phase 2 收口 | ADR-0155/0156 + closeout |

### Phase 3 · 元治全自 (W6-W8)

| Step | 任务 | 预期产出 |
|------|------|---------|
| 3.1 | `agent-workflow register --auto` 子命令 | 后台 cron |
| 3.2 | check-* 工具全部接入 gac-local-gate | `--strict` 模式补全 |
| 3.3 | debt_closed_per_feature 指标 | 新 bin 工具 |
| 3.4 | Phase 3 收口 | ADR-0157 |

### Phase 4 · 演化动力学 (W9-W11)

| Step | 任务 | 预期产出 |
|------|------|---------|
| 4.1 | X 扩展晋升机制 ADR | ADR-0158 |
| 4.2 | 主仓-子仓不对称修复 | submodule-bump-check 钩子 |
| 4.3 | mesh-router 真初始化或登记移除 | 单一决定 |
| 4.4 | Phase 4 收口 | ADR-0158 |

### Phase 5 · 收敛面 + 演化平台 (W12)

| Step | 任务 | 预期产出 |
|------|------|---------|
| 5.1 | omostation-bootloader 设计 | 设计文档 |
| 5.2 | Knowledge Foundry 雏形 (4 cron 编排) | cron 调度 |
| 5.3 | 全部 phase 总结 | STRAT-P76 closeout |

---

## 5. NEXT 候选清单 (S 步 - 必答第三问)

| 候选 | 触发条件 |
|------|---------|
| Phase 6 · 把 L0 SSB + M4 元模型迁到 v8 | governance score < 90 持续 1 月 |
| Phase 7 · cockpit-ui vs cockpit 接口契约形式化 | 出现跨仓 cockpit-ui 提交阻塞 |
| Phase 8 · 真正"knowledge agent"应用化 | kairon 16 包跑稳后 |
| Phase 9 · 跨工作区 federation (omostation + ToolBox 合并) | toolbox X1 audit=true 后 |

---

## 6. 关键风险与反向警示

| 反向警示 | 替代方案 |
|---------|---------|
| 不该重写 agora | 用分层契约约束依赖方向 |
| 不该拆 cockpit-ui monorepo | 引入接口契约 |
| 不该动 L0 SSB (与 ADR-0133 冲突) | 留给 v8 |
| 不该强加 ontology kind 到 toolbox | deliberate exception 清单 |

---

## 7. 验证清单 (实施 Phase 1 前必答)

- [ ] 用户授权 Phase 1 执行 (含 registry yaml 修复)
- [ ] worktree 创建 + agent-workflow start
- [ ] Phase 1 6 步全部走完, 每个 commit 都跑 gac-local-gate
- [ ] Phase 1 closeout ADR 写入 `.omo/_knowledge/decisions/0155-...md`
- [ ] 在 PR body 中 reference 本 STRAT 文档

---

## 8. 状态

- [x] R (Research) 完成: 5 项基线指标采集
- [x] I (Investigate) 完成: 4 项 P0 隐藏债务识别
- [x] S (Strategize) 完成: 3 方案对比选定 B
- [ ] E (Execute) **待用户授权 Phase 1**
- [ ] C (Closeout) Phase 1 closeout 待写

---

*最后更新: 2026-07-06 · P76 战略路线图 · 沿用 P60+ governance-phase-orchestrator RISE 循环*
