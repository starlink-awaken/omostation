# Documents 归档族冻结回执 (rollback receipt)

> BET-Y1Q4-T10-123 | 2026-09-07 | 回滚方式: 只读声明回退，不动源文件

## 回滚程序

1. 恢复 registry 中 6 个家族 status 为 pending/in_progress，删除 evidence 块。
2. 删除 freeze-summary 与 runtime 索引。
3. 源文件从未移动/删除（274,102 文件 / ~58.8GB 原位只读），无需数据恢复。
