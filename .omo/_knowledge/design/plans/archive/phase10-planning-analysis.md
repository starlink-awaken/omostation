# Phase 10 债务治理需求分析

> 类型: 债务需求分析
> 基线: Phase 9 执行中 (W3 身份/权限 in_progress, W4 gated)
> 前置依赖: Phase 9 完成后方可启动 Phase 10
> 创建日期: 2026-05-31

---

## 一、与 Phase 9 的关系

```
Phase 9 (Workspace Plane Refactor — 边界重构)
├── W1 首次迁移切片           [✅ 已完成]
├── W2 空间注册与所有权        [✅ 已完成]
│    ├── spaces/registry.yaml
│    ├── spaces/system-space.yaml
│    └── .omo/tests 109 passed
├── W3 身份/权限/准入契约      [🔴 执行中]
│    └── P9-W3-IDENTITY-ADMISSION-CONTRACT
├── W4 运营/推广与结项治理     [⏳ Gated]
│
└── 交付基线:
    1. workspace 边界明确 (spaces/data/runtime 根目录就绪)
    2. 身份模型锚定 actor + space membership
    3. 跨 root 授权语言明确
                    ↓
Phase 10 (Debt Governance — 债务治理)
    ├── Wave 1 状态修复 + Quick Wins
    ├── Wave 2 核心债务清理
    └── Wave 3 遗留风险处理

定位: Phase 10 是 Phase 9 完成后的债务治理阶段。
       Phase 9 的边界/身份能力为部分债务 (D1/D4/P1) 的解决创造了更好条件。
       本文件是 Phase 10 planning gate 的输入需求文档。
```

---

## 二、债务全景

所有债务按来源分为 4 个维度：

| 维度 | 计数 | 代表债务 |
|:----:|:----:|---------|
| **跨阶段积压 (D1-D7)** | 7 项 | D2 CI 环境、D3 eu-pricing、D6 Hermes 断链 |
| **产品债务** | 6 项¹ | SharedBrain 零测试、KOS 零消费者、SSOT 覆盖不全 |
| **架构债务** | 4 项 | 硬编码路径、目录非标准、健康分停滞 |
| **治理债务** | 4 项 | Cross-repo 未执行、控制闸门覆盖面窄、运行样本小 |

**总计**: 约 25 项已识别的债务问题。

> ¹ 产品债务实际枚举 P1-P6 共 6 项。DEBT-ANALYSIS.md 中还涉及 4 项 Feature Debt（如 `viz state/graph` 非真实数据、`pipeline.yaml` 仅 JSON 格式）未独立编号，归入产品债务大类统计。

### 时间线视图 — 哪些被反复延期

```
D2 CI 测试环境:     P5 ██→ P6 ██→ P7 ██→ P8 ██→ P9 ██→ ✗ 跨越 5 个阶段未处理*
D3 eu-pricing 测试: P5 ██→ P6 ██→ P7 ██→ P8 ██→ P9 ██→ ✗ 跨越 5 个阶段未处理*
D6 Hermes 断链:     P5 ██→ P6 ██→ P7 ██→ P8 ██→ P9 ██→ ⬤ W2 部分解决，未全清
D4 跨仓库同步:       P5 ██→ P6 ██→ P7 ██→ P8 ██→ P9 ██→ ⬤ 标准有了，未执行
D5 连接器阻塞:       P5 ██→ P6 ██→ P7 ██→ P8 ██→ P9 ██→ ✅ 已处理
D1 KOS 存储耦合:     P5 ██→ P6 ██→ P7 ██→ P8 ██→ P9 ██→ ⬤ 间接解决
SharedBrain 零测试:  发现于 P2 → P3 → P4 → ... → P9 → 至今未处理
```

*Phase 9 为 Workspace Plane Refactor（边界重构），非债务清理阶段，D2/D3 未纳入其范围。但跨越 5 个阶段未被排入任何阶段的计划是事实性风险信号。*

**Phase 10 是 D2/D3 的第 6 次机会。必须解决，不能再退。**

---

## 三、基于 Phase 9 的债务重新评估

| ID | 债务 | 受 Phase 9 影响 | 新评估 |
|:--:|------|:--------------:|--------|
| **D1** | KOS 存储耦合 | 🟢 正向 | Phase 9 的边界模型 (data/ root) 使存储抽象更容易实施 |
| **D2** | CI 测试环境 | 🟡 中性 | 不受边界重构影响，独立处理 |
| **D3** | eu-pricing 测试 | 🟡 中性 | 独立处理 |
| **D4** | Cross-repo 治理 | 🟢 正向 | Phase 9 已有 30+ 文件迁移经验和测试模式可复用 |
| **D5** | 连接器阻塞 | ✅ 已处理 | — |
| **D6** | Hermes 断链 | 🟡 中性 | 独立 |
| **D7** | Orphaned task (blocked_tasks:2) | 🟡 中性 | W1 确认实际数量与影响，归入 W2 治理 |
| **P1** | SharedBrain 零测试 | 🟢 正向 | Phase 9 的身份模型 (actor + space) 有助于明确决策者 |
| **P2-P6** | 其他产品债务 | 🟡 中性 | 独立 |
| **T1-T6** | 技术债务 | 🟡 中性 | 独立 |
| **G1** | 健康分停滞 | 🟢 正向 | Phase 9 完成后应有自然提升 |
| **G2** | 控制闸门 | 🟡 中性 | 独立扩展 |
| **G3** | 运行样本小 | 🟢 正向 | Phase 9 执行中已有更多 dispatch 数据 |
| **G4** | Cross-repo 治理 | 🟢 正向 | 同 D4，受益于 Phase 9 经验 |
| **G5** | plans/README 状态 | 🟡 已修复 | 纳入 Phase 10 首个 Quick Win |

---

## 四、完整债务清单

### 类别 A: 跨阶段积压债务 (D1-D7)

| ID | 债务 | 来源 | 首次识别 | 当前状态 | Phase 9 影响 |
|:--:|------|:----:|:--------:|:--------:|:-----------:|
| **D1** | KOS 存储耦合 gbrain SQLite | Phase 1-6 Review | P2 | ⬤ 间接解决 | 🟢 data/ root 前置条件 |
| **D2** | E2E 测试需运行中服务 | Phase 1-6 Review | P5 | ✗ **未解决, 5 阶段** | 🟡 独立 |
| **D3** | eu-pricing 无独立测试 | Phase 1-6 Review | P5 | ✗ **未解决, 5 阶段** | 🟡 独立 |
| **D4** | 跨仓库治理未对齐 (43 仓库) | Phase 1-6 Review | P5 | ⬤ 部分解决 | 🟢 可复用 P9 经验 |
| **D5** | Apple/WeChat/Family OS blocked | Phase 1-6 Review | P5 | ✅ 已处理 | — |
| **D6** | Hermes 179 断链 | Phase 1-6 Review | P5 | ⬤ 部分解决 (wrapper-first) | 🟡 独立 |
| **D7** | Orphaned task (blocked_tasks:2) | Phase 1-6 Review | P6 | ⬤ 待 W1 确认 → 归 W2 清理 | 🟡 独立 |

### 类别 B: 产品债务

| ID | 债务 | 来源 | 严重度 | 说明 |
|:--:|------|:----:|:-----:|------|
| **P1** | SharedBrain 210 万行零测试 | DEBT-ANALYSIS.md | 🔴 高 | 最大风险点 |
| **P2** | Forge 1,762 LOC 零测试 | DEBT-ANALYSIS.md | 🟠 中 | 用途不明 |
| **P3** | KOS 零消费者 (无项目 import kos) | DEBT-ANALYSIS.md | 🟠 中 | API 未经验证 |
| **P4** | SSOT 元模型覆盖 ~60% | DEBT-ANALYSIS.md | 🟡 低 | 缺 3 种关系类型/4 种推理规则 |
| **P5** | 交互式 `eidos define` 缺失 | DEBT-ANALYSIS.md | 🟡 中 | 用户需手写 JSON |
| **P6** | `viz state/graph` 使用 demitter 数据 | DEBT-ANALYSIS.md | 🟡 中 | 非真实数据 |

### 类别 C: 技术债务

| ID | 债务 | 来源 | 严重度 | 量化 |
|:--:|------|:----:|:-----:|:----:|
| **T1** | KOS 5,263 ruff 问题 | DEBT-ANALYSIS.md | 🟠 高 | 5,263 |
| **T2** | Minerva 955 ruff 问题 | DEBT-ANALYSIS.md | 🟡 中 | 955 |
| **T3** | OntoDerive 1,307 ruff 问题 | DEBT-ANALYSIS.md | 🟡 中 | 1,307 |
| **T4** | PipelineStep.to_cli() 硬编码路径 | DEBT-ANALYSIS.md | 🟡 中 | `/Users/xiamingxing/` |
| **T5** | OntoDerive 非标准目录嵌套 | DEBT-ANALYSIS.md | 🟢 低 | 4 层 `engine/engine/formal/` |
| **T6** | KOS CLI 28 个 subparser 多数 unused | DEBT-ANALYSIS.md | 🟢 低 | 28 命令 |

### 类别 D: 治理债务

| ID | 债务 | 来源 | 严重度 | 说明 |
|:--:|------|:----:|:-----:|------|
| **G1** | 健康分 90 连续 4 个阶段停滞 | Phase 8 分析 | 🟠 高 | P5→P8 均为 90，评分体系可能饱和 |
| **G2** | 控制闸门仅覆盖 2 个维度 | Phase 8 分析 | 🟡 中 | 仅 cost + freshness，缺 resource/security |
| **G3** | 运行数据样本量太小 (9 次 dispatch) | Phase 8 分析 | 🟢 低 | 不足验证控制闸门有效性 |
| **G4** | Cross-repo rollout 有标准未执行 | Phase 8 复盘 | 🟠 中 | W3 做了定义，未落地其他仓库 |
| **G5** | plans/README.md Phase 8 状态标为 active | 实地检查 | 🟢 低 | 应为 completed |

---

## 五、优先级矩阵

```
                    影响程度
              低             中             高
       ┌─────────────────────────────────────
       │   S3 控制面刷新      T1 KOS ruff
       │   S2 README 状态     T2 Minerva ruff
高     │   T5 目录            T3 OntoDerive ruff
       │   T6 CLI 归档        T4 硬编码路径
容     │   G3 样本小          G1 健康分停滞
易     │                     G4 cross-repo
程     ├─────────────────────────────────────
度     │   S1 system.yaml     P1 SharedBrain  D2 CI 环境
       │   G2 闸门窄          P2 Forge         D3 eu-pricing
低     │                      P3 KOS 零消费者  D6 Hermes 断链
       │                      P4 SSOT 覆盖     D4 cross-repo
       │                      D1 KOS 存储耦合
       └─────────────────────────────────────
              Quick wins        Core debt        Debt mountain
               (先做)          (重点规划)       (需独立 phase)
```

---

## 六、Wave 结构

### Wave 1 — 状态修复 + Quick Wins (3-5 天)

**目标**: 修复系统状态不一致，快速清理低风险债务，建立动量

| 优先级 | ID | 债务 | 工作量 | 验证标准 |
|:------:|:--:|------|:-----:|---------|
| 🥇 | **S1** | 系统 SSOT 状态全面修复 | 30 分钟 | system.yaml (current_phase→9, phase9_status, next_milestone 同步) + goals/current.yaml (Phase 8→Phase 9 目标更新) + blocked_tasks 核查 |
| 🥇 | **S2** | `plans/README.md` Phase 8 状态修正 | 10 分钟 | 所有 phase8 条目从 active→completed (原 G5) |
| 🥇 | **S3** | 控制面新鲜度刷新 + 证据链重建 | 1 小时 | freshness_score ≥ 90, decision: allow, 证据链(current.yaml)重新生成 |
| 🥇 | T5 | OntoDerive 目录扁平化 | 2 小时 | ruff 通过 + 测试通过 |
| 🥇 | T6 | KOS CLI 未使用 subparser 归档 | 1 小时 | 命令数从 28 减到 ≤15 |
| 🥇 | G3 | 运行数据采集自动化 | 4 小时 | dispatch/usage/cost 每日自动采集 |
| 🥇 | **D7** | Orphaned task 确认 | 1 小时 | blocked_tasks:2 的来源、状态、影响书面记录 |

### Wave 2 — 核心债务清理 (2-3 周)

**目标**: 消除最严重的 D2/D3/D6/D4/D7 积压

| 优先级 | ID | 债务 | 应对方案 | 验证标准 | Phase 9 加持 |
|:------:|:--:|------|---------|:--------:|:-----------:|
| 🥇 | **D2** | CI 测试环境 | 容器化 Agora + SharedBrain 用于 E2E | E2E 测试可在 CI 中运行 | P9 身份模型做 CI 准入 |
| 🥇 | **D3** | eu-pricing 无独立测试 | 创建独立测试目录 + mock 环境 | 测试通过率 ≥80% | 独立 |
| 🥇 | **D6** | Hermes 断链全清 | 延续 P8 W2 方向，清理剩余 179 条 | 断链数 ≤20 | 独立 |
| 🥇 | **D4** | Cross-repo 治理执行 | 推广 AGENTS.md/CI 到 10+ 仓库 | 10 仓库治理对齐 | P9 迁移经验可复用 |
| 🥈 | G4 | 健康分体系重新校准 | 增加采用率/新鲜度/覆盖率指标 | 可区分 90/92/94 | P9 完成后有新基线 |
| 🥈 | T4 | 硬编码路径替换 | PipelineStep.to_cli()→相对路径/配置 | 无 `/Users/` 硬编码 | 独立 |
| 🥈 | P5 | 交互式 eidos define | CLI 交互式 schema 建模 | 不需手写 JSON | 独立 |
| 🥈 | **D7** | Orphaned task 清理 | W1 确认后执行清理或归档 | blocked_tasks 清零 | 独立 |

### Wave 3 — 遗留风险处理 (2-3 周)

**目标**: 处理长期遗留和低优先级但有价值的债务

| 优先级 | ID | 债务 | 应对方案 | Phase 9 加持 |
|:------:|:--:|------|---------|:-----------:|
| 🥇 | D1 | KOS 存储抽象层 | 正式实施存储抽象接口 + 适配器 | Phase 9 data/ root 是前置条件 |
| 🥇 | P1 | SharedBrain 零测试决策 | 正式确认去留；保留则增加冒烟测试 | P9 权限模型明确决策者 |
| 🥈 | T1 | KOS ruff 清理 | 从 5,263 降到 ≤500 | 独立 |
| 🥈 | T2 | Minerva ruff 清理 | 从 955 降到 ≤200 | 独立 |
| 🥈 | T3 | OntoDerive ruff 清理 | 从 1,307 降到 ≤300 | 独立 |
| 🥉 | G2 | 控制闸门覆盖扩展 | 增加到 resource + security 维度 | 独立 |

---

## 七、红队分析

### R1: "债务清理仍然是喊口号而不是动真格"

**攻击**: D2/D3 已经跨越 5 个阶段未被处理。Phase 10 如果也被拖延，就是第 6 次空头支票。

**严重性**: 🔴 Critical

**缓解**:
- Phase 10 的 GO 条件必须包含 D2 和 D3 被处理
- Wave 2 不给"做不做"的选择，只给"怎么做"的选择
- 如 Wave 1 关闭时 D2/D3 仍未被主动解决 → No-Go
- **新增** 计数器: Phase 9 → 10 入学时 D2/D3 作为强制入学条件

### R2: "清理了债务但没有新的能力增长"

**攻击**: 整个 Phase 10 如果只做清理不做新能力，用户/系统会感觉在倒退。

**严重性**: 🟠 Major

**缓解**:
- 每个 Wave 至少包含 1 个小能力增益（S3 控制面刷新本身是一个新能力）
- Debt cleanup 应与治理增强绑定（清理 D2 的同时得到 CI 自动化的新能力）
- S1/S2/S3 都是"修复即增益"——修复不一致本身就提升了系统可信度

### R3: "技术债务清理无尽头"

**攻击**: KOS ruff 5,263 条 + Minerva 955 条 + OntoDerive 1,307 条——如果不设收敛标准，Wave 3 永无止境。

**严重性**: 🟠 Major

**缓解**:
- ruff 清理设"够好"标准而非"完美"（KOS ≤500, Minerva ≤200, OntoDerive ≤300）
- 每个 Wave 只做量化目标内的量，不追求 0 错误
- 超出目标的部分标记为"Phase ∞ 清理"不做在本阶段

### R4: "Phase 10 是否真的依赖 Phase 9 完成？"

**攻击**: Phase 9 W3 还在执行中，如果 Phase 9 延迟完成，Phase 10 也跟着延迟。

**严重性**: 🟡 Minor

**缓解**:
- Phase 10 的规划文档可提前准备（本文件就是）
- 部分 Wave 1 的 Quick Win（T5/T6/G3）可在 Phase 9 尾声中并行推进（不冲突）
- 但正式启动 gate = Phase 9 完成

---

## 八、Go/No-Go 规则

### Go 条件
1. Phase 9 已完成 (W3 + W4 关闭)
2. 每个 Wave 有可验证的交付标准，不是"研究一下"
3. 债务清理有量化目标（不是"尽量清理"）
4. 每个 Wave 至少包含 1 个小能力增益
5. system.yaml 中 D2/D3 债务不再被标记为"后续阶段处理"

### No-Go 条件
1. Phase 9 未完成 — 不可启动
2. Wave 2 关闭时 D2/D3 仍未解决 — 不能转入 Wave 3
3. 债务清理指标无量化 — 避免"做了但不知道做完了没"
4. 清理过程破坏现有功能

---

## 九、Wave 详细结构

### Wave 1 — 状态修复 + Quick Wins

```
Wave 1: 状态修复 + Quick Wins (3-5 天)
├── S1  系统 SSOT 状态全面修复 (system.yaml + goals/current.yaml + blocked_tasks)
├── S2  plans/README.md Phase 8 状态修正 + Phase 10 条目添加
├── S3  控制面新鲜度刷新 (degrade→allow + 证据链重建)
├── T5  OntoDerive 目录扁平化
├── T6  KOS CLI 未使用 subparser 清理
├── G3  运行数据采集自动化
└── 验证: 所有 quick wins 有可审计的改动记录
```

### Wave 2 — 核心债务清理

```
Wave 2: 核心债务清理 (2-3 周)
├── D2  CI 测试环境容器化
├── D3  eu-pricing 独立测试目录
├── D6  Hermes 断链剩余清理
├── D4  Cross-repo 治理执行 (10 仓库)
├── G4  健康分体系重新校准
├── T4  硬编码路径替换
├── P5  交互式 eidos define
├── D7  Orphaned task 清理 (W1 确认后执行)
└── 验证: D2/D3/D6/D4/D7 全部有可验证的交付物
```

### Wave 3 — 遗留风险处理

```
Wave 3: 遗留风险处理 (2-3 周)
├── D1  KOS 存储抽象层实施
├── P1  SharedBrain 零测试决策 + 冒烟测试
├── P2  Forge 确认去留
├── T1  KOS ruff 清理 (5,263→≤500)
├── T2  Minerva ruff 清理 (955→≤200)
└── T3  OntoDerive ruff 清理 (1,307→≤300)
```

---

## 十、交付标准矩阵

| Wave | 交付物 | 量化标准 | 验证命令 |
|:----:|--------|:--------:|---------|
| W1 | system.yaml + goals/current.yaml 全面同步 | current_phase: 9, phase9_status, goals phase updated, blocked_tasks 核查记录 | `grep "current_phase" state/system.yaml && grep "phase:" goals/current.yaml` |
| W1 | plans/README.md 状态更新 | Phase 8 文档从 active→completed | `grep "phase8.*completed" plans/README.md` |
| W1 | 控制面新鲜度 | freshness_score ≥ 90, decision: allow | `cat _delivery/task-center/control/current.yaml` |
| W1 | OntoDerive 目录规范化 | ruff 通过 | `ruff check packages/ontoderive/` |
| W1 | KOS CLI 精简 | subparser 数 ≤15 | `python kos-cli.py --help \| wc -l` |
| W1 | 数据采集自动运行 | 每日 dispatch 记录 | `_truth/task-center/usage-accounting.yaml` 更新时间 |
| W2 | CI E2E 测试可用 | `make test-e2e` 在 CI 中通过 | CI pipeline green |
| W2 | eu-pricing 测试通过率 | ≥80% | `pytest tests/eu-pricing/ -q` |
| W2 | Hermes 断链数 | ≤20 | 断链扫描脚本 |
| W2 | Cross-repo 对齐 | 10 仓库 AGENTS.md 统一 | 对齐检查脚本 |
| W2 | 健康分区分能力 | 90/92/94 可区分 | 评分模拟测试 |
| W2 | 无硬编码路径 | grep `/Users/` 结果为空（排除注释/文档） | `grep -rn '"/Users/' packages/ --include='*.py'` |
| W2 | D7 Orphaned task 清理 | blocked_tasks 清零 | `grep "blocked_tasks:" state/system.yaml` |
| W3 | KOS 存储抽象 | 接口定义 + 1 适配器 | 抽象层单元测试 |
| W3 | SharedBrain 决策 | 正式记录（保留/迁移/归档） | 决策文档存在 |
| W3 | Forge 得失确认 | 正式记录 | 决策文档存在 |
| W3 | KOS ruff ≤500 | 5,263→≤500 | `ruff check packages/kos/ --statistics` |
| W3 | Minerva ruff ≤200 | 955→≤200 | `ruff check packages/minerva/ --statistics` |
| W3 | OntoDerive ruff ≤300 | 1,307→≤300 | `ruff check packages/ontoderive/ --statistics` |
| W3 | G2 控制闸门 resource+security 维度 | 新增 2 个 gate 维度实现 | `_delivery/task-center/control/current.yaml` 含 resource/security 字段 |

---

## 十一、健康目标

```
Phase 10 健康目标:

当前实际基线: 90.0 (取自 system.yaml)
           ↓
Phase 9 假设完成基线 (预测): 93-95 (W3+W4 关闭后)
  ⚠ G4 健康分体系校准可能改变基线数值——优先校准，再定目标
           ↓
Phase 10 W1 (预测): 95  (S1/S2/S3 修复消除系统不一致)
           ↓
Phase 10 W2 (预测): 97  (D2/D3 解决带来结构性提升)
           ↓
Phase 10 W3 (预测): 98  (D1 解决 + 存储抽象是架构级改善)

关键杠杆:
- D2/D3 解决: 健康分 +2~3
- D1 存储抽象: 健康分 +1~2
- S1/S2/S3 修复: 健康分 +1 (基线可信度提升)
- G4 健康分体系校准: ①优先重新设计评分体系 ②再用新体系评估实际健康分
- G4 拆分为子项: (a) 评分体系设计 (b) 新体系评估

附加建议:
- T1 (KOS ruff) 设 Wave 3 中间目标: 5,263→1,500 (W3 内)，剩余 1,500→≤500 归入 Phase ∞
```

---

## 十二、与现有 OMO 文档的关系

```
Phase 10 规划 (本文件)
    提供债务输入
        ↑
Phase 1-6 Review ───── D1-D7 债务来源
Phase 7 需求分析    ─── D1-D7 优先级建议
Phase 8 分析验证    ─── D1-D7 Phase 8 处理评估 + G1-G5
Phase 9 (执行中)    ─── 边界重构 + 身份模型 (D1/D4/P1 前置条件)
DEBT-ANALYSIS.md    ─── P1-P6 / T1-T6 债务来源
system.yaml         ─── 当前系统状态 (W1 S1 修复目标)
goals/current.yaml  ─── 当前阶段目标 (W1 S1 修复目标)
```

**参考指针**:
- Phase 9 计划: `.omo/plans/phase9-program-plan.md`
- Phase 9 W2 结项: `.omo/summaries/phase9-wave2-closeout.md`
- Phase 9 W3 执行: `.omo/tasks/active/P9-W3-IDENTITY-ADMISSION-CONTRACT.yaml`
- 空间注册: `spaces/registry.yaml`, `spaces/system-space.yaml`
- 债务分析: `.omo/DEBT-ANALYSIS.md`
- 系统状态: `.omo/state/system.yaml`
- 当前目标: `.omo/goals/current.yaml`
- 计划注册表: `.omo/plans/README.md` (W1 S2 在注册表中添加 Phase 10 条目)

---

## 十三、进一步拆分建议

Phase 10 体量大（25 项债务），如果一次性执行困难，可进一步拆分为：

```
Phase 10a: 债务治理 · 前半 (W1 + W2 D2/D3 优先)
    条件: D2/D3 必须解决
Phase 10b: 债务治理 · 后半 (W2 剩余 + W3)
    条件: D2/D3 已在 10a 中解决
```

---

*维护: 2026-05-31 · 基于 Phase 1-6 Review、Phase 8 Analysis、Phase 9 现状、DEBT-ANALYSIS.md 汇总*
