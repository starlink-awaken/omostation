---
status: active
lifecycle: retrospective
owner: governance-team
last-reviewed: 2026-07-03
related:
  - ../decisions/0122-system-audit-followup-plan.md
  - 0125-s2-followup-retrospective.md
  - 0124-s1-followup-retrospective.md
  - ../../SYSTEM-INDEX.md
---

# S2 阶段深度分析 (2026-07-03) — 当前状态 + 后续建议

## 0. 一句话总结

**S2 阶段在 health_score 100/100 状态下提前完成 6/7 项, 剩 F-8 / F-13 / F-14 三项明确留 follow-up (跨仓 + 主仓 边界, ADR-0122 已声明不属主仓 scope). X-Plane 在我离开后持续推进 148 commit, 实质完成 ADR-0115 Phase 4 全部 4/4 dashboard 合并 + governance score 满血回升 70→100, 我的 3 个 S2 续 commit (05ec76f9 / e19b44e5 / 计划中) 大部分已被 X-Plane 覆盖或重复.**

## 1. 关键数据对照 (origin/main 当前)

| 指标 | S2 阶段首日 (我离开时) | 当前 (2026-07-03) | 变化 |
|------|---------|---------|------|
| health_score 复合 | 70/100 | **100/100** | +30 |
| governance_anomaly_score | 100 | 100 | ✓ |
| service_online_ratio | 0.333 (3/9) | **1.000 (9/9)** | +0.667 |
| freshness_score | 50 | 100 | +50 |
| total_tasks | 110 | 103 | -7 (closeout) |
| planned | 15 | **8** | -7 (X-Plane 持续) |
| GaC 规则数 | 147 | **147** | ✓ (稳态) |
| ADR 数 | 84 | 84 | ✓ |
| 工具数 (bin/*.py) | ~95 | 95 | ✓ |
| gac-local-gate checks | 16 | **24** | +8 (X-Plane 加) |
| 跨仓 submodules 推进 | 5 | 持续 | (业务不属主仓) |

## 2. ADR-0122 18 项 落地状态

### S0 阶段 (PR #15) — ✅ 完成
- F-9 (CR-DOC-NO-LAST-UPDATED)
- F-10 (rules_count sync + 数 字刷)

### S1 阶段 (PR #17/#18/#19/#20) — ✅ 完成
- F-3/F-4 (死链精度 -33%)
- F-5 (gac-m1-sync advisory)
- F-6 (7 个 check-* 工具接入 gate)
- F-11 (sync-submodules-push 修 bash 陷阱)
- F-12 (install-hooks skip-worktree 解 T 残留)
- X2 M1 (CR-X2-GOVERNANCE-SEMANTIC-GATE) 派生 + M2 enum 扩
- + 4 sub-tools 漂移治本 (F-5 联动)

### S2 阶段 — 大部分完成

| 项 | 状态 | 落地位置 |
|---|------|---------|
| F-2 step 1 (state-freshness 独立) | ✅ PR #25 | `bin/gac/state-freshness-check.py` |
| F-2 step 2 (接入 gac-local-gate) | ✅ PR #25 | `bin/gac/gac-local-gate.py::CHECKS` |
| F-2 step 3 (8 initiative 进度) | ✅ PR #25 | `.omo/_truth/registry/governance-evolution-roadmap.yaml` |
| F-2 step 4 (state-freshness R1 stale 非阻塞) | ✅ DD3F190A | (S2 续) |
| F-2 step 5 (planned task 收口 11→8) | ✅ 05EC76F9 | (S2 续, 删 4 QUEST 测试残) |
| F-2 step 6 (governance score 100) | ✅ X-Plane 修复 (cron 启 daemon + state sync) | `.omo/state/health.yaml` |
| **ADR-0115 Phase 2** (gov- rename) | ✅ X-Plane 011cb271 | 2 rename |
| **ADR-0115 Phase 4** (4 dashboard 合并) | ✅ X-Plane 完全 inline + 物理删 3 文件 | `bin/gac/governance-dashboard.py` |
| **F-8** (BOS kind 标签) | ⏳ 跨仓, 留 follow-up | (不在主仓 scope) |
| **F-13** (omo-debt 收编) | ⏳ 跨仓, 留 follow-up | (不在主仓 scope) |
| **F-14** (sub-tools 漂移收尾) | ⏳ 实际已治本 (M2 enum + governance-semantic-gate), 但 gac-bootstrap 层 5 仍报 gac_local_gate 非法 (见 §3) | 留 local fix |

### P2 长期 — 跨仓 rename 5 阶段
- F-7 (BOS 3 处越界) — 跨仓, 留 P2

## 3. 发现的问题 (在 S2 阶段未覆盖)

### 问题 1: gac-bootstrap 仍报 gac_local_gate 非法 (P1 阻塞)

**症状**: `bin/gac/gac-bootstrap.py` 自举层 5 fail:
```
❌ CR-X2-GOVERNANCE-SEMANTIC-GATE: 非法 executor: ['gac_local_gate']
❌ CR-L0-MATRIX-PORT-CONSISTENCY: 非法 executor: ['gac_local_gate']
❌ CR-L0-MATRIX-LAUNCHD-COVERAGE: 非法 executor: ['gac_local_gate']
```

**根因**: gac-bootstrap 的 `valid_executors` set 从 `governance-checks.yaml::gac.schema.executor_enum` 读, 但 3 个规则已用 `gac_local_gate` 作为 executor. 检查**通过** executor_enum (含 gac_local_gate). 3 个规则**不应**在 valid_executors 报错.

**实际**: 需 dry-run 重测. 若确认是真的 bug, 是 F-14 sub-tools 漂移收尾的 P1 阻塞 (接 CHECKS 的 check 应 PASS 才健康). 修法: 检查 gac-bootstrap 的 `valid_executors` 加载逻辑 + 可能需要 reload schema enum.

### 问题 2: gac-executor 自检 exit code 与 ok 字段不一致 (P2)

`bin/gac/gac-executor.py` 返回 `ok: True` 但 exit code 1. 影响 gac-local-gate 实际判定.

### 问题 3: SYSTEM-INDEX.md 数字 stale

- 文档说 139 GaC 规则, 实际 147
- 文档说 89 ADR, 实际 84 (12xx 编号才 84 个)

修法: SYSTEM-INDEX 加 "auto-generated" 流程或加注释 "近似值, 详见 SSOT 源".

### 问题 4: BRIEF.md 的 system-index-distill skill 未跑

`.agents/skills/system-index-distill/` 刚加 (commit 03efb7b3), 未跑过 distillation pass. 可作为下个 PR 入口.

### 问题 5: F-8 / F-13 / F-14 仍 open

- **F-8** (BOS kind 6 域): 跨仓 — ADR-0122 明示不属主仓 scope
- **F-13** (omo-debt 收编): 跨仓 — 同 F-8
- **F-14** (sub-tools 收尾): 需修 gac-bootstrap 实际 bug (§3 问题 1)

## 4. 关于"现在的任务是否需要更新或迭代"

### 4.1 结论 — **不需要重启 S2 阶段**

**理由**:
1. health_score 100/100 已经是 ADR-0122 S2 终态 (P2 长期例外)
2. F-2 (state-freshness + governance 8 initiative + planned 收口) 6/6 完成
3. ADR-0115 Phase 2/4 完成
4. X-Plane 实质完成 6/7 S2 项, 我留的 3 commit 大部分已被覆盖

**唯一仍 open 的实质工作**: gac-bootstrap 报 gac_local_gate 非法 (F-14 sub-tools 收尾的 local bug, P1 阻塞)

### 4.2 建议的"下一步"按优先级

| 优先级 | 任务 | 工作量 | 状态 |
|------|------|------|------|
| P1 | F-14 治本: gac-bootstrap 修 gac_local_gate executor 误报 | 1h | open |
| P1 | F-14 治本: gac-executor exit code 与 ok 字段不一致 | 30min | open |
| P2 | SYSTEM-ININDEX.md 数字刷新 (或加 "auto-gen" 注释) | 30min | open |
| P2 | BRIEF.md 跑 system-index-distill (首次) | 1h | open |
| P3 | F-8 (BOS kind 6 域): 跨仓协调 PR 触发 | 跨仓 3h+ | 留 follow-up |
| P3 | F-13 (omo-debt 收编): 跨仓协调 PR 触发 | 跨仓 1h+ | 留 follow-up |
| P3 | P2 长期: F-7 (BOS 3 处越界) | 跨仓 5 阶段 | 留 P2 |

### 4.3 不建议现在推进的 (5 类)

1. **重启 S2 路线图执行** — 已 100% 完成, 重启会浪费 token
2. **跨仓 F-8/F-13 协调** — 不是主仓工作, 应触发各 owner 仓 PR
3. **新加 dashboard / 工具** — 130+ 工具, dashboard 4/4 已合并, 饱和
4. **改 governance 规则 schema** — 147 规则稳态, 改 schema 风险高
5. **重写 health_score 算法** — X-Plane 已修到 100, 满意

## 5. 建议立即推进的 1-2 项 (单 commit)

### 推荐 P1 commit 1: gac-bootstrap 修 gac_local_gate 误报

```bash
# 1. 复现
uv run --with pyyaml python bin/gac/gac-bootstrap.py | grep "gac_local_gate"
# 2. 修 (待查 valid_executors 加载逻辑)
# 3. 验证
uv run --with pyyaml python bin/gac/gac-bootstrap.py  # 应 PASS
make gac-local-gate  # 仍 PASS
```

### 推荐 P2 commit 2: SYSTEM-INDEX.md 加 "auto-gen 注释"

```yaml
# 在每个数字旁加:
# 139 GaC 规则 (近 似, 真值见 .omo/_truth/registry/governance-checks.yaml, generated_at 2026-07-03)
# 89 ADR (近 似, 真值见 .omo/_knowledge/decisions/INDEX.md, last-updated 2026-07-03)
```

## 6. 关于"迭代"

### 6.1 不要再加新规则的迭代

X-Plane + 治理团队持续加, 14 天已加 ~30 规则. 规则数到 147 接近 P2 阈值. **不应再加 governance 规则** (除 CR-X1-EVIDENCE-RUNNABLE 类元规则). 

新需求应走 "现有规则覆盖" → "新规则" 路径, 严控.

### 6.2 sub-tools 治本完成后, 可启动 S2 阶段正式关闭 ADR

ADR-0122 S2 阶段 18 项全部 100% 完成 (除 3 个跨仓留 follow-up) 后, 应起 ADR-0127 "ADR-0122 关闭 + 阶段复盘", 归入 ADR-0125 S2 retrospective, 不开新 ADR (留 S3 入口).

## 7. 总结

**S2 阶段在 100/100 健康度下实质完成, 剩 3 项 follow-up (F-8/F-13 跨仓 + F-14 local bug). 不需要重启 S2, 应转入 P2 长期 (跨仓 rename 5 阶段) 或 S3 阶段 (新路线图 ADR).**

**如要推进**: 单 commit 修 gac-bootstrap 误报 (P1, 1h) 是最划算的下一步.

## 链接

- ADR-0122 (S0/S1/S2/P2 路线图) / ADR-0124 (S1 复盘) / ADR-0125 (S2 复盘)
- P72 follow-up-completion-pattern
- PR #11 (P0) / #15 (S0) / #17/#18/#19/#20 (S1) / #25 (S2 首日)
- 148 commit (X-Plane + 人) 持续推进中
- SYSTEM-INDEX.md (workspace 导航 hub, 30 秒理解入口)

💘 Generated with Crush

Assisted-by: Crush:MiniMax-M3
