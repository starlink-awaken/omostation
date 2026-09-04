---
id: ADR-0407
title: ci-local-fast 真实退出码与 Ruff 有界债务门
status: ACCEPTED
lifecycle: spec
owner: governance-team
last_updated: 2026-08-11
related:
  - ADR-0379
  - ADR-0388
  - ADR-0390
  - BET-Y1Q2-T6-03
---

# ADR-0407: ci-local-fast 真实退出码与 Ruff 有界债务门

## 背景

`Makefile::ci-local-fast` 在默认 `/bin/sh` 中使用
`producer | sed || CI_LOCAL_FAIL=1`。POSIX shell 返回管道最后一个命令的
状态，因此 GaC、目录卫生、Ruff、YAML 的 producer 即使失败，只要 `sed`
成功，目标仍会输出“全部通过”。实测完整 Ruff 面存在 997 条历史诊断，
直接切换全局 `pipefail` 又会把所有 push 锁死。

这使 BET-Y1Q2-T6-03 的 `make ci-local-fast exit 0` 验收证据失真，并违反
G-1 的 fail-closed、evidence-first 约束。

## 决策

1. `Makefile` 只委托 `bin/gac/ci-local-fast.py`；不修改全局 shell。
2. runner 直接合并 stdout/stderr、添加前缀并保留每个 producer 的真实退出码。
3. GaC、目录卫生、Ruff 回归门、HTML 实体检查和 YAML 校验均为 blocking；
   任一失败则最终退出 1，且禁止输出绿色总结。
4. Ruff 分为两层：
   - CI 级规则使用 `.omo/_truth/registry/ruff-diagnostics-baseline.yaml`，
     当前 26 条已审阅诊断作为债务；任何 path/code/message 桶的净新增硬阻断。
   - 原 OMO + scripts 全量面保留为显式 `DEBT/ADVISORY` 报告，当前 997 条，
     不计作 PASS，也不在本修复中强行清零。
5. baseline 只允许收缩，不允许扩容或换桶；runner 在代码中冻结六个已批准
   bucket 的逐项最大值及 hard cap=26，代码修复后移除相应条目。
6. `.githooks/pre-push` 继续以 blocking 方式调用 `make ci-local-fast`。

## 放弃方案

- 全局 `SHELL := /bin/bash` 或全局 `pipefail`：影响所有 recipe，且立即被
  997 条存量债锁死。
- `ruff --exit-zero` / `|| true`：继续制造假绿。
- 只按错误总数放行：修掉一个旧错误即可掩盖一个新错误。
- 将 997 条诊断全部加入 blocking baseline：体量大且把风格债与 CI 级
  回归混为一谈。

## 验收合同

- 四类 producer 失败注入均返回非零，且无绿色总结。
- 已知 Ruff 债务可通过；path/code/message bucket 净新增返回非零。
- 全量 Ruff 债务必须显示 `DEBT/ADVISORY`，不得显示为通过。
- 真实 `make ci-local-fast` 只有 blocking checks 全绿时才退出 0。

## 影响与后续

本 ADR 恢复本地 pre-push 证据可信度，不声称 997 条 Ruff 债务已经解决。
后续修复 OMO 诊断时应同步收缩 26 条 blocking baseline；全量债务清理另走
独立质量 sweep，不得塞入 G-1 控制面修复。
