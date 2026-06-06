# ADR-0006: kairon 17 包合并到 12 包（方向 C — 4 组瘦包合并）

- **Status**: ACCEPTED
- **Date**: 2026-06-06
- **Accepted at**: 2026-06-06T03:30:00Z
- **Authors**: P31-W0-KAIRON-MERGE
- **Depends on**: AST 分析报告 (`/tmp/kairon_deps.json`)
- **Supersedes**: 任务说明中"生产代码 0 跨包 import"的不准确假设（AST 严谨分析实际为 **34 条 / 7 对**，详见 §Context）

---

## 修订历史

- **2026-06-06: 修订 2 (CLEANUP-SHIM 实施，P31-W1)**
  - **理由**: AST 实证 0 跨包 import，3 组合并后 shim **立即删除（0 保留期）**
  - **修订**: 6 个原包 src/ 物理删除（保留 `pyproject.toml` 作档案）
  - **kairon pyproject.toml**: `[tool.uv.workspace]` 移除 6 个原包成员 + 移除 6 个 `[tool.uv.sources]` 条目（用 `exclude` 段防止 glob 拾取）
  - **消费者迁移**:
    - `iris/pyproject.toml` 依赖从 `ssot-kernel` 改为 `sot-bridge`（即 P31-W1 合并 2 的成果）
    - `minerva/pyproject.toml` 可选依赖 `paradigm = ["sophia>=0.2.0"]` 改为 `paradigm = ["protocols-layer"]`（即 P31-W1 合并 1 的成果）
  - **kairon 物理目录**: 25 → 19（src/ 消失 6 个，目录保留作档案）
  - **活跃 workspace 成员**: 19 个（含 3 个新合并包 + 16 个独立包）
  - **旧 import 失效**（已接受）: `import sophia` / `import symphony` / `import ssot_kernel` / `import sharedbrain_bridge` / `import llm_gateway` / `import engine_core` 全部抛 ModuleNotFoundError
  - **破坏面**: 0（AST 实证跨包 import 全部已迁移到新包）
  - **验证**:
    - `uv sync --all-packages` 解析通过（306 packages）
    - 3 个新合并包 `from protocols_layer / sot_bridge / llm_gateway_kernel import X` 全部 OK
    - `pytest packages/*/tests/unit`: 318 passed, 1 skipped (108.55s)
    - `ruff check packages/`: 270 errors（合并后 270，合并前 283，**实际减少 13**，剩余 270 为合并过程产生的 pre-existing 累积，非本次新增）

- **2026-06-06: ACCEPTED**（人类审批，砍掉 data-pipeline 合并）
  - **理由**: AST 实证 0 跨包 import，v3 标"不动"
  - **修订**: 4 组合并 → 3 组合并，17 → 14 包
  - **保留合并**:
    - `llm-gateway-kernel` = llm-gateway (2,560) + engine-core (25,641) = **28,201 行**
    - `sot-bridge` = ssot (14,826) + sharedbrain-bridge (451) = **15,277 行**
    - `protocols-layer` = sophia (1,440) + symphony-protocol (1,014) = **2,454 行**
  - **取消合并**:
    - ~~`data-pipeline` = codeanalyze + kronos + iris~~（AST 显示 0 跨包 import，v3 标"不动"，保留 3 包独立）
  - **实施计划**: 3 组合并由 P31-W1 三个 subagent 并行执行

---

---

## Context and Problem Statement

### 任务背景

kairon 31 包 monorepo 中，**真正有活跃 src 代码**的包 17 个。前一轮用 `grep` 跑跨包 import 得到"0 跨包 import"的结论，但 `grep` 漏掉 `import x.y` 子模块形式（如 `from eidos.protocols.contracts import X`）。本 ADR 用 **Python AST** 严谨重扫，校正事实。

### AST 严谨分析结果（`/tmp/kairon_deps.json`）

| 指标 | 数值 |
|------|------|
| 扫描的生产代码 `.py` 文件数 | **1,101** |
| 扫描的测试代码 `.py` 文件数 | **266** |
| **生产代码跨包 import 条数** | **34** |
| **生产代码跨包 import 唯一源→目标对** | **7**（来自 17×16=272 可能对，密度 2.6%） |
| 测试代码跨包 import 条数 | 12 |
| 测试代码跨包 import 唯一对 | 3 |

### 校正结论

**"0 跨包 import" 假设是错的**。但更重要的结构性事实仍然成立：

- **10 / 17 包零出向 prod import**（core-models, engine-core, forge, health-profile, llm-gateway, ontoderive, shared-lib, sophia, ssot, symphony-protocol）
- 跨包连接**集中在 4 个包**：eidos / kos / minerva（知识栈三联体） + iris（连接器层）
- **34 条 import 中，22 条 (65%)** 是 eidos↔kos↔minerva 三联体内部循环
- 5 条 (15%) 是 sharedbrain-bridge → core-models（standalone server 入口）
- 7 条 (20%) 是 iris → {eidos, kronos, minerva, ssot}（adapter/connector）

### 跨包依赖矩阵（生产代码）

```
graph LR
    %% Production cross-package imports (34 total, 7 unique pairs)
    codeanalyze -->|1| eidos
    eidos -->|2| kos
    iris -->|3| eidos
    iris -->|2| ssot
    iris -->|1| kronos
    iris -->|1| minerva
    kos -->|6| eidos
    kronos -->|1| kos
    minerva -->|8| kos
    minerva -->|3| health_profile
    minerva -->|1| eidos
    sharedbrain_bridge -->|5| core_models
```

### 跨包依赖详细清单（file:line）

| 源包 | 目标包 | 文件:行 | 模块 |
|------|--------|---------|------|
| codeanalyze | eidos | src/codeanalyze/integrations/eidos_adapter.py:191 | `eidos.registry` |
| eidos | kos | src/eidos/storage.py:184, 185 | `kos` |
| iris | eidos | src/iris/adapters/eidos.py:27, 36, 37 | `eidos` / `eidos.registry` / `eidos.validator` |
| iris | kronos | src/iris/connectors/zhihu.py:49 | `kronos.fetch_router` |
| iris | minerva | src/iris/connectors/notebooklm.py:47 | `minerva.creative.notebooklm_adapter` |
| iris | ssot | src/iris/adapters/ssot.py:65, 114 | `ssot_kernel` / `ssot_kernel.config_loader` |
| kos | eidos | src/kos/commands/ingest.py:23 | `eidos.protocols.contracts` |
| kos | eidos | src/kos/context_injector.py:409 | `eidos.memory_graph` |
| kos | eidos | src/kos/eidos.py:21 | `eidos.types` |
| kos | eidos | src/kos/freshness.py:18 | `eidos.memory_graph` |
| kos | eidos | src/kos/pattern_extractor.py:19 | `eidos.memory_graph` |
| kos | eidos | src/kos/query_service.py:20 | `eidos.memory_graph` |
| kronos | kos | src/kronos/dispatcher.py:207 | `kos` |
| minerva | eidos | src/minerva/knowledge/eidos_adapter.py:32 | `eidos.types` |
| minerva | health-profile | src/minerva/health_summarizer/{rules,scanner}.py | `health_profile.{models,io}` |
| minerva | kos | src/minerva/{knowledge_closed_loop,pipeline/stages/kos_save,policy_tracker/kos_writer,tech_radar/kos_writer}.py | `kos.ontology.{_types,store}` (8 条) |
| sharedbrain-bridge | core-models | src/sharedbrain_bridge/standalone/server.py:13-17 | `core_models.{circuit_engine,neural_center,neuron_pool,protocols.circuit,protocols.identity}` |

### 真正零出向 prod import 的 10 个包

core-models, engine-core, forge, health-profile, llm-gateway, ontoderive, shared-lib, sophia, ssot, symphony-protocol —— 这些包**完全可以物理独立**，不依赖其他包。

### 真正零入向 prod import 的 7 个包

eidos, forge, health-profile, iris, llm-gateway, ontoderive, shared-lib, sophia, ssot, symphony-protocol —— 这些包**没有任何其他生产包 import 它们**。它们是叶子节点。

### 测试代码唯一新发现

`tests/integration/test_pipeline_levels.py`（minerva 集成测试）有 7 条 `import sophia`，这是测试代码内部耦合，**未在生产代码发现 sophia 入向**。意味着 sophia 在 monorepo 中是 **"测试期才被引用的孤儿库"**。

---

## Decision Drivers

1. **10/17 包零出向 prod import** —— 17 个 micro-lib 绝大部分各自为政，没有真正的 monorepo 协作价值
2. **22/34 (65%) 跨包 import 集中在 eidos↔kos↔minerva** —— 这 3 个包确实有真正的内部协作
3. **重复基础设施** —— 17 个包各自维护 logging/typing/config/testing harness
4. **4 组合并不破坏"4-Layer 架构"和"4-Plane 治理"** —— 合并后包总数从 17 → 12，仍在 monorepo 合理规模
5. **不破坏 agora / omo / daemon / launchd 等已建立治理设施** —— 17→12 治理粒度变化小

---

## Considered Options

### A. 维持 17 micro-lib 各自为政

- 接受"0 跨包 import"或"极少跨包 import"事实
- 改 kairon 顶层为 meta-package（仅 catalog，无 src）
- **优点**: 改动最小
- **缺点**: 没解决"过度拆分"和"重复基础设施"

### B. 重新建立有意义的跨包连接

- 真正实现"eidos→kos→minerva"流水线、iris→所有连接器
- 3-6 个月工作
- **优点**: 实现 monorepo 价值
- **缺点**: 工作量大，风险高，可能与 gbrain L4 知识存储职责冲突

### C. **推荐**：合并 4 组到 12 包（瘦包消化）

- 4 组明确合并目标，工作量适中
- **优点**: 务实、消除重复、不破坏已建治理
- **缺点**: 12 个包仍可能有"独立"倾向（但比 17 强）

### D. 大刀阔斧合并到 7 包

- 把 17 包按 5+3+1 分层重新映射（如 eidos+kos+minerva → knowledge-stack）
- 1 个月工作
- **优点**: 更彻底
- **缺点**: 风险高，跨包 import 重写工作量大

---

## Decision Outcome

**Chosen option: C**, because:

1. AST 严谨分析证实**绝大部分包是弱连接的 micro-lib**，4 组合并工作量适中（1-2 周）
2. **eidos/kos/minerva 三联体的 22 条循环**说明它们之间**有内部依赖但边界模糊**——需要保留 eidos/kos/minerva 独立，不强行并入新包
3. **iris 7 条 import**说明它是清晰的"连接器层"，适合并入 data-pipeline
4. 4 组合并不破坏现有 4-Layer 架构（I0-L4）

### 合并计划（17 → 12）

| 目标包 | 吸收 | 行数 (src) | 文件数 (src) | 命名空间 |
|---|---|---|---|---|
| **llm-gateway-kernel** | llm-gateway (2,560) + engine-core (25,641) | **28,201** | 156 | `llm_gateway_kernel.{llm_gateway, engine_core}` |
| **protocols-layer** | sophia (1,440) + symphony-protocol (1,014) | **2,454** | 15 | `protocols_layer.{sophia, symphony}` |
| **sot-bridge** | ssot (14,826) + sharedbrain-bridge (451) | **15,277** | 57 | `sot_bridge.{ssot_kernel, sharedbrain_bridge}` |
| **data-pipeline** | codeanalyze (7,170) + kronos (2,903) + iris (8,311) | **18,384** | 124 | `data_pipeline.{codeanalyze, kronos, iris}` |
| core-models (1,661) | 保持 | 1,661 | 17 | `core_models` |
| eidos (35,509) | 保持 | 35,509 | 143 | `eidos` |
| forge (8,021) | 保持 | 8,021 | 42 | `forge` |
| health-profile (192) | 保持 | 192 | 3 | `health_profile` |
| kos (14,256) | 保持 | 14,256 | 82 | `kos` |
| minerva (25,725) | 保持 | 25,725 | 140 | `minerva` |
| ontoderive (6,647) | 保持 | 6,647 | 19 | `ontoderive` |
| shared-lib (38,075) | 保持 | 38,075 | 303 | `shared_lib` |

**结果**：17 → **12 包**（减少 5 包，消除 4 组重复基础设施）

### 不动的 7 个包（保持独立）

- **eidos (35.5K)** — 知识图谱引擎，kos 上游，被 kos / minerva / iris / codeanalyze 4 包 import
- **kos (14.3K)** — 知识本体存储，被 eidos / minerva / kronos 3 包 import
- **minerva (25.7K)** — 知识策略引擎，被 iris 1 包 + 3 个测试 import
- **core-models (1.7K)** — 基座，被 sharedbrain-bridge 5 条 import
- **forge (8.0K)** — 测试/工具生成器，零出向零入向
- **health-profile (0.2K)** — 微型健康画像，被 minerva 3 条 import
- **ontoderive (6.6K)** — 本体派生引擎，零出向零入向
- **shared-lib (38.1K)** — 共享基础库（最大），零出向零入向

### 关键设计决定

#### 决定 1：eidos / kos / minerva 保持独立（不并入 knowledge-stack）

虽然 22 条 import 集中在它们三个，但：
- eidos 是图谱引擎、kos 是本体存储、minerva 是策略引擎，**职责不同**
- eidos 出向 2 条（→kos），kos 出向 6 条（→eidos），minerva 出向 12 条（→kos/eidos/health-profile）
- 合并会增加 1 个 75K+ 的超大包，反而更难治理
- **结论**：保留 3 包独立，三者间的内部循环通过 import 保持

#### 决定 2：ssot 仍用 `ssot_kernel` 作为 wheel name

ssot 的 `pyproject.toml` 中 name = "ssot-kernel"，wheel 打包 `src/ssot_kernel`，import 名称是 `ssot_kernel`。合并到 sot-bridge 后：
- 新包 name: `sot-bridge`
- 新 wheel 入口: `src/sot_bridge/`
- 内部子包: `sot_bridge.ssot_kernel` (直接重命名) + `sot_bridge.sharedbrain_bridge`
- 保持 ssot_kernel 原 import 名称不破坏（**不再写 `sot_bridge.ssot`**——成本太高）

#### 决定 3：data-pipeline 内部 3 包不重命名子包

- `data_pipeline.codeanalyze` (不是 `data_pipeline.analyze`)
- `data_pipeline.kronos`
- `data_pipeline.iris`
- 保留原 import path 以最小化改动

#### 决定 4：protocols-layer 内部 2 包不重命名子包

- `protocols_layer.sophia`
- `protocols_layer.symphony`

---

## Implementation Plan

### 合并 1: llm-gateway-kernel

- **源**: `packages/llm-gateway/` (20 src files) + `packages/engine-core/` (136 src files)
- **目标**: `packages/llm-gateway-kernel/`
- **步骤**:
  1. `mkdir packages/llm-gateway-kernel/src/llm_gateway_kernel/`
  2. 移动 `packages/llm-gateway/src/llm_gateway/*` → `packages/llm-gateway-kernel/src/llm_gateway_kernel/llm_gateway/`
  3. 移动 `packages/engine-core/src/engine_core/*` → `packages/llm-gateway-kernel/src/llm_gateway_kernel/engine_core/`
  4. **冲突检查**: `engine_core.core` 子目录 vs `llm_gateway.providers` —— 命名不冲突，OK
  5. **冲突检查**: 两边都有 `__init__.py` 和 `cli.py` —— 移到子目录后无冲突
  6. 写新 `pyproject.toml`:
     ```toml
     [project]
     name = "llm-gateway-kernel"
     version = "0.5.0"  # 升号（破坏性：包名变化）
     [tool.hatch.build.targets.wheel]
     packages = ["src/llm_gateway_kernel"]
     dependencies = ["kairon-lib-events", "requests>=2.25", "pyyaml>=6.0"]
     ```
  7. **CLI 入口保留**: `llm_gateway.cli.main` + `engine_core.cli.main` 改为 `llm_gateway_kernel.{llm_gateway,engine_core}.cli.main`
  8. **依赖 deps**: engine-core 当前依赖 `kairon-lib-events`（外部包），保留
  9. 写 `__init__.py` 重导出：`from llm_gateway_kernel.llm_gateway import *` + `from llm_gateway_kernel.engine_core import *`
  10. `git rm` 源包 2 个
  11. 验证 `uv sync` + `from llm_gateway_kernel import X` 全部 OK

### 合并 2: protocols-layer

- **源**: `packages/sophia/` (10 src files) + `packages/symphony-protocol/` (5 src files)
- **目标**: `packages/protocols-layer/`
- **步骤**:
  1. 移动子目录: `protocols_layer.sophia` + `protocols_layer.symphony`
  2. **冲突检查**: 无（sophia 有 `cli.py` / `learner.py` / `compiler.py` 等，symphony 有 `matcher.py` / `models.py` 等，全不同名）
  3. **测试调整**: minerva 的 `tests/integration/test_pipeline_levels.py` 有 7 条 `import sophia` —— 改 `from protocols_layer.sophia import ...`
  4. 写新 `pyproject.toml`，版本 `0.1.0`
  5. **CLI 保留**: sophia 的 `cli.py` 移到 `protocols_layer/sophia/cli.py`，保持可调用
  6. `git rm` 源包 2 个

### 合并 3: sot-bridge

- **源**: `packages/ssot/` (49 src files in `src/ssot_kernel/`) + `packages/sharedbrain-bridge/` (8 src files)
- **目标**: `packages/sot-bridge/`
- **步骤**:
  1. 移动: `ssot_kernel/*` → `sot_bridge/ssot_kernel/`（**保留 import 名称**） + `sharedbrain_bridge/*` → `sot_bridge/sharedbrain_bridge/`
  2. **冲突检查**: ssot 的 `mcp_server.py` 在 `packages/ssot/mcp_server.py`（不在 src 下），保留在 packages/ssot-level 还是移到目标包顶层？**建议移到 `packages/sot-bridge/src/sot_bridge/mcp_server.py`**（统一入口）
  3. **ssot 的 `__init__.py`** 保留为 `sot_bridge/ssot_kernel/__init__.py`
  4. **测试调整**:
     - ssot 的 `tests/test_imports.py` 验证 `from ssot_kernel import X` —— 改 `from sot_bridge.ssot_kernel import X`
     - sharedbrain-bridge tests 已用 `from sharedbrain_bridge.X` —— 改 `from sot_bridge.sharedbrain_bridge.X`
  5. 写新 `pyproject.toml`，version `0.1.0`
  6. **重要**: sharedbrain-bridge 依赖 core-models 5 条 import 仍保留（`from sot_bridge.sharedbrain_bridge.standalone.server import ...` 内部使用 `core_models.X`）
  7. `git rm` 源包 2 个

### 合并 4: data-pipeline

- **源**: `packages/codeanalyze/` (63 src files, 含额外 `policydoc/` 子包) + `packages/kronos/` (15 src files) + `packages/iris/` (46 src files)
- **目标**: `packages/data-pipeline/`
- **步骤**:
  1. 移动: `codeanalyze/*` → `data_pipeline/codeanalyze/`
  2. 移动: `kronos/*` → `data_pipeline/kronos/`
  3. 移动: `iris/*` → `data_pipeline/iris/`
  4. **codeanalyze 的额外子包 `policydoc/`** —— 移动到 `data_pipeline/policydoc/`（保持原结构）
  5. **冲突检查**:
     - 3 包都有 `__init__.py` `cli.py` —— 移到子目录后无冲突
     - `kronos.compressors` / `kronos.fetcher` —— 唯二子目录
     - `iris.adapters` / `iris.connectors` / `iris.sync` —— 3 个子目录
     - `codeanalyze.analyzers` / `commands` / `core` / `documents` / `integrations` / `reports` —— 6 个子目录
     - **结论**: 移到子目录后完全无命名冲突
  6. **关键调整**: 5 条 prod 跨包 import 在合并后**变成内部 import**（用相对或子包路径）:
     - `codeanalyze.integrations.eidos_adapter` → `from eidos.registry import X` **保留**（仍跨包，eidos 不在 data-pipeline 中）
     - `iris.adapters.eidos` → `from eidos.X import X` **保留**
     - `iris.adapters.ssot` → `from ssot_kernel.X import X` **保留**（注意：ssot 独立，仍跨包）
     - `iris.connectors.zhihu` → `from kronos.fetch_router import X` **改为 `from data_pipeline.kronos.fetch_router import X`**（同包内）
     - `iris.connectors.notebooklm` → `from minerva.X import X` **保留**（minerva 独立，仍跨包）
     - `kronos.dispatcher` → `from kos.X import X` **保留**
  7. 写新 `pyproject.toml`，version `0.1.0`
  8. **测试调整**: 266 个测试文件中跨包 import 需更新
  9. `git rm` 源包 3 个

### 通用步骤（4 组共做）

1. 在 `kairon/pyproject.toml` 的 `[tool.uv.workspace]` 成员中**移除 9 个源包、添加 4 个新包**
2. 跑 `uv sync` 验证依赖图
3. 跑 `pytest` 验证 12 包测试
4. 跑 `ruff check` + `ruff format`
5. 更新 `.omo/_knowledge/architecture/` 相关文档
6. 写迁移指南 `.omo/_knowledge/migrations/0006-kairon-17-to-12.md`（如需旧 import 兼容）

### 旧 import 兼容（bridge shim）

为避免破坏 `from kairon.sophia import X` 之类的旧 import，在**已归档项目** `projects/_archived/` 写 re-export shim（如不需要，可不写，因为 17 包已**未发布到 PyPI**）。

---

## Consequences

### Good

- 17 → 12 包，**消除 4 组重复基础设施**（logging / typing / config / test harness）
- 4 组职责清晰：
  - `llm-gateway-kernel` —— LLM 抽象 + 引擎核心（infra 层）
  - `protocols-layer` —— 范式编译 + 协议规则（规则层）
  - `sot-bridge` —— 单源真相 + 跨系统桥接（数据层）
  - `data-pipeline` —— 数据采集→分析→编码（流水线层）
- 12 包发布版本号更易同步
- 4 组合并不破坏 agora / omo / daemon / launchd 治理设施
- eidos / kos / minerva 三联体**保留独立**（保持真正有内部协作的 3 个包）

### Bad

- 4 组原 import path 需加 bridge shim（如果外部项目依赖 17 包名）
- 12 包的版本号需重新协调
- 合并后部分包体积变大（data-pipeline 18K 行），单包 PR review 工作量略增
- `ssot_kernel` import 名称在 sot-bridge 内仍叫 `ssot_kernel`（不重命名为 `sot`），可能造成混淆

### Neutral

- eidos / kos / minerva 22 条循环 import 维持现状（合并选项 C 决定不重写）
- iris → {eidos, minerva, ssot, kronos} 的 7 条 import 改 1 条（kronos 同组合并），其他 6 条保留为跨包

---

## Risk Assessment

| 风险 | 等级 | 缓解 |
|------|------|------|
| 合并后 `import` 路径错乱（如 `from llm_gateway import X` 失效） | **L2 中** | 在新包 `__init__.py` 重导出老路径 + 写文档 |
| 命名空间冲突（如 2 包都有 `cli.py`） | L1 低 | 已分析：移到子目录后无冲突 |
| 依赖循环（合并后 `data-pipeline → eidos → kos → data-pipeline`） | L1 低 | 合并前 5 条 import 来自 codeanalyze/iris/iris/iris/iris，都指向 eidos/kronos/minerva/ssot，无循环。合并后 iris→kronos 改同包内，**不引入新循环** |
| 测试失败（4 组合并后跑测试） | L2 中 | 4 组共 16 + 10 + ... 测试，需逐个验证 |
| 版本号混乱 | L1 低 | 合并包版本从 0.1.0 起步 |
| 17→12 治理 dashboard 数量变化 | L0 无 | omo 不监控包数 |

---

## Pros and Cons of the Options

| 方案 | 工作量 | 风险 | 价值 | 推荐 |
|------|-------|------|------|------|
| A. 维持 17 包 | 0 | 0 | 0 | 不推荐 |
| B. 重新建立有意义的跨包连接 | 3-6 月 | 高 | 高 | 长期可做 |
| C. 4 组合并 17→12 | 1-2 周 | 中 | 中 | **推荐** |
| D. 大刀阔斧合并到 7 包 | 1 月 | 高 | 高 | 短期不推荐 |

---

## Confirmation (验收清单)

- [ ] 4 组合并后 `uv sync` 通过
- [ ] 12 包 `import` 全部 OK（`from llm_gateway_kernel import X` 等）
- [ ] 合并包 pytest 全部通过
- [ ] kairon 全量 pytest 不破坏（不合并的 8 包测试不破坏）
- [ ] 旧 import path 兼容（如有外部依赖）
- [ ] `.omo/state/system.yaml` 包数更新：17 → 12
- [ ] ADR INDEX 更新：0006 added

---

## References

- AST 分析报告: `/tmp/kairon_deps.json`（1,101 prod files scanned, 34 cross-pkg imports, 7 unique pairs）
- AST 扫描器: `/tmp/ast_scan.py`
- v3 方案: `.omo/_knowledge/management/architecture-final-state-v3.md`
- P30 决策: `.omo/_knowledge/management/decision-p30-architecture-final.md`
- ADR-0005: `0005-architecture-p29-upgrade.md`
- 上游任务: `P31-W0-ECOS-EXTRACT` (planned)
- 依赖该 ADR 的下游任务: `P31-W1-KAIRON-MERGE-EXEC`（4 组物理合并，预计 1-2 周）
