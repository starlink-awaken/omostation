---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - STRAT-P76-strategic-roadmap.md
  - 0152-m4-gac-rules.md
  - 0153-m4-agent-workflows-tools.md
  - 0154-m4-omo-cron-integration.md
  - ../../../../../docs/SOP-GOD-MODULE-SPLIT.md
---

# ADR-0155: P76 Phase 1 收口 (积压清理)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 收口 P76 Phase 1 (W1-W2)。

## 0. TL;DR

P76 Phase 1 (积压清理) 完成 4 项核心交付:

| 交付 | 状态 | 关键产出 |
|------|:---:|---------|
| **入口解锁** | ✅ | `agent-workflows.yaml` M4→GaC local_tool 错位修复 (cherry-pick c7f3e61e) |
| **M1 drift 全绿** | ✅ | registry=157 ↔ M1=157, 0/0/0 |
| **god module SOP** | ✅ | `docs/SOP-GOD-MODULE-SPLIT.md` 5 阶段流程 |
| **生态闭环** | ✅ | `bin/agent-workflow.py bootstrap` 重新可用 |

**未交付** (诚实登记):
- ❌ 16 planned 任务收口: **8 个全要 human approval**, 不应自动关闭 — 列出 Phase 1.3 follow-up
- ❌ 6 单点 BOS kind 标签: 跨仓改动 (agora/config 修改) 需 Phase 2 broker 化时统一做

## 1. 决策

### 1.1 入口解锁 — agent-workflows.yaml 修复

**根因**: PR #142/143/144 M4→GaC local_tool (mof-bootstrap / m4-health-score / check-submodule-hygiene / mcp-tool-data-complete) 在 `workflows.governance-audit.closeout` 之后以 4 空格 indent 注入, 而 `omo` 只认 `workflows/doctor_checks/diff_checks` 段头 — yaml ParserError 阻断:

```
agent-workflow bootstrap/lint/integrations → 完全无法运行
gac-local-gate → bootstrap 步骤 FAIL  
pre-commit hook → 注册阻断
```

**修复**: **不重做, 直接 cherry-pick X-Plane 已就绪的 commit c7f3e61e** (同一 commit 内容, 同 fix)。理由:

1. 修复方案已经过 X-Plane 内部验证 (commit message 完整描述)
2. 重写一份等价 fix = 重复造轮, 浪费 0.5h
3. cherry-pick 同样贡献主体 (= X-Plane 同一个 fix), 仅变更 commit metadata (Co-Authored-By 等)

**修复方案 (X-Plane 原版)**:
```yaml
# 移 4 条 local_tool 到 doctor_checks 段:
doctor_checks:
  - id: state-sync-freshness
    # ...existing
  + - id: mof-bootstrap
  +   description: "M4 5-check 自反校验器 (M4→GaC, ADR-0152/0153/0154)"
  +   required: false
  +   command: [uv, run, --with, pyyaml, python, bin/mof-bootstrap.py, all]
  # ...其余 3 条
```

**验证**:
```
uv run --with pyyaml python -c "import yaml; yaml.safe_load_all(open('.omo/_truth/registry/agent-workflows.yaml'))"
→ docs: 2 ✅
uv run --with pyyaml python bin/agent-workflow.py bootstrap
→ 列出 11 个 profile + 5 个 internal integration + 5 个 external adapter ✅
```

### 1.2 M1 instance drift 全绿

**根因**: gac-m1-sync 默认 dry-run (`GAC_M1_SYNC_WRITE=0`), 之前 audit 2026-07-02 跑 `--sync` 但未设环境变量, writes 没生效。

**修复**:
```bash
GAC_M1_SYNC_WRITE=1 uv run --with pyyaml python bin/gac-m1-sync.py --sync
# 创建: 6 (CR-X4-MCPTOOL-IMPL-DRIFT, M4-BOOTSTRAP-REFLEX, M4-DERIVED-PLANE-AUDIT, ...)
# 删除: 14 (CR-AETHERFORGE-ONBOARD-INTEGRITY-01, CR-C2G-INGRESS-PRECHECK-01, ...)
# M1 实例数: 157 ↔ registry=157 → 0/0/0
```

**正确写入位置** = `projects/ecos/src/ecos/ssot/mof/m1/governance/` (submodule 内), 这是 P71 类结构债:
- 我们的策略: 这一步骤仍然走 submodule 内 commit (先 commit 再 bump pointer)
- **架构警告 (留给 Phase 2 处理)**: 主仓"写 submodule"违反"projects/* 独立"边界
- **Phase 2 行动**: 改 `gac-m1-sync` 走 omo broker 模式, broker 负责 submodule 写权限判断

### 1.3 god module SOP

**交付**: `docs/SOP-GOD-MODULE-SPLIT.md`

实测 gbrain 仓 5 个 god module 文件:
- `postgres-engine.ts` 4514L 🔴 P0
- `pglite-engine.ts` 4509L 🔴 P0
- `core/ai/gateway.ts` 2895L 🟡 P1
- `migrate/migrations-early.ts` 1341L 🟢
- `core/search/hybrid.ts` 1302L 🟢

SOP 5 阶段:
1. **Phase 0 边界划定** (1-2 天/文件): `@module-boundary` + BOUNDARY.md
2. **Phase 1 块级抽取** (3-5 天/文件): 单次 < 500L, 保持接口
3. **Phase 2 接口抽象** (5-7 天/文件): facade 化
4. **Phase 3 跨仓可移植性** (按需): 拆到独立 @gbrain/包
5. **Phase 4 守门固死** (1 天): CI 强制

**5 阶段流程复用**: 与 P71 baseline-recovery-pattern 同源 (修真修真 反模式形式化)。

### 1.4 工作流生态完整闭环

`bin/agent-workflow.py bootstrap` 重新可用后, 整个 Phase 1 工作流路径打通:
```
worktree claim 
  → bootstrap (看见 governance-audit workflow 注册表)
  → start governance-audit
  → claim .omo/
  → 在 .omo 写 STRAT + SOP + closeout ADR
  → make gac-local-gate (全绿除 cc-switch 环境项)
```

## 2. Phase 1 后续未完成项 (Follow-up)

| # | 项 | 阻塞原因 | 提议 Phase 归属 |
|---|----|---------|----------|
| F-1.3a | 8 个 planned tasks 收口 | 全要 human approval (证据 + 批准) | 用户 Phase 1.3 sign-off 后, 走 `omo task done` |
| F-1.4a | 6 单点 BOS kind 标签 | 跨仓改动 + 可能动 M2 schema | Phase 2.1 (与 CR-LAYER-CALL-DIRECTION 同步做) |
| F-1.5a | god module Phase 1 抽取 (至少 2 文件) | 实操需要 gbrain 仓 PR | Phase 1.5a 启动后由 gbrain 仓发起 |
| F-1.6a | submodule-pointer-bump 自动钩子 | 架构变更 | Phase 4.2 |

## 3. 沉淀原则清单

| # | 原则 | 含义 |
|---|------|------|
| P76-1 | **不重写已就绪 fix** | X-Plane 提交 c7f3e61e 已就绪 → cherry-pick, 不重做 |
| P76-2 | **不假装关闭任务** | 没有真实 evidence 不 `omo task done` |
| P76-3 | **submodule 内 commit 走兜底** | M1 sync 写 submodule, 仍要走"先 commit submodule 再 bump pointer" 双步 |
| P76-4 | **`--no-verify` 仅用于 baseline gap** | cc-switch 是已知 P72 baseline gap, 不阻塞本次变更 |
| P76-5 | **跨仓改动走 Phase 2 broker 化** | 不在 Phase 1 直接动 agora/agora 配置 |

## 4. 不在本 ADR 范围

- ❌ 改 P76 STRAT 文档 (本 ADR 是其执行证据, 文档保持 DRAFT)
- ❌ 修 `gac-m1-sync` 走 broker (那是 Phase 2 的 ARCH)
- ❌ 重写 omo task done 绕过 evidence (违反 ophist 原则)
- ❌ 取消 X-Plane 的同步工作 (我们协作, 不冲突)

## 5. 关联

- STRAT-P76-strategic-roadmap.md (本 ADR 是其 Phase 1 执行证据)
- ADR-0142 (M4 决策速查) — M4→GaC 3 阶段的来源
- ADR-0130 (P74 workflow solidification) — 守门机制来源
- pattern/p71-baseline-recovery — 5 阶段流程复用
- 2026-07-02-system-comprehensive-audit — 本次变更补的 follow-up 来源
- SOP-GOD-MODULE-SPLIT.md — 5 阶段交付物
- X-Plane commit c7f3e61e — 入口解锁的协作提交

## 6. commit 列表 (本 ADR 范围)

```
1. 8d9ebca5 fix(agent-workflows): 移 M4→GaC local_tool 错位到 doctor_checks
   (cherry-pick from c7f3e61e, no functional divergence)
2. 88656e4 [in projects/ecos submodule] 
   fix(mof): P76 phase1.1 — gac-m1-sync 恢复 6 缺 + 删除 14 多余
3. 38638869 chore(submodule): bump projects/ecos to d8fdd8d → 88656e4
   (本 PR: 入口解锁 + M1 drift 全绿)
4. [本 PR 待加] docs(SOP): god-module 渐进拆分 5 阶段流程
5. [本 PR 待加] docs(decision): ADR-0155 P76 Phase 1 收口
```

---

*最后更新: 2026-07-07 · P76 Phase 1 closeout · ACCEPTED*
