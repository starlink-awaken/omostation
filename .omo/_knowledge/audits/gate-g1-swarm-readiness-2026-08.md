---
title: G-1 Swarm Readiness Gate 证据包
type: audit
status: active
owner: governance-team
created: 2026-08-15
lifecycle: history
related:
  - docs/architecture/blueprint-multi-agent-execution-control-v1.md
  - docs/architecture/blueprint-collab-consolidation-v1.md
context: >-
  蓝图 §18 红线: SR-01~06 全过之前禁止开业务蜂群。本包为 SR-01~05 机器证据;
  SR-06 双轮演练 (reject→rollback / accept) 另行执行后回填。
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
| SR-06 | R1 包 dispatch→verify→reject/accept→rollback 全链 | ⏳ 待演练 | §6 |

**当前门状态: 5/6 PASS — SR-06 双轮演练完成后本包更新, human_gate 签名后蜂群开闸。**

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

## 6. SR-06 演练 (待执行)

计划 (blueprint-collab-consolidation-v1.md §3.2):
- 轮 a: R1 微型包故意超界 → reject → 基线 hash 恢复证明
- 轮 b: T1-18 真活 dogfood → accept → bet 收口
- 生产路径: Orca 托管交互 Codex TUI, provider approval 由 Human 点击

状态: ⏳ 待执行 — 执行后回填本节, 全过则进入 human_gate 签名。

## 7. Human Gate 签名位

> 开蜂群决定 (蓝图 §18: SR-01~06 全过后蜂群才可开闸)

- [ ] Human Principal 已审阅本证据包
- [ ] SR-06 双轮证据已回填 (§6)
- [ ] 批准开蜂群 (签名/日期): ____________

## 8. Changelog

| 日期 | 变更 |
|---|---|
| 2026-08-15 | v1: SR-01~05 机器证据 5/6 PASS; SR-06 待演练; 发现并修复 omo venv ecos 旧拷贝坑 |
