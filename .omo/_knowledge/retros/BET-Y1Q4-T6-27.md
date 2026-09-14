---
type: retro
bet_id: BET-Y1Q4-T6-27
title: "GraphRAG 实体感知切片与 SHACL 架构形状验证引擎"
status: in_progress
created: 2026-09-13
track: T6-EVOLUTION
---

# BET-Y1Q4-T6-27 复盘记录

## 交付摘要

| 项目 | 状态 |
|------|------|
| EntityAwareChunker 实现 | ✅ 完成 |
| SHACLValidator 实现 | ✅ 完成 |
| DFSQ SHACL Shapes (TTL) | ✅ 完成 |
| Scene Card SHACL Shapes (TTL) | ✅ 完成 |
| 单元测试覆盖 | ✅ 完成 |
| CI 门禁集成 | ⏳ 待后续 PR |

## 技术决策

### 1. 实体检测策略
- **选择**: 基于正则模式匹配（无需外部 NLP 依赖）
- **理由**: 保持 kairon 包轻量，避免引入 heavy NLP 模型
- **覆盖**: 中文机构名、日期、标准号、英文专有名词

### 2. 分块边界优化
- **策略**: 实体保护 + 句子边界偏好
- **回退**: 若无句子边界，使用实体起始位置

### 3. SHACL 验证实现
- **选择**: Python 原生验证（非 RDF 库依赖）
- **理由**: 降低依赖复杂度，YAML 原生验证足够治理需求
- **扩展点**: 未来可接入 pyrdflib 做完整 SHACL 推理

## 踩坑记录

1. **子模块初始化**: worktree 创建后 kairon/iris 子模块需单独 init
2. **导入路径**: iris 包内部使用相对导入，测试需手动添加 sys.path
3. **TTL 语法**: SHACL-SPARQL 约束需确保 PREFIX 声明完整

## 验收标准对照

- [x] Iris 连接器与 Minerva 分块管线接入 EntityAwareChunker
- [x] 编制 dfsq-shapes.ttl 与 scene-card-shapes.ttl
- [ ] CI 门禁集成 SHACL 静态拓扑校验器（待后续 PR）
- [x] 单元测试覆盖实体切分保全率与 SHACL 形状违例告警

## 后续建议

- 接入 pyrdflib 实现完整 SHACL 闭包验证
- 扩展实体模式库（医疗实体、法律实体等垂直领域）
- 性能基准测试（大文档分块吞吐量）
