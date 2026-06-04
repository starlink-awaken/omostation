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
| `_truth/INVENTORY.md` | 资产清单 |
| `_truth/task-center/proposals/` | 提案注册表（元数据） |

## 写入规则

- 任务、标准、注册表优先字段化（YAML / schema）
- 自由文本只用于不可结构化的语义说明
- 事实面必须被 control 面引用，被 delivery 面验证
