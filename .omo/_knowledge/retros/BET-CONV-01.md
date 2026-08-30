---
title: "BET-CONV-01 retro — Phase 1 门禁建立"
status: active
bet: BET-CONV-01
date: 2026-08-30
last-reviewed: 2026-08-30
lifecycle: current
owner: governance-team
type: retro
---

# BET-CONV-01 复盘

## 北极星

bin/ 脚本发散失控（728 文件、无分层、无注册、无绑定检查），导致治理成本指数上升。本 BET 建立四重硬门禁，从制度上阻止进一步发散。

## 做了什么

- **4 个新检查脚本创建**:
  - `bin/gac/check-script-sfop-declaration.py`: 检查 SFOP_SLOT/DAO_LAYER 声明，519 脚本全通过
  - `bin/gac/check-bin-lifecycle.py`: 检查 bin/_registry/ 注册，全通过
  - `bin/gac/check-bos-uri-binding.py`: 检查 BOS URI 双向绑定，39 个未注册（warn mode）
  - `bin/ssot/state-manager.py`: 检查 .omo/state/ 文件规范，2 个需迁移（warn mode）
- **2 个标准文档创建**:
  - `docs/standards/bin-script-lifecycle.md`
  - `.omo/standards/state-management-spec.md`
- **gac-local-gate.py 集成**: 4 个新 check 已加入 GATES_LIST
- **spec 创建**: `docs/superpowers/specs/2026-08-30-conv-01-script-convergence-gates.md`

## 没做什么

- 未合并任何现有脚本（只建立规则）
- 未清理任何历史文件（只建立规则）
- 未修改 CI pipeline 结构（只增加 check）

## 证据

- gac-validate: 0 error, 0 warning
- gac-local-gate: 4 个新 check 全部 PASS
- 519 个 bin/ 脚本已声明 SFOP_SLOT/DAO_LAYER
- 519 个 bin/ 脚本已在 bin/_registry/ 注册

## 下一步

- BET-CONV-02: Wave 1 债务偿还（health/scorecard + governance 脚本合并）
- BET-CONV-03: Wave 2 债务偿还（orchestrator/unified/connector 合并 + scene 单一实现）
- 迁移 2 个 state 文件至新规范
- 将 BOS URI 和 state manager check 从 warn mode 转为 fail mode
