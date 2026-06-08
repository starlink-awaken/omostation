# L4 管理支撑模块 — 深度分析与设计方案

**2026-06-08 · 架构决策**

---

## 一、现状问题诊断

### 1.1 核心矛盾

L4 的 19 域中，7 个 Document 域共享完全同构的 KEMS 六面结构，但：

- **操作代码分散**：ecos domain_manager.py (1428行) + cockpit_mcp.py (domain搜索) — 两套逻辑
- **路径硬编码不一致**：`@卫健委` vs `@工作文档/卫健委` — 已发现 bug
- **无统一 Schema**：每个域的 STATE/MEMORY/signals 格式各异，无法聚合
- **健康度不可见**：各域 STATUS 独立，无全局 DASHBOARD

### 1.2 KEMS 六面模型 (已成熟)

```
每个 Document 域的标准结构:
  _control/     ← 控制面: STATE, MEMORY, TIMELINE, signals, control-rules, STATUS, PLANE_INDEX, 决策日志, CLAUDE.md
  _entities/    ← 实体面: 域内实体的 SSOT 定义
  _knowledge/   ← 知识面: 方法论/经验/概念/系统
  _storage/     ← 存储面: 资料库/订阅/灵感
  _archive/     ← 归档面: 历史版本
  _runtime/     ← 运行时面 (仅 cockpit): 生成产物
```

### 1.3 跨域重复操作

9 类同构文件在 7 域之间完全重复，每次操作都需要：
- 相同的读/写/校验逻辑
- 相同的 YAML frontmatter 解析
- 相同的格式约定

---

## 二、设计方案：L4 Domain Kernel

### 2.1 定位

```
L4 Domain Kernel (新模块)
│
├── 不是新的"层" — 是 L4 自我层内的管理面
├── 不是新的"项目" — 是现有 cockpit/ecos 中的共享库
└── 角色: 统一 L4 19 域的 CRUD + 校验 + 聚合
```

### 2.2 模块架构

```
cockpit/src/cockpit/l4/  (或独立包 kairon/packages/l4-kernel/)
│
├── domain.py          ← 域注册表 (与 DOMAIN-INDEX.md 同步)
│   ├── DomainRegistry: 19域元数据管理
│   ├── resolve_path(domain_id) → Path (统一路径解析)
│   └── list_domains(filter) → 按类型/状态筛选
│
├── kems.py            ← KEMS 六面操作
│   ├── KemsPlane: 面的读写抽象
│   ├── read_state(domain) / write_state(domain, data)
│   ├── read_memory(domain) / write_memory(domain, data)
│   ├── read_signals(domain) / append_signal(domain, event)
│   ├── read_timeline(domain) / append_timeline(domain, event)
│   └── read_status(domain) / write_status(domain, status)
│
├── schema.py          ← Schema 校验 (基于 M1 YAML)
│   ├── validate_domain(domain_id) → 面完整性检查
│   ├── validate_kems_structure(domain_id) → 文件存在性检查
│   └── diff_kems(domain_id) → 与 M1 模型的差异
│
├── dashboard.py       ← 跨域聚合
│   ├── aggregate_health() → 全域健康 DASHBOARD
│   ├── aggregate_signals() → 跨域信号汇总
│   └── cross_domain_search(query) → 跨域全文搜索
│
└── templates.py       ← 控制面文件模板
    ├── init_domain(name, type) → 创建标准 KEMS 骨架
    ├── template_STATE / template_MEMORY / template_signals
    └── migrate_v3_to_v4(domain) → KEMS 版本迁移
```

### 2.3 实现位置

**推荐方案**: 在 `cockpit/src/cockpit/l4/` 下新建

理由：
1. L3 cockpit 已经是 L4 的唯一读写入口
2. 现有 MCP 工具 (`workspace_context`, `vault_search`) 都在 cockpit 中
3. 避免新增跨项目依赖
4. 可以与现有 `l4bridge.py` 和 `cockpit_mcp.py` 无缝集成

### 2.4 与现有代码的关系

```
替换前                              替换后
─────────────────────────────       ───────────────────────────
cockpit_mcp.py: _L4_DOMAINS         → l4/domain.py: DomainRegistry
cockpit_mcp.py: _scan_cards()       → l4/kems.py: read_cards()
cockpit_mcp.py: _search_vault()     → l4/kems.py: search_domain()
cockpit_mcp.py: _read_omo_goals()   → l4/kems.py: read_omo()
ecos domain_manager.py: 域创建       → l4/domain.py: register_domain()
手工路径拼接                          → l4/domain.py: resolve_path()
```

---

## 三、实施计划

### 迭代 1 (核心 — 本周)

| 文件 | 内容 |
|------|------|
| `cockpit/src/cockpit/l4/__init__.py` | 包入口 |
| `cockpit/src/cockpit/l4/domain.py` | DomainRegistry + resolve_path (替换 _L4_DOMAINS) |
| `cockpit/src/cockpit/l4/kems.py` | KemsPlane 抽象 (STATE/MEMORY/signals 读写) |

**产出**: 消除 cockpit_mcp.py 中的硬编码域映射 + 路径 bug

### 迭代 2 (管理面 — 下周)

| 文件 | 内容 |
|------|------|
| `cockpit/src/cockpit/l4/schema.py` | 域完整性校验 (对比 M1 YAML) |
| `cockpit/src/cockpit/l4/dashboard.py` | 跨域健康聚合 |

**产出**: `cockpit domains check` → 全域一致性报告

### 迭代 3 (模板 — 下下周)

| 文件 | 内容 |
|------|------|
| `cockpit/src/cockpit/l4/templates.py` | KEMS 骨架生成 + 版本迁移 |

**产出**: `cockpit domains init <name>` → 一键创建标准域

---

## 四、风险评估

| 风险 | 等级 | 缓解 |
|------|------|------|
| 破坏现有 MCP 工具接口 | 低 | 新模块作为底层库，MCP 工具改为调用新模块 |
| ecos domain_manager.py 重复 | 中 | L4 kernel 专注 Document 域，ecos 专注 MOF 模型，边界清晰 |
| 域映射路径历史不一致 | 中 | 迭代 1 即统一到 DOMAIN-INDEX.md 的 SSOT |

---

## 五、ROI 分析

| 投入 | 产出 |
|------|------|
| ~500 行新代码 | 消除 cockpit_mcp.py + domain_manager.py 中 ~200 行重复 |
| 3 个新模块 | 9 类同构文件操作统一，消除 7 域 × N 次的分散维护 |
| 1 次路径 bug 修复 | 消除 @卫健委 vs @工作文档/卫健委 不一致 |
| Schema 校验 | 自动检测域结构漂移，提前发现不一致 |
