# omo CLI 工作计划

> 创建时间: 2026-07-07
> 最后更新: 2026-07-07

## Phase 1-4: Tier 1-4 迁移 ✅ 已完成

| Tier | 工具 | 新命令 | PR |
|------|------|--------|-----|
| 1 | bin/gac/omo-health.py | `omo health dashboard` | #144 |
| 2 | bin/gac/omo-state-projection-guard.py | `omo lint projection-guard` | #144 |
| 2 | bin/gac/omo-runtime-stamp-policy.py | `omo lint stamp-policy` | #144 |
| 3 | bin/omo-manage | `omo manage` | #144 |
| 3 | bin/omo-validate | `omo validate` | #144 |
| 4 | scripts/omo/cards_x3_metrics.py | `omo audit cards` | #152 |
| 4 | scripts/omo/vault_x1_audit.py | `omo audit vault` | #152 |
| 4 | scripts/omo/x2_freshness_audit.py | `omo audit freshness` | #152 |

## Phase 5: 命名空间优化 + 退役 + 文档 ✅ 已完成

| 方向 | 内容 | 状态 |
|------|------|------|
| A | `omo doctor` + `omo inspect` 统一入口 | ✅ #152 |
| B | scripts/omo/ 标记 deprecated | ✅ scripts 子模块 |
| C | `omo docs` 文档自动生成 | ✅ #152 |
| 文档 | README + CHANGELOG + CLI-REFERENCE | ✅ #153 |

## Phase 6: 下一阶段工作 (待规划)

### 方向 D: omo CLI 测试覆盖扩展
- 为 `omo doctor`、`omo inspect` 添加单元测试
- 为 `omo manage`、`omo validate` 添加单元测试
- 为 `omo lint` 子命令添加单元测试

### 方向 E: omo CLI 集成测试
- 端到端测试: `omo doctor` → `omo inspect` → `omo audit`
- 错误场景测试: 缺失文件、损坏 YAML、stale 状态

### 方向 F: omo CLI 性能优化
- 并行执行独立检查项
- 缓存机制: 避免重复读取相同文件

### 方向 G: omo CLI 扩展
- `omo report` — 生成综合报告 (doctor + inspect + audit)
- `omo watch` — 实时监控模式 (定期运行 doctor)

## 当前命令层级

```
omo
├── doctor                    # 统一健康检查
├── inspect                   # 统一检查
├── docs                      # CLI 文档自动生成
├── health {check,dashboard}
├── lint {schemas,projection-guard,stamp-policy,...}
├── manage {status,health,tasks}
├── validate {completeness,references,state,all}
├── audit {cards,vault,freshness}
├── worker {task,worker}
└── task / debt / state / ...
```

## 测试状态

- 748 passed, 274 skipped
- 无回归
