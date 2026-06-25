---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# X4: 治理一致性 (Governance Consistency) — 5+3+1 第四横切面设计

> 2026-06-06 · 基于全量审计后治理需求 · 补充 X1-X3

---

## 一、为什么需要 X4

X1-X3 覆盖了安全、保鲜、价值三个维度, 但遗漏了一个事实:

**规则制定了, 但谁来检查规则是否被遵守？**

| 现象 | X1-3 能覆盖吗 |
|------|-------------|
| CI workflow 坏了没人发现 | ❌ X1-3 不关心 CI |
| 新 CLI 入口未在 registry 注册 | ❌ X1-3 不关心接口 |
| 端口冲突 | ❌ 除非导致安全漏洞(X1) |
| CLAUDE.md 90 天未更新 | ❌ 除非标记为 stale(X2) |
| Agent 跳过 startup 直接改代码 | ❌ 无人监督 |
| 跨层 import 违规 | ❌ 除非导致安全漏洞(X1) |
| Phase 门禁条件未满足但标记 done | ❌ |

**X4 = "我们是否在遵守我们自己的规则"**

---

## 二、X4 定义

```
X4: 治理一致性 (Governance Consistency)
  目标: 保证 5+3+1 体系的所有规则实时生效
  度量: 规则覆盖率 + 违规清零率 + 保鲜延迟
```

### 二维度量

| 维度 | 定义 | 测量方式 |
|------|------|---------|
| **覆盖度** (Coverage) | 多少接口/文档/CI 受规则约束 | registered_entries / total_entries |
| **合规度** (Compliance) | 受约束的项目中多少是合规的 | compliant / total_registered |

### 具体指标

| 指标 | 目标 | 当前 |
|------|------|------|
| CLI 注册率 | 100% | ~95% (protocols-layer 断裂) |
| 端口冲突 | 0 | 2 real (9090/8765) |
| 文档保鲜 (<30d) | 100% | ✅ |
| CI 覆盖率 | 9/9 | ✅ |
| 跨层 import 违规 | 0 | ✅ |
| Phase gate 合规 | 100% | ✅ (P30 all done) |

---

## 三、X4 与其他 X 轴的关系

```
X1 安全:   "操作是否安全"      → 沙箱/权限/审计
X2 保鲜:   "数据是否新鲜"      → 过期检测/自愈/版本
X3 价值:   "投入是否合理"      → 成本/Token/资源
X4 一致性: "规则是否被遵守"    → 注册/冲突/合规/门禁
```

### X4 ← X1 借用
- KEI 沙箱的审计记录格式 (用于记录违规事件)
- OMO debt X1 标注 (用于严重违规)

### X4 ← X2 借用
- 保鲜周期模型 (fresh → stale → dormant)
- 周常检查节奏

### X4 ← X3 借用
- 违规成本估算 (每次违规浪费多少 Time/Token)

---

## 四、X4 实现: 治理一致性检查 (Governance Compliance Check)

### 4.1 数据模型

```yaml
# .omo/_truth/x4-governance-compliance.yaml
rules:
  - id: GC-001
    name: CLI 入口注册
    check: scripts/check-interfaces.py --cli-only
    severity: high
    owner: omo
  - id: GC-002
    name: 端口冲突
    check: scripts/check-interfaces.py --port-only
    severity: critical
    owner: omo
  - id: GC-003
    name: 跨层 import
    check: scripts/check-cross-deps.py
    severity: high
    owner: omo
  - id: GC-004
    name: 文档保鲜
    check: scripts/check-interfaces.py --doc-only
    severity: medium
    owner: omo
  - id: GC-005
    name: CI 覆盖
    check: 扫描 .github/workflows/ 覆盖 9 项目
    severity: high
    owner: omo
  - id: GC-006
    name: Phase gate 合规
    check: 对比 .omo/_truth/goals/ 状态 vs 实际
    severity: critical
    owner: omo
  - id: GC-007
    name: Agent 启动链
    check: CLAUDE.md §0 存在性 + cockpit MCP 可用
    severity: medium
    owner: cockpit
```

### 4.2 X4 检查脚本

```python
# scripts/check-x4-compliance.py
# 聚合所有 X4 规则检查, 输出合规度报告

COMPLIANCE_CHECKS = [
    ("CLI注册", check_signal=lambda: check_cli_registration()),
    ("端口冲突", check_signal=lambda: check_port_conflicts()),
    ("跨层依赖", check_signal=lambda: check_cross_deps()),
    ("文档保鲜", check_signal=lambda: check_doc_freshness()),
    ("CI覆盖", check_signal=lambda: check_ci_coverage()),
    ("Phase门禁", check_signal=lambda: check_phase_gate()),
]
```

### 4.3 X4 MCP 工具 (cockpit)

```python
@mcp.tool()
def governance_compliance() -> str:
    """X4 治理一致性: 一键检查所有规则合规度。返回覆盖度 + 违规列表。"""
    # 运行所有 X4 检查 → 汇总报告
    return json.dumps({
        "x4_score": 85,  # 百分比
        "rules_checked": 7,
        "rules_passed": 5,
        "violations": [
            {"rule": "GC-002", "desc": "端口9090冲突", "severity": "critical"},
            {"rule": "GC-001", "desc": "protocols-layer CLI 未注册", "severity": "high"},
        ],
        "trend": "improving",  # 比上次 +5%
    })
```

---

## 五、X4 如何持久化 (不遗忘)

### 5.1 OMO 债务集成

```
X4 违规 → omo debt register
  x1_policy_ref: GC-xxx (映射到违规规则)
  x2_freshness: fresh (7d review)
  x3_tier: P1 (架构偏差)
```

### 5.2 周报集成

```
每周一早8: CI cron → 跑 X4 check → 生成合规报告
  → P0 违规 → omo debt register + 通知
  → P1 违规 → 列入下周计划
  → score < 80 → 触发 Phase gate review
```

### 5.3 Phase 门禁集成

```
Phase 切换 → X4 检查 → score ≥ 90 且 0 critical → 通过
```

---

## 六、X4 的三阶段落地

| 阶段 | 内容 | 状态 |
|------|------|------|
| P0 | 定义 X4 维度 + 数据模型 | ✅ 本文档 |
| P1 | 实现 check-x4-compliance.py + MCP tool | 待实施 |
| P2 | OMO 债务集成 + 周报自动化 | 待实施 |
| P3 | Phase 门禁强制 X4 check | 待实施 |

---

## 七、集成后的 5+3+1

```
L4 自我层   ─┐
L3 入口层   ─┤
I0 织层    ─┤
L2 内核    ─┼── 5 层主干
L1 运行时   ─┤
L0 协议    ─┘

X1 安全   ─ 谁在操作? 操作了什么?
X2 保鲜   ─ 数据过没过期? 系统有没有 self-heal?
X3 价值   ─ 花了多少 Token? 值不值?
X4 一致性 ─ 规则有没有人遵守? 检查结果是什么?
```

**X4 不增加任何新规则。它是 X1-X3 之上的"元规则"——检查规则本身是否被遵守。**
