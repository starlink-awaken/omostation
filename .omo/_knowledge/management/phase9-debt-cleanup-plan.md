# Phase 9 债务清理需求分析

> 类型: 债务需求分析
> 基线: Phase 8 已完成 (health 90, 93/95 tasks)
> 当前系统状态: phase_status: completed, next_milestone: Phase 9 planning gate
> 创建日期: 2026-05-31

---

## 一、债务全景

所有债务按来源分为 4 个维度：

| 维度 | 计数 | 代表债务 |
|:----:|:----:|---------|
| **跨阶段积压 (D1-D7)** | 7 项 | D2 CI 环境、D3 eu-pricing、D6 Hermes 断链 |
| **产品债务** | 10 项 | SharedBrain 零测试、KOS 零消费者、SSOT 覆盖不全 |
| **架构债务** | 4 项 | 硬编码路径、目录非标准、健康分停滞 |
| **治理债务** | 4 项 | Cross-repo 未执行、控制闸门覆盖面窄、运行样本小 |

**总计**: 约 25 项已识别的债务问题。

### 时间线视图 — 哪些被反复延期

```
D2 CI 测试环境:     P5 ██→ P6 ██→ P7 ██→ P8 ██→ ✗ 跨越 4 个阶段未处理
D3 eu-pricing 测试: P5 ██→ P6 ██→ P7 ██→ P8 ██→ ✗ 跨越 4 个阶段未处理
D6 Hermes 断链:     P5 ██→ P6 ██→ P7 ██→ P8 ██→ ⬤ W2 部分解决，未全清
D4 跨仓库同步:       P5 ██→ P6 ██→ P7 ██→ P8 ██→ ⬤ 标准有了，未执行
D5 连接器阻塞:       P5 ██→ P6 ██→ P7 ██→ P8 ██→ ✅ W3 已处理
D1 KOS 存储耦合:     P5 ██→ P6 ██→ P7 ██→ P8 ██→ ⬤ 间接解决
D7 Orphaned task:    P5 ██→ P6 ██→ P7 ██→ P8 ██→ ? 状态不明
SharedBrain 零测试:  发现于 P2 → 至今未处理
```

---

## 二、完整债务清单

### 类别 A: 跨阶段积压债务 (D1-D7)

| ID | 债务 | 来源 | 首次识别 | 当前状态 | 为何仍未解决 |
|:--:|------|:----:|:--------:|:--------:|------------|
| **D1** | KOS 存储耦合 gbrain SQLite | Phase 1-6 Review | P2 | ⬤ 间接解决 (P8 W2 可配置 OMO 根) | 存储抽象层未正式实施 |
| **D2** | E2E 测试需运行中服务 | Phase 1-6 Review | P5 | ✗ **未解决** | CI 环境容器化从未排期 |
| **D3** | eu-pricing 无独立测试 | Phase 1-6 Review | P5 | ✗ **未解决** | 测试分离从未排期 |
| **D4** | 跨仓库治理未对齐 (43 仓库) | Phase 1-6 Review | P5 | ⬤ 部分解决 (有标准无执行) | P8 W3 只做了标准定义 |
| **D5** | Apple/WeChat/Family OS blocked | Phase 1-6 Review | P5 | ✅ 已处理 (有核定标准) | — |
| **D6** | Hermes 179 断链 | Phase 1-6 Review | P5 | ⬤ 部分解决 (wrapper-first) | 179 条未全部消除 |
| **D7** | Orphaned task (1 个) | Phase 1-6 Review | P6 | ? 状态不明 | system.yaml 中 blocked_tasks:2 可能包含 |

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

### 类别 D: 治理债务 (Phase 8 识别)

| ID | 债务 | 来源 | 严重度 | 说明 |
|:--:|------|:----:|:-----:|------|
| **G1** | 健康分 90 连续 4 个阶段停滞 | Phase 8 分析 | 🟠 高 | P5→P8 均为 90，评分体系可能饱和 |
| **G2** | 控制闸门仅覆盖 2 个维度 | Phase 8 分析 | 🟡 中 | 仅 cost + freshness，缺 resource/security |
| **G3** | 运行数据样本量太小 (9 次 dispatch) | Phase 8 分析 | 🟢 低 | 不足以验证控制闸门有效性 |
| **G4** | Cross-repo rollout 有标准未执行 | Phase 8 复盘 | 🟠 中 | W3 做了定义，未落地其他仓库 |
| **G5** | plans/README.md Phase 8 状态标为 active | 实地检查 | 🟢 低 | 应为 completed |

---

## 三、优先级矩阵

```
                    影响程度
              低             中             高
       ┌─────────────────────────────────────
       │                      T1 KOS ruff
       │         P5 viz       T2 Minerva ruff
高     │         P6 eidos     T3 OntoDerive ruff
       │         T5 目录       T4 硬编码路径
容     │         G3 样本小     G1 健康分停滞
易     │                     G4 cross-repo
程     ├─────────────────────────────────────
度     │         T6 KOS CLI   P1 SharedBrain  D2 CI 环境
       │         G5 README    P2 Forge         D3 eu-pricing
低     │         G2 闸门窄    P3 KOS 零消费者  D6 Hermes 断链
       │                      P4 SSOT 覆盖     D4 cross-repo
       │                      D1 KOS 存储耦合  D7 orphaned
       └─────────────────────────────────────
              Quick wins        Core debt        Debt mountain
               (先做)          (重点规划)       (需独立 phase)
```

---

## 四、分 Wave 建议

### Wave 1 — Quick Wins (4 项)

**目标**: 快速见成效，建立债务清理的动量

| 优先级 | ID | 债务 | 工作量估计 | 验证标准 |
|:------:|:--:|------|:---------:|---------|
| 🥇 | G5 | plans/README.md 状态更新为 completed | 10 分钟 | plans/README.md Phase 8 条目从 active→completed |
| 🥇 | T5 | OntoDerive 目录扁平化 | 2 小时 | ruff 通过 + 测试通过 |
| 🥇 | T6 | KOS CLI 未使用 subparser 归档 | 1 小时 | 命令数从 28 减到 ≤15 |
| 🥇 | G3 | 运行数据采集自动化 | 4 小时 | dispatch/usage/cost 自动采集脚本 |

### Wave 2 — 核心债务清理 (7 项)

**目标**: 消除最严重的 D2/D3/D6/D4 积压

| 优先级 | ID | 债务 | 应对方案 | 验证标准 |
|:------:|:--:|------|---------|---------|
| 🥇 | **D2** | CI 测试环境 | 容器化 Agora + SharedBrain 用于 E2E 测试 | E2E 测试可在 CI 中运行 |
| 🥇 | **D3** | eu-pricing 无独立测试 | 创建独立测试目录 + mock 环境 | eu-pricing 测试通过率 ≥80% |
| 🥇 | **D6** | Hermes 断链全清 | 延续 P8 W2 方向，清理剩余 179 条断链 | 断链数降至 <20 |
| 🥇 | **D4** | Cross-repo 治理执行 | 将 AGENTS.md/CI 配置推广到 10+ 关键仓库 | 10 仓库治理对齐 |
| 🥈 | G4 | 健康分体系重新校准 | 增加采用率/新鲜度/覆盖率指标 | 健康分可区分 90/92/94 |
| 🥈 | T4 | 硬编码路径替换 | PipelineStep.to_cli() → 相对路径或配置 | 无 `/Users/` 硬编码 |
| 🥈 | P5 | 交互式 eidos define | CLI 交互式 schema 建模 | 不需要手写 JSON |

### Wave 3 — 遗留风险处理 (6 项)

**目标**: 处理长期遗留和低优先级但有价值的债务

| 优先级 | ID | 债务 | 应对方案 |
|:------:|:--:|------|---------|
| 🥇 | D1 | KOS 存储抽象层 | 正式实施存储抽象接口 + 适配器 |
| 🥇 | P1 | SharedBrain 零测试决策 | 正式确认去留；保留则增加冒烟测试 |
| 🥈 | T1 | KOS ruff 清理 | 从 5,263 降到 ≤500 |
| 🥈 | T2 | Minerva ruff 清理 | 从 955 降到 ≤200 |
| 🥈 | T3 | OntoDerive ruff 清理 | 从 1,307 降到 ≤300 |
| 🥉 | G2 | 控制闸门覆盖扩展 | 增加到 resource + security 维度 |

---

## 五、红队分析

### R1: "债务清理仍然是喊口号而不是动真格"

**攻击**: 连续 4 个阶段 D2/D3 都被"后续阶段处理"的借口拖延。Phase 9 如果也这样，就是第 5 次空头支票。

**严重性**: 🔴 Critical

**缓解**:
- Phase 9 的 GO 条件必须包含 D2 和 D3 被处理
- Wave 2 不给"做不做"的选择，只给"怎么做"的选择
- 如 Wave 1 关闭时 D2/D3 仍未被主动解决→No-Go

### R2: "清理了债务但没有新的能力增长"

**攻击**: 整个 Phase 9 如果只做清理不做新能力，用户/系统会感觉在倒退。

**严重性**: 🟠 Major

**缓解**:
- 每个 Wave 至少包含 1 个小能力增益（如 G3 运行数据采集本身也是一个新能力）
- Debt cleanup 应与治理增强绑定（清理 D2 的同时得到 CI 自动化的新能力）

### R3: "技术债务清理无尽头"

**攻击**: KOS ruff 5,263 条、Minerva 955 条、OntoDerive 1,307 条——光 ruff 清理就够做几个月。如果不设收敛标准，Wave 3 永无止境。

**严重性**: 🟠 Major

**缓解**:
- ruff 清理设"够好"标准而非"完美"（KOS ≤500, Minerva ≤200, OntoDerive ≤300）
- 每个 Wave 只做量化目标内的量，不追求 0 错误
- 超出目标的部分标记为"Phase ∞ 清理"不做在本阶段

---

## 六、Go/No-Go 规则

### Go 条件
1. 每个 Wave 有可验证的交付标准，不是"研究一下"
2. 债务清理有量化目标（不是"尽量清理"）
3. 每个 Wave 至少包含 1 个小能力增益

### No-Go 条件
1. Wave 2 关闭时 D2/D3 仍未解决 — 不能转入 Wave 3
2. 债务清理指标无量化 — 避免"做了但不知道做完了没"
3. 清理过程破坏现有功能

---

## 七、Wave 详细结构

### Wave 1 — Quick Wins

```
Wave 1: Quick Wins (3-5 天)
├── G5  plans/README.md 状态更新
├── T5  OntoDerive 目录扁平化
├── T6  KOS CLI 未使用 subparser 清理
├── G3  运行数据采集自动化
└── 验证: 所有 quick wins 有可审计的改动记录
```

### Wave 2 — Core Debt Cleanup

```
Wave 2: Core Debt Cleanup (2-3 周)
├── D2  CI 测试环境容器化
├── D3  eu-pricing 独立测试目录
├── D6  Hermes 断链剩余清理
├── D4  Cross-repo 治理执行 (10 仓库)
├── G4  健康分体系重新校准
├── T4  硬编码路径替换
├── P5  交互式 eidos define
└── 验证: D2/D3/D6/D4 全部有可验证的交付物
```

### Wave 3 — Legacy Risk Treatment

```
Wave 3: Legacy Risk Treatment (2-3 周)
├── D1  KOS 存储抽象层实施
├── P1  SharedBrain 零测试决策 + 冒烟测试
├── P2  Forge 确认去留
├── T1  KOS ruff 清理 (5,263→≤500)
├── T2  Minerva ruff 清理 (955→≤200)
└── T3  OntoDerive ruff 清理 (1,307→≤300)
```

---

## 八、交付标准矩阵

| Wave | 交付物 | 量化标准 | 验证命令 |
|:----:|--------|:--------:|---------|
| W1 | plans/README.md 状态更新 | Phase 8 文档从 active→completed | `grep "phase8.*completed" plans/README.md` |
| W1 | OntoDerive 目录规范化 | ruff 通过 | `ruff check packages/ontoderive/` |
| W1 | KOS CLI 精简 | subparser 数 ≤15 | `python kos-cli.py --help \| wc -l` |
| W1 | 数据采集自动运行 | 每日 dispatch 记录 | `_truth/task-center/usage-accounting.yaml` 更新时间 |
| W2 | CI E2E 测试可用 | `make test-e2e` 在 CI 中通过 | CI pipeline green |
| W2 | eu-pricing 测试通过率 | ≥80% | `pytest tests/eu-pricing/ -q` |
| W2 | Hermes 断链数 | ≤20 | 断链扫描脚本 |
| W2 | Cross-repo 对齐 | 10 仓库 AGENTS.md 统一 | 对齐检查脚本 |
| W2 | 健康分区分能力 | 90/92/94 可区分 | 评分模拟测试 |
| W2 | 无硬编码路径 | grep `/Users/` 结果为空 | `grep -r "/Users/" packages/` |
| W3 | KOS 存储抽象 | 接口定义 + 1 适配器 | 抽象层单元测试 |
| W3 | SharedBrain 决策 | 正式记录（保留/迁移/归档） | 决策文档存在 |
| W3 | Forge 得失确认 | 正式记录 | 决策文档存在 |
| W3 | KOS ruff ≤500 | 5,263→≤500 | `ruff check packages/kos/ --statistics` |
| W3 | Minerva ruff ≤200 | 955→≤200 | `ruff check packages/minerva/ --statistics` |
| W3 | OntoDerive ruff ≤300 | 1,307→≤300 | `ruff check packages/ontoderive/ --statistics` |

---

## 九、与现有 OMO 文档的关系

```
Phase 9 规划 (本文件)
    提供债务输入
        ↑
Phase 1-6 Review ─── D1-D7 债务来源
Phase 7 需求分析    ─── D1-D7 优先级建议
Phase 8 分析验证    ─── D1-D7 Phase 8 处理评估 + 新增 G1-G5
DEBT-ANALYSIS.md    ─── P1-P6 / T1-T6 债务来源
```

**定位**: 本文件是 Phase 9 planning gate 的输入需求文档，不替代现有的 Program Plan。

---

## 十、健康目标

```
Phase 9 健康目标:

当前: 90 → Wave 1 后: 90 → Wave 2 后: 92 → Wave 3 后: 94
                          ↑                    ↑
                    D2/D3 解决可带来        所有主要债务清理 +
                    结构性的健康分提升      健康分体系重新校准
```

---

*维护: 2026-05-31 · 基于 Phase 1-6 Review、Phase 8 Analysis、DEBT-ANALYSIS.md 汇总*
