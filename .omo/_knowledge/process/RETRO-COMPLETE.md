---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# 知识基座项目完整复盘

**复盘时间**: 2026-05-23  
**会话跨度**: 2026-05-19 ~ 2026-05-23（5 天）  
**范围**: 从 0 到全链路的本体建模工具集建设

---

## 一、项目回顾

### 最初目标
构建三层分离的知识基座：Eidos(定义) → KOS(存取) → OntoDerive(推理)，覆盖本体建模全生命周期。

### 最终交付

| 维度 | 交付物 |
|------|--------|
| **元模型层** | SSOT 8 MetaType × 4 MetaRelationType + 约束系统 |
| **Schema 定义** | Eidos: 6 种类型 (KnowledgeCard/Fact/OntologyNode/InferenceRule/StateMachine/Relation) |
| **CLI 标准化** | 5 工具统一 `--json` 输出 |
| **MCP 覆盖** | 5 工具全部 MCP 可达 |
| **管线编排** | Pipeline 协议 + 2 个预设 |
| **全链路验证** | 5000 节点 / 2.5 min bench |
| **代码质量** | 8 项目 ruff 清零 |
| **测试** | ~1000 测试 |
| **Agora 统一入口** | `agora run <command>` 自动路由 |
| **AI Agent** | `eidos-agent` NL→CLI 解析 |
| **共享Brain适配器** | SharedBrain 器官→MetaType 映射 |
| **文档** | README、架构文档、产品分析 |

---

## 二、关键数据

### 工作量

| 项目 | 初始 | 最终 | 增长 |
|------|------|------|------|
| **eidos** | 0 LOC, 0 tests | 2,136 LOC, 70 tests | +2,136 LOC |
| **kos** | 369 LOC, 0 tests | 600 LOC, 83 tests | +231 LOC |
| **ontoderive** | 10,006 LOC, ~500 tests | 11,035 LOC, 747 tests | +1,029 LOC |
| **agora** | 4,892 LOC, 238 tests(eixoisting) | 5,091 LOC, 238 tests | +199 LOC |
| **minerva** | 8,752 LOC, 258 tests(eixoisting) | 8,752 LOC, 258 tests | +0 |
| **gateway** | 0 LOC | ~50 LOC | +50 LOC |
| **.omo/** | 0 files | ~15 files | +15 files |
| **docs** | 0 files | 10+ files | +10+ files |

### 测试增长

| 阶段 | eidos tests | 说明 |
|------|-----------|------|
| Phase 1 | 23 | Schema + Validator 基础 |
| Phase 2 | 27 | 集成测试 |
| Phase 3A | 57 | 元模型 + 类型 + viz |
| Phase 3B | 59 | Pipeline 编排 |
| 红队修复后 | 70 | MCP 测试 + 约束测试 |
| 最终 | **70** | +47 测试 |

### 代码质量

| 项目 | 初始 ruff | 最终 ruff |
|------|----------|----------|
| eidos | 279 | 0 |
| ontoderive | 1,307 | 0 |
| kos | 5,263 | 0 |
| minerva | 955 | 0 |
| agora | 0 | 0 |
| sophia | 121 | 0 |
| eCOS | 65 | 0 |
| pallas | 18 | 0 |
| **总计** | **~8,008** | **0** |

---

## 三、关键决策回顾

### 正确的决策

| 决策 | 原因 | 结果 |
|------|------|------|
| **三层分离 + 零硬依赖** | Eidos/KOS/OntoDerive 完全独立 | 红队验证为最佳架构 |
| **SSOT 元模型驱动** | 不是造轮子，而是基于已有设计 | 8×4 体系完整、可扩展 |
| **适配器模式** | try/except 可选集成 | 5 工具独立，可按需组合 |
| **Pipeline 协议** | 跨工具 JSON 交换而非共享内存 | 松散耦合，可独立升级 |
| **MCP 优先** | 一从始为 AI 集成设计 | 5 工具全部 MCP 可达 |
| **--json 标准化** | CLI 输出统一 | Pipeline 模式直接消费 |

### 需要改进的决策

| 决策 | 问题 | 改进 |
|------|------|------|
| **KOS 索引器插件** | `spec_from_file_location` 脆弱 | 应改用标准 Python 导入 |
| **OntoDerive 目录布局** | `engine/` 在根目录而非 `src/` | 导致 PYTHONPATH 混乱 |
| **Pipeline 硬编码路径** | `/Users/xiamingxing/` 和其他绝对路径 | 应相对化或可配置 |
| **子代理频繁被中断** | deep/quick 类别任务 45 分钟超时 | 大任务拆小、用 quick 替代 deep |

---

## 四、技术债务

### 已清理

| 债务 | 清理方式 | 效果 |
|------|---------|------|
| ruff 8,008 violations | 自动化 + 手动逐项修复 | 8/8 项目清零 |
| 274 未提交 | 逐项目提交 | 清理完成 |
| KOS 索引器缺少 KosIndexer | 修复 kos-indexer.py | 500 文件索引通过 |
| Pipeline Python 路径 | 改为 sys.executable | 跨平台可用 |
| 废弃项目/文件 | 清理 ~1.2GB | 空间释放 |

### 剩余

| 债务 | 优先级 | 说明 |
|------|--------|------|
| OntoDerive 目录非标准 | 🟢 低 | `engine/` → `src/` 迁移 |
| KOS 索引器 sys.path 依赖 | 🟢 低 | 脆弱但不是阻塞 |
| Pipeline 硬编码 Workspace 路径 | 🟢 低 | 仅影响文档示例 |
| Eidos MCP 纯 stdio 非 SDK | 🟢 低 | 手写 JSON-RPC 稳定但非标准 |
| SharedBrain 6100+ 测试待验证 | 🟢 低 | 映射已建但未执行 |

---

## 五、经验教训

### 流程类

1. **子代理频繁超时** — deep 类别任务几乎全部被中断，改用 quick + 详细 prompt 后成功。改进方向：大任务拆小，步骤不超过 10 分钟。

2. **计划文件不同步导致 boulder 续接** — Phase 2 的 plan checkbox 未及时更新，导致系统反复触发续接提示。后续应每完成一个 Wave 立即更新。

3. **系统噪声过多** — ALGORITHM 模式的 classifier 持续失败，产生大量无用 hooks。应在任务密集执行期关闭 classifier。

### 技术类

4. **KOS 插件架构脆弱** — `spec_from_file_location` + shim 文件模式不可靠，shim 被删除后索引器立即失效。应改用标准 Python 包导入。

5. **最小改动原则被违反** — 偶有直接编辑代码而非通过 task() 的情况。应该更严格地执行"Atlas 不做实现"。

6. **测试先行有效但未坚持** — 初期 phase 有 TDD，后期测试滞后。MCP 测试在红队才补上。

---

## 六、后续路线

| 阶段 | 目标 | 预估 |
|------|------|------|
| **S1** | 生产就绪 — pip install 可用，MCP 加固 | 1-2 天 |
| **S2** | 10 万+ 节点压力测试 + 性能优化 | 1 天 |
| **S3** | SharedBrain 实际索引 + 本体映射验证 | 1 天 |
| **S4** | 开源准备 — license、贡献指南、CI | 1 天 |
| **S5** | Web Dashboard 全面增强 | 2 天 |
