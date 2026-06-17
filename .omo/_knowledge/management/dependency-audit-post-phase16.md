# 跨项目依赖与耦合审计报告 — Phase 16 后

> 日期: 2026-06-03
> 范围: kairon 33 包、agentmesh、gbrain、SharedBrain
> 基线: `ARCH-AUDIT-2026-05.md` 历史发现
> 历史依赖审计记录 / reference only。本文记录 Phase 16 后的依赖判断，不是当前依赖拓扑、当前消费者数量或当前运行验证状态 SSOT。
> 当前架构与依赖事实请回看 `/.omo/PROJECTS.yaml`、`/docs/PANORAMA.md`、当前项目测试/审计证据。

---

## 执行摘要

| 历史问题 | Phase 16 后状态 | 变化 |
|----------|----------------|------|
| Agora → OntoDerive 硬耦合 (12 处 import) | **已解耦** | ✅ 消除 |
| KOS 零消费者 (无人 import) | **已有消费者** | ✅ 消除 |
| sharedbrain-bridge 未连接 | **无外部消费者** | 🟡 维持 |
| gbrain → agentmesh 依赖 | TypeScript 编译依赖 | 🟡 待确认 |

**总体评价**: 两个历史架构债务（Agora→OntoDerive 耦合、KOS 零消费者）**已在 Phase 9-16 期间自然解决**。剩余耦合度处于健康水平。

---

## 详细审计

### 1. Agora → OntoDerive 耦合

**历史状态** (ARCH-AUDIT-2026-05):
> "agora 有 12 处 `from engine...` 导入，说明 Agora 重度依赖 OntoDerive 的内部模型。这是唯一的'真·硬依赖'关系。"

**当前验证**:
```bash
grep -r "from engine" packages/agora/src/ --include="*.py" -n
# 结果: 无匹配

grep -r "import engine" packages/agora/src/ --include="*.py" -n
# 结果: 无匹配
```

**结论**: ✅ **已完全解耦**。Agora 不再直接导入 OntoDerive 的内部模型。历史耦合已通过接口抽象或反向依赖消除。

**验证证据**: `agora/src/agora/` 目录下无任何 `engine` 模块引用。

---

### 2. KOS 消费者验证

**历史状态** (ARCH-REVIEW.md):
> "没有项目 `import kos`。KOS 只是一个 CLI 工具，不是库。"

**当前验证**:
```bash
grep -r "import kos\|from kos" projects/ --include="*.py" -l
```

**找到的 KOS 消费者**:

| 消费者 | 路径 | 用途 |
|--------|------|------|
| eidos | `packages/eidos/src/eidos/storage.py` | 存储层调用 KOS |
| agora | `packages/agora/src/agora/hermes_mcp.py` | Hermes MCP 集成 |
| kronos | `packages/kronos/src/kronos/dispatcher.py` | 任务调度 |
| minerva | `packages/minerva/src/minerva/pipeline/stages/kos_save.py` | Pipeline 保存阶段 |
| minerva | `packages/minerva/src/minerva/knowledge_closed_loop.py` | 知识闭环 |
| tests | `projects/kairon/tests/test_e2e_knowledge.py` | E2E 测试 |

**结论**: ✅ **KOS 已有 5 个活跃消费者**。零消费者问题已解决。KOS 从 CLI 工具升级为被库代码依赖的服务层。

---

### 3. sharedbrain-bridge 连接状态

**当前验证**:
```bash
grep -r "sharedbrain_bridge\|from sharedbrain" projects/ --include="*.py" -l
# 结果: 无 kairon 包外匹配
```

**分析**:
- `sharedbrain-bridge` 包有 2 个测试，源代码存在
- 无外部项目显式导入 sharedbrain-bridge
- 但 bridge 的设计目的就是双向连接，需要 kairon 侧和 SharedBrain 侧同时激活

**结论**: 🟡 **Bridge 代码存在但连接状态未验证**。由于 SharedBrain 已分解为文档仓库，bridge 的实际用途需要重新评估。若 SharedBrain 不再作为运行时存在，bridge 可能需要重构为与 kairon 内部 SharedBrain 兼容层（sharedbrain-standalone）的接口。

---

### 4. gbrain → agentmesh 依赖

**验证**:
```bash
# package.json 依赖检查
cat projects/gbrain/package.json | grep agentmesh
```

**当前状态**: gbrain 作为 TypeScript 项目，依赖 agentmesh SDK。由于 agentmesh 是 L3 层、gbrain 是 L4 层，这是架构设计中的预期依赖方向。

**结论**: 🟡 **未执行运行时验证**。gbrain 包编译和测试状态需要单独确认。基于架构设计，此依赖是合理的，不构成债务。

---

### 5. kairon 内部包循环依赖

**验证方法**: 检查 workspace pyproject.toml 中的 `workspace = true` 依赖。

**观察**:
- kairon 使用 uv workspace，33 个包通过 `workspace = true` 互相引用
- 核心包（core-models, engine-core, shared-lib）被多个上层包依赖
- 未发现反向依赖（如 L2 包依赖 L4 包）

**结论**: ✅ **层次依赖方向正确**。L1(契约) → L2(能力) → L3(协作) → L4(元层) 的依赖方向未被破坏。

---

## 依赖关系图（当前）

```
P0 (产品层)
  ↓ 无活跃入口

I0 (Agora 路由)
  ↓ MCP 协议

L1 (契约层)
  eidos ←──┐
  ssot     │
  pipeline─┘

L2 (能力层)
  ontoderive ←──┐
  minerva  ←────┤
  sophia   ←────┤
  forge    ←────┤
  kos ←─────────┤ ← 5 个消费者 ✅
  kronos   ←────┤
  iris     ←────┤
  ...      ←────┘
  (全部通过 workspace 依赖 L1)

L3 (协作层)
  agentmesh ←── gbrain (预期依赖)

L4 (自我层)
  sharedbrain-standalone (0 消费者)
  sharedbrain-bridge (0 外部消费者)
```

---

## 新发现的风险

### Risk D1: sharedbrain-standalone 孤立包

**描述**: `sharedbrain-standalone` 有源代码但零测试，且没有其他 kairon 包导入它。

**影响**: 若此包是分解后保留的 SharedBrain 运行时核心，缺乏集成测试意味着分解后的兼容性未验证。

**建议**: 确认 standalone 与 bridge、kos、agora 的交互方式，或评估是否可合并到 sharedbrain-bridge。

---

## 历史债务消除确认

| 债务 | 历史严重度 | 当前状态 | 关闭依据 |
|------|:----------:|----------|----------|
| Agora→OntoDerive 硬耦合 | 中 | **已消除** | 代码搜索零匹配 |
| KOS 零消费者 | 中 | **已消除** | 5 个活跃消费者确认 |

---

*审计时间: 2026-06-03*
*验证命令: `grep -r "from engine" packages/agora/src/`, `grep -r "import kos" projects/`*
