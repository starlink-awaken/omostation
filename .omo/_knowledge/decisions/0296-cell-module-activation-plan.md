---
id: ADR-0296
status: active
lifecycle: spec
owner: governance-agent
last-reviewed: 2026-09-01
type: ssot
---

# Cell 模块激活方案 (chain_4 修复)

> SSOT: .omo/_knowledge/decisions/0296-cell-module-activation-plan.md
> Created: 2026-09-01
> Status: active

## 背景

chain_4 (cell→everything) 断链: 10 个 Cell 模块 dormant。

## Cell 模块清单

| 模块 | 状态 | 入口 | 依赖 |
|------|------|------|------|
| cell plan | dormant | cockpit cell plan | omo resident |
| cell execute | dormant | cockpit cell execute | omo resident |
| cell verify | dormant | cockpit cell verify | omo resident |
| cell govern | dormant | cockpit cell govern | omo resident |
| cell pdp | dormant | cockpit cell pdp | omo resident |
| cell pep | dormant | cockpit cell pep | omo resident |
| cell memory | dormant | cockpit cell memory | omo resident |
| cell replay | dormant | cockpit cell replay | omo resident |
| cell dashboard | active | cockpit cell_dashboard | cockpit |
| cell effect receipt | active | bin/ssot/agent-cell-effect-receipt-canary.py | omo |

## 激活方案

### Phase 1: 状态检查 (已完成)
- 添加 Cell 状态检查到 harness-compliance-check.py
- 添加 Cell 状态到 OMO system.yaml

### Phase 2: 模块激活 (待执行)
1. 初始化 omo submodule
2. 检查每个 Cell 模块的依赖
3. 逐个激活或归档

### Phase 3: 集成验证 (待执行)
1. 运行 `cockpit cell plan` 验证
2. 运行 `cockpit cell execute` 验证
3. 运行 `cockpit cell verify` 验证

## 验证标准

- [ ] Cell 模块激活率 > 50%
- [ ] `cockpit cell plan` 可执行
- [ ] `cockpit cell execute` 可执行
- [ ] Cell 状态同步到 OMO system.yaml
