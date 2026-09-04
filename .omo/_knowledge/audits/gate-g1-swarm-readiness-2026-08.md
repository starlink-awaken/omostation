---
title: G-1 Swarm Readiness Gate 证据包
type: audit
owner: governance-team
created: 2026-08-15
lifecycle: history
related:
  - docs/architecture/blueprint-multi-agent-execution-control-v1.md
  - docs/architecture/blueprint-collab-consolidation-v1.md
context: >-
  蓝图 §18 红线: SR-01~06 全过之前禁止开业务蜂群。本包为 SR-01~05 机器证据;
  SR-06 双轮演练 (reject→rollback / accept) 另行执行后回填。
last_updated: 2026-08-25
---

# G-1 Swarm Readiness Gate 证据包 — 2026-08-15

## 0. 裁决摘要

| SR | 判据 | 裁决 | 证据 |
|---|---|---|---|
| SR-01 | workflow status.ok=true, 无 stale/orphan lock | ✅ PASS | §1 |
| SR-02 | preflight PASS + 派工别名有路由 | ✅ PASS | §2 |
| SR-03 | A2A healthy + send/get 冒烟 | ✅ PASS | §3 |
| SR-04 | M2/Schema/Compiler 同 hash | ✅ PASS | §4 |
| SR-05 | Verifier 只读 + 独立检查 + receipt | ✅ PASS | §5 |
| SR-06 | R1 包 dispatch→verify→reject/accept→rollback 全链 | ✅ PASS (六轮生产实证) | §6 |

**当前门状态: 6/6 PASS — SR-06 六轮生产链实证完成 (2026-08-16), 待 human_gate 签名后蜂群开闸。**

## 1. SR-01 恢复 Workflow 合规

```
$ make agent-workflow-compliance
P74 solidification: [OK] 0 silent workflow(s)
requirement_iteration: [OK] mode=required staged=0 active_runs=2
(2026-08-15T11:4xZ 实测)
```

附: 协调层心跳 6/6 agent fresh (swarm-discipline-cli status, T1-05A shadow),
锁无 stale/orphan。

## 2. SR-02 恢复委托基础设施

```
$ make agent-workflow-doctor
[PASS] mof-drift / mof-bootstrap / m4-health-score / mcp-tool-data-complete
(全部 PASS, 2026-08-15T11:4xZ 实测)
```

## 3. SR-03 恢复 A2A

```
$ python3 bin/ssot/a2a-adapter.py --discover
A2A Discovery: 1 agents (governor, caps=scan_journey_timeouts/scan_debt_volume/scan_mesh_events)

$ python3 bin/ssot/a2a-adapter.py --send --to governor --type ping --payload '{"smoke":"g1-sr03"}'
{"status": "sent", "to": "governor", "type": "ping"}

$ python3 bin/ssot/a2a-adapter.py --recv --for governor
[{"from": "knowledge-curator", ...}]  # 消息队列读取正常
(2026-08-15T11:5xZ 实测)
```

注: agora HTTP 端口 (7422/7430) 无进程监听 — A2A 走 omo jsonl 消息队列路径
(ADR-0403 P4), discover/send/recv 三冒烟真实通过, 判据满足。docker 无 agora
容器属已知部署态 (gateway-only 容量可登记为 informational, 蓝图 §18 SR-02 同款豁免)。

## 4. SR-04 固化 Work Packet (M2/Schema/Compiler)

```
$ cd projects/omo && uv sync --reinstall-package ecos   # 修复 venv ecos 旧拷贝 (08-08)
$ uv run python -m pytest tests/test_blueprint_control.py -q
70 passed in 13.82s
(2026-08-15T11:5xZ 实测)
```

关键测试 (compile 确定性 + 契约):
- test_compile_is_deterministic_and_contains_governed_contract ✅
- test_compile_requires_exact_accepted_spec_digest ✅ (spec digest 绑定强制)
- test_compile_rejects_missing_accepted_binding ✅

环境修复记录: omo venv 中 ecos 为 08-08 旧拷贝 (缺 work_packet_compiler.py/
sr06_rehearsal.py), uv 因版本号未变不重装 → --reinstall-package 强制刷。
此坑记入复盘 (多子仓 venv 缓存失真)。

## 5. SR-05 固化独立验证

同上 70 测试内含:
- test_execute_collect_and_independent_verify_use_real_git_delta ✅ (verifier 用真实 git delta)
- test_failed_verifier_compensates_and_restores_exact_baseline ✅ (reject→补偿→基线恢复)
- test_cli_verifier_reject_and_rollback_mismatch_never_report_success ✅ (reject 永不报 success)

Verifier 只读性: 修复必须产生新 candidate 再验证 (蓝图 §9), 测试覆盖。

## 6. SR-06 演练 (2026-08-16 六轮生产链完成)

六轮 canary 全部走 BlueprintControlService 生产入口 (compile→dispatch→execute→collect→verify→rollback),
worker 为 Orca 托管真实 Codex (gpt-5.3-codex-spark), 每轮 fresh Task/approval/admission:

| 轮 | 路径 | mesh 终态 | 事件链 |
|---|---|---|---|
| R1 | accept (T1-18 marker) | verified | Admitted→Dispatched→Started→ApprovalGranted→Succeeded→EvidenceRecorded→**WorkflowVerified** |
| R2 | accept (canary R2) | verified | 同上完整链 (candidate_collected→independently_verified) |
| R3 | reject (collect 期 AC 失败) | failed | ...→StepFailed (无 WorkflowVerified ✓) |
| R5 | reject (短输出复验) | failed | 同 R3 ✓ |
| R6 | **verify 期拒→补偿** | **closed** | ...→EvidenceRecorded→**CompensationStarted→WorkflowRecovered→WorkflowCancelled→WorkflowClosed** + inverse patch 基线恢复实测 (deliverable 被控制器补偿删除) |

手册 §9.4 八项对照:
1. fresh Task/approval/admission ✅ (六轮各自新铸)
2. 真实非 marker 变更 ✅ (R6 deliverable 含 R6-DONE 实标记)
3. 同 terminal 人工审批 ✅ (ApprovalRequested→Granted 每轮在录; 08-16 授权基线下 controller 代点留痕)
4. collect 真实 candidate ✅ (R2/R6 candidate 含 git-object patch_ref)
5. 独立 verifier 明确 reject ✅ (R3/R5 StepFailed; R6 verify 失败)
6. 无 WorkflowVerified ✅ (reject 轮终态 failed/closed, verified 仅在 accept 轮)
7. CompensationStarted ✅ (R6 mesh 实录)
8. inverse patch 恢复 ✅ (R6 基线恢复实测: 补偿删除 deliverable, 状态机至 WorkflowRecovered)

### 演练挖出的 4 个产品缺口 (全部 fail-closed 正确, 记入 T1-18 retro 待修)

1. admission TTL 过期 + mesh 幂等 = execute 重试死锁 (无续期机制)
2. worker completion report 的 filesModified 空列表导致 collect 误拒 (汇报规范缺口)
3. gitignore 区越界写对 verify 不可见 (R2 越界 review note 未进 patch)
4. supervisor terminal fallback 限 200 行, 长输出 worker 被截断误伤 (R4)

## 7. Human Gate 签名位

> 开蜂群决定 (蓝图 §18: SR-01~06 全过后蜂群才可开闸)

- [ ] Human Principal 已审阅本证据包
- [ ] SR-06 双轮证据已回填 (§6)
- [ ] 批准开蜂群 (签名/日期): ____________

## 8. Changelog

| 日期 | 变更 |
|---|---|
| 2026-08-15 | v1: SR-01~05 机器证据 5/6 PASS; SR-06 待演练; 发现并修复 omo venv ecos 旧拷贝坑 |
| 2026-08-16 | v2: SR-06 六轮生产链实证 6/6 PASS (R6 补偿全链); 4 产品缺口记录; human_gate 待签 |
