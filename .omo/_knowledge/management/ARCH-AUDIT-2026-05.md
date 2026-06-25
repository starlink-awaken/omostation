---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# Workspace 架构审计报告

**时间**: 2026-05-21  
**范围**: Workspace 全部 12 个活跃项目 + 基础设施
**属性**: 历史架构审计记录 / reference only，不是当前项目清单、当前测试状态、当前 Git 健康或当前架构结论 SSOT。当前事实请回看 `/.omo/PROJECTS.yaml`、`/docs/PANORAMA.md` 与当前治理审计证据。

---

## 一、项目总览

| 项目 | 版本 | 代码量 | 测试数 | Lint | Git健康 | 用途 |
|------|------|--------|--------|------|---------|------|
| **agora** | v1.5.0 | 7,289 LOC / 42 files | 238 | ✅ | ⚠️ 9 未提交 | MCP 服务路由 |
| **bos-skill-cli** | MVP | 2,185 LOC / 9 files | 27 | ✅ | ⚠️ 7 未提交 | 技能发现 CLI |
| **eCOS** | v0.6.0 | 11,760 LOC / 52 files | 98 | ❌ 1 err | ⚠️ 14 未提交 | 涌现意识系统 |
| **eidos** | v0.1.0 | 2,099 LOC / 26 files | 57 | ❌ 1 err | ⛔ NO GIT | Schema 定义层 |
| **Forge** | — | 5,220 LOC / 22 files | — | ❌ 1 err | ⚠️ 43 未提交 | 工具链 (疑似废弃) |
| **kos** | v0.x | 8,934 LOC / 42 files | 58 | ❌ 1 err | ⚠️ 18 未提交 | 知识存储 |
| **minerva** | v0.11.0 | 7,931,647 LOC / 20,407 files | 258 | ❌ 1 err | ⚠️ 17 未提交 | 研究系统 |
| **ontoderive** | v3.5.0 | 10,919 LOC / 88 files | 204 | ❌ 1 err | ⚠️ 7 未提交 | 推理引擎 |
| **pallas** | — | 497 LOC / 3 files | — | ❌ 1 err | ⚠️ 21 未提交 | 知识工程工具 (thin) |
| **SharedBrain** | — | 2,107,901 LOC / 7,658 files | — | ✅ | ⚠️ 48 未提交 | 数字化生命 OS |
| **sophia** | v0.2.1 | 1,661 LOC / 14 files | 87 | ❌ 1 err | ⚠️ 4 未提交 | 符号化研究范式 |
| **gateway** | — | 0 LOC / 0 files | — | ✅ | ⚠️ 1 未提交 | MCP Gateway |

**总计**: ~10M LOC, 28,363 files, ~1,027 测试

---

## 二、依赖关系审计

### 2.1 核心层依赖

```
eidos (Schema)   ← 0 个项目硬依赖    ← 完全独立
kos (Storage)    ← 0 个项目硬依赖    ← 完全独立
ontoderive       ← agora(12) eidos(4)  ← 有消费者
minerva          ← 0 个项目硬依赖    ← 完全独立
```

### 2.2 关键发现

**发现 1: "三层架构"是概念层不是代码层**
Eidos/KOS/OntoDerive 之间没有任何硬依赖。所有集成通过：
- `try/except ImportError`（可选适配器）
- CLI subprocess 调用（Pipeline 模式）
- 无共享内存、无共享对象、无共享状态

**这是设计选择还是架构问题？**
✅ 好的：零耦合，任一层可独立升级/替换
⚠️ 代价：跨层数据交换必须序列化 JSON，无类型安全

**发现 2: KOS 无人消费**
没有项目 `import kos`。KOS 只是一个 CLI 工具，不是库。这意味着 KOS 的 API 没有消费者验证，可能存在设计缺陷而不自知。

**发现 3: Agora → OntoDerive 强依赖**
agora 有 12 处 `from engine...` 导入，说明 Agora 重度依赖 OntoDerive 的内部模型。这是唯一的"真·硬依赖"关系。

**发现 4: SharedBrain/Forge 状态不明**
- SharedBrain: 210 万行，7,658 文件，无测试，48 未提交。是否还在活跃开发？
- Forge: 零测试，43 未提交，5,220 LOC 不确定用途。

---

## 三、测试覆盖率审计

| 项目 | 测试数 | 覆盖率 (估算) | 评价 |
|------|--------|-------------|------|
| agora | **238** | HIGH | ✅ 最强 |
| ontoderive | **204** | HIGH | ✅ 强 |
| minerva | **258** | MED | ⚠️ 数据文件占 99.9% LOC |
| eCOS | **98** | MED | ⚠️ 13 未提交 |
| eidos | **57** | MED | ⚠️ 无 git 初始化 |
| sophia | **87** | HIGH | ✅ 覆盖率不错 |
| kos | **58** | LOW | ⚠️ 大量 stub 未测试 |
| bos-skill-cli | **27** | HIGH (77% cov) | ✅ MVP 够用 |
| SharedBrain | **0** | NONE | ❌ 210 万行零测试 |
| Forge | **0** | NONE | ❌ 零测试 |
| pallas | **0** | NONE | ❌ 零测试 |
| gateway | **0** | NONE | ⚠️ 空项目 |

### 关键问题

| 问题 | 严重度 |
|------|--------|
| SharedBrain 210 万行零测试 | 🔴 致命 |
| eidos 无 git 初始化 | 🟡 中 (代码可能丢失) |
| Forge 用途不明 + 零测试 | 🟡 中 |
| kos 58 测试但 CLI 覆盖率不足 | 🟢 低 |

---

## 四、架构债务

### 4.1 代码级债务

| 债务 | 项目 | 说明 | 优先级 |
|------|------|------|--------|
| `ruff check` 报错 (每项目 ~1 个) | 多数 | RUF100 未使用 noqa 注释 | 🟢 低 |
| 非标准目录布局 | ontoderive | `engine/engine/formal/` 四层嵌套 | 🟢 低 |
| 无 git 初始化 | eidos | 无版本控制 | 🟡 中 |
| 大量未提交 | SharedBrain(48) | 48 修改未提交 | 🟡 中 |
| KOS CLI 仍有 stub | kos | 部分命令是占位符 | 🟢 低 |

### 4.2 架构级债务

| 债务 | 说明 | 优先级 |
|------|------|--------|
| KOS 无人消费 | 存储层缺少 API 消费者验证 | 🟡 中 (随 pipeline 使用增加会自然解决) |
| Agora → OntoDerive 硬耦合 | 12 处 import 破坏模块独立性 | 🟡 中 |
| Pipeline 未接入 Agora | 管线编排目前是本地 CLI 模式 | 🟢 低 |
| 可视化工具未接入 Minerva | eidos-viz 只展示 Schema/类型，不展示实际知识图 | 🟢 低 |

---

## 五、项目健康评分

| 项目 | 代码质量 | 测试覆盖 | 文档 | 活跃度 | 总分 |
|------|---------|---------|------|--------|------|
| eidos | A (零依赖) | B (57 tests) | B | A | **A-** |
| ontoderive | A (MOF 设计) | A (204 tests) | B | A | **A** |
| agora | A | A (238 tests) | B | A | **A** |
| minerva | B | B (258 tests) | B | A | **B+** |
| sophia | A | A (87 tests) | B | B | **A-** |
| kos | B (stub 多) | C (58 tests) | B | A | **B** |
| bos-skill-cli | B | A (27 tests, 77% cov) | B | B | **B** |
| eCOS | B | B (98 tests) | C | B | **B-** |
| gateway | — | — | — | B | **N/A** |
| pallas | B | F (0 tests) | C | C | **C** |
| Forge | C | F (0 tests) | D | D | **D** |
| SharedBrain | C | F (0 tests) | C | B | **C-** |

---

## 六、关键建议

### P0 立即做
1. **eidos 初始化 git** — 57 tests 的代码无版本控制有风险
2. **修复全局 ruff 错误** — 每个项目的 1 个 RUF100 错误，几分钟可修完
3. **SharedBrain/Forge 决策** — 确认 Forge 用途，SharedBrain 是否应加入测试

### P1 本月做
4. **KOS API 定型** — KOS 目前无人 import，随 pipeline 使用后会被调用，应提前设计好 API
5. **Agora → OntoDerive 解耦** — 12 处 import 应改为可选适配器模式
6. **pipeline 接入 Agora** — 让 pipeline 可通过 Agora MCP 调度

### P2 按需做
7. **eidos-viz 支持知识图可视化** — 目前只展示类型结构
8. **KOS CLI stub 清理** — 低优，不影响使用
9. **ontoderive 目录标准化** — `engine/` → `src/`
