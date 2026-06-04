# debt/ — 技术债务治理

> 事实面债务系统。回答"系统的技术健康状况如何？有哪些债务需要管理？"
>
> 参考: [DOC-ARCH.md](../DOC-ARCH.md) §2

---

## 债务系统组件

| 组件 | 位置 | 说明 |
|------|------|------|
| **债务注册表** | [registry.yaml](registry.yaml) | 债务项生命周期注册 |
| **债务项** | [items/](items/) | 单个债务 YAML 定义 |
| **仪表盘** | [dashboard/](dashboard/) | 当前债务健康度聚合 |
| **审查队列** | [review-queue/](review-queue/) | 待审查债务项 |
| **行动包** | [action-packet/](action-packet/) | 债务修复行动提案 |
| **分派** | [dispatch/](dispatch/) | 债务任务分派记录 |
| **报告** | [reporting/](reporting/) | 债务趋势与差异报告 |
| **所有者路由** | [owner-routing/](owner-routing/) | 债务责任人映射 |
| **活动** | [campaign/](campaign/) | 债务清理活动记录 |
| **审查** | [reviews/](reviews/) | 债务审查结果 |
| **工具** | [tooling/](tooling/) | omo-debt Python 工具包（src/ + tests/） |

## 债务项状态

| 状态 | 说明 |
|------|------|
| `open` | 活跃债务，需要处理 |
| `watching` | 监控中，暂不处理 |
| `closed` | 已解决 |

## 残余风险 (R1-R6)

当前监控中的残余风险：

| ID | 名称 | 状态 |
|----|------|------|
| R1 | P0 产品层缺失 | watching |
| R2 | Agora 服务未运行 | watching |
| R3 | LAYER-INDEX 漂移 | watching |
| R4 | 运行时适配器债务 | watching |
| R5 | metaos 路径插入残留 | watching |
| R6 | sharedbrain-standalone 零测试 | watching |

---

*维护: 2026-06-03 · 债务状态以 registry.yaml 为准*
