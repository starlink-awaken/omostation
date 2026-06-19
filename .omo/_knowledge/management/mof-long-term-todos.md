# MOF 长期 TODO — 待后续迭代

> Created: 2026-06-20 | Status: TODO

## 1. 智能重构建议 (mof-analyze --quality)

分析代码质量，自动建议重构方向：
- agora: 7 个 bos_*.py 模块碎片化，建议合并为 3 个
- gbrain: operations.ts 3841 行，建议拆分为 19 个域文件
- omo: 125 个扁平文件，建议按子系统分包
- cockpit: dashboard_server.py 1028 行，建议拆分

**依赖**: 需要深度理解每个模块的职责边界
**ROI**: 高 (自动发现重构机会)

## 2. 测试覆盖分析 (mof-analyze --testing)

分析测试覆盖情况，自动发现测试盲区：
- gbrain: 67 个 MCP 工具，仅 3 个有测试
- c2g: 17 个模块，仅 3 个测试文件
- family-hub: 双栈 (TS + Python)，测试不完整

**依赖**: 需要解析每个项目的测试文件
**ROI**: 高 (自动发现测试盲区)

## 3. 成本优化建议 (mof-analyze --cost)

基于价值推理优化成本结构：
- 分析每个组件的 infrastructure/operational/development 成本
- 识别高成本低价值的组件
- 建议优化方向

**依赖**: 需要准确的成本数据
**ROI**: 中 (成本优化)

## 4. 系统健康仪表盘

从模型聚合生成实时仪表盘：
- 哪些组件在线？(runtime_status)
- 哪些服务健康？(health checks)
- 哪些工具有问题？(validation failures)
- 哪些域有风险？(value_metrics)

**依赖**: 需要实时数据源
**ROI**: 高 (可视化监控)

## 5. 智能决策支持

当团队讨论"要不要做 X"时，自动回答：
- 做 X 会影响什么？(impact analysis)
- 做 X 的成本是多少？(cost model)
- 做 X 的收益是什么？(value metrics)
- 做 X 的风险是什么？(risk assessment)

**依赖**: 需要完整的价值/成本/风险数据
**ROI**: 高 (决策支持)

## 6. 跨项目依赖图自动生成

从 relations.depends_on 自动生成依赖图：
- 可视化展示项目间依赖关系
- 识别循环依赖
- 识别关键路径

**依赖**: 需要完整的 depends_on 数据
**ROI**: 中 (架构可视化)

## 7. MOF 模型版本管理

对 MOF 模型进行版本管理：
- 每次变更记录版本
- 支持 diff 对比
- 支持 rollback

**依赖**: 需要 git 或其他版本控制
**ROI**: 中 (变更追踪)

## 8. MOF 模型导入/导出

支持从其他格式导入/导出 MOF 模型：
- 从 CSV/Excel 导入
- 导出为 JSON/XML
- 与 ArchiMate/UML 集成

**依赖**: 需要格式转换逻辑
**ROI**: 低 (互操作性)
