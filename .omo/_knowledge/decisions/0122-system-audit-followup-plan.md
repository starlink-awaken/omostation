---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-07-02
related:
  - ../audits/2026-07-02-system-comprehensive-audit.md
  - ../patterns/p71-baseline-recovery-pattern.md
  - 0115-bin-governance-rationalize.md
  - 0119-systemic-optimization-roadmap-2026h2.md
  - 0120-runtime-health-semantics-fix.md
  - 0121-gcsi-governance-convergence-special-initiative.md
---

# ADR-0122: 系统全面审计 18 项 Follow-up 实施计划 (排除 god-module)

- **Status**: PROPOSED → ACTIVE (本 PR 推 S0 后转 active)
- **Date**: 2026-07-02
- **Authors**: governance-team (基于 PR #11 系统全面审计 18 项 follow-up)
- **Supersedes**: 0119 systemic-optimization 28 项中与本审计重复部分
- **Related**: ADR-0115 (bin 治理面 4 phase) / ADR-0119 (S0-S3 28 item) / ADR-0120 (freshness semantics) / ADR-0121 (GCSI) / P71 baseline recovery pattern

## Context and Problem Statement

PR #11 (`23702782`) 系统全面审计 (架构/功能/文档/债务/配置 5 维) 报告 20 项问题. 本 PR 修 2 P0 + 加 1 守护规则. **剩余 18 项 follow-up** (god-module 用户排除) 需要分阶段规划, 避免散点式 commit 造成 lane 混乱和元治理盲区再次累积.

18 项 follow-up 来源:
- 1.1.4 gac-m1-sync 写 submodule 架构问题 (F-5)
- 1.1.5 omo-debt 弃用 (F-13)
- 1.2.2 16 planned 任务累积 (F-2)
- 1.2.3 governance score 下滑 (F-2 联动)
- 1.3.1 cross-refs 4701 死链 (F-3)
- 1.3.2 dead-path-refs 50+ (F-4)
- 1.3.3 `> 最后更新` 时间戳反复加 (F-9)
- 1.3.4 FCM/NORTH-STAR 数字 stale (F-10)
- 1.4.2 BOS 3 处越界 (F-7)
- 1.4.3 + 1.5.2 6 单点 BOS 域无 kind (F-8)
- 新加 1.1.4 pre-push hook 误报 (F-11)
- 新加 1.1.4 gitconfig 配置漂移 (F-12)
- 新加 omo-debt 弃用收编 (F-13)
- 依赖项: ADR-0119 S2-5/S2-6 (state-freshness) + ADR-0115 Phase 2/3/4

## Decision Drivers

- **避免 god-module 跨仓债**(用户明示排除)
- **可执行**: 每项有责任项目 + 工作量 + 依赖
- **阶段化**: S0/S1/S2 + P2 渐进, 避免单 PR 巨型化
- **lane 守门**: 每 commit 单 lane, pre-commit hook 强制
- **X-Plane 协作**: mode=advisory 不阻塞, 避其 claimed paths
- **跨仓协调**: F-7/F-8/F-13 需 agora/omo/cockpit 团队, 不能主仓独立做

## Considered Options

### A. 3 阶段路线图 (推荐)

- S0 即时 (本 PR, ~1h): 4 commit, 1 PR
- S1 短期 (1-2 周): 4 PR + 1 submodule commit, ~12h
- S2 中期 (3-4 周): 3 PR + ADR-0115 P2+4, ~16h
- P2 长期: 跨仓 rename 5 阶段 (本仓无法独立)

### B. 单 PR 全做

- ❌ 单 PR 巨型化 (>20 commit), review 难
- ❌ 跨仓 F-7/F-8/F-13 不属主仓 scope
- ❌ 违反 lane check + GaC 7 机制

### C. 接受现状 (不规划)

- ❌ governance score 持续下滑 (97.8 趋势)
- ❌ 元治理盲区累积 (P49 已清零又累积, 周期循环)
- ❌ 与 ADR-0119 systemic roadmap 方向冲突

## Decision

**采用 A: 3 阶段 + P2 长期**, 每阶段独立 PR, 阶段间保留可中断性.

## 18 项路线图

### S0 即时 (本 PR, ~1h)

| 项 | 文件 | 工作量 | 验收 |
|---|---|---|---|
| **F-9** GaC 规则 `CR-DOC-NO-LAST-UPDATED` (守文档不再有"最后更新时间戳"行, 治 X-Plane 自动化副作用) | `.omo/_truth/registry/governance-checks.yaml` | 5min | gac-validate 140→141 PASS |
| **F-10** 修 FCM "115 规则" / AGENTS "7 机制 + 115 规则" / NORTH-STAR "118 规则" 数字 → 140 (清理"现在的事实"段落, 不改历史快照日期) | `docs/FUNCTIONAL-CAPABILITY-MAP.md` + `AGENTS.md` | 10min | rg 0 stale 数字 |
| **ADR-0122** 写本计划 (本文件) | `.omo/_knowledge/decisions/0122-system-audit-followup-plan.md` | 30min | commit + push |
| **ecos submodule M1 commit** + 主仓 bump pointer (5 个 GAC-RULE-*.yaml 在 `projects/ecos/` 内 untracked, 需 submodule 维护者 commit) | `projects/ecos/` 内 commit + 主仓 submodule pointer bump | 15min | main 包含 5 GAC-RULE M1 instance |

### S1 短期 (1-2 周, 4 PR)

| 项 | 责任项目 | 工作量 | 依赖 |
|---|---|---|---|
| **F-3** 修 `check-cross-refs` 4701 死链 (大头: archive 文件旧路径引用, 修链接 OR 删 archive) | 主仓 + archive 清理 | 4h | - |
| **F-4** 修 `check-dead-path-refs` 50+ `.omo/PROJECTS/` 死引用 | 主仓 | 1h | 跟 F-3 同步 |
| **F-5** 修 `gac-m1-sync` 写 submodule 内架构问题: 改 omo broker 写 (路径 `projects/ecos/.git/worktrees/<wt>/modules/projects/ecos` 替换) | omo 仓 + bin/ 工具 | 2h | - |
| **F-6** ADR-0115 Phase 3: 7 个 check-* 工具接入 `gac-local-gate.py::CHECKS` (按 false-positive 风险分级: 立即接 / scoped / CI-only / 归档) | 主仓 | 3h | ADR-0115 已接受 |
| **F-11** 修 `bin/sync-submodules-push.sh` 的 `noupstream=$((noupstream+1))` 在 `set -euo pipefail` 下被 stdin parsing 误触发; 改用更稳的检测 (e.g. 不用 pipefail 或加 guard) | 主仓 | 1h | - |
| **F-12** 修 auto-PR ISO 配置漂移: `make install-hooks` 后 `T .githooks/pre-commit` 残留, 改 Makefile 或加 install-hooks fix-up | 主仓 | 1h | - |
| **ecos submodule M1 5 commit (bump pointer)** | omo 仓 + 主仓 | 1h | F-5 完成 |
| **ADR-0121** 跟踪: X-Plane branch `work/gcsi-adr-0121` GCSI 推进 | governance-team | 0 | 跟踪即可 |

### S2 中期 (3-4 周, 3 PR + ADR-0115 Phase 2/4)

| 项 | 责任项目 | 工作量 | 依赖 |
|---|---|---|---|
| **F-2** ADR-0119 S2-5: 新建 `bin/state-freshness-check.py` (基于 ADR-0120 freshness fix) | 主仓 | 3h | S0 完成 |
| **F-2 cont.** ADR-0119 S2-6: state-freshness 纳入 gac-local-gate | 主仓 | 1h | F-2 step 1 |
| **F-2 cont.** governance-evolution initiative 进度填充 (8 个全 active, 0 done) | 主仓 | 2h | - |
| **governance score 回升 97.8 → 100** (配合 F-2 完成) | 主仓 | 2h | F-2 完成 |
| **F-8** 6 个单点 BOS 域加 `kind: bridge` 或 `kind: facet` 标签 (`bos://cockpit/` / `bos://l4-kernel/` / `bos://runtime/` / `bos://meta/` / `bos://swarm/` / `bos://omo/`) | agora 仓 + 各 owner 仓 | 3h | 跟 F-7 同步 |
| **F-13** 删 `projects/omo-debt/` 独立仓, 收编到 cockpit 入口 | 主仓 + cockpit | 1h | - |
| **ADR-0115 Phase 2** `gov-` → `governance-` 短前缀 rename (2 文件: `gov-history-stats.py` + `gov-trend-report.py`) | 主仓 | 1h | F-6 完成 |
| **ADR-0115 Phase 4** 4 个 dashboard 工具合并为单 `bin/governance-dashboard.py <subcommand>` | 主仓 | 3h | F-6 完成 |

### P2 长期 (渐进, 跨仓协调)

| 项 | 描述 | 状态 |
|---|---|---|
| **F-7** BOS 域 3 处越界跨仓 rename 5 阶段: 本仓标准(已, ADR-0115) → agora PR 加 `kind:` + `deprecated_uri:` redirect → consumer PR 切新 URI → 主仓 bump → radar_cron 跑 gac-gc 删 deprecated | 跨仓协调, 5 阶段计划, 主仓无法独立 |
| **F-3 archive 文件** | 决定: 保留 (历史价值) 还是删 (减少死链) — ADR 决定, 默认保留 + 修链接 |
| **FCM "115 规则" / NORTH-STAR "118 规则"** | 接受现状(历史快照不可改) |
| **`.omo/_knowledge/management/append-only-log-pattern-*` deleted 引用** | 接受现状(archive 文档保留历史) |

## 阶段依赖图

```
S0 (本 PR)
  ├─ F-9 守时间戳 → 1 规则
  ├─ F-10 数字 → 2 文件
  ├─ ADR-0122 计划 → 1 ADR
  └─ ecos M1 commit → 1 submodule commit + 1 主仓 commit

S1 (1-2 周)
  ├─ F-3 + F-4 死链 ─────┐
  ├─ F-5 broker 写 ──────├─ 4 PR + 1 submodule commit
  ├─ F-6 check-* 接 ─────┤
  ├─ F-11 hook 误报 ─────┤
  └─ F-12 gitconfig ─────┘

S2 (3-4 周)
  ├─ F-2 + governance 回升 ──┐
  ├─ F-8 单点 BOS kind ───────├─ 3 PR + ADR-0115 P2+4
  ├─ F-13 omo-debt 删 ────────┤
  └─ ADR-0115 P2+4 ──────────┘

P2 (长期)
  └─ F-7 BOS 跨仓 rename (5 阶段) — 跨仓协调
```

## 责任分配

| 阶段 | 主要责任 | 配合责任 |
|------|---------|---------|
| S0 | governance-team (本 PR) | X-Plane (auto 监控) |
| S1 | governance-team + omo-team (F-5) | gbrain / agora teams (F-3 跨仓) |
| S2 | governance-team + cockpit-team (F-13 + P2) | agora / omo (F-8 + ADR-0115 P2/P4) |
| P2 | agora-team 主导 | omo / metaos (consumer 改) |

## Failure Modes (反模式)

- ❌ "S0 跳过, 直接做 S1/S2" — 立即可做的不做, 治理债累积
- ❌ "S1 跳过 F-5 broker 写, 直接做 F-6" — broker 写不改, F-6 接入的 check-* 工具有 false-positive 风险
- ❌ "S2 跳过 F-2 直接做 F-8" — governance score 持续下滑, 跨仓协调失去依据
- ❌ "P2 F-7 不启动" — BOS 域越界持续, 5 阶段计划作废
- ❌ "用 'gov-' 短前缀记新文件" — 重复触发 ADR-0115 Phase 2 治理面

## Consequences

### 正面

- 18 项 follow-up 有明确阶段 + 责任 + 工作量 + 依赖
- 避免散点 commit 触发 GaC drift
- 阶段间可中断, 不阻塞其他工作
- 与 ADR-0119/0115/0120/0121 现有 roadmap 协同
- governance score 回升路径明确

### 负面

- S1/S2 跨仓协调需多仓 owner 配合
- F-3 4701 死链修复 ROI 低(均匀分布, 无单点大贡献)
- P2 F-7 跨仓 rename 5 阶段需数月, 进度可能慢

## Verification

- [x] S0: make gac-local-gate PASS, F-9 规则加, F-10 数字刷
- [ ] S1 完成后: 4 PR merged, F-5 broker 写生效, F-6 check-* 接入
- [ ] S2 完成后: governance score 100, mof-drift 0 MEDIUM, ADR-0115 P2/4 done
- [ ] P2 启动: agora PR 走 5 阶段跨仓 rename

## Related

- PR #11 (`23702782`) — 系统全面审计 5 维 P0 闭环
- PR #10 (`f7beb558`) — X-Plane ADR-0120 freshness fix + matrix SSOT lint
- ADR-0115 — bin 治理面 4 phase
- ADR-0119 — systemic-optimization 28 item (S0-S3)
- ADR-0120 — freshness semantics
- ADR-0121 — GCSI governance convergence
- P71 baseline recovery pattern
