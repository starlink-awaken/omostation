# OMO-Debt 收敛设计

> **状态**: 起草中 · **日期**: 2026-06-05  
> **目标**: 消除 omo-debt 的双轨架构，统一为单一收敛数据模型

## 背景

OMO Debt 子系统经过多轮迭代，形成了两条并行的数据路径：

| 路径 | 入口 | 数据存储 | 特征 |
|------|------|---------|------|
| **Registry** | `omo_debt_registry.py` | `.omo/_truth/registry/debt*.yaml` | 指针式，引用 governance surfaces |
| **Ledger** | `omo_debt_*.py` (CLI) | `.omo/debt/` | 分离式运行记录，含 dispatch/evidence/history |

两套路径都对同一概念建模（债务项、所有者、门控级别、状态转移），但：
1. **数据模型不同** — Registry 用指针，Ledger 用快照
2. **状态机不同** — Registry 分两轮（seed→active），Ledger 有 dispatch→run→review→approve 生命周期
3. **查询路径不同** — 上层 consumer 需要同时读两个来源才能获得完整视图

## 收敛决策树

```
目前有双轨 debt 模型，如何收敛？

├── 方案 A: 合并 → 保留一个统一数据模型
│   ├── A1: Registry 主导（Ledger 迁移到 Registry 模型）
│   ├── A2: Ledger 主导（Registry 迁移到 Ledger 模型）
│   └── A3: 新统一模型（两个都迁到新模型）
│
├── 方案 B: 保持双轨 + API 层封装
│   └── 上层通过统一查询接口读取两套数据
│
└── 方案 C: 保持双轨 + 增量同步
    └── Registry 变更时自动同步到 Ledger
```

### 推荐: A1 (Registry 主导)

**理由**:
- Registry 架构更接近 OMO 的 SSOT 设计哲学（指针式、引用式）
- Ledger 的 dispatch→evidence→history 流可以转为 Registry 的元数据标注
- 无需引入新数据模型，减少迁移风险

**迁移步骤**:
1. Registry 扩展 `gate_level`、`status`、`owner` 字段以覆盖 Ledger 语义
2. Ledger 的 dispatch/evidence 记录转为 Registry 的 timeline 注解
3. Ledger 的 reporting/history 转为 Registry 的 snapshot 生成器
4. CLI 命令适配 Registry 模型
5. 废弃 Ledger 文件路径 → 保留只读兼容层 6 个月

## 当前进度

- [ ] 方案选定（决策已做: A1）
- [ ] Registry 模型扩展设计
- [ ] Ledger→Registry 映射矩阵
- [ ] 迁移计划与分阶段里程碑
- [ ] 兼容层设计
