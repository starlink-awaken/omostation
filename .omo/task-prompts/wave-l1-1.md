# Wave L1-1: 契约版本化

**目标**: 完成 L1 契约层缺失的版本化策略+SSOT规则+kronos消费

## Task L1-1.1: 契约版本化策略文档
- 文件: `~/Documents/学习进化/基建架构/41-L1-契约版本化策略.md`
- 内容: semver策略, backward/breaking分类, 过期规则, 字段定义
- 验证: 文档含8个schema的版本号快照

## Task L1-1.2: SSOT版本验证规则
- 文件: `~/Workspace/SSOT/tool/ssot-kernel/src/ssot_kernel/patterns/consistency.py`
- 新增 pattern: `version_consistency` 检查各schema version字段
- 测试: `tests/test_engine.py` 新增 version 测试用例
- 验证: `pytest tests/ -q`

## Task L1-1.3: kronos 消费 eidos schema
- 检查 kronos/schemas/pipeline-schemas.json 是否与 eidos 重复
- 如重复: 删除独立schema, import eidos
- 验证: `pytest tests/ -q`
