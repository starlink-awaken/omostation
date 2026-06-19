# Truth Plane — 事实面

> 维护任务、标准、注册表等唯一真相源（SSOT）。
> 不复制总结性叙述，不存放运行日志。

## 核心 SSOT

| 文件/目录 | 职责 |
|-----------|------|
| `tasks/registry/INDEX.md` | 任务注册表总索引 |
| `tasks/active/` | 活跃任务 YAML |
| `tasks/planned/` | 计划任务 YAML |
| `tasks/done/` | 已完成任务归档 |
| `standards/` | 标准与规范 |
| `registry/` | 注册表（workers, organs 等） |
| `registry/omo-governance-surfaces.yaml` | `.omo` 顶层资产分类 + `omo/c2g` 联动治理注册表 |
| `registry/task-policies.yaml` | 特殊任务红线的机器可读注册表（与 `omo_task_policy.py` 对齐） |
| `registry/mutation-surfaces.yaml` | OMO 人类/桥接 mutation surfaces 的机器可读清单（brokered vs direct） |
| `goals/` | 目标事实面镜像 / 索引；运行时写入仍以 `../goals/current.yaml` 为准 |
| `x1-governance-policies.yaml` | X1 边界、审计、写入 gate 的权威策略 |
| `x2-freshness-rules.yaml` | X2 保鲜与过期处理规则 |
| `x3-value-stack.yaml` | X3 价值/成本分层归因 |
| `x4-consistency-rules.yaml` | X4 跨层一致性规则 |
| `_truth/04-omo-architecture-and-governance.md` | OMO 双核联邦分形架构与治理总纲 |
| `_truth/05-omo-v4-evolutionary-architecture.md` | OMO v4.0 超越四平面与动态演化机制 |
| `../standards/omo-governance-surfaces.md` | `.omo` 状态面、`projects/omo`、`projects/c2g` 三层治理标准 |
| `_truth/INVENTORY.md` | 项目资产索引（路由文档，不是运行时快照） |
| `_truth/task-center/proposals/` | 提案注册表（元数据） |

## 写入规则

- 任务、标准、注册表优先字段化（YAML / schema）
- 自由文本只用于不可结构化的语义说明
- 事实面必须被 control 面引用，被 delivery 面验证
- `AGENTS.md`、README、计划文档只能引用这里的 X1-X4 文件，不得复制规则正文成为第二事实源
