# 债务清理方案设计

> 基于 SystemsThinking 冰山分析和治理债务审计，针对 Phase 16 完成后的五项核心债务的实施方案。
>
> 日期: 2026-06-01 | Phase: 17 | 优先级: P0

---

## 一、债务全景（已识别 5 项）

> 2026-06-02 update: this document remains the historical cleanup design surface. The canonical live debt ledger now lives under `.omo/debt/registry.yaml` and `.omo/debt/items/*.yaml`; `state/system.yaml` should be read as derived summary only.

| ID | 债务项 | 积压时长 | 当前状态 |
|----|--------|---------|---------|
| **SB** | SharedBrain 去留 & 能力拆分 | P2→P16 | 代码已迁至 kairon/sharedbrain-bridge，仅剩 data/db 空壳 |
| **D2** | CI E2E 测试环境 | P5→P16（12 Phase） | `integration.yml` 存在但只跑了 `make test`（等于是单元测试） |
| **D3** | eu-pricing 独立测试 | P5→P16（12 Phase） | 有 tests/ 目录但覆盖率不详 |
| **T0** | 无测试覆盖的包 | — | core-models, shared-lib, sharedbrain-bridge, wksp 零测试 |
| **G1** | 健康分公式失真 | P9→P16 | 97 分掩盖 D2/D3/SB 全未解决的事实 |
| **O1** | Orphaned_tasks blob | — | `state/system.yaml` 中的大段 backlog 列表 |

---

## 二、SharedBrain 拆解方案（SB）

### 现状核实

SharedBrain 物理目录 `/SharedBrain/` **已经没有 Python 代码**（0 个 .py 文件），只剩：

```
SharedBrain/
├── data/db/
│   ├── core/        ← event_store.db, registry.db
│   └── organs/
│       ├── economy/ ← tasks.db
│       └── execution/
```

代码已迁入 kairon：
- `kairon/packages/core-models/` — Entity/Relation/Provenance/KnowledgeGraph 核心模型 ✅
- `kairon/packages/sharedbrain-bridge/` — EU/Immune/Sync 桥接代码（140 行）✅

### 决策：保留核心 + 能力拆分

**保留在 SharedBrain 的内容：**

```
SharedBrain/
├── data/db/          ← SQLite 数据库（event_store, registry, tasks）
├── README.md         ← 说明这是数据持久层，代码在 kairon
```

**拆入 kairon 的内容（已完成，需加固）：**

| 包 | 已存在？ | 加固动作 |
|----|---------|---------|
| `kairon/core-models` | ✅ 已存在 | 加单元测试 |
| `kairon/sharedbrain-bridge` | ✅ 已存在 | 加单元测试 + 完善 cli |
| `kairon/shared-lib` | ✅ 已存在 | 加单元测试 |

### 执行步骤

1. 确认 SharedBrain/AGENTS.md 指向 kairon（不存在，需创建）
2. core-models 加单元测试（核心模型必须有测试保护）
3. sharedbrain-bridge 加测试
4. SharedBrain/README.md 说明架构现状

---

## 三、D2 CI E2E 容器化方案

### 现状

- `tests/integration/` 下有 11 个 test-*.sh 脚本 + 4 个 .py 测试
- `integration.yml` 只跑了 `make test`（单元测试），没跑 E2E
- E2E 需要容器化环境（Postgres + gbrain + agentmesh 等依赖）

### 方案

```
kairon/
├── docker/                ← 新建
│   ├── docker-compose.yml  ← kairon + Postgres + gbrain
│   ├── Dockerfile.kairon   ← kairon 容器
│   └── Dockerfile.gbrain   ← gbrain 容器
├── Makefile
│   └── test-e2e            ← docker compose up + pytest tests/integration/
```

### 执行步骤

1. 创建 `docker/` 目录和 docker-compose.yml
2. 创建 `Makefile` 中 `test-e2e` 目标
3. 确认 `make test-e2e` 在 CI 中独立通过
4. 移除 `integration.yml` 对 `make test` 的冗余调用

### 关键技术决策

- gbrain 需要 Postgres → docker-compose 管理
- agentmesh 只需装 bun 即可，无需容器化
- E2E 测试脚本全部通过 `tests/integration/test-*.sh` 驱动
- 不依赖外部正在运行的服务实例

---

## 四、D3 eu-pricing 独立测试方案

### 现状

- `eu-pricing/` 有 `tests/` 目录（已确认）
- D3 问题：测试可能依赖实际服务，不够独立

### 方案

| 步骤 | 动作 | 预期产出 |
|------|------|---------|
| 1 | 审计现有 eu-pricing 测试 | 覆盖率和依赖分析报告 |
| 2 | 添加 mock 计价服务层 | `MockerPricingService` |
| 3 | 确保不依赖外部服务运行 | 独立 CI 步骤 |
| 4 | pytest 通过率 >= 80% | CI 验证 |

---

## 五、无测试包覆盖计划（T0）

| 包 | 当前测试 | 最低测试目标 | 优先级 |
|----|---------|-------------|-------|
| `core-models` | 0 | 每个模型至少 1 个测试（entity/relation/provenance/knowledge_graph） | P1 |
| `shared-lib` | 0 | 核心依赖函数单元测试 | P1 |
| `sharedbrain-bridge` | 0 | CLI + EU/Immune/Sync 各 1 测试 | P1 |
| `wksp` | 0 | CLI 入口测试 | P2 |

---

## 六、健康分公式重构（G1）

### 当前公式（隐含）

```yaml
health_score = task_completion_rate × 100
# 当前：124/126 = 98.4%
# 显示：97.0（含 phase 完成度因子）
```

### 新公式

```yaml
health_score = task_completion_rate × debt_weight × phase_factor

debt_weight:
  - 1.0  → D2 + D3 + SB 均已解决
  - 0.85 → 部分解决
  - 0.70 → 全部未解决  # 当前应在此区间
```

### 预期效果

- 当前 97.0 × 0.70 ≈ **67.9** — 真实反映系统健康度
- 当 D2/D3/SB 清完后回到正常区间
- 后续可扩展 debt_item 列表

---

## 七、Orphaned_tasks 结构化方案（O1）

### 现状

`state/system.yaml` 中有大段 `orphaned_tasks` blob（待确认具体内容）。

### 方案

```
tasks/registry/           ← 新建
├── INDEX.md              ← 索引
├── orphaned-<id>.yaml    ← 每个 task 独立文件
```

`state/system.yaml` 中只保留指针：

```yaml
orphaned_tasks_ref: ".omo/tasks/registry/INDEX.md"
```

---

## 八、Phase 17 门禁规则

### Entry Gate

```
Phase 17 ENTRY 条件（必须全部满足）:
  ✅ SB-SharedBrain 正式去留决策已记录（human_approval）
  ✅ D2-CI E2E 方案已排期
  ✅ D3-eu-pricing 方案已排期
  ✅ G1-健康分公式已更新
```

### Exit Gate

```
Phase 17 EXIT 条件:
  ✅ SB-能力拆分完成 + 测试基线达标
  ✅ D2-容器化 E2E 在 CI 通过
  ✅ D3-eu-pricing 独立测试通过率 >= 80%
  ✅ T0-4 个 untested 包最低测试基线达标
  ✅ G1-健康分公式已生效
  ✅ O1-orphaned_tasks 结构化完成
```

---

## 九、执行路线图

```
Wave 1 (M17.1) — 治理门禁 + 决策
  ├── SharedBrain 正式去留决策（human_approval ✅）
  ├── Phase 17 GO 门禁规则设定（human_approval ✅）
  ├── 健康分公式重构
  ├── orphaned_tasks 结构化
  └── Blocked tasks triage (C1-C6)

Wave 2 (M17.2) — 基础设施
  ├── CI E2E docker-compose 搭建
  ├── eu-pricing mock 测试层
  ├── core-models 单元测试
  └── sharedbrain-bridge 单元测试

Wave 3 (M17.3) — 验证
  ├── make test-e2e CI 集成
  ├── eu-pricing 独立测试 CI 集成
  ├── shared-lib + wksp 测试
  └── 全量债务验收
```

---

## 十、风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|:----:|:----:|------|
| E2E 容器化复杂度过高 | 中 | 中 | 先做最小可行：仅 kairon + gbrain + Postgres |
| eu-pricing 与外部服务深度耦合 | 中 | 高 | 抽接ロ层加 mock，运行期间依赖注入 |
| 健康分骤降 67 引起恐慌 | 低 | 中 | 前置沟通：这是更准确的度量 |
| SharedBrain data/db 迁移阻力 | 低 | 低 | 仅 symlink 指向即可，无需物理迁移 |

---

## 十一、验收标准

```
[ ] SB — SharedBrain/README.md 说明架构现状
[ ] SB — core-models 测试通过
[ ] SB — sharedbrain-bridge 测试通过
[ ] D2 — make test-e2e 在 CI 独立通过
[ ] D3 — eu-pricing 独立测试通过率 >= 80%
[ ] T0 — 4 个无测试包均有最低测试覆盖
[ ] G1 — 健康分公式含 debt_weight 因子
[ ] O1 — orphaned_tasks 结构化到 tasks/registry/
[ ] GATE — Phase 17 entry/exit 门禁已定义
```

---

*维护: 2026-06-01 · Phase 17 债务清理方案 v1.0*
