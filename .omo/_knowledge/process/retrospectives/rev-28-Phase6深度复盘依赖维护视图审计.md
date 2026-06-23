---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Phase 6 深度复盘 + 依赖自动维护 + 视图完成审计

> **文档编号**: 28 | **前序**: #27 Phase 6 细化方案 | **Phase**: 6 (依赖自动维护 + 视图)
> **时间**: 2026-05-28 | **生成**: 自动审计

---

## 一、完成概览

### Phase 6 任务完成度

| ID | 任务 | 工时 | 状态 | 产出 |
|----|------|------|------|------|
| **6.6** | 健康仪表盘 HTML | 6h | ✅ | `arcnode-evolve --dashboard` → `dashboard.html` (5 Plotly 图表) |
| **6.1** | sniff-deps auto-fix | 4h | ✅ | `arcnode-sniff-deps --reconcile --auto-fix` 3次观察→闭环 |
| **6.2** | 依赖时效性检查 | 4h | ✅ | `arcnode-dep-aging` 7d idle→observation / 30d→OPTIONAL |
| **6.7** | 自评价 Level 2 | 4h | ✅ | 约束违反率/处理速度/时效性/往返时间/宪法年龄 |
| **6.3** | C4 Context 视图 | 3h | ✅ | `arcnode-graph --format c4 --level context` → HTML |
| **6.4** | C4 Container 视图 | 3h | ✅ | `arcnode-graph --format c4 --level container` → HTML |
| **6.5** | Archimate 视图 | 3h | ✅ | `arcnode-graph --format archimate` → 三层分层 HTML |
| **6.8** | Phase 6 复盘 | 2h | ✅ | 本文档 |

### 理论框架

```
Phase 6 三支柱:

依赖自动维护 (X2)                   可视化 (X3)
┌─────────────────┐               ┌──────────────────┐
│ sniff → obs ×3  │               │ C4 Context        │
│   → auto-fix    │               │ C4 Container      │
│ dep-aging:      │               │ C4 Component      │
│ 7d idle→obs     │               │ C4 Code           │
│ 30d→OPTIONAL    │               │ Archimate 3层     │
│                 │               │ Dashboard HTML    │
└──────┬──────────┘               └────────┬─────────┘
       │                                   │
       └─────────── 治理体系 ──────────────┘
                    │
            ├── Level 2 自评价
            │   5 指标量化治理有效性
```

---

## 二、实现细节

### 6.6 健康仪表盘

**仪表盘 5 面板:**

```
┌─ 统计卡片(4) ──────────────────────────────────────────┐
│ 架构熵: 0.0   处理速度: 0%   注册节点: 26   热插拔: 0  │
├──────────────────────┬─────────────────────────────────┤
│ 架构熵趋势(折线图)    │ 类型分布(饼图)                  │
│ ← 30 个数据点        │ ← 7 种 MetaType                 │
├──────────────────────┴─────────────────────────────────┤
│ 节点健康热力图(Plotly Heatmap)                           │
│ ← 26 节点 × 4 维度 (source/port/health/gov)            │
├────────────────────────────────────────────────────────┤
│ 决策追溯时间线(散点图)                                    │
│ ← 最近 50 条治理事件(颜色区分类型)                       │
└────────────────────────────────────────────────────────┘
```

- 使用 Plotly.js CDN（无后端依赖）
- 暗色主题匹配 AAMF 风格
- 响应式布局
- 5 个 interaction 图表（缩放/悬浮/拖拽）

### 6.1 sniff-deps auto-fix

**闭环逻辑:**

```
首次 sniff → 发现未声明连接 → observation (置信度=1)
第二次 sniff → 再次发现 → observation (置信度=2)
第三次 sniff → 再次发现 → observation (置信度=3) → TRIGGERED
                                                   ↓
                                         在 YAML 追加 dependency:
                                           {id: target, dependency: SOFT}
                                                   ↓
                                         写入 governance log:
                                           action: auto-fix, status: resolved
```

**门禁规则:**

| 规则 | 处理 |
|------|------|
| HARD offline × 3 | 只记录不修复（需人工确认） |
| undeclared × 3 | auto-fix 追加 SOFT dependency |
| 置信度 < 3 | 等待下次 sniff |

### 6.2 依赖时效性检查

`arcnode-dep-aging` 读取运行时依赖快照，比对声明的 `depends_on`：

```
检测 13 个空闲依赖:
  agent-runtime → agora (SOFT)
  agent-runtime → kos (SOFT)
  gateway → agora (HARD)
  kronos → kos (HARD)
  ... (共 13 条)

输出:
  dry-run: 13 → 写入 observation
  7d idle: observation (status=idle-dep-warning)
  30d idle: SOFT→OPTIONAL downgrade
```

### 6.7 自评价 Level 2

**5 项量化指标:**

| 指标 | 当前值 | 健康范围 | 状态 |
|------|--------|---------|------|
| 约束违反率 | 0.0% | < 10% | ✅ |
| 观察处理速度 | 0.0% | > 80% | 🔴 (尚无 auto-fix) |
| 治理时效性 | 1081s | < 60s | 🔴 (初始日志间隔大) |
| 往返时间 | N/A | < 7d | ⚠️ (尚无 auto-fix) |
| 宪法时效性 | 0d | < 90d | ✅ |

> 注：处理速度和时效性标志为红是正常现象——系统刚建立，observation 累积中且无 auto-fix 数据。随 cron 运行自然改善。

### 6.3-6.5 C4 + Archimate 视图

**C4 Context 图:** 系统边界图 — 人类架构师 / governance-system / 外部依赖

**C4 Container 图:** 26 节点按 MetaType 分组 + 依赖关系列表

**C4 Component 图:** 每个节点的 provides / depends_on 详情卡片

**C4 Code 图:** 每个节点的 ARCH_NODE.yaml JSON 声明

**Archimate 3 层:**
```
Business Layer     → 宪法修订/热插拔审批/审计/进化引擎
Application Layer  → 12 CLI 工具 (validate→hotswap→evolve→graph)
Technology Layer   → YAML/log/git/launchd/Mac mini
```

---

## 三、验收测试

### Test 1: 健康仪表盘

```bash
arcnode-evolve --dashboard
```

结果: ✅ `dashboard.html` 生成 (14.7KB, 5 Plotly charts)

### Test 2: sniff auto-fix (dry-run)

```bash
arcnode-sniff-deps --reconcile --auto-fix --dry-run
```

结果: ✅ 0 auto-fixes (置信度不足 3, 正确行为)
- reconcile 写入 2 条新 observation
- auto-fix 等待累积

### Test 3: 依赖时效性 (dry-run)

```bash
arcnode-dep-aging --dry-run
```

结果: ✅ 13 个空闲依赖正确识别
- 11 SOFT + 2 HARD
- 均为合理标记（服务在 MBP 运行不在 Mac mini 本地）

### Test 4: C4/Archimate 视图

```bash
arcnode-graph --format c4 --level context
arcnode-graph --format c4 --level container
arcnode-graph --format c4 --level component
arcnode-graph --format c4 --level code
arcnode-graph --format archimate
```

结果: ✅ 5 个 HTML 文件生成
- `c4_context.html` (3.5KB)
- `c4_container.html` (13.5KB)
- `c4_component.html` (28.4KB)
- `c4_code.html` (36.3KB)
- `archimate.html` (5.5KB)

### Test 5: 自评价 Level 2

```bash
arcnode-evolve --self-report
```

结果: ✅ 包含 5 项 Level 2 指标 + 更新健康评分

---

## 四、治理数据

### 脚本层统计

```
~/.hermes/scripts/ 治理脚本量: 14 个 (+2 Phase 6)
├── arcnode-validate        (S1-S8, T1-T7 校验)
├── arcnode-reason          (LLM 软推理)
├── agora-register-node     (注册 7 步)
├── agora-update-node       (更新 4 步)
├── agora-hotswap           (热插拔 7 步)        ← Phase 5
├── arcnode-graph           (8 种格式: mermaid/dot/html/json/c4/archimate)
├── arcnode-drift-check     (漂移检测 + 详细节点数据)
├── arcnode-sniff-deps      (运行时依赖嗅探 + reconcile + auto-fix)
├── arcnode-dep-aging       (依赖时效性检查)      ← Phase 6 NEW
├── arcnode-resolve-review  (unresolved 队列审查)
├── arcnode-report          (完整周报)
├── arcnode-evolve          (进化引擎 + 仪表盘 + Level 2 自评价)
└── schema.py               (共享枚举 + 约束 + 工具函数)
```

### Cron 链 (Phase 6)

```
每日 5:00 arcnode-drift-check         ← 四维漂移 + 嗅探 (no_agent)
每日 6:00 arcnode-evolve              ← 熵趋势 + auto-fix + 自评价 L2 (agent)
每日 6:05 arcnode-sniff-deps          ← 依赖 auto-fix (no_agent)  ← NEW
每日 6:10 arcnode-dep-aging           ← 依赖时效性检查 (no_agent)  ← NEW

周一 7:00 arcnode-graph               ← Mermaid + C4/Archimate 图 (agent)
周一 9:00 arcnode-resolve-review      ← unresolved 队列 (no_agent)
周一 9:30 arcnode-report + evolve     ← 周报 + 仪表盘 + 自评价 (agent)
```

### 治理日志条目数

```
governance.jsonl 条目: 33 (+4 Phase 6)
├── 27 register-node (registered)
├── 2 register-node (blocked by S6)
├── 4 observation (runtime_drift + idle-dep)
└── 0 auto-fix (尚无足够置信度)

SHA256 链: 33 连续校验
```

### 约束覆盖率

| 约束 | 类型 | 代码化 | 验证脚本 |
|------|------|--------|---------|
| S1-S8 | Schema | ✅ | arcnode-validate |
| T1-T7 | Type | ✅ | arcnode-validate --strict |
| R1 | Runtime | ⏭️ | — |
| R2-R6 | Runtime | ✅ | register/hotswap/evolve/aging |
| G1-G5 | Governance | ✅ | 治理日志链 |

---

## 五、架构债务状态

| 债务 | 描述 | 严重度 | 状态 |
|------|------|--------|------|
| D01 | HARD 依赖停服检测（R2 运行时） | P1 | 延续 |
| D02 | 宪法与元模型文档未 100% 同步 | P2 | 延续 |
| D04 | 依赖图自维护 → 已实现 (6.1+6.2) | P1 | ✅ 已修复 |
| **新 D05** | 自评价 L2 的 metrics 需时间积累 | P3 | 日常运维 |

## 六、残余风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| auto-fix 误修复（错误追加 dep） | 低 | 3 次 observation 门槛 + SOFT 类型 |
| 仪表盘 Plotly.js CDN 离线 | 中 | 静态 HTML 仍可阅读文本内容 |
| dep-aging 基于单次 sniff 快照 | 中 | 快照每次 sniff 自动覆盖 |

---

## 七、下一步建议

### 可选优化 Phase 6.5（非必须）

| 任务 | 说明 |
|------|------|
| C4 视图交互增强 | 添加 vis.js 交互式 C4 图 |
| Dashboard 定时导出 | cron 链自动推送到 WeChat |
| 依赖图 SVG 导出 | C4→PNG 自动截图 |

### Phase 7 预备

**L4 自我层** (从 24-AAMF-v2-全面架构补全方案.md):

| ID | 任务 | 说明 |
|----|------|------|
| 7.1 | 元模型变更控制流程 | 版本化元模型 |
| 7.2 | 宪法修订自动化 | proposal→approve→amend 流水线 |
| 7.3 | 架构模式识别 | 从历史数据学习模式 |
| 7.4 | 自进化验证 | 端到端测试 |
| 7.5 | 终极自指测试 | governance-system 替换自身 |

---

> **文档位置**: `~/Documents/学习进化/基建架构/28-Phase6-深度复盘+依赖自动维护+视图审计.md`
> **前序**: #27 Phase 6 细化方案
> **当前**: Phase 6 ✅ → 待确认 Phase 7
