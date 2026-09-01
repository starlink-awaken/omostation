# CLAUDE.md — Session Startup

## Harness 快速参考

### 常用命令

```bash
# 运行完整 DAG (8 阶段)
bin/harness run --bet <BET> --profile <profile> --objective "..."

# 并行校验 (带缓存)
bin/harness verify --parallel --cache

# 7 探针 + Event Bus 发射
bin/harness probe --emit

# Cockpit 入口 (12 子命令)
cockpit harness compliance|mof|omo|enforce|full|status|run|verify|trace|explain|retro|ledger
```

### 约束检查

```bash
# 架构合规 (7 项标准文件)
python3 bin/gac/architecture-check.py

# GaC 规则验证
python3 bin/gac/gac-validate.py

# 自进化循环 (5 数据源)
python3 bin/gac/self-evolution-loop.py --sync-omo

# 全量合规检查
python3 bin/gac/harness-compliance-check.py --report
```

### MCP 工具 (5 个)

| 工具 | 功能 |
|------|------|
| harness_compliance_check | 12 章节合规检查 |
| harness_status | 合规状态总览 |
| harness_run | 8 阶段 DAG 运行 |
| harness_verify | 并行校验 |
| harness_probe | 7 探针 + Event Bus |

### BOS URI (9 个)

| URI | 功能 |
|-----|------|
| bos://harness/compliance/check | 12 章节合规检查 |
| bos://harness/mof/bridge | MOF 约束联动 |
| bos://harness/omo/bridge | OMO 状态同步 |
| bos://harness/constraint/enforce | 统一约束驱动 |
| bos://harness/architecture/perceive | 架构感知预编辑 |
| bos://harness/compliance/full | 全量合规检查 |
| bos://harness/run | 8 阶段 DAG 运行 |
| bos://harness/verify | 并行校验 |
| bos://harness/probe | 7 探针 + Event Bus |

### 强制约束

- Hook 层: 6 个 exit 1 拦截点
- GaC 规则: 32 个强制/高优先级规则
- Harness 策略: 19 个强制约束
- Agent 约束: 16 个 enforcement 点

### SSOT 文档

- 策略: `.omo/_truth/registry/harness-policy.yaml`
- 感知注册: `.omo/_truth/registry/architecture-perception-registry.yaml`
- 合规预算: `.omo/standards/anti-corrosion-budget.yaml`
- 维度系统: `.omo/standards/dimension-system.yaml`
- Agent 约束: `.omo/standards/mof-agent-constraints.yaml`
