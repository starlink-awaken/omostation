# L4 Kernel · 约束体系与跨层交互设计

**2026-06-08 · 架构设计**

---

## 一、约束体系

### 1.1 约束金字塔

```
                    ┌─────────────────────┐
                    │   X4 · 一致性        │  ← 跨层规则 (CI + pre-commit)
                    │   mof-validate       │
                    ├─────────────────────┤
                    │   X1 · 审计链        │  ← 运行时校验
                    │   KemsValidator      │
                    ├─────────────────────┤
                    │   X2 · 抗熵          │  ← 新鲜度检查
                    │   DomainHealth       │
                    ├─────────────────────┤
                    │   l4-kernel Schema   │  ← 域级 Schema
                    │   KemsValidator      │
                    ├─────────────────────┤
                    │   KEMS 标准模板      │  ← 创建时约束
                    │   init_domain_kems() │
                    └─────────────────────┘
```

### 1.2 四层约束机制

| 层级 | 机制 | 触发时机 | 强制程度 |
|------|------|---------|:---:|
| **创建时** | `init_domain_kems()` 生成标准骨架 | 新域创建 | 建议 |
| **读写时** | `KemsPlane` 统一接口，屏蔽直接文件操作 | 每次操作 | 强制 (API) |
| **校验时** | `KemsValidator.validate_all()` 7 条规则 | 定时/手动 | 检查 |
| **聚合时** | `DomainHealth.aggregate_health()` 跨域对比 | 定时/手动 | 报告 |

### 1.3 约束如何生效

```
用户/Agent 操作 L4 数据
  │
  ├── 通过 l4-kernel API (正确路径)
  │   ├── KemsPlane.read_state()     → 自动校验 frontmatter
  │   ├── KemsPlane.write_state()    → 自动注入标准字段
  │   └── KemsPlane.append_signal()  → 自动补 ts
  │
  ├── 绕过 l4-kernel 直接写文件 (错误路径)
  │   └── KemsValidator.validate_all() 发现不一致 → 告警
  │
  └── 定时扫描
      └── DomainHealth.aggregate() → cockpit health --full 展示
```

**核心设计**: l4-kernel 不是防火墙（不强阻拦），而是**护栏** — 提供正确路径，检测偏离。

---

## 二、与 X1-X4 的交互

### 2.1 X1 · 审计链

```
l4-kernel → X1 交互:
  │
  ├── 操作日志
  │   └── KemsPlane 每次 write 操作 → 追加 signals 信号
  │       └── signals.md: "🔴 | 2026-06-08 | KEMS 结构变更: STATE.md 更新"
  │
  ├── 域完整性审计
  │   └── KemsValidator.validate_all() → 7 条规则检查
  │       └── 输出: [{rule, severity, message}, ...]
  │
  ├── 与 KEI 沙箱协同
  │   └── l4-kernel 的写操作 → KEI audit hook 拦截
  │       └── kei_sandbox.py: record_audit("l4_kernel.write", ...)
  │
  └── 与 OMO governance 协同
      └── KemsValidator 发现 violation → 写入 OMO debt registry
          └── omo_debt.create("DEBT-L4-001", "域结构不完整")
```

### 2.2 X2 · 抗熵 (新鲜度)

```
l4-kernel → X2 交互:
  │
  ├── 文件新鲜度检查
  │   └── DomainHealth.check_freshness(domain_id)
  │       ├── STATE.md last-reviewed > 30 天 → ⚠️ 信号
  │       ├── STATUS.md 状态为 ALERT 持续 > 7 天 → 🔴 信号
  │       └── 输出: freshness_report.json
  │
  ├── 与 runtime scheduler 协同
  │   └── runtime scheduler 定时调用 l4-kernel
  │       └── cron: "0 6 * * *" → l4-kernel health --json
  │           └── → matrix_state.json 写入 L4 健康分
  │
  ├── 与 OMO X2 协同
  │   └── omo.omo_audit.check_freshness()
  │       └── 调用 l4-kernel.DomainHealth
  │           └── → OMO debt staleness 更新
  │
  └── 信号闭环检测
      └── signals.md 中 🔴 信号 > 48h 未处理 → CRITICAL 升级
```

### 2.3 X3 · 价值栈

```
l4-kernel → X3 交互:
  │
  ├── 域活跃度评分
  │   └── DomainHealth.aggregate_health()
  │       ├── signals 活跃度: 最近 7 天信号数 / 30 天
  │       ├── CARDS 完成率: done / total
  │       └── 文件新鲜度: 最近更新文件数 / 总数
  │
  ├── 与 cockpit 协同
  │   └── cockpit status → 展示 L4 域健康度
  │       └── cockpit health --full → 包含 L4 聚合数据
  │
  └── 与 OMO X3 协同
      └── omo.omo_cost 调用 l4-kernel
          └── 域维护成本 = 信号处理时间 + 文件更新频率
```

### 2.4 X4 · 一致性

```
l4-kernel → X4 交互:
  │
  ├── 跨域一致性检查
  │   └── KemsValidator.validate_all()
  │       ├── 7 域 STATUS 三态定义是否一致
  │       ├── 7 域 control-rules CR01-CR03 是否存在
  │       ├── 7 域 MEMORY.md frontmatter 必选字段
  │       └── 输出: consistency_report.json
  │
  ├── 与 ecos MOF 协同
  │   └── DomainValidator.diff_with_m1()
  │       └── 对比 M1 DOMAIN-*.yaml 的 kems_planes
  │           └── 发现不一致 → 写入 MOF drift 报告
  │
  ├── 与 CI/pre-commit 协同
  │   └── pre-commit hook: l4-kernel validate --ci
  │       └── 阻断提交: 如果 7 域中有 error 级别 violation
  │
  └── 与 cockpit governance 协同
      └── cockpit governance drift-check
          └── → l4-kernel consistency report
```

---

## 三、完整交互拓扑

```
                    ┌──────────────────────────────┐
                    │        X4 · 一致性            │
                    │  CI hook → l4-kernel validate │
                    │  MOF diff → drift report      │
                    └──────────┬───────────────────┘
                               │
    ┌──────────────┬───────────┼───────────┬──────────────┐
    │              │           │           │              │
    ▼              ▼           ▼           ▼              ▼
┌────────┐  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  L0    │  │   L1     │ │   L2     │ │   L3     │ │   L4     │
│  ecos  │  │ runtime  │ │ omo      │ │ cockpit  │ │ l4-kernel│
│        │  │          │ │ metaos   │ │          │ │          │
│ MOF M1 │  │ scheduler│ │ minerva  │ │ MCP tools│ │ DomainR  │
│ domain │  │ cron     │ │          │ │ CLI      │ │ KemsPlane│
│ *.yaml │  │ KEI      │ │          │ │          │ │ Validator│
└───┬────┘  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
    │            │            │            │            │
    │  Schema源  │ 定时调用    │ 审计/注入   │ 用户入口    │ 管理面
    │            │            │            │            │
    └────────────┴────────────┴────────────┴────────────┘
                               │
                    ┌──────────▼───────────┐
                    │    X1/X2/X3 监控      │
                    │  X1: 操作审计         │
                    │  X2: 新鲜度检查       │
                    │  X3: 活跃度评分       │
                    └──────────────────────┘
```

### 3.1 调用方向

```
l4-kernel 被调用 (被动 — 提供 API):
  ├── cockpit → import l4_kernel (MCP tools + CLI)
  ├── metaos  → import l4_kernel (cards_context)
  ├── minerva → import l4_kernel (VaultSink)
  ├── omo     → import l4_kernel (审计/健康)
  └── runtime → subprocess l4-kernel health (cron)

l4-kernel 调用 (主动 — 读取外部):
  └── ecos MOF M1 → 读取 DOMAIN-*.yaml (作为 Schema 源)
```

### 3.2 数据流向

```
写路径:
  用户/Agent → cockpit → l4-kernel.KemsPlane.write_state()
                         └→ signals 信号
                         └→ KEI audit log
                         └→ OMO debt (如果违规)

读路径:
  用户/Agent → cockpit → l4-kernel.KemsPlane.read_state()
  定时       → runtime → l4-kernel.DomainHealth.aggregate()
                         └→ matrix_state.json
                         └→ cockpit health --full

校验路径:
  定时/手动  → l4-kernel.KemsValidator.validate_all()
              └→ X4: consistency report
              └→ X1: audit violations
              └→ X2: freshness alerts
```

---

## 四、实现优先级

| 优先级 | 功能 | 依赖 | 预估 |
|--------|------|------|------|
| P0 | `init_domain_kems()` 创建时约束 | 已完成 ✅ | — |
| P0 | `KemsValidator` 7 条校验规则 | 已完成 ✅ | — |
| P1 | `DomainHealth` 新鲜度检查 (X2) | health.py 待实现 | 2h |
| P1 | cockpit 集成 → `cockpit domains check` | cockpit 依赖 l4-kernel | 1h |
| P2 | runtime cron 集成 → 定时健康扫描 | runtime 依赖 l4-kernel | 1h |
| P2 | OMO 集成 → violations → debt 注册 | omo 依赖 l4-kernel | 1h |
| P3 | CI pre-commit hook | .pre-commit-config.yaml | 0.5h |

---

## 五、关键设计原则

1. **护栏而非防火墙** — l4-kernel 提供正确路径 (KemsPlane API)，检测偏离 (KemsValidator)，但不强行阻止直接文件操作
2. **被动为主** — l4-kernel 不主动运行，由上层 (cockpit/runtime/omo) 调用
3. **信号驱动** — 所有变更通过 signals.md 记录，X1-X4 通过信号触发
4. **渐进式约束** — 创建时建议 → 读写时强制 (API) → 校验时检测 → 聚合时报告
5. **与现有体系互补** — 不替代 KEI/OMO/ecos，而是为它们提供 L4 域的数据源
