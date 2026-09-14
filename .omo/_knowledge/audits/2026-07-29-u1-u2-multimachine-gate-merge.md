---
status: needs-human
lifecycle: history
owner: governance-team
last-reviewed: "2026-07-29"
type: ephemeral
status: archived
---
# U1/U2: #592 多机违规 + 合并门真接

## U1: #592 违反 ADR-0247 DEFERRED (送卡用户二选一)

### 事实
- **#592 MERGED**: `feat(registry): Agent Registry MVP for W5 multi-machine coordination`
- commit: a86cbe7ae (origin/main)
- author: starlink-awaken
- **违反**: ADR-0247 line 18/34 "物理多机 DEFERRED (不设时间表, 不占预算, 不再周提醒)"

### agent 立场 (不擅自决策)
- 🔴 **agent 不显式授权** (ADR-0247 DEFERRED 是用户战略决策, agent 无权单方解除)
- 🔴 **agent 不擅自 revert** (已 MERGED, revert 破坏性, 需用户确认)
- → **送卡用户二选一** (U1 原文):

### 二选一 (请用户决定)
1. **回滚** (守 ADR-0247 DEFERRED):
   `git revert a86cbe7ae` → 新 PR → 合并 (恢复 main 无多机代码)
   - 影响: 删除 Agent Registry MVP (W5 多机)
   - agent 建议: **选回滚** (DEFERRED 未解除, #592 违规在先)
2. **显式授权** (解除 DEFERRED):
   - 用户 amends ADR-0247, 把多机从 DEFERRED 提到 active
   - 然后 #592 合规
   - agent 不代决策

### agent 推荐: 回滚 (理由)
- ADR-0247 DEFERRED 明确"不设时间表/不占预算", #592 占了预算 (W5 工作)
- T1 刚定性产能轨污染违规, #592 是同类"擅自扩战线"
- 守 ADR 纪律 > 接受既成事实

## U2: check-scenario-growth 真合并门 (✅ 已接, 实测)

### 事实 (实测)
- sgf-policy.yaml line 174: `check-scenario-growth` gate (perf_budget_s: 2) ✅
- gac-gate.yml (CI): PR + push main 跑 `gac-local-gate --strict`
- **本地模拟 CI 实测**: `gac-local-gate --strict` 跑 check-scenario-growth ✅
  (`check-scenario-growth 在 strict gate 跑: ['check-scenario-growth']`)

### --no-verify 绕不过 CI (关键)
- --no-verify 绕**本地** .githooks/pre-commit (gac-local-gate)
- 但 **CI gac-gate.yml 在 PR 合并前必跑 strict** (GitHub Actions, --no-verify 无效)
- → check-scenario-growth 在 **CI 真合并门**, --no-verify 绕不了

### --no-verify 泛化使用 (风险记录, U2 关切)
历史 --no-verify 使用 (grep audits):
- M1 reachability push (summary 记录, CI submodule-freshness 兜底)
- debt 门禁断裂 (check_health_ssot 失败 → --no-verify 绕, 后修)
- m1-conflict-rootcause: flag no_verify_push

**性质**: --no-verify 绕本地门, 依赖 CI 兜底. 风险 = 本地门失效时, CI 是否真兜底.
- check-scenario-growth: CI 兜底 ✅ (gac-gate --strict 跑)
- 但 --no-verify 泛化是治理风险 (本地门信任度下降)

### U2 加固建议
1. ✅ check-scenario-growth 已在 CI 合并门 (本审计实测)
2. 🟡 限制 --no-verify 使用 (policy: 只用于 reachability 这类 CI 兜底的冗余验证,
   不用于消性能/质量警 — N1 红线"不跳过检查")
3. 🟡 本地 pre-commit 失效时, 必须修 (非 --no-verify 绕), 防"本地门长期失效靠 CI 兜"

## 🔴 红线
- U1: agent 不擅自授权/revert (送卡用户二选一)
- U2: 门真接 CI 合并路径 (非 informational, --no-verify 绕不了)

## References
- ADR-0247 (物理多机 DEFERRED)
- U1/U2 用户指令
- T1 产能污染违规 (同类"擅自扩战线")
- check-scenario-growth (S1/T2 门)
