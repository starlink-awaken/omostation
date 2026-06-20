# MOF 长期 TODO — 待后续迭代

> Created: 2026-06-20 | Updated: 2026-06-20

## ✅ 已完成

### 1. 智能重构建议 (mof-analyze --quality) ✅
- 已实现 `bin/mof-analyze quality`
- 能检测大型文件、模块膨胀等问题

### 2. 测试覆盖分析 (mof-analyze --testing) ✅
- 已实现 `bin/mof-analyze testing`
- 能检测测试覆盖比例、标记 poor/warning/good

### 3. 成本优化建议 (mof-analyze --cost) ✅
- 已实现 `bin/mof-analyze cost`
- 能分析 infrastructure/operational/development 成本

### 4. 系统健康仪表盘 ✅
- 已实现 `bin/mof-analyze dashboard`
- 能展示节点统计、状态分布、层分布、服务状态

### 6. 跨项目依赖图自动生成 ✅
- 已实现 `bin/mof-graph`
- 能生成 Mermaid 依赖图 + 循环依赖检测

## 🔄 待实现

### 5. 智能决策支持
- 当团队讨论"要不要做 X"时，自动回答影响/成本/收益/风险
- 依赖: 需要更完整的价值/成本/风险数据
- ROI: 高 (决策支持)
- 优先级: P2

### 7. MOF 模型版本管理
- 对 MOF 模型进行版本管理
- 支持 diff 对比
- 支持 rollback
- 依赖: 需要 git 或其他版本控制
- ROI: 中 (变更追踪)
- 优先级: P3

### 8. MOF 模型导入/导出
- 支持从其他格式导入/导出 MOF 模型
- 从 CSV/Excel 导入
- 导出为 JSON/XML
- 与 ArchiMate/UML 集成
- 依赖: 需要格式转换逻辑
- ROI: 低 (互操作性)
- 优先级: P3
