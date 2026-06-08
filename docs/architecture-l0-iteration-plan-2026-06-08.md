# L0 迭代计划 · 与 L4 Kernel 模型对齐

**2026-06-08 · 9 项操作 · 3 个文件域**

---

## 审计发现

### 域对齐 (3 项)
| # | 问题 | 操作 |
|---|------|------|
| 1 | Registry 缺 `ecos-workbench` + `l4-kernel` 域 | 添加到 _BUILTIN_DOMAINS (19→21) |
| 2 | `toolbox` vs `toolbox-tools` ID 不一致 | 统一为 `toolbox` |
| 3 | M2 domain stateMachine 与 lifecycle 状态机不同 | 对齐两套状态机 |

### M2 类型定义 (2 项)
| # | 问题 | 操作 |
|---|------|------|
| 4 | 无 DomainLifecycle 类型 | 新增 m2/domain_lifecycle.yaml |
| 5 | 无 Plugin 类型 | 新增 m2/plugin.yaml |

### M1 节点 (1 项)
| # | 问题 | 操作 |
|---|------|------|
| 6 | 缺 11 个 M1 节点 (3 workflow + 3 mechanism + 4 spec + 1 process) | 创建对应 M1 节点 |

### L0-registry (2 项)
| # | 问题 | 操作 |
|---|------|------|
| 7 | L4 Gateway/Domains 条目过时 (12域→19域) | 更新描述 |
| 8 | 缺 L4 Kernel MCP 条目 | 新增协议注册 |

---

## 实施

### 优先级排序

**高优先级 (P0)**: #1 #4 #7 #8 — 域对齐 + 新类型 + L0-registry
**中优先级 (P1)**: #2 #5 #6 — ID 统一 + 新类型 + M1 节点
**低优先级 (P2)**: #3 — 状态机对齐 (需要两方协商)
