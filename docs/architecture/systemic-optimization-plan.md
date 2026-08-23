# 系统性架构优化总体方案

> 最后更新: 2026-08-22
> 状态: Draft
> 负责人: governance-team

## 1. 优化目标

1. **体系健康**：CI 全绿、子模块指针一致、无预存在失败项
2. **可持续迭代**：统一测试/Ruff/CI 基线，减少配置漂移
3. **治理约束**：建立 ruff/lint/test/CI/MOF 的硬门禁与自动修复
4. **全面推进**：分阶段落地，每阶段可独立验证

## 2. 现状诊断

### 2.1 测试体系
- 根仓 `tests/` 118 文件，子项目 751+ 文件
- **缺口**：`cockpit-ui`、`observability` 无测试；`family-hub` 仅 3 个测试文件
- **超时**：`agora`、`omo`、`runtime` 测试执行超时

### 2.2 Ruff 配置
- 基础 select 已统一：`["E", "F", "W", "I", "N", "UP", "S", "PLE", "RUF100"]`
- **漂移**：`runtime` 忽略 27 条规则；`agora` 忽略 BLE001（277 处）
- **缺失**：`cockpit-ui`、`observability` 无 ruff 配置；`knowledge` 无 `[tool.ruff]`

### 2.3 CI 门禁
- `service-config-drift`：已修复
- `gac-validate`：`script_baseline` 已更新为 421
- `mof-schema-validate`：已修复
- `governance-semantic-gate`：有预存在 WARN

### 2.4 MOF 约束
- M1 实例 status 已规范化
- `MODEL-PRICING-DEFAULT` 已补全 required 字段
- `ecos-constraint-compiler.py` F541 已修复

## 3. 优化策略

### 3.1 测试体系重构
| 优先级 | 行动 | 预期结果 |
|--------|------|----------|
| P0 | 为 `cockpit-ui`、`observability` 建立基础测试框架 | 有测试入口 |
| P1 | 提升 `family-hub`、`model-driven` 测试覆盖 | 达到 20+ 测试 |
| P1 | 统一 pytest 配置（`testpaths`、`addopts`、`asyncio_mode`） | 配置一致性 |
| P2 | 根仓 `tests/` 按 domain 分层 | 可维护性 |

### 3.2 Ruff 配置治理
| 优先级 | 行动 | 预期结果 |
|--------|------|----------|
| P0 | 统一基础 select 规则为项目标准 | 所有子项目一致 |
| P1 | 治理 `runtime` 过度宽松配置（27 → 5 条 ignore） | 有效 lint |
| P1 | 治理 `agora` BLE001（分批重构） | 技术债务减少 |
| P2 | 为 `cockpit-ui`、`observability`、`knowledge` 补 ruff 配置 | 覆盖完整 |

### 3.3 CI 门禁强化
| 优先级 | 行动 | 预期结果 |
|--------|------|----------|
| P0 | 消除所有预存在失败项 | CI 全绿 |
| P1 | 建立 CI 健康度监控 | 可观测 |
| P2 | 实施 ruff 配置漂移检测 | 自动预警 |

### 3.4 MOF 约束体系
| 优先级 | 行动 | 预期结果 |
|--------|------|----------|
| P0 | 完成 M1 实例 status 规范化 | 100% 合规 |
| P1 | 建立 MOF schema 自动校验 CI | 门禁覆盖 |
| P2 | 实施 MOF drift 自动检测 | 持续合规 |

## 4. 实施路径

### Phase 1：基线统一（1-2 天）
- [x] 修复 `service-config-drift`
- [x] 更新 `script_baseline` 420 → 421
- [x] 修复 ecos `mof-scan.py` F541
- [x] 修复 `ecos-constraint-compiler.py` F541
- [ ] 统一 ruff select 基线
- [ ] 治理 `runtime` 过度宽松配置

### Phase 2：测试覆盖（3-5 天）
- [ ] 为 `cockpit-ui` 建立测试框架
- [ ] 为 `observability` 建立测试框架
- [ ] 提升 `family-hub` 测试覆盖
- [ ] 统一 pytest 配置

### Phase 3：CI/MOF 强化（2-3 天）
- [ ] 消除所有预存在 CI 失败项
- [ ] 建立 CI 健康度监控
- [ ] 实施 ruff 配置漂移检测
- [ ] MOF schema 自动校验 CI

### Phase 4：治理固化（1-2 天）
- [ ] 建立可持续迭代机制
- [ ] 文档化治理规范
- [ ] 建立定期审计周期

## 5. 成功标准

1. **CI 健康**：`make ci-local-fast` 全绿，无预存在失败项
2. **测试覆盖**：所有子项目至少有 10 个测试文件
3. **配置一致**：ruff select 规则统一，ignore 差异 < 5 条
4. **MOF 合规**：M1 实例 100% status 合规
5. **可持续**：建立自动化审计与修复机制

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 大规模 ruff 配置变更导致 CI 失败 | 分阶段、分批、有回滚方案 |
| 子项目测试超时 | 增加 timeout、标记 skip |
| MOF 变更影响运行时 | 先在 staging 验证，再合入 main |
