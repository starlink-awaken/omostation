---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 5.1.B — KOS EntityType 扩展

> 类型: P9 → P8 Task Prompt | 状态: backlog | 预估: 90min
> Phase: 5 → 5.1.B | 负责人: prometheus | 日期: Day 2

## 一、目标

在KOS的实体系统中增加8个新EntityType和Value Stack字段，为L4/L3/X3的数据存储提供基础。

## 二、范围

### 修改文件

| 文件 | 操作 |
|------|------|
| `kos/ontology/_types.py` | 增加8个EntityType + ENTITY_ID_PREFIXES |
| `kos/ontology/_types.py` | Entity dataclass增加Value Stack字段 |
| `kos/ontology/engine.py` | ENTITY_REF_RE模式扩展支持新类型 |

## 三、验收标准

```
☐ python3 -c "from kos.ontology._types import EntityType; print(list(EntityType))" 显示15个类型
☐ python3 -c "from kos.ontology._types import ENTITY_ID_PREFIXES; print(len(ENTITY_ID_PREFIXES))" 显示15
☐ kos ontology rebuild 不报错
☐ Kos索引器可提取新类型实体
```

## 四、依赖

- **前置**: Wave 5.1.A已完成
- **确认命令**: `cat eidos/schemas/registry.json | grep identity-role`

## 五、执行步骤

见09-架构Review与机制设计.md Day 2部分。

## 六、输出

| 文件 | 操作 |
|------|------|
| `kos/ontology/_types.py` | 修改 |
| `kos/ontology/engine.py` | 修改(模式扩展) |
| `.omo/TASK_POOL.md` | T066-T068 → done |
| `.omo/STATE.md` | 更新Wave 5.1.B进度 |
