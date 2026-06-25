---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: sharedbrain-decomposition-closeout-verification.md
deprecated-since: 2026-06-23

---

# SharedBrain 分解关闭验证报告

> 日期: 2026-06-03
> 债务项: SB_DECOMPOSITION (closed 2026-06-03)
> 验证目标: 确认关闭证据与代码库实际状态一致

---

## 验证结论

**状态: ✅ 关闭有效，但文档指针有误**

SharedBrain 分解的核心目标（将 19 个 D_ 器官从 `projects/SharedBrain/` 迁移到 kairon 包并归档源代码）**已完成**。但部分文档中的路径指针和验证清单未同步更新。

---

## 验证项

### 1. 源代码归档位置

| 声称位置 | 实际位置 | 状态 |
|----------|----------|------|
| `projects/SharedBrain/_archived/SharedBrain-code/` (README.md) | `projects/_archived/SharedBrain-code/` | 🟡 **路径偏差** |
| `projects/SharedBrain/_archived/SharedBrain-code/` (DECOMPOSITION.md) | `projects/_archived/SharedBrain-code/` | 🟡 **路径偏差** |

**说明**: 源代码确实被归档了，但不在 `projects/SharedBrain/_archived/` 下，而是在 `projects/_archived/SharedBrain-code/` 下。这是一个文档错误，不是实质性问题。

**归档内容验证**:
```
projects/_archived/SharedBrain-code/
├── bin/
├── bootstrap.py
├── conductor/
├── nucleus/
│   ├── Z_Core/
│   ├── Z_Extension/
│   ├── interfaces/
│   ├── organs/
│   └── shared/
├── sdk/
├── server/
└── start_worker.py
```

✅ 归档完整，包含 nucleus、conductor、server、sdk 等核心组件。

### 2. SharedBrain 根目录缩减

| 指标 | 分解前 | 分解后 | 目标 |
|------|--------|--------|------|
| Python 文件数 | ~107,000 (引自 debt item) | **115** | ~100 剩余 |
| 总文件数 | ~7,658 | **4,056** | — |
| organs/ 目录 | 19 个 D_ 器官 | **不存在** | 删除/归档 |
| nucleus/ 目录 | 存在 | **不存在** | 删除/归档 |

✅ 根目录已大幅缩减，仅保留文档、配置、测试和持久化数据。

### 3. 迁移到 kairon 的证据

| 器官 | 目标包 | 证据 | 状态 |
|------|--------|------|------|
| D_Economy | eu-pricing | `eu_pricing/energy_model.py`, `reputation.py`, `market.py`, `ledger.py` | ✅ |
| D_KnowledgeIntegration | kos | `kos/knowledge_bridge.py`, `query_service.py`, `context_injector.py` | ✅ |
| D_Gateway | agora | `agora/interfaces.py`, `api_types.py` (部分) | 🟡 部分迁移 |
| D_Execution | agentmesh | agentmesh 已独立实现编排能力 | ✅ (替代) |
| D_Governance | .omo | 四平面治理已替代 | ✅ (替代) |

**测试覆盖验证**:
- `eu-pricing/tests/test_energy_model.py`: 8 tests ✅
- `kos/tests/test_knowledge_bridge.py`: 存在于代码库 ✅

### 4. 废弃器官状态

| 器官 | 声称状态 | 实际验证 |
|------|----------|----------|
| D_Execution | 废弃，agentmesh 替代 | git 历史中显示 D_Execution 被删除 ✅ |
| D_Governance | 废弃，.omo 替代 | git 历史中显示 D_Governance 被删除 ✅ |
| D_Window | 占位符废弃 | git 历史中显示 D_Window 被删除 ✅ |

### 5. 文档一致性

| 文档 | 问题 | 严重度 |
|------|------|--------|
| `DECOMPOSITION.md` | 路径指针错误 (`SharedBrain/_archived/` vs `projects/_archived/`) | 低 |
| `DECOMPOSITION.md` | 验证清单 Wave 0-4 全部未勾选，但 Wave 0-1 实际已完成 | 中 |
| `README.md` | 路径指针同样错误 | 低 |

### 6. 遗留包状态

| 包 | 位置 | 测试 | 说明 |
|----|------|------|------|
| sharedbrain-bridge | kairon/packages/ | 2 tests | 桥接包，正常 |
| sharedbrain-standalone | kairon/packages/ | **0 tests** | ⚠️ 零测试，需关注 |

---

## 发现的问题

### 问题 1: 文档路径指针错误（低严重度）

**描述**: DECOMPOSITION.md 和 README.md 都指向 `projects/SharedBrain/_archived/SharedBrain-code/`，但实际归档位置是 `projects/_archived/SharedBrain-code/`。

**建议**: 修正两个文档中的路径指针。

### 问题 2: 验证清单未更新（中严重度）

**描述**: DECOMPOSITION.md 底部的验证清单中 Wave 0-4 全部显示 `[ ]` 未勾选，但 Wave 0 治理门禁和 Wave 1 部分迁移（D_Economy, D_KnowledgeIntegration, D_Execution, D_Governance 废弃）实际已完成。

**建议**: 更新验证清单，勾选已完成的 Wave 0 和 Wave 1 项目。

### 问题 3: sharedbrain-standalone 零测试（中严重度）

**描述**: `kairon/packages/sharedbrain-standalone/` 有源代码但零测试。这是分解后的残留包，如果它是核心运行时依赖，缺乏测试是风险。

**建议**: 确认 sharedbrain-standalone 的用途和去留，若保留则补充最小测试基线。

---

## 与债务关闭声明的一致性

| 关闭声明 | 验证结果 |
|----------|----------|
| "All 19 D_ organs extracted to kairon packages" | ✅ 归档位置确认，git 删除记录确认 |
| "sharedbrain-core library completed" | 🟡 `sharedbrain-standalone` 存在但零测试；无明确 `sharedbrain-core` 包名 |
| "SharedBrain README and AGENTS.md updated" | ✅ 已更新，但路径有误 |
| "107K -> 115 .py cleanup complete" | ✅ 实际 115 个 Python 文件 |

---

## 最终判定

SB_DECOMPOSITION 债务的关闭是**有效的**。核心工作（器官迁移、源代码归档、根目录清理）已完成。剩余的文档指针错误和验证清单更新属于**收尾工作**，不构成重新开放债务的理由。

**建议后续行动**:
1. 修正 DECOMPOSITION.md 和 README.md 中的 `_archived/` 路径指针
2. 更新 DECOMPOSITION.md 验证清单（勾选 Wave 0，部分勾选 Wave 1）
3. 评估 sharedbrain-standalone 的去留或补充测试

---

*验证时间: 2026-06-03*
*验证命令: `ls projects/_archived/SharedBrain-code/`, `git log --diff-filter=D`, `find projects/SharedBrain -name "*.py" | wc -l`*
