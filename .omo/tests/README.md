# .omo/tests — 治理与集成测试标准

> 日期: 2026-05-30  
> 状态: active  
> 范围: `.omo` 治理测试、Phase gate 测试、跨项目集成测试

---

## 1. 测试分层

| 层级 | 目标 | 示例 |
|------|------|------|
| Spec tests | 文档/YAML schema 完整 | task YAML 必填字段、Phase 状态一致 |
| Integration tests | 跨项目主路径 | Eidos ↔ OntoDerive ↔ Minerva |
| Failure-injection tests | 失败路径可控 | KOS count drop、L2 未确认写入、Agent deadlock |
| Acceptance tests | 用户可见闭环 | 用户问题 → KOS → minerva → 保存 → 审计 |

---

## 2. Governance consistency tests

必须检查：

1. `plans/README.md` 的 EXECUTION/REFERENCE 状态与 `goals/current.yaml` 一致。
2. `goals/current.yaml` 的 phase 与 `state/system.yaml.current_phase` 一致，除非 `state/system.yaml.phase_status = limited_go` 并说明原因。
3. 每个 active goal 至少有一个 `.omo/tasks/active/*.yaml`。
4. `TASK_POOL.md` 不再是唯一任务源。
5. Phase 关闭证据必须存在于 `goals/history/` 或 `summaries/`。
6. `state/system.yaml.divergence_detail_refs` 必须把 orphaned / stale / dangling debt 收敛到结构化 artifact，而不是仅保留计数。
7. `state/system.yaml.promotion_blockers` 必须能解释为什么某个 active task 还不能被推进。
8. 任务文档必须明确区分 active executable queue 与 planned queue。

## 3. Task schema tests

每个 `.omo/tasks/{active,done,blocked}/*.yaml` 必填：

- `id`
- `phase`
- `milestone`
- `priority`
- `title`
- `status`
- `source_docs`
- `depends_on`
- `risk_level`
- `operation_level`
- `human_approval_required`
- `evidence_required`
- `test_plan`

## 4. KOS baseline tests

KOS 修复任务必须提供：

1. before/after document count。
2. expected source inventory。
3. 10 known documents 查询清单。
4. reindex dry-run 或 snapshot/backup 证据。
5. degradation simulation：模拟 >20% count drop 时进入 CRITICAL 并暂停写入。

## 5. Operation level tests

Safe Mesh 必须验证：

1. L0 read 可以自主执行。
2. L1 low-risk write 自动执行但审计。
3. L2 high-risk write 未确认时拒绝。
4. L3 destructive action 需要人类确认和冷静期。
5. allow/deny 都写入审计证据。

## 6. Agent control plane tests

ACP 必须验证：

1. Agent heartbeat 超时后不再参与调度。
2. Registry 不可用时使用本地缓存且降级可见。
3. 未验证身份的 Agent 不能进入 active routing。
4. 恶意 Agent 注入场景被拒绝或隔离。
5. Agent 等待循环可以被检测为 deadlock。

## 7. Debt governance tests

Debt ledger 机制必须验证：

1. `.omo/debt/registry.yaml` 能列出 canonical debt items 与 output refs。
2. `.omo/debt/items/*.yaml` 保持 pointer-based truth，而不是复制 task/project 状态。
3. `scripts/omo_debt_metrics.py` 能从 ledger 派生 debt health / entropy / backlog / coupling 指标。
4. `scripts/sync_omo_state.py` 只把 debt summary 和 refs 写回 `state/system.yaml`。
5. `python3 scripts/omo_debt.py register|schedule|refresh` 的 lifecycle / generated outputs 可重放。
6. `.omo/AGENT.md` 必须记录 debt refresh 与 full verification 命令。

## 8. Test Plan References

### kos-baseline-tests
Referenced by: `M2.1-kos-index-diagnosis.yaml`, `M2.1-kos-repair-plan.yaml`

```yaml
test_cases:
  - id: KOS-BASELINE-01
    desc: "Before/after document count recorded"
    pass: "current_count matches expected source inventory ±5%"
  - id: KOS-BASELINE-02
    desc: "10 known documents searchable"
    pass: "10/10 return >0 results"
  - id: KOS-BASELINE-03
    desc: "Degradation simulation: 20% drop"
    pass: "system enters CRITICAL state, writes paused"
  - id: KOS-BASELINE-04
    desc: "Repair no-loss guard"
    pass: "backup exists, dry-run passes, rollback possible"
```

### operation-level-tests
Referenced by: `M2.2-operation-levels.yaml`

```yaml
test_cases:
  - id: OPLEVEL-01
    desc: "L0 read allowed without confirmation"
    pass: "read succeeds"
  - id: OPLEVEL-02
    desc: "L1 write auto-approved with audit"
    pass: "write succeeds, audit entry created"
  - id: OPLEVEL-03
    desc: "L2 write denied without _confirmed flag"
    pass: "PermissionError raised, audit entry shows deny"
  - id: OPLEVEL-04
    desc: "L2 write allowed with _confirmed=true"
    pass: "write succeeds, audit entry shows allow"
  - id: OPLEVEL-05
    desc: "L3 write denied without cool-down"
    pass: "PermissionError: requires 24h cool-down"
```

### agent-control-plane-tests
Referenced by: `M2.2-agent-registry-heartbeat.yaml`

```yaml
test_cases:
  - id: ACP-01
    desc: "Heartbeat timeout → zombie"
    pass: "agent removed from active routing after 180s"
  - id: ACP-02
    desc: "Registry unavailable → local cache"
    pass: "existing routes work, new registration denied"
  - id: ACP-03
    desc: "Malicious agent injection rejected"
    pass: "HMAC validation failure → registration denied"
  - id: ACP-04
    desc: "Deadlock detection"
    pass: "30min task timeout → probe sent, task rescheduled"
```

## 7. Existing Phase 2 integration test note

`test_phase2_integration.py` 目前用于 Eidos/OntoDerive/Minerva adapter 主路径验证。后续迭代应避免硬编码用户绝对路径，并将 ImportError 场景显式标记为 skip，而不是静默 return。
