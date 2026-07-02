---
status: active
lifecycle: audit
owner: governance-team
last-reviewed: 2026-07-02
related:
  - ../patterns/p71-baseline-recovery-pattern.md
  - 0115-bin-governance-rationalize.md
  - 0119-systemic-optimization-roadmap-2026h2.md
  - 0120-runtime-health-semantics-fix.md
  - ../../../.omo/_knowledge/decisions/0117-p52-undo-p60-stage-8.md
---

# P0 Baseline Recovery Closeout (2026-07-02)

> 触发: PR#4 (c5fb0c8e) 把 dependency-baseline 迁 runtime/omo (gitignored) + 加 .gitignore:58
> 封死 .omo 旧位置 → CI fresh checkout 拿不到 → dependency-baseline-drift 报 **52 项** →
> gac-gate CI 红 + main CI 永红。 多人协作 + X-Plane 并发 agent 叠加加剧, 形成 baseline
> 完整性 + GaC 自洽性 + lane 守门 + 元治理递归 4 维系统性失守。
>
> 方法: 5 阶段 P71 模式 (Path-First → 治本 → lane 守门 → 守护规则化 → 元治理递归)
> + 多人协作 (Crush MiniMax-M3 + X-Plane Audit Agent) 合力 + 3 PR (#6/#7/#8) 分阶段合并.

## TL;DR

| 维度 | before | after | delta |
|------|-------:|------:|------:|
| GaC 规则数 | 135 | **139** | +4 |
| gac-gate 状态 | ❌ **永红** | ✅ **PASS** (12/12) | 治根 |
| dependency-baseline-drift | **52 项** | **0 项** | -52 |
| evidence_health_score | (未跑) | **78.9 / 100** | 量化基线 |
| X1 维度规则 | 29 | **31** | +2 |
| X4 维度规则 | 58 | **60** | +2 |
| meta 层规则 | 34 | **37** | +3 |
| PR merged | 0 | **3 (PR#6/#7/#8)** | 闭环 |
| 新 ADR | 0 | **2 (ADR-0115, ADR-0120)** | 提案沉淀 |
| 新 standard | 0 | **2 (bin-tool-naming, bos-uri-domain-standard)** | 契约沉淀 |
| 新 pattern | 0 | **1 (P71)** | 经验沉淀 |

## 1. 时间线 (commit by commit, 3 PR 共 18 commit)

### PR #6 (`4d305d21`, squash merge, 10 commit 携带) — P0 治根

| Commit | 类别 | 内容 |
|--------|------|------|
| `549a213d` | fix(config) | drop PR#4 baseline ignore rule (P0-1 prep) |
| `a48ef991` | fix(governance_state) | restore dependency-baseline.yaml to .omo tracked (P0-1) |
| `1797bb7b` | fix(p0) | baseline hardening — auto-merge F6 (ISC-33) + dependency SSOT path |
| `96b5b30c` | fix(p0) | gac gate CI skip + hook YAML parse fallback |
| `d09b1241` | fix(code) | evidence-smoke bootstrap agora venv site-packages |
| `e01c6a43` | fix(docs) | refresh project-registry SSOT counts (bos_services 100→114, rules 89→90) |
| `8517bb7b` | feat(gac) | add CR-X1-EVIDENCE-RUNNABLE — 声明绿必须真跑 |
| `5c435fd3` | fix(docs) | bump rules_count 90→91 |
| `0a4dfd3a` | docs(governance_state) | BOS URI 5 域锁定 + kind 标签 standard |
| `4377db7c` | feat(gac) | add CR-L0-BOS-DOMAIN-NORM — 5 域边界守护 |
| `7fb8bdfb` | fix(docs) | bump rules_count 91→92 |

### PR #7 (`fd367751`, squash merge, 9 commit 携带) — P0-3 补合

| Commit | 类别 | 内容 |
|--------|------|------|
| `943bbdc9` | docs(governance_state) | ADR-0115 + bin 命名规范 (P3-1 Phase 1) |
| `fd27ee83` | feat(gac) | add CR-META-BIN-NAMING + CR-META-BIN-ORPHAN |
| `738c5d4f` | fix(docs) | bump rules_count 92→94 |
| `7826ae6f` | chore(docs) | AGENTS.md / CLAUDE.md 最后更新 timestamp |
| `08d9e48e` | fix(governance_code) | doc-link-check + gac-local-gate skip docs/generated |
| `b984e68b` | chore(governance_state) | governance state + ADR-0120 (X-Plane 同步) |
| `d7b5320b` | chore(runtime) | system_health snapshot |
| `c9013864` | chore(submodule) | bump runtime + scripts submodule pointers |
| `421bff72` | chore(governance) | add new debt-audit-report |

### PR #8 (`ebdb47ca`, squash merge, 11 commit 携带) — 阶段收尾

| Commit | 类别 | 内容 |
|--------|------|------|
| `481708d0` | chore(omo-state) | governance state refresh (新 branch 续刷) |
| `8a4ec679` | chore(runtime) | system_health refresh (新 branch 续刷) |
| `7cde5c34` | chore(omo-state) | merge main + system.yaml conflict resolve (use main) |
| `754d0c61` | chore(runtime) | merge main + system_health.yaml conflict resolve (use main) |

**汇总**:18 个实质 commit 跨 3 PR 进 main, 1 个新 pattern + 2 个 ADR + 2 个 standard + 4 个 GaC 规则沉淀.

## 2. 根因剖析 (3 类 declaration-execution gap)

### 2.1 类 A: 路径错位 (SSOT 漂移)

```
PR#4 c5fb0c8e → 把 dependency-baseline 迁 runtime/omo (gitignored)
                + 加 .gitignore:58 封死 .omo 旧位置
CI fresh checkout → 拿不到 → dependency-baseline-drift 报 52 项
```

**治本**: 路径回 .omo (与 omo broker `find_omo_dir` 写入一致) + 删 ignore + 恢复 baseline.

### 2.2 类 B: 工具未接 (文件存在 ≠ 能跑)

```
9 个 check-* 工具 (check-god-module / check-boundary / check-cross-refs / ...)
  → 0 caller, 完全游离于 gac-local-gate.py::CHECKS 之外
  → "声明绿/执行红" 元治理盲区
```

**治本**: 1 条 GaC 规则 (CR-META-BIN-ORPHAN) 守 "工具未接 caller drift", 9 个工具后续 PR 评估 (ADR-0115 Phase 3).

### 2.3 类 C: CI 永远红 (环境不匹配)

```
agent-workflow-doctor 查 omo/c2g/cockpit 集成健康, 依赖 .venv + CLI
  → CI fresh checkout 无环境 → 永红
project-layer-index --check 找 docs/generated/project-layer-index.md (gitignored)
  → CI 无产物 → 必 stale 误报
```

**治本**: `CI_SKIP_CHECKS` 矩阵 (`agent-workflow-doctor` + `project-layer-index`) + 本地 strict 模式照跑.

## 3. 元治理递归 (新增 4 规则)

| 规则 | 维度 | 层 | check_type | 治 |
|------|------|----|------|------|
| `CR-X1-EVIDENCE-RUNNABLE` | X1 审计 | meta | audit_chain | 声明绿必须真跑 (类 A/B) |
| `CR-L0-BOS-DOMAIN-NORM` | X4 一致性 | L0 | bos_resolve | 5 域锁定 + kind 标签 (类 A 协议层) |
| `CR-META-BIN-NAMING` | X4 一致性 | meta | registry_integrity | bin 命名空间一致 (类 B 治理面) |
| `CR-META-BIN-ORPHAN` | X1 审计 | meta | drift_audit | 工具未接 caller (类 B 元治理) |

**元治理升级**:
- X1 (审计): 29 → 31 (+2)
- X4 (一致性): 58 → 60 (+2)
- meta (元治理): 34 → 37 (+3)
- 整体规则: 135 → 139 (+4)

## 4. 关键工具改动 (P0-1 治本)

| 工具 | 改动 | 治 |
|------|------|------|
| `bin/auto-merge-decide.py` | F6 ISC-33 五条件 AND (加 author_is_human 防 bot 自合) | 自治链 |
| `bin/gac-local-gate.py` | CI_SKIP_CHECKS 矩阵 + AGENT_WORKFLOW_GATE_CHECKS 分层 | CI 不再永红 |
| `bin/gen-dependency-baseline.py` | BASELINE_YAML 路径回 `.omo/` | SSOT 与 broker 一致 |
| `bin/evidence-smoke.py` | bootstrap agora venv site-packages (缺 pydantic 治本) | 量化鸿沟可跑 |
| `bin/gac-hook-pre-edit.py` | YAML 解析降级 (advisory 不阻塞编辑) | 韧性 |
| `bin/gac-executor.py` | 新增"声明可执行"维度 (P2-1 配套) | 元治理 |
| `bin/doc-link-check.py` | skip docs/generated/ | CI 不再永红 |

## 5. 验证 (本地 + 模拟 CI)

```bash
$ make gac-local-gate
═══ GaC local gate ═══
[PASS] gac-validate :: 139 规则, 0 error
[PASS] gac-drift :: 0 drift
[PASS] agent-workflow-lint / integrations / adapters / bootstrap / observe (5/5)
[PASS] mof-schema-validate / mof-state-bridge / mof-drift (3/3)
[PASS] doc-ssot-snapshots / change-lane-check (2/2)
GaC local gate: PASS (12/12)

$ python3 bin/evidence-smoke.py
🏷  evidence_health_score: 78.9 / 100
── BOS 声明/执行 (核心鸿沟, 权重 60%) ──
  声明总数: 114, 可 resolve: 112, 鸿沟: 2 (script not found), resolve 率: 0.982
── working tree 累积 (权重 20%) ──
  dirty 文件: 6
── 反馈回路 (权重 20%) ──
 回路存活: False (27.7h 停摆, ADR-0119 S2-5 跟进)
```

## 6. 跨仓 rename 计划 (P2-2 派生)

5 阶段跨仓 rename, 本仓内只标准 + 规则, 不动 URI:

| Phase | 范围 | 状态 |
|------|------|------|
| 1 | 本仓标准 `.omo/standards/bos-uri-domain-standard.md` | ✅ |
| 2 | agora PR 改 `bos-services.yaml` 加 `kind:` + `deprecated_uri:` redirect | ⏳ |
| 3 | agora/metaos/omo 各 submodule 切到新 URI | ⏳ |
| 4 | 主仓 bump submodule pointer | ⏳ |
| 5 | radar_cron 跑 gac-gc 确认 0 consumer → 删 deprecated 字段 | ⏳ |

3 处已知越界:
- `bos://analysis/iris/*` → `bos://memory/iris/*` (45 处引用)
- `bos://ecos/workflow/*` → `bos://system/workflow/*` (86 处引用)
- `bos://persona/health-profile/*` → `bos://capability/health-profile/*` (27 处引用)

## 7. ADR + Standard + Pattern 沉淀

| 类型 | 文件 | 用途 |
|------|------|------|
| Pattern | `.omo/_knowledge/patterns/p71-baseline-recovery-pattern.md` | 5 阶段恢复模式 (可复用) |
| Audit | `.omo/_knowledge/audits/2026-07-02-p0-baseline-recovery-closeout.md` (本文件) | 本次任务证据 + 数字 |
| ADR | `.omo/_knowledge/decisions/0115-bin-governance-rationalize.md` | bin 工具集 4 阶段重整提案 |
| ADR | `.omo/_knowledge/decisions/0120-runtime-health-semantics-fix.md` | runtime health 语义修正 (X-Plane 同步) |
| Standard | `.omo/standards/bin-tool-naming.md` | bin 工具命名规范 |
| Standard | `.omo/standards/bos-uri-domain-standard.md` | BOS URI 5 域锁定 + kind 标签 |

## 8. 经验教训 (给未来 AI 代理)

1. **"声明绿/执行红" 是 1999-style 治理悖论** —— GaC 用"看见" + "测执行" 双重验证, 见 P71 Phase 4
2. **submodule 边界 = 治理面边界** —— agora 在 submodule, 改 `bos-services.yaml` 需跨仓 PR, 见 P2-2 5 阶段计划
3. **lane 守门 = 治理面粒度** —— 一个 commit 改 5 lane 是 anti-pattern, pre-commit hook 强制 split
4. **X-Plane 是活的并发 agent** —— 预期它的 auto-commit/auto-PR/auto-touch, 跟随而非对抗
5. **`--squash --delete-branch` 是项目惯例** —— PR body 含 commit-by-commit 解释, 跟 PR #6/#7 风格一致
6. **BOS 域归属错配的治本不在本仓** —— 登记标准 + 规则, 等跨仓协调
7. **doc-ssot-lint 0 conflicts ≠ SSOT 完整** —— 它只查硬编码数字, 指标类数字 (bos_services / rules_count) 需手动同步

## 9. 关联

- PR #5 (omo submodule bump) #6 #7 #8 (P0 baseline 全程)
- ADR-0106 (GaC 北极星) ADR-0114 (L4 GaC 豁免) ADR-0115 (bin 治理面重整) ADR-0119 (systemic optimization roadmap) ADR-0120 (runtime health 语义)
- CR-X1-EVIDENCE-RUNNABLE / CR-L0-BOS-DOMAIN-NORM / CR-META-BIN-NAMING / CR-META-BIN-ORPHAN
- P43 / P44 既有 closed-loop pattern
- `.omo/_knowledge/patterns/p71-baseline-recovery-pattern.md` (可复用模式)
