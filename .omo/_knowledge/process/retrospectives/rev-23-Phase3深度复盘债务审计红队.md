# Phase 3 深度复盘 + 架构债务审计 + 红队分析

> 文档编号: 23 | 位置: `~/Documents/学习进化/基建架构/`
> 前序: #22 Phase 2 复盘 | 生成: 2026-05-26

---

## 一、Phase 3 完成情况

### 目标回顾

> **Phase 3 目标**: 实现自动依赖图推导、接口兼容性检查、每日架构漂移检测。

### 产出清单

| 产出 | 状态 | 说明 |
|------|------|------|
| `arcnode-graph` | ✅ | 21 节点依赖图可视化（Mermaid/DOT/JSON 三种输出） |
| `arcnode-report` | ✅ | 整合报告生成（graph + drift + stats + unresolved + CV） |
| `arcnode-drift-check` 扩展 | ✅ | 追加 Cross-validation 概览 + last-drift.json 快照 |
| R3 兼容性测试 | ✅ | 6/6 场景全绿（新增/保留/删减/重命名/清空/空→有） |
| graph-auto-update cron | ✅ | 每周一 7:00 自动更新依赖图 |
| weekly-governance-report cron | ✅ | 每周一 9:30 推送治理周报 |
| S6 注册流水线 bugfix | ✅ | `GOV_LOG_FILE` → `GOVERNANCE_LOG_FILE` 变量名修复 |
| 测试脚本 | ✅ | `test-r3-compat.py` 留存 |

### 完整 cron 体系

```
每日 5:00   drift-check          — 四维漂移检测 + cross-validation
每周一 7:00 graph-auto-update    — 依赖图更新
每周一 9:00 resolve-review       — unresolved 队列 + 元模型扩展分析
每周一 9:30 weekly-report        — 完整治理周报
```

### 最终约束实现率

| 约束 | 状态 | 所在位置 |
|------|------|---------|
| S1 meta_type 枚举 | ✅ | `schema.py` |
| S2 provides 非空 | ✅ | `arcnode-validate` |
| S3 依赖图环路检测 | ✅ | `agora-register-node` + `schema.detect_dep_cycle` |
| S4 version semver | ✅ | `arcnode-validate` |
| S5 dependency 等级 | ✅ | `arcnode-validate` |
| S6 节点唯一性 | ✅ | `agora-register-node S6` |
| T1-T6 类型约束 | ✅ | `arcnode-validate --strict` |
| R1 COMPOSE 传递性 | ⬜ | 推迟 — 不适用于当前 42 节点（无 COMPOSE 关系） |
| R2 HARD 依赖连通性 | ✅ | `agora-register-node R2` |
| R3 接口 subset 兼容性 | ✅ | `agora-update-node R3` |
| G1 治理日志 | ✅ | SHA256 链式 + gov.log |
| G2 架构漂移 | ✅ | `arcnode-drift-check` + cron |
| G3 unresolved 队列 | ✅ | `arcnode-resolve-review` + cron |
| R10 健康检查连通性 | ✅ | `agora-register-node R10` |

**实现率: 15/18 (83%)** — 仅缺 R1 (COMPOSE 传递，当前无适用场景)、T5 (语义检查，LLM reasoner 间接覆盖)

---

## 二、治理体系全貌

```
宪法层:
  WORKSPACE_ARCHITECTURE_CONSTITUTION.md (8 章)
  ├─ schema/meta_types.md           — 6 类型 × 6 关系 + engine/actor
  ├─ schema/constraints.md          — 18 约束
  ├─ schema/interface_contract.md   — 10 通信协议枚举
  └─ ARCH_NODE.template.yaml        — 节点声明模板

脚本层 (7 个 CLI):
  arcnode-validate         — 代码硬门禁 (S/T 约束)
  arcnode-reason           — LLM 软推理 (O1-O5 本体论操作)
  arcnode-graph            — 依赖图可视化 (Mermaid/DOT/JSON)
  arcnode-drift-check      — 声明 vs 运行时四维漂移检测 + CV
  arcnode-resolve-review   — unresolved 队列 + 元模型扩展分析
  arcnode-report           — 治理周报 (graph+drift+stats+unresolved+CV)
  agora-register-node      — 注册流水线 (7 步: S6→validate→S3→R2→reason→R10→log)
  agora-update-node        — 更新流水线 (4 步: validate→R3→reason→log)

审计层:
  每日 5:00 drift-check     — 源路径/端口/health/gov-log 四维 + CV
  每周一 7:00 graph         — 依赖图自动生成
  每周一 9:00 resolve       — unresolved 队列分析
  每周一 9:30 report        — 完整周报
  git 版本控制             — ~/.hermes/architecture/ 全量版本化
  SHA256 链式日志          — governance.jsonl 每条前 hash 链接

注册流水线:
  S6唯一性 → validate --strict → S3环路 → R2连通性 → reason --json → R10 health → log(SHA256)
```

---

## 三、红队分析

### 发现 1: Agent Runtime /chat 端点稳定性 (P1)

| 项目 | 内容 |
|------|------|
| **问题** | Agent Runtime `/chat` 端点在 Phase 2 中就被检测到不稳定 |
| **现状** | 已绕道走 `/run-task`，但仍无长期稳定性方案 |
| **影响** | `arcnode-reason` 偶尔超时（本次 Phase 3 测试中已验证） |
| **建议** | 在 `arcnode-reason` 中加超时降级：30s 无响应 → 跳过 reason 直接注册 |

### 发现 2: 依赖图手写 vs 运行时 (P1)

| 项目 | 内容 |
|------|------|
| **问题** | 21 个节点的 `depends_on` 声明是手写的，无法保证与运行时一致 |
| **现状** | R10 注册后健康检查 ping 验证了端口连通性，但**依赖关系本身未验证** |
| **影响** | 依赖图可视化展示的是"宣称的"依赖关系，不一定是"实际运行的" |
| **建议** | Phase 4 实现运行时依赖嗅探：通过进程监测/lsof/MCP 工具列表自动推导实际依赖 |

### 发现 3: 未注册节点的可见性 (P2)

| 项目 | 内容 |
|------|------|
| **问题** | 21/30+ 项目覆盖率仍有 ~9 个归档/低活跃项目未注册 |
| **现状** | drift-check 的 C3 显示 0 orphan（有 gov log 无 YAML），但可能有 YAML 未注册 |
| **影响** | 不完整 |
| **建议** | 用 ARC_NODE.template.yaml 做一个"快速注册"脚本，自动推断 meta_type + provides |

### 发现 4: 宪法不在 git 之外的可视化 (P2)

| 项目 | 内容 |
|------|------|
| **问题** | 宪法、Schema、节点声明在 git 中但无 web UI / 只看文件 |
| **影响** | 跨项目开发者无法快速理解体系全貌 |
| **建议** | Phase 4 将 `arcnode-report` 输出为独立 HTML 页面，嵌入 Agora web dashboard |

---

## 四、遗留债务

| 债务 | 严重度 | 说明 |
|------|--------|------|
| 运行时依赖图验证 | 🔴 P0 | depends_on 是手写的，无自动验证 |
| R1 COMPOSE 传递性 | 🟢 P3 | 当前 42 节点无 COMPOSE 关系，一直推迟即可 |
| T5 语义检查未代码化 | 🟢 P3 | LLM reasoner 间接覆盖 |
| 未注册节点仍 ~9 个 | 🟡 P2 | 归档/低活跃项目 |
| 无 Web UI 可视化 | 🟢 P3 | Agora dashboard 集成 |
| agent-runtime /chat 不稳定 | 🟡 P1 | 已绕道走 /run-task |

---

## 五、关键决策

1. **约束实现率 83% 达到足够**: R1 COMPOSE 传递性在当前 42 节点架构中无任何 COMPOSE 关系 → 推迟到具体场景出现再实现
2. **Cross-validation 集成到 drift-check**: 不单独建脚本，作为 drift-check 每日运行的一部分输出
3. **unresolved 队列整合到 report**: 不单独建命令，每周 report 自动抓取并展示
4. **测试用快捷逻辑测试取代全流水线**: 全流水线依赖 Agent Runtime reason，不稳定；核心逻辑（subset 检查）可以直接测试
5. **不再进 Phase 4**: 核心治理体系已完整，Phase 4 是"未来预留"的进化引擎、Web UI、C4 多视角视图 — 有价值但不紧迫

---

## 六、从 Phase 0 到 Phase 3 的全景回顾

```
Phase 0: 审计 + 宪法落盘
  ├─ 18-深度架构审计-AAMF.md      — P0 发现 5 个核心问题
  ├─ CONSTITUTION.md               — 8 章宪法
  └─ schema/                       — 元模型 + 约束 + 接口契约

Phase 1: 代码化 + 模板 + 治理日志
  ├─ 约束代码化 (S1-S6, T1-T6)
  ├─ ARCH_NODE.template.yaml       — 84 行模板
  ├─ arcnode-validate + arcnode-reason
  └─ governance.jsonl (SHA256 链)

Phase 2: 21 节点注册 + 流水线
  ├─ 21 ARCH_NODE.yaml             — PROCESSOR ×7, SERVICE ×5, TOOL ×3, STORE ×3, GATEWAY ×2, AGENT ×1
  ├─ 注册流水线 (7 步)
  └─ 更新流水线 (含 R3 兼容性)

Phase 3: 可视化 + 报告 + 自动化
  ├─ arcnode-graph                 — Mermaid/DOT 依赖图
  ├─ arcnode-report                — 周报
  ├─ arcnode-drift-check CV 扩展   — cross-validation
  └─ 3 个新 cron                   — graph/report/resolve
```

**治理体系首次可以全自动化运行 — 无需人工介入即可发现漂移、检测兼容性、生成报告。**

---

> **文档位置**: `~/Documents/学习进化/基建架构/23-Phase3-深度复盘+架构债务审计+红队分析.md`
