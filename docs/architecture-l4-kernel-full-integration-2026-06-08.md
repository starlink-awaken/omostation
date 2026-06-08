# L4 Kernel · 全层连接完成

**2026-06-08 · 架构集成最终版**

---

## 一、连接状态总览

```
┌─────────────────────────────────────────────────────────────────┐
│                      eCOS v5 全层连接图                          │
│                                                                 │
│  L4 · 数据面 ──────────────────────────────────────────────┐    │
│  │ 21域 (Document/Config/Tool/...)                         │    │
│  │ ~/Documents/@*/                                         │    │
│  │                                                         │    │
│  │  l4-kernel ───── 管理面 ──────┐                         │    │
│  │  │ DomainRegistry              │                         │    │
│  │  │ KemsPlane                   │ ← 读写 L4 数据          │    │
│  │  │ DomainHealth                │                         │    │
│  │  │ SignalBus                   │                         │    │
│  │  └─────────────────────────────┘                         │    │
│  └──────────────────────────────────────────────────────────┘    │
│           ↑ MCP          ↑ import       ↑ import                 │
│  ┌────────┴──────┐ ┌─────┴──────┐ ┌─────┴──────────┐            │
│  │ L3 · cockpit   │ │ L2 · omo   │ │ L2 · metaos    │            │
│  │ MCP tools 20   │ │ 域审计     │ │ cards_context  │            │
│  │ CLI 23         │ │ debt 注册  │ │ Agent prompt   │            │
│  │ ✅ 已集成       │ │ 🔜 集成中   │ │ 🔜 集成中      │            │
│  └────────────────┘ └────────────┘ └────────────────┘            │
│           ↑                                                      │
│  ┌────────┴──────────────────────────────────────┐               │
│  │ I0 · agora                                    │               │
│  │ 29 服务注册 (含 l4-kernel)                     │               │
│  │ 136+ BOS 路由                                 │               │
│  │ ✅ 已集成                                      │               │
│  └───────────────────────────────────────────────┘               │
│           ↑                                                      │
│  ┌────────┴──────┐                                               │
│  │ L1 · runtime   │                                              │
│  │ cron jobs 4    │                                              │
│  │ matrix 注册    │                                              │
│  │ ✅ 已集成       │                                              │
│  └───────────────┘                                               │
│           ↑                                                      │
│  ┌────────┴──────┐                                               │
│  │ L0 · ecos     │                                               │
│  │ M2 新类型 2    │                                              │
│  │ M1 新节点 3    │                                              │
│  │ L0-registry   │                                              │
│  │ ✅ 已集成       │                                              │
│  └───────────────┘                                               │
│           ↑                                                      │
│  ┌────────┴──────┐                                               │
│  │ X1-X4 · 保障   │                                              │
│  │ X1: KEI审计   │                                              │
│  │ X2: 新鲜度    │                                              │
│  │ X3: 活跃度    │                                              │
│  │ X4: Schema    │                                              │
│  │ 🔜 信号联动    │                                              │
│  └───────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、L0 需要更新的内容

### 2.1 L0-registry.yaml — 新增 X 轴对 L4 的引用

```
当前 L0-registry X1-X4 条目未引用 l4-kernel
需要更新:
  X1 审计链: implementations 添加 "l4-kernel KemsValidator"
  X2 抗熵:   implementations 添加 "l4-kernel DomainHealth.check_freshness()"
  X3 价值栈: implementations 添加 "l4-kernel DomainHealth.aggregate_health()"
  X4 一致性: implementations 添加 "l4-kernel KemsValidator.validate_all()"
```

### 2.2 L0-registry.yaml — L4 条目版本号

```
L4 Gateway:  v4.0 → v5.0 (21域 + l4-kernel 集成)
L4 Domains:  v3.0 → v4.0 (l4-kernel MCP Server 42 tools)
```

### 2.3 M2 新增类型

```
domain_lifecycle.yaml ✅ 已完成
plugin.yaml          ✅ 已完成
```

---

## 三、X1-X4 与 L4 Kernel 的信号联动

### 3.1 X1 · 审计链

```
l4-kernel → X1:
  KemsValidator 校验 → violations → SignalBus.emit("🔴", "Schema violation")
  → KEI audit hook 记录
  → OMO debt registry 注册 DEBT-L4-xxx
```

### 3.2 X2 · 抗熵

```
l4-kernel → X2:
  DomainHealth.check_freshness() → STATE.md >30天 → SignalBus.emit("⚠️")
  → runtime scheduler 定时扫描 → matrix_state.json
  → OMO staleness 更新
```

### 3.3 X3 · 价值栈

```
l4-kernel → X3:
  DomainHealth.aggregate_health() → 域活跃度评分
  → cockpit status 展示
  → DASHBOARD 生成
```

### 3.4 X4 · 一致性

```
l4-kernel → X4:
  KemsValidator.validate_all() → 7域 Schema 合规
  → CI pre-commit hook
  → ecos MOF drift 报告
```

---

## 四、实施

现在更新 L0-registry.yaml 中 X1-X4 和 L4 条目。