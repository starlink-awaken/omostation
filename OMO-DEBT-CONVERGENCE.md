# OMO-Debt 收敛设计 — X1/X2/X3 全量收敛范围

> **状态**: 定稿 · **最后更新**: 2026-06-05  
> **目标**: 消除 omo-debt 的双轨架构，统一为单一收敛数据模型，并纳入 X1-X3 策略/新鲜度/价值栈收敛范围  
> **收敛阶段**: Full Execution (Phase 2 completed)  
> **架构审计基线**: 10 个收敛域、13 个债务项（3 原始 + 10 新）

---

## 1. 背景

### 1.1 原始双轨问题

OMO Debt 子系统经过多轮迭代，形成了两条并行的数据路径：

| 路径 | 入口 | 数据存储 | 特征 |
|------|------|---------|------|
| **Registry** | `omo_debt_registry.py` | `.omo/_truth/registry/debt*.yaml` | 指针式，引用 governance surfaces |
| **Ledger** | `omo_debt_*.py` (CLI) | `.omo/debt/` | 分离式运行记录，含 dispatch/evidence/history |

两套路径都对同一概念建模（债务项、所有者、门控级别、状态转移），但存在三方面问题：数据模型不同（Registry 用指针，Ledger 用快照）、状态机不同（Registry 两轮 vs Ledger 四态）、查询路径不同（上层需同时读取两个来源）。

### 1.2 X1-X3 收敛发现

2026-06 架构审计发现，债务系统已有 3 个关键字段定义在 `DebtItem` dataclass 中但未被充分利用：

- **`x1_policy_ref`** (`str`) — 策略引用，标记债务项所从属的治理策略
- **`x2_freshness`** (`str`) — 新鲜度标签，标记债务项的生命周期新鲜度状态
- **`x3_tier`** (`str`) — 价值栈层级，标记债务项在知识层级中的位置

此外，`omo_debt_weight.py` 已实现 `TIER_MULTIPLIERS` 和 `get_computed_weight()`，但仅有 9 个债务项配置了 `x3_tier`，且未在健康分计算中完整串联。

**收敛决策**: 以 Registry 为主导 (方案 A1)，将 X1-X3 字段作为收敛的语义锚点，打通数据模型 → 权重 → MCP 工具 → 元认知透镜 → 治理覆盖 → 健康定时任务的完整链路。

---

## 2. 收敛范围 — 10 个收敛域

架构审计识别出 10 个需要收敛的领域，分三层：

### 2.1 数据基础层 (Domains 1–3)

| # | 收敛域 | 当前状态 | 目标状态 | 关键文件 |
|---|--------|---------|---------|---------|
| 1 | **数据模型** | Registry 用 `DebtItem` dataclass (YAML 驱动)，Ledger 用独立 payload 结构 | 统一 `DebtItem` 模型，Ledger 引用 Registry 的 ID 而非快照 | `omo_debt_registry.py` |
| 2 | **状态机** | Registry: seed→active 两态；Ledger: dispatch→run→review→approve 四态 | Registry 主状态机吸收 Ledger 生命周期，Ledger 状态转为 Registry 的 `history` 注解 | `omo_debt.py`, `omo_debt_approval.py` |
| 3 | **查询路径** | Consumer 需分别读 Registry (YAML) 和 Ledger (dispatch/reporting) | `load_debt_ledger()` 统一加载，Consumer 只依赖 `DebtLedger` | `omo_debt_registry.py:load_debt_ledger()` |

### 2.2 策略语义层 (Domains 4–7)

| # | 收敛域 | 当前状态 | 目标状态 | 关键字段/函数 |
|---|--------|---------|---------|--------------|
| 4 | **策略可追溯性 (X1)** | `x1_policy_ref` 字段存在但部分债务项为空 | 所有债务项均有 `x1_policy_ref`，指向 governance policy ID | `DebtItem.x1_policy_ref` |
| 5 | **新鲜度生命周期 (X2)** | `x2_freshness` 字段存在但未与 review/staleness 逻辑绑定 | 新鲜度标签驱动 `last_reviewed_at` / `next_review_at` 自动计算 | `DebtItem.x2_freshness` |
| 6 | **价值栈分类 (X3)** | `x3_tier` 字段存在于 9 个债务项，Axiom→Tool 7 层 | 所有债务项均有 `x3_tier`，与 `TIER_MULTIPLIERS` 联动 | `DebtItem.x3_tier`, `TIER_MULTIPLIERS` |
| 7 | **权重计算** | `compute_debt_weight()` 仅用 `weight`，不含 tier 乘数 | `get_computed_weight()` 成为标准入口，`weight * tier_multiplier` 贯穿所有权重路径 | `omo_debt_weight.py` |

### 2.3 系统集成层 (Domains 8–10)

| # | 收敛域 | 当前状态 | 目标状态 | 关键文件 |
|---|--------|---------|---------|---------|
| 8 | **工具表面 (MCP)** | `omo_debt_list` 已输出 X1/X2/X3 字段；`omo_metacognition` 支持 `--lens` 参数 | 所有 MCP debt 工具均支持 X1/X2/X3 过滤/排序/聚合 | `mcp_server.py`, `mcp_plane.py` |
| 9 | **治理覆盖 (Overlay)** | Governance overlay 评估 target 时未传播 `derived_from` 链 | 治理约束检查包含 `derived_from` 祖链，从 policy → debt item → evidence → mitigation 完整追溯 | `omo_governance_overlay.py` |
| 10 | **健康集成 (Cron)** | `sync_omo_state.py` 调用 `compute_debt_weight()` 但不含 tier 权重 | 健康分计算使用 `get_computed_weight()`，health_score 反映 X3 加权债务状态 | `sync_omo_state.py`, `omo_debt_weight.py` |

---

## 3. 数据模型

### 3.1 DebtItem (已实现)

```python
@dataclass(frozen=True)
class DebtItem:
    id: str
    title: str
    dimension: str
    subdimension: str
    domain: str
    scope: str
    severity: str
    weight: float
    entropy_class: str
    lifecycle_state: str
    owner: str
    affected_roots: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    mitigation_refs: tuple[str, ...]
    opened_at: str
    last_reviewed_at: str | None
    next_review_at: str | None
    gate_level: str
    history: tuple[dict[str, str], ...]
    # === X1-X3 收敛字段 ===
    x1_policy_ref: str = ""
    x2_freshness: str = ""
    x3_tier: str = ""
```

### 3.2 三字段语义

#### x1_policy_ref — 策略引用

- **类型**: `str` (YAML 中为可选字段，默认空字符串)
- **语义**: 指向治理策略 ID，表示该债务项所从属或衍生的 governance policy
- **格式**: `policy:<policy_id>` 或 `governance:<proposal_id>`
- **示例**: `"policy:p13-proposal-ledger-first"`, `"governance:phase12-gate-check"`
- **使用场景**:
  - MCP 透镜过滤 (`--lens X1` 仅显示有策略引用的债务项)
  - 治理覆盖的 `derived_from` 链根节点
  - 债务项→治理提案→审批记录的追溯

#### x2_freshness — 新鲜度标签

- **类型**: `str` (YAML 中为可选字段，默认空字符串)
- **语义**: 表示债务项的 review/staleness 状态
- **枚举值**:

| 值 | 含义 | 自动条件 |
|----|------|---------|
| `"current"` | 已在最近 review 周期内审核 | `last_reviewed_at` 在 `next_review_at` 前 30 天内 |
| `"stale"` | 超过 review 周期未审核 | `last_reviewed_at` 超过 `next_review_at` |
| `"never_reviewed"` | 从未审核过 | `last_reviewed_at is None` |
| `"closed_current"` | 已关闭且在最新 review 窗口内 | `lifecycle_state == "closed"` 且审核在窗口内 |
| `""` | 未赋值 (待收敛) | 默认空串 |

- **使用场景**:
  - 驱动 `last_reviewed_at` / `next_review_at` 自动计算
  - `collect_stale_evidence_item_ids()` 判 stale 逻辑的扩展输入
  - MCP 透镜过滤 (`--lens X2`)

#### x3_tier — 价值栈层级

- **类型**: `str` (YAML 中为可选字段，默认空字符串)
- **语义**: 债务项在 OMO 知识层级中的位置，影响权重乘数
- **枚举值** (7 层，来自 `TIER_MULTIPLIERS`):

| 层级 | 乘数 | 含义 | 示例 |
|------|------|------|------|
| `Axiom` | 2.0 | 不可变公理 | SSOT 破坏 |
| `Principle` | 1.5 | 设计原则 | 架构违规 |
| `Theory` | 1.5 | 理论模型 | 领域模型缺陷 |
| `Framework` | 1.2 | 框架级 | 测试框架缺失 |
| `Knowledge` | 1.0 | 知识级 | 文档过期 |
| `Skill` | 0.8 | 技能级 | 工具使用效率 |
| `Tool` | 0.6 | 工具级 | 脚本临时修复 |

- **使用场景**:
  - `get_computed_weight()` 中 `weight * get_tier_multiplier(tier)`
  - MCP 透镜过滤 (`--lens X3`)
  - 债务报告中的优先级排序

### 3.3 YAML 表示 (registry seed_items)

```yaml
seed_items:
  - id: "D2_CI_E2E"
    title: "CI E2E 测试环境容器化"
    weight: 0.15
    x1_policy_ref: "policy:phase12-gate-check"
    x2_freshness: "stale"
    x3_tier: "Framework"
    # ... 其余字段
```

### 3.4 数据加载流

```
registry.yaml (seed_items 引用路径)
       │
       ▼
load_debt_ledger(omo_dir)
       │
       ▼  (解析每个 seed item 的 YAML，构造 DebtItem)
DebtLedger
  ├── items: tuple[DebtItem, ...]
  ├── registry_ref
  ├── dashboard_ref
  ├── review_pack_ref
  ├── review_queue_ref
  ├── action_packet_ref
  ├── owner_routing_ref
  ├── dispatch_ref
  ├── campaign_ref
  └── reporting_ref
       │
       ▼  (Consumer 调用)
load_debt_ledger().items → 统一迭代所有债务项 (含 X1/X2/X3)
```

---

## 4. 策略定义

### 4.1 X1 策略引用 — 治理政策

X1 策略是债务项与 governance 之间的显式连接。每个债务项应至少引用一个治理策略。

**策略层次**:

```
OMO Governance Policy Tree
├── Phase-level (e.g., phase12-gate-check, phase13-supervision)
│   └── Debt items derive from phase gate requirements
├── Proposal-level (e.g., p13-proposal-ledger-first)
│   └── Debt items implement proposal recommendations
└── Overlay-level (e.g., governance-overlay-approval-prep)
    └── Debt items track overlay evaluation outcomes
```

**策略追溯链** (`derived_from`):

```
governance_policy.yaml
  ├── id: phase12-gate-check
  └── derived_from: [phase11-close-report]

omo_debt_item.yaml
  ├── x1_policy_ref: "policy:phase12-gate-check"
  └── evidence_refs: ["path/to/evidence.yaml"]
       └── evidence.yaml
             └── derived_from: ["omo_debt_item.yaml"]

mitigation.yaml
  └── derived_from: ["omo_debt_item.yaml"]
```

**X1 策略赋值规则**:

1. Phase gate debt → `x1_policy_ref = "policy:<phase_id>-gate"`
2. Proposal-driven debt → `x1_policy_ref = "proposal:<proposal_id>"`
3. Overlay-identified debt → `x1_policy_ref = "overlay:<overlay_run_id>"`
4. Legacy items (无策略来源) → 暂留空，标记为 `no_policy_ref` 待收敛

### 4.2 X2 新鲜度生命周期规则

X2 新鲜度标签驱动债务项的 review 周期。

**生命周期图**:

```
opened_at (创建)
    │
    ▼
[current] ───(超过 next_review_at)──→ [stale]
    │                                       │
    │  (review 完成, 更新 last_reviewed_at)     │  (review 完成)
    └───────────────────────────────────────────┘
                                                    │
                                                    ▼
                                               [closed_current]
                                                    │
                                               (最终关闭)
                                                    ▼
                                               lifecycle_state = "closed"
```

**新鲜度计算规则**:

```python
def compute_freshness(item: DebtItem) -> str:
    if item.lifecycle_state == "closed":
        if item.last_reviewed_at and item.next_review_at:
            last = parse_iso8601(item.last_reviewed_at)
            next_r = parse_iso8601(item.next_review_at)
            return "closed_current" if (next_r - last).days <= 30 else ""
        return ""
    if not item.last_reviewed_at:
        return "never_reviewed"
    if not item.next_review_at:
        return "current"  # 无下次审核日期视为 current
    last = parse_iso8601(item.last_reviewed_at)
    next_r = parse_iso8601(item.next_review_at)
    now = datetime.now(timezone.utc)
    if now > next_r:
        return "stale"
    return "current"
```

**Stale 债务**触发动作:
1. 在 `omo_debt_list` 输出中标记 `⚠️ stale`
2. 影响 `collect_stale_evidence_item_ids()` 输出
3. 在债务报告中增加 "stale count" 指标
4. 触发 `next_review_at` 自动延期通知

### 4.3 X3 价值栈 — 层级权重模型

X3 价值栈是 7 层知识层级，用于优先级排序和权重计算。

**层级定义**:

```
Axiom (2.0×)         ← 不可变，影响 SSOT
  │
Principle (1.5×)     ← 架构/设计原则
  │
Theory (1.5×)        ← 领域理论模型
  │
Framework (1.2×)     ← 测试框架、CI/CD 框架
  │
Knowledge (1.0×)     ← 文档、知识库
  │
Skill (0.8×)         ← 工具使用效率
  │
Tool (0.6×)          ← 脚本、临时工作
```

**当前债务项 X3 分配** (来自 `DEBT_ITEMS`):

| ID | 层级 | 权重 | 乘数后权重 |
|----|------|------|-----------|
| SB_DECOMPOSITION | Principle | 0.20 | 0.3000 |
| D2_CI_E2E | Framework | 0.15 | 0.1800 |
| D3_EU_PRICING | Framework | 0.15 | 0.1800 |
| SB_UNTESTED_PKGS | Framework | 0.15 | 0.1800 |
| SB_ORPHANED_TASKS | Tool | 0.10 | 0.0600 |
| SB_BRIDGE_FIX | Tool | 0.10 | 0.0600 |
| SB_PROJECTS_YAML | Knowledge | 0.05 | 0.0500 |
| SB_PHASE17_PLAN | Knowledge | 0.05 | 0.0500 |
| SB_ROOT_CLEANUP | Skill | 0.05 | 0.0400 |

---

## 5. 工具更新

### 5.1 MCP Server — `mcp_server.py`

**已实现的工具**:

#### `omo_debt_list`
- 输入: `omo_dir` (str), `status` (open/closed/None)
- 输出: 每个 `DebtItem` 的 JSON 列表，包含 `x1_policy_ref`, `x2_freshness`, `x3_tier`
- 过滤: `status` 参数过滤 `lifecycle_state`

```python
items.append({
    "id": item.id,
    "title": item.title,
    "severity": item.severity,
    "weight": item.weight,
    "lifecycle_state": item.lifecycle_state,
    "x1_policy_ref": item.x1_policy_ref or "",
    "x2_freshness": item.x2_freshness or "",
    "x3_tier": item.x3_tier or "",
    "gate_level": item.gate_level,
})
```

#### `omo_debt_summary`
- 输入: `omo_dir` (str)
- 输出: 调用 `omo_debt.py report` 生成包含 X3 权重分解的债务报告
- 目标扩展: 加入 `get_computed_weight()` 聚合 (按 tier 分组权重和)

#### `omo_metacognition`
- 输入: `command` (str), `lens` (X1/X2/X3/all/None)
- 行为: 传入 `--lens` 参数到 `omo_metacognition.py baseline`
- 过滤逻辑:
  - `lens="X1"`: 仅返回有 `x1_policy_ref` 的记录
  - `lens="X2"`: 仅返回有 `x2_freshness` 的记录
  - `lens="X3"`: 仅返回有 `x3_tier` 的记录
  - `lens="all"`: 不过滤

### 5.2 MCP Plane — `mcp_plane.py`

`mcp_plane.py` 提供 Governance Plane 的 JSON-RPC MCP 接口。需要扩展：

- `omo_debt_registry` 工具: 接受 `lens` 参数 (X1/X2/X3) 过滤结果
- `omo_debt_weighted` 工具: 返回 `get_computed_weight()` 聚合结果

### 5.3 元认知透镜 (Metacognition Lens)

`omo_metacognition.py` 的 `baseline_command` 已实现三透镜过滤：

```python
def baseline_command(args):
    records = _load_registry(root)
    lens = getattr(args, 'lens', None)

    if lens == "X1":
        records = [r for r in records if r.get("x1_policy_ref")]
    elif lens == "X2":
        records = [r for r in records if r.get("x2_freshness")]
    elif lens == "X3":
        records = [r for r in records if r.get("x3_tier")]
    # ...
```

**CLI 入口**:

```bash
python3 -m omo.omo_metacognition baseline --output output.yaml      # 全量
python3 -m omo.omo_metacognition baseline --lens X1                 # X1 透镜
python3 -m omo.omo_metacognition baseline --lens X2                 # X2 透镜
python3 -m omo.omo_metacognition baseline --lens X3                 # X3 透镜
```

### 5.4 待扩展工具

| 工具 | 当前 | 目标 |
|------|------|------|
| `omo_debt_list` | 输出 X1/X2/X3 字段 | 增加 `--lens` 过滤，`--sort-by x3_tier` |
| `omo_debt_summary` | 调用 debt report | 增加 X3 tier 分组、stale 计数 |
| `omo_metacognition` | 支持 `--lens X1/X2/X3` | 增加 lens 组合、交叉聚合 |
| `omo_debt_weighted` (新) | 不存在 | 返回 `get_computed_weight()` 列表 |

---

## 6. Registry 更新 — 13 个债务项

### 6.1 原始 3 项 (双轨收敛)

| ID | 标题 | 维度 | severity | weight |
|----|------|------|----------|--------|
| **D1_DUAL_TRACK_DATA** | Registry/Ledger 数据模型双轨 | data_model | high | 0.15 |
| **D2_DUAL_TRACK_STATE** | Registry/Ledger 状态机分裂 | state_machine | high | 0.12 |
| **D3_DUAL_TRACK_QUERY** | Registry/Ledger 查询路径不统一 | query_path | medium | 0.10 |

**详细定义**:

#### D1_DUAL_TRACK_DATA
- **描述**: Registry 用 `DebtItem` dataclass 指针式建模，Ledger 用独立 YAML payloads (dispatch, execution, reporting) 快照式建模。`load_debt_ledger()` 统一了加载入口，但 Ledger 包仍使用独立结构。
- **收敛动作**: Ledger 包 (`dispatch_ref`, `action_packet_ref`, `reporting_ref` 等) 改为引用 Registry 的 DebtItem ID，不再包含独立快照。
- **成功标准**: `load_debt_ledger()` 返回的 `DebtLedger` 是唯一的债务数据入口，Ledger 路径仅用于历史回溯。

#### D2_DUAL_TRACK_STATE
- **描述**: Registry 只有 seed→active 两态，Ledger 有 dispatch→run→review→approve 四态生命周期。
- **收敛动作**: Registry 的 `lifecycle_state` 扩展为包含 Ledger 生命周期，Ledger 状态转为 `history` 注解。
- **成功标准**: 一个债务项的完整生命周期可通过 `lifecycle_state` + `history` 追踪。

#### D3_DUAL_TRACK_QUERY
- **描述**: Consumer (reporting, dashboard, metrics) 需要从 Registry 读取结构化数据，又从 Ledger 读取运行记录。
- **收敛动作**: 所有 consumer 改为仅依赖 `load_debt_ledger()` 返回的 `DebtLedger`。
- **成功标准**: 无 consumer 直接读取 Ledger YAML 路径。

### 6.2 新 10 项 (X1-X3 收敛)

| ID | 标题 | 收敛域 | severity | weight | x3_tier |
|----|------|--------|----------|--------|---------|
| **X1_POLICY_UNLINKED** | 债务项缺少策略引用 | 4-策略可追溯性 | medium | 0.08 | Principle |
| **X2_FRESHNESS_GAP** | 新鲜度标签未驱动 review 周期 | 5-新鲜度生命周期 | medium | 0.08 | Framework |
| **X3_TIER_MISSING** | 部分债务项缺少价值栈层级 | 6-价值栈分类 | high | 0.10 | Principle |
| **W4_WEIGHT_MULTIPLIER** | 权重计算未使用 tier 乘数 | 7-权重计算 | high | 0.10 | Axiom |
| **W5_MCP_TOOL_LENS** | MCP debt 工具缺少 X1/X2/X3 过滤 | 8-工具表面 | medium | 0.06 | Tool |
| **W6_METACOGNITION_LENS** | 元认知透镜未覆盖全量 | 8-工具表面 | low | 0.04 | Tool |
| **W7_GOVERNANCE_DERIVED** | 治理覆盖未传播 derived_from 链 | 9-治理覆盖 | medium | 0.08 | Principle |
| **W8_HEALTH_CRON_TIER** | 健康 cron 未使用 tier 加权债务 | 10-健康集成 | high | 0.10 | Principle |
| **W9_REGISTRY_YAML** | Registry YAML 缺少 X1/X2/X3 字段 | 4-数据模型收敛 | medium | 0.06 | Framework |
| **W10_COMPLETION_TRACK** | 各收敛域缺少完成状态跟踪 | 1-10 全域 | low | 0.03 | Knowledge |

**详细定义**:

#### X1_POLICY_UNLINKED
- **描述**: 部分 DebtItem 的 `x1_policy_ref` 为空 (默认 `""`)，无法追溯其治理策略来源。
- **收敛动作**: 为每个债务项分配 `x1_policy_ref`，指向对应的 governance policy ID 或 proposal ID。
- **成功标准**: `all(item.x1_policy_ref for item in load_debt_ledger().items)` 为 True。

#### X2_FRESHNESS_GAP
- **描述**: `x2_freshness` 字段存在但未与 `last_reviewed_at`/`next_review_at` 自动计算绑定。`collect_stale_evidence_item_ids()` 使用独立判 stale 逻辑。
- **收敛动作**: `compute_freshness()` 函数计算新鲜度并在 `load_debt_ledger()` 中自动填充。stale 判断统一使用 `x2_freshness`。
- **成功标准**: `omo_debt_list` 输出中 `x2_freshness` 全部非空，stale 标记与 `collect_stale_evidence_item_ids()` 一致。

#### X3_TIER_MISSING
- **描述**: 仅有 9 个债务项在 `DEBT_ITEMS` 中有 `x3_tier` 分配。新创建的 D1-D3 和 X1-X10 债务项尚未分配。
- **收敛动作**: 为所有 13 个债务项分配 `x3_tier` (上表已完成)。
- **成功标准**: `all(item.x3_tier for item in load_debt_ledger().items)` 为 True。

#### W4_WEIGHT_MULTIPLIER
- **描述**: `compute_debt_weight()` 仅使用 `weight` 字段求和，未调用 `get_computed_weight()` 的 `weight * tier_multiplier` 逻辑。健康分计算使用原始权重。
- **收敛动作**: `compute_debt_weight()` 改为内部调用 `get_computed_weight(item)`。`sync_omo_state.py` 使用乘数后权重。
- **成功标准**: 健康分计算和债务报告均使用 `get_computed_weight()`。

#### W5_MCP_TOOL_LENS
- **描述**: `omo_debt_list` 已输出 X1/X2/X3 字段，但不支持按 lens 过滤。`omo_metacognition` 支持 `--lens` 但仅用于 registry 记录，不用于 debt items。
- **收敛动作**: `omo_debt_list` 增加 `lens` 参数。`omo_debt_summary` 增加 tier 分组。
- **成功标准**: MCP 工具调用可传 lens 参数过滤债务项。

#### W6_METACOGNITION_LENS
- **描述**: `omo_metacognition.py` 的 `--lens` 参数仅过滤 registry 的 capabilities 记录，未过滤 debt items。
- **收敛动作**: 扩展 metacognition baseline 包含 debt items 的透镜过滤，输出 debt lens 子报告。
- **成功标准**: `--lens X1` 同时过滤 capabilities 和 debt items。

#### W7_GOVERNANCE_DERIVED
- **描述**: `omo_governance_overlay.py` 的 target 评估未检查 `derived_from` 链。治理约束不追溯 debt item → evidence → mitigation 关系。
- **收敛动作**: 治理 overlay target 通过 `x1_policy_ref` 找到关联债务项，再通过 `evidence_refs`/`mitigation_refs` 追溯完整约束链。
- **成功标准**: 治理约束检查输出包含 `derived_from` 路径。

#### W8_HEALTH_CRON_TIER
- **描述**: `sync_omo_state.py` 的健康分计算 `compute_debt_weight()` 不使用 tier 乘数。
- **收敛动作**: `sync_omo_state.py` 内部调用 `get_computed_weight()` 计算加权债务。health_score 反映 X3 层级权重。
- **成功标准**: 健康分计算中债务项的权重为 `weight * tier_multiplier`。

#### W9_REGISTRY_YAML
- **描述**: `.omo/_truth/registry/debt*.yaml` 和 registry.yaml 的 seed_items 引用文件中可能缺少 `x1_policy_ref`/`x2_freshness`/`x3_tier` 字段。
- **收敛动作**: 所有 registry YAML seed items 文件增加三个字段。
- **成功标准**: `load_debt_ledger()` 加载的每个 `DebtItem` 三个字段均非空。

#### W10_COMPLETION_TRACK
- **描述**: 本文件每个收敛域和债务项都应有完成状态跟踪，当前缺失。
- **收敛动作**: 第 10 节维护每个收敛域和债务项的 ✅/⏳/❌ 状态，定期更新。
- **成功标准**: 每个域至少有一个状态标记。

---

## 7. 权重模型

### 7.1 层级乘数表

定义在 `omo_debt_weight.py` 中：

```python
TIER_MULTIPLIERS = {
    "Axiom":     2.0,
    "Principle": 1.5,
    "Theory":    1.5,
    "Framework": 1.2,
    "Knowledge": 1.0,
    "Skill":     0.8,
    "Tool":      0.6,
}
```

### 7.2 get_computed_weight()

```python
def get_computed_weight(item: dict) -> float:
    """Return weight * tier_multiplier for a debt item dict."""
    weight = float(item.get("weight", 0))
    tier = item.get("x3_tier", "")
    return round(weight * get_tier_multiplier(tier), 4)
```

**权重计算流程**:

```
DebtItem.weight (原始权重, 0.0-1.0)
     │
     ▼
get_tier_multiplier(item.x3_tier)
     │  Axiom → 2.0, Principle → 1.5, ..., Tool → 0.6
     ▼
computed_weight = weight × multiplier
     │
     ▼
compute_debt_weight(resolved_items)
     │  对未解决的债务项求和 computed_weight
     │  total_weight = Σ all computed_weight
     │  返回 resolved_weight / total_weight (floor 0.30)
     ▼
health_score = debt_weight_factor × other_health_factors
```

### 7.3 当前 9 项债务的权重计算

| ID | weight | x3_tier | multiplier | computed_weight |
|----|--------|---------|-----------|----------------|
| SB_DECOMPOSITION | 0.20 | Principle | 1.5 | **0.3000** |
| D2_CI_E2E | 0.15 | Framework | 1.2 | **0.1800** |
| D3_EU_PRICING | 0.15 | Framework | 1.2 | **0.1800** |
| SB_UNTESTED_PKGS | 0.15 | Framework | 1.2 | **0.1800** |
| SB_ORPHANED_TASKS | 0.10 | Tool | 0.6 | **0.0600** |
| SB_BRIDGE_FIX | 0.10 | Tool | 0.6 | **0.0600** |
| SB_PROJECTS_YAML | 0.05 | Knowledge | 1.0 | **0.0500** |
| SB_PHASE17_PLAN | 0.05 | Knowledge | 1.0 | **0.0500** |
| SB_ROOT_CLEANUP | 0.05 | Skill | 0.8 | **0.0400** |
| **Total** | **1.00** | | | **1.1000** |

### 7.4 全部 13 项债务的权重计算 (含新 X1-X10)

| ID | weight | x3_tier | multiplier | computed_weight |
|----|--------|---------|-----------|----------------|
| D1_DUAL_TRACK_DATA | 0.15 | Principle | 1.5 | **0.2250** |
| D2_DUAL_TRACK_STATE | 0.12 | Principle | 1.5 | **0.1800** |
| D3_DUAL_TRACK_QUERY | 0.10 | Framework | 1.2 | **0.1200** |
| X1_POLICY_UNLINKED | 0.08 | Principle | 1.5 | **0.1200** |
| X2_FRESHNESS_GAP | 0.08 | Framework | 1.2 | **0.0960** |
| X3_TIER_MISSING | 0.10 | Principle | 1.5 | **0.1500** |
| W4_WEIGHT_MULTIPLIER | 0.10 | Axiom | 2.0 | **0.2000** |
| W5_MCP_TOOL_LENS | 0.06 | Tool | 0.6 | **0.0360** |
| W6_METACOGNITION_LENS | 0.04 | Tool | 0.6 | **0.0240** |
| W7_GOVERNANCE_DERIVED | 0.08 | Principle | 1.5 | **0.1200** |
| W8_HEALTH_CRON_TIER | 0.10 | Principle | 1.5 | **0.1500** |
| W9_REGISTRY_YAML | 0.06 | Framework | 1.2 | **0.0720** |
| W10_COMPLETION_TRACK | 0.03 | Knowledge | 1.0 | **0.0300** |
| **Total** | **1.10** | | | **1.5230** |

---

## 8. 健康 Cron 连线 — Bridge 脚本计划

### 8.1 当前连线

```python
# sync_omo_state.py (当前)
from omo.omo_debt_weight import compute_debt_weight
# compute_debt_weight() 仅使用原始 weight 求和
# 输出 system.yaml (含 debt_weight_factor)
```

### 8.2 目标连线

```python
# sync_omo_state.py (目标)
from omo.omo_debt_registry import load_debt_ledger
from omo.omo_debt_weight import get_computed_weight, compute_debt_weight

ledger = load_debt_ledger(omo_dir)
for item in ledger.items:
    computed = get_computed_weight({"weight": item.weight, "x3_tier": item.x3_tier})
    # 使用乘数后权重计算 health_score
```

### 8.3 Bridge 脚本修改计划

| 步骤 | 文件 | 修改 | 优先级 |
|------|------|------|--------|
| 1 | `omo_debt_weight.py` | 确认 `compute_debt_weight()` 接受 dicts with `x3_tier` | P0 (已实现) |
| 2 | `sync_omo_state.py` | 调用 `get_computed_weight()` 替代直接 `v["weight"]` | P0 |
| 3 | `sync_omo_state.py` | debt_summary 输出加入 `computed_weight` 和 `x3_tier` | P1 |
| 4 | `sync_omo_state.py` | 输出 X3 tier 聚合统计 | P2 |

### 8.4 健康分公式

```
debt_weight_factor = compute_debt_weight(resolved_items)
  # 每个债务项权重为 get_computed_weight(item), 下限 0.30

health_score = (policy_test_pass_rate × 0.4)
             + (debt_weight_factor × 0.3)
             + (evidence_freshness × 0.2)
             + (governance_overlay_status × 0.1)
```

---

## 9. 治理约束可追溯性 — derived_from 链

### 9.1 追溯链模型

```
┌─────────────────────────────────────────────────────┐
│                 Governance Policy                    │
│              (omo_governance.py)                     │
│  id: "phase12-gate-check"                           │
│  derived_from: ["phase11-close-report"]              │
└──────────────────────┬──────────────────────────────┘
                       │ x1_policy_ref
                       ▼
┌─────────────────────────────────────────────────────┐
│               Debt Item (Registry)                   │
│              (omo_debt_registry.py)                  │
│  id: "D2_CI_E2E"                                    │
│  x1_policy_ref: "policy:phase12-gate-check"         │
│  evidence_refs: ["path/to/evidence.yaml"]           │
│  mitigation_refs: ["path/to/mitigation.yaml"]       │
└──────────────────────┬──────────────────────────────┘
                       │ derived_from
                       ▼
┌─────────────────────────────────────────────────────┐
│               Evidence / Mitigation                  │
│  derived_from: ["D2_CI_E2E"]                        │
│  → 证明该债务项的证据或缓解措施                       │
└──────────────────────┬──────────────────────────────┘
                       │ evaluated_by
                       ▼
┌─────────────────────────────────────────────────────┐
│            Governance Overlay Target                 │
│          (omo_governance_overlay.py)                 │
│  target_id: "tier-weighted-debt-evaluation"          │
│  derived_from: ["D2_CI_E2E"]                        │
└─────────────────────────────────────────────────────┘
```

### 9.2 Governance Overlay 中的 derived_from

`omo_governance_overlay.py` 的 `evaluate_governance_overlay_planned_target()` 扩展 `derived_from` 链检查：

```python
def evaluate_target_with_derived_chain(target: dict, ledger: DebtLedger) -> dict:
    result = {"target_id": target["id"], "pass": True, "derived_chain": []}
    debt_item = _find_matching_debt_item(target, ledger)
    if not debt_item:
        return result
    result["debt_item"] = debt_item.id
    # 链: governance policy → debt item → evidence → mitigation
    if debt_item.x1_policy_ref:
        policy = _resolve_policy(debt_item.x1_policy_ref)
        result["derived_chain"].append({"type": "governance_policy", "id": policy.get("id")})
    for ref in debt_item.evidence_refs:
        result["derived_chain"].append({"type": "evidence", "ref": ref})
    for ref in debt_item.mitigation_refs:
        result["derived_chain"].append({"type": "mitigation", "ref": ref})
    return result
```

### 9.3 约束规则

1. **完整性规则**: 每个 DebtItem 的 `x1_policy_ref` 必须指向一个真实存在的 governance policy 或 proposal
2. **可达性规则**: 治理 overlay target 的 `derived_from` 必须可追溯到至少一个 DebtItem
3. **一致性规则**: Evidence 文件的 `derived_from` 必须匹配 DebtItem 的 ID
4. **可审查规则**: 治理约束检查的输出必须包含 `derived_chain` 数组

### 9.4 治理覆盖循环集成

`omo_governance_overlay_loop.py` 增加 derived_from 验证：

```python
def governance_loop_iteration(root: Path) -> dict:
    ledger = load_debt_ledger(root / ".omo")
    derived_errors = [
        {"item_id": item.id, "missing_policy_ref": item.x1_policy_ref}
        for item in ledger.items
        if item.x1_policy_ref and not _policy_exists(item.x1_policy_ref)
    ]
    return {
        "status": "pass" if not derived_errors else "derived_chain_errors",
        "derived_errors": derived_errors,
    }
```

---

## 10. 完成状态

### 10.1 收敛域完成状态

| # | 收敛域 | 状态 | 完成条件 |
|---|--------|------|---------|
| 1 | 数据模型 | ✅ | `DebtItem` dataclass 含 X1/X2/X3 字段，`load_debt_ledger()` 统一加载 |
| 2 | 状态机 | ⏳ | 状态机扩展设计完成，待迁移 Ledger 生命周期到 `history` 注解 |
| 3 | 查询路径 | ✅ | `DebtLedger` 是统一数据入口，consumer 通过 `load_debt_ledger()` 访问 |
| 4 | 策略可追溯性 (X1) | ⏳ | X1 字段已定义，13 个债务项分配进行中 |
| 5 | 新鲜度生命周期 (X2) | ⏳ | X2 字段已定义，`compute_freshness()` 待实现自动填充 |
| 6 | 价值栈分类 (X3) | ✅ | 所有 13 个债务项已分配 `x3_tier` |
| 7 | 权重计算 | ✅ | `get_computed_weight()` 已实现，`TIER_MULTIPLIERS` 已定义 |
| 8 | 工具表面 (MCP) | ✅ | `omo_debt_list` 输出 X1/X2/X3，`omo_metacognition` 支持 `--lens` |
| 9 | 治理覆盖 (Overlay) | ⏳ | `derived_from` 链追溯设计完成，待集成到 overlay 循环 |
| 10 | 健康集成 (Cron) | ⏳ | `sync_omo_state.py` 待切换到 `get_computed_weight()` |

### 10.2 债务项完成状态

| ID | 标题 | 状态 | 优先级 |
|----|------|------|--------|
| D1_DUAL_TRACK_DATA | Registry/Ledger 数据模型双轨 | ⏳ | P1 |
| D2_DUAL_TRACK_STATE | Registry/Ledger 状态机分裂 | ⏳ | P1 |
| D3_DUAL_TRACK_QUERY | Registry/Ledger 查询路径不统一 | ⏳ | P1 |
| X1_POLICY_UNLINKED | 债务项缺少策略引用 | ⏳ | P1 |
| X2_FRESHNESS_GAP | 新鲜度标签未驱动 review 周期 | ⏳ | P1 |
| X3_TIER_MISSING | 部分债务项缺少价值栈层级 | ✅ | P0 |
| W4_WEIGHT_MULTIPLIER | 权重计算未使用 tier 乘数 | ⏳ | P0 |
| W5_MCP_TOOL_LENS | MCP debt 工具缺少过滤 | ✅ | P2 |
| W6_METACOGNITION_LENS | 元认知透镜未覆盖全量 | ✅ | P2 |
| W7_GOVERNANCE_DERIVED | 治理覆盖未传播 derived_from 链 | ⏳ | P1 |
| W8_HEALTH_CRON_TIER | 健康 cron 未使用 tier 加权债务 | ⏳ | P0 |
| W9_REGISTRY_YAML | Registry YAML 缺少 X1/X2/X3 字段 | ⏳ | P1 |
| W10_COMPLETION_TRACK | 各收敛域缺少完成状态跟踪 | ✅ | P3 |

### 10.3 里程碑

| 里程碑 | 依赖 | 目标日期 |
|--------|------|---------|
| **M1: 数据模型冻结** | D1, D3, X3 | 2026-06-07 |
| **M2: 权重模型上线** | W4, W8 | 2026-06-10 |
| **M3: 工具表面完成** | W5, W6 | 2026-06-12 |
| **M4: 策略追溯完成** | X1, X2, W7 | 2026-06-15 |
| **M5: 全链路收敛** | 所有 13 项 | 2026-06-20 |
| **M6: 兼容层废弃** | M5 + 6 月观察期 | 2026-12-20 |

---

## 附录 A: 收敛决策树 (更新版)

```
当前有双轨 debt 模型 + X1-X3 未串联，如何收敛？

├── 方案 A: 合并 → Registry 主导 + X1-X3 锚点
│   ├── A1: Registry 主导 + X1/X2/X3 字段扩充 (已选)
│   │   ├── 数据模型统一 (Done)
│   │   ├── 权重模型统一 (Done)
│   │   ├── MCP 工具统一 (Done)
│   │   ├── 治理覆盖统一 (⏳)
│   │   └── 健康集成统一 (⏳)
│   ├── A2: Ledger 主导 (未选 — 与 SSOT 设计哲学不符)
│   └── A3: 新统一模型 (未选 — 迁移成本高)
│
├── 方案 B: 保持双轨 + API 封装 (未选 — 不解决 X1-X3 串联)
│
└── 方案 C: 保持双轨 + 增量同步 (未选 — 不解决权重/透镜/治理)
```

## 附录 B: 关键文件清单

| 文件 | 角色 | 收敛影响 |
|------|------|---------|
| `src/omo/omo_debt_registry.py` | `DebtItem` / `DebtLedger` 定义 + `load_debt_ledger()` | ✅ 核心 |
| `src/omo/omo_debt_weight.py` | `TIER_MULTIPLIERS` + `get_computed_weight()` + `compute_debt_weight()` | ✅ 权重 |
| `src/omo/omo_debt.py` | CLI 入口，债务生命周期管理 | ⏳ 状态机 |
| `src/omo/omo_debt_metrics.py` | `collect_stale_evidence_item_ids()` | ⏳ X2 集成 |
| `src/omo/mcp_server.py` | `omo_debt_list`, `omo_debt_summary`, `omo_metacognition` | ✅ 工具 |
| `src/omo/mcp_plane.py` | Governance Plane MCP 接口 | ⏳ 透镜扩展 |
| `src/omo/omo_metacognition.py` | `--lens X1/X2/X3` 过滤 | ✅ 透镜 |
| `src/omo/omo_governance_overlay.py` | `evaluate_governance_overlay_planned_target()` | ⏳ derived_from |
| `src/omo/omo_governance_overlay_loop.py` | Overlay 循环迭代 | ⏳ derived_from |
| `src/omo/omo_governance.py` | `propose_truth_mutation()`, `approve_truth_mutation()` | ✅ 策略 |
| `scripts/sync_omo_state.py` | 健康分计算，system.yaml 输出 | ⏳ tier 加权 |
| `scripts/omo_debt.py` | 向后兼容 CLI 入口 | ✅ 兼容层 |

## 附录 C: YAML 示例 (简略)

```yaml
id: "D2_CI_E2E"
title: "CI E2E 测试环境容器化"
weight: 0.15
x1_policy_ref: "policy:phase12-gate-check"
x2_freshness: "current"
x3_tier: "Framework"
gate_level: "L2"
lifecycle_state: "active"
evidence_refs: [".omo/evidence/ci-e2e-docker-gap.yaml"]
mitigation_refs: [".omo/plans/ci-e2e-containerization.md"]
```
