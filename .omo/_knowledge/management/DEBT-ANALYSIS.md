# 四维债务分析报告

> 历史诊断快照；当前治理判断请结合 `.omo/CONSISTENCY-CHECK.md` 与 `.omo/state/system.yaml`。

**时间**: 2026-05-21  
**范围**: 全 Workspace 19 个项目

---

## 一、产品债务 (Product Debt)

SSOT 06-本体建模/ 中定义的元模型体系，当前实现覆盖率：

| SSOT 文档 | 已实现 | 未实现 | 债务 |
|-----------|--------|--------|------|
| 01-元模型定义 (6层架构/8实体/7关系) | 8 MetaType ✅ / 4 MetaRelationType ✅ | 7关系类型缺3种 | 🟡 低 |
| 02-实例化本体 | Core CLI ✅ | 交互式向导 | 🟡 中 |
| 03-推理规则集 (5类型) | 1 种 (forward) ✅ | 4种规则未实现 | 🟡 中 |
| 04-技能本体映射 | ❌ | 全未实现 | 🔴 高 |
| 05-文档本体 | KnowledgeCard ✅ | Detail docs | 🟢 低 |

**关键产品债务**:
- `eidos define` 交互式建模命令缺失 — 用户必须手写 JSON
- Pipeline viz 输出使用 demitter 数据而非真实数据
- `eidos pipeline --name` 的 help 文本仍显示旧版
- PipelineStep.to_cli() 硬编码绝对路径到 `/Users/xiamingxing/...`

---

## 二、架构债务 (Architecture Debt)

| 债务 | 项目 | 严重度 | 说明 |
|------|------|--------|------|
| 非标准目录 | ontoderive | 🟡 中 | `engine/engine/formal/` 四层嵌套 |
| 零消费者 | KOS | 🟡 中 | 无项目 `import kos`，API 未经验证 |
| 硬编码路径 | eidos pipeline | 🟡 中 | `PipelineStep.to_cli()` 含 `/Users/xiamingxing/` |
| Agora→OntoDerive | agora | 🟢 低 | 0 hard imports (已解耦) |
| 28 个 CLI subparser | kos-cli.py | 🟢 低 | 大量命令但多数 unused |

---

## 三、功能债务 (Feature Debt)

| 缺失功能 | 项目 | 严重度 | 说明 |
|---------|------|--------|------|
| `eidos define` | eidos CLI | 🟡 中 | 无交互式 schema 定义 |
| `viz graph` 真实数据 | eidos CLI | 🟡 中 | 输出 demitter 结点 |
| `viz state` 真实数据 | eidos CLI | 🟡 中 | 输出 demitter 状态机 |
| pipeline.yaml 格式 | eidos pipeline | 🟢 低 | 仅支持 JSON |
| KOS 查询无 Eidos schema 过滤 | kos search | 🟢 低 | `meta_type` 已存但不可搜索 |
| `TODO/FIXME` 代码 | 多个项目 | 🟢 低 | Eidos(1) / KOS(3) / ontoderive(2) |

---

## 四、技术债务 (Technical Debt)

### 代码质量

| 项目 | Ruff | Git 未提交 | LOC | Tests | 评分 |
|------|------|-----------|-----|-------|------|
| **eidos** | **0** ✅ | 22 | 1,367 | 57 🟢 | **A** |
| **agora** | **0** ✅ | 9 | 4,892 | 238 🟢 | **A** |
| **ontoderive** | 1,307 | 94 | 10,006 | 204 🟡 | **B** |
| **kos** | 5,263 | 58 | 369 | 54 🟡 | **D** |
| **minerva** | 955 | 78 | 8,880 | 258 🟡 | **C** |
| **sophia** | 121 | 12 | 1,255 | 87 🟢 | **B** |

> 注：上表 ruff 计数为 2026-05-21 快照。当前计数请运行 `ruff check packages/ --statistics` 获取最新值。

### 零测试项目 (Critical)

| 项目 | LOC | Tests | 风险 |
|------|-----|-------|------|
| Forge | 1,762 | 0 | 🔴 用途不明 + 零测试，建议确认去留 |
| SharedBrain | 2,107,901 | 0 | 🔴 210万行零测试，最大风险 |
| pallas | 300 | 0 | 🟡 小项目，可接受 |

---

## 五、四维综合评分

| 维度 | 评分 | 最关键项 |
|------|------|---------|
| 🏗️ **产品** (Product) | **B** | SSOT 元模型覆盖 ~60%，缺交互式建模和本体映射 |
| 🏛️ **架构** (Architecture) | **B+** | 三层分离明确，但 OntoDerive 目录非标准和 KOS 零消费者 |
| ⚡ **功能** (Feature) | **B** | CLI 基础功能完备，但 viz/pipeline 有 demitter 数据 |
| 🔧 **技术** (Technical) | **C** | Eidos/Agora 优秀，KOS/Minerva/零测试项目拉低分数 |

**综合评级: B-**  

亮点: Eidos+agora 质量高、三层分离清晰、模型统一初步完成  
短板: KOS 代码质量差、3 个零测试项目 (210万行无验证)、大量未提交

---

## 六、处理建议

### P0 立即
1. **SharedBrain 决策** — 210 万行零测试，确认是否还维护

### P1 本周
2. **Forge 确认去留** — 1,762 LOC 零测试用途不明
3. **KOS 核心 ruff 清理** — 5000+ 中有 ~100 个真实问题，其余自动生成
4. **硬编码路径替换** — PipelineStep.to_cli() 改为相对路径或配置

### P2 本月
5. **交互式 `eidos define`** — 用户不需要手写 JSON
6. **`viz state/graph` 真实数据源** — 替换 demitter
7. **Minerva ruff 清理** — 955 个逐步修复
