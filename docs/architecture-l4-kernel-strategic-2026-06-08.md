# L4 Kernel 独立项目 — 战略架构设计

**2026-06-08 · 架构决策 · 长期演进**

---

## 一、战略定位

### 1.1 为什么是独立项目

```
eCOS v5 7 层架构中，每层都有自己的一等公民项目:

L4 · 自我层      ← l4-kernel (新) — 管理面
                   CARDS + Vault + 19域 (数据面)
L3 · 入口层      ← cockpit
I0 · 集成织层    ← agora
L2 · 引擎层      ← kairon / omo / metaos / gbrain
L1 · 运行时      ← runtime
L0 · 协议层      ← ecos

L4 此前只有数据面 (被动文档)，缺少管理面 (主动操作)。
l4-kernel 填补了这个空白 — 它是 L4 的"操作系统层"。
```

### 1.2 类比

| 概念 | 类比 |
|------|------|
| L4 数据面 (19域) | 文件系统 (磁盘上的文件) |
| L4 Kernel (新) | 操作系统内核 (文件系统驱动) |
| cockpit MCP | Shell (用户态工具) |
| ecos MOF M1 | 文件系统 Schema (inode 定义) |

L4 Kernel 是 L4 的 **VFS 层** — 它为上层提供统一的域操作接口，屏蔽底层文件系统差异。

### 1.3 长期愿景

```
Phase 1 (现在):    域注册 + KEMS 六面统一读写
Phase 2 (3个月):   域健康聚合 + Schema 自动校验
Phase 3 (6个月):   跨域事件总线 + 智能信号路由
Phase 4 (12个月):  域联邦 — 多机器 L4 数据同步
```

---

## 二、战术设计 — 覆盖全部 19 域

### 2.1 域分类与特化策略

```
┌─────────────────────────────────────────────────────────────┐
│                  L4 Kernel 域覆盖全景                        │
│                                                             │
│  DocumentDomain (7域)  ← KemsPlane (核心 · 六面操作)        │
│  ├── @驾驶舱     cockpit     6面 + CARDS                    │
│  ├── @学习进化   vault       5面 + Obsidian                 │
│  ├── @个人       personal    5面                            │
│  ├── @公共       shared      4面                            │
│  ├── @家庭生活   family      3面                            │
│  ├── @卫健委     work-weijian 6面                           │
│  └── @国转中心   work-guozhuan 6面                          │
│                                                             │
│  ConfigDomain (3域)  ← ConfigPlane (YAML/JSON Schema)       │
│  ├── ~/.ai              ai-config                           │
│  ├── ~/.agents          agents-config                       │
│  └── ~/SharedConf       icloud-sharedconf                   │
│                                                             │
│  ToolDomain (2域)   ← ToolPlane (脚本注册表)                 │
│  ├── ~/bin                                                  │
│  └── ~/ToolBox                                              │
│                                                             │
│  WorkspaceDomain (1域) ← WorkspacePlane (文件索引)           │
│  └── SharedWork                                             │
│                                                             │
│  StorageDomain (1域)  ← StoragePlane (磁盘监控)              │
│  └── SharedDisk                                             │
│                                                             │
│  ModelDomain (2域)    ← ModelPlane (校验和 + 版本)           │
│  ├── Model                                                  │
│  └── SharedModel                                            │
│                                                             │
│  EngineDomain (1域)   ← EnginePlane (进程管理)               │
│  └── Minerva 引擎                                           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 每域的标准化管理操作

| 操作 | Document | Config | Tool | Workspace | Storage | Model | Engine |
|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 注册 (register) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 路径解析 (resolve) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 存在性检查 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 结构校验 | KEMS六面 | YAML Schema | 脚本注册表 | 文件索引 | 挂载状态 | 校验和 | 进程状态 |
| 健康检查 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 新鲜度 (X2) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 骨架生成 | ✅ | ✅ | ✅ | — | — | — | — |
| 版本迁移 | ✅ | — | — | — | — | — | — |
| 全文搜索 | ✅ | — | — | — | — | — | — |
| 信号日志 | ✅ | — | — | — | — | — | — |

### 2.3 DocumentDomain — 最复杂类型 (80% 代码量)

```
KemsPlane 六面操作:
  _control/
    ├── STATE.md        ← read_state / write_state
    ├── MEMORY.md       ← read_memory / write_memory
    ├── TIMELINE.md     ← read_timeline / append_event
    ├── signals.md      ← read_signals / append_signal
    ├── control-rules.md← read_rules / write_rules
    ├── STATUS.md       ← read_status / write_status
    ├── PLANE_INDEX.md  ← read_index / rebuild_index
    ├── 决策日志/        ← list_decisions / add_decision
    └── CLAUDE.md       ← read_entrypoint / validate_entrypoint

  _entities/            ← list_entities / get_entity / validate_entity
  _knowledge/           ← list_knowledge / search_knowledge
  _storage/             ← list_storage / get_storage_stats
  _archive/             ← list_archive / archive_item / restore_item
  _runtime/ (cockpit)   ← list_runtime / get_runtime_stats

CARDS 特化 (cockpit 域):
  ├── scan_cards()      ← 替代 _scan_cards()
  ├── get_card(id)      ← 按 ID 获取卡片
  ├── check_compliance()← 操作前合规检查
  └── list_by_priority()← 按 P0-P3 排序
```

### 2.4 ConfigDomain (3域)

```
ConfigPlane:
  ├── read_config(path)     ← YAML/JSON 解析
  ├── write_config(path, d) ← 安全写入 (原子操作)
  ├── validate_schema(path) ← 与 Schema 对比
  ├── list_configs()        ← 列出所有配置文件
  └── diff_configs(v1, v2)  ← 版本对比

特化:
  ai-config:    模型配置 + API key (敏感信息处理)
  agents-config: Agent 角色定义 + 权限
  icloud:       同步状态 + 冲突检测
```

### 2.5 ToolDomain (2域)

```
ToolPlane:
  ├── list_tools()          ← 扫描 ~/bin + ~/ToolBox
  ├── register_tool(name)   ← 添加到注册表
  ├── check_tool(name)      ← 可执行性 + 版本检查
  ├── get_tool_metadata()   ← shebang/依赖/大小/修改时间
  └── sync_with_ecos_link() ← 与 ecos-link 注册表同步
```

### 2.6 其余域 (StorageDomain/ModelDomain/WorkspaceDomain/EngineDomain)

```
StoragePlane:
  ├── get_disk_usage()      ← df -h 解析
  ├── check_mount_status()  ← 挂载点状态
  └── list_top_consumers()  ← 磁盘大户

ModelPlane:
  ├── list_models()         ← 模型文件索引
  ├── get_model_checksum()  ← SHA256 校验
  └── check_model_version() ← 版本比对

WorkspacePlane:
  ├── index_files()         ← 文件索引
  └── search_files()        ← 文件名搜索

EnginePlane:
  ├── check_process()       ← 进程存活检查
  ├── get_config()          ← 引擎配置
  └── get_logs()            ← 最近 N 行日志
```

---

## 三、完整 API 设计

### 3.1 Python API (其他项目 import 使用)

```python
from l4_kernel import DomainRegistry, KemsPlane, DomainHealth

# ── 域注册 ──
registry = DomainRegistry()
registry.list_all()                        # → list[Domain]
registry.list_by_type("document")          # → list[DocumentDomain]
registry.get("vault")                      # → Domain
registry.resolve_path("vault")             # → Path("~/Documents/@学习进化")
registry.resolve_bos_uri("vault")          # → "bos://vault/**"
registry.health_check("vault")             # → HealthReport

# ── KEMS 操作 ──
kems = KemsPlane(registry.get("vault"))
kems.read_state()                          # → dict (STATE.md 解析)
kems.write_state({"status": "active", ...})
kems.read_signals()                        # → list[Signal]
kems.append_signal({"ts": ..., "event": ...})
kems.search("方法论")                       # → list[SearchResult]
kems.validate_structure()                  # → list[str] (缺失文件)

# ── CARDS 操作 ──
from l4_kernel.kems import CardsPlane
cards = CardsPlane(registry.get("cockpit"))
cards.scan_cards()                         # → list[Card]
cards.get_card("TASK-2026-06-06-012")      # → Card
cards.check_compliance("TASK-...")         # → ComplianceResult

# ── 跨域聚合 ──
health = DomainHealth(registry)
health.aggregate()                         # → Dashboard
health.cross_domain_search("AI 架构")       # → list[SearchResult]
health.aggregate_signals(window_hours=24)  # → list[Signal]
```

### 3.2 CLI 命令

```
l4-kernel domain list [--type document|config|tool|...]
l4-kernel domain info <domain_id>
l4-kernel domain check [domain_id]      # 不指定 = 全部
l4-kernel domain init <name> --type document --path ~/Documents/@xxx
l4-kernel domain migrate <domain_id> --to v5
l4-kernel domain dashboard

l4-kernel kems state <domain_id>        # 读取 STATE
l4-kernel kems signals <domain_id>      # 读取信号日志
l4-kernel kems search <keyword> [--domain xxx]
l4-kernel kems validate <domain_id>

l4-kernel cards list [--priority P0]
l4-kernel cards get <card_id>
l4-kernel cards check <card_id>

l4-kernel health [--json]
l4-kernel health dashboard
```

### 3.3 MCP 工具 (通过 cockpit 暴露)

```
mcp tool: l4_domain_list(type)            → 域列表
mcp tool: l4_domain_check(domain_id)      → 域健康
mcp tool: l4_domain_init(name, type, path)→ 创建域
mcp tool: l4_kems_read(domain, file)      → 读取控制面文件
mcp tool: l4_kems_search(domain, keyword) → 全文搜索
mcp tool: l4_cards_status()               → CARDS 状态
mcp tool: l4_cards_check(card_id)         → 合规检查
mcp tool: l4_health_dashboard()           → 全域健康
```

---

## 四、项目结构

```
projects/l4-kernel/
│
├── pyproject.toml           ← hatchling, Python 3.13+, pyyaml
├── Makefile                 ← make test/lint/fmt/install
├── INTERFACE.yaml           ← 接口注册
├── CLAUDE.md                ← AI 助手指南
├── AGENTS.md                ← 开发者指南
├── README.md
│
├── src/l4_kernel/
│   ├── __init__.py           ← 公开 API: DomainRegistry, KemsPlane, ...
│   │
│   ├── registry.py           ← DomainRegistry (19域注册 + DOMAIN-INDEX.md 同步)
│   │   ├── Domain (基类)
│   │   ├── DomainRegistry
│   │   └── resolve_path / resolve_bos_uri
│   │
│   ├── domain_types.py       ← 7 种域类型特化
│   │   ├── DocumentDomain (KEMS 六面)
│   │   ├── ConfigDomain (YAML/JSON Schema)
│   │   ├── ToolDomain (脚本注册表)
│   │   ├── WorkspaceDomain (文件索引)
│   │   ├── StorageDomain (磁盘监控)
│   │   ├── ModelDomain (校验和 + 版本)
│   │   └── EngineDomain (进程管理)
│   │
│   ├── kems.py               ← KemsPlane (DocumentDomain 六面读写)
│   │   ├── KemsPlane
│   │   ├── CardsPlane
│   │   └── KemsVersion
│   │
│   ├── health.py             ← DomainHealth (跨域健康聚合)
│   │   ├── DomainHealth
│   │   ├── HealthReport
│   │   └── aggregate_health / cross_domain_search
│   │
│   ├── schema.py             ← Schema 校验 + 迁移
│   │   ├── DomainValidator
│   │   ├── ValidationResult
│   │   └── MigrationEngine
│   │
│   ├── templates.py          ← 域骨架生成
│   │   ├── init_domain()
│   │   ├── template_STATE / template_MEMORY / template_signals
│   │   └── migrate_v4_to_v5()
│   │
│   ├── signals.py            ← 跨域信号总线
│   │   ├── SignalBus
│   │   ├── Signal
│   │   └── route_signal()
│   │
│   └── cli.py                ← CLI 入口 (l4-kernel 命令)
│
├── tests/
│   ├── conftest.py            ← 共享 fixtures (临时域)
│   ├── test_registry.py       ← 域注册表测试
│   ├── test_kems.py           ← KEMS 操作测试
│   ├── test_health.py         ← 健康聚合测试
│   ├── test_domain_types.py   ← 各类型域特化测试
│   ├── test_schema.py         ← Schema 校验测试
│   └── test_signals.py        ← 信号总线测试
│
└── docs/
    └── architecture.md        ← 架构文档
```

---

## 五、依赖关系

### 5.1 l4-kernel 的依赖 (最少化)

```toml
[project]
name = "l4-kernel"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=9.0", "ruff>=0.8"]
```

**零外部依赖** — 仅 pyyaml (标准库之外)。

### 5.2 谁依赖 l4-kernel

```
cockpit  → l4-kernel  (MCP tools + CLI 命令)
metaos   → l4-kernel  (cards_context)
minerva  → l4-kernel  (VaultSink)
omo      → l4-kernel  (域审计)
ecos     → l4-kernel  (互补: MOF → 文件系统)
```

### 5.3 不被依赖的

```
l4-kernel 不依赖: agora, runtime, kairon, gbrain
l4-kernel 不依赖: cockpit, metaos, omo, ecos
```

**单向依赖**: 上层依赖 l4-kernel，l4-kernel 不依赖任何项目。

---

## 六、长期演进路线

### Phase 1 · 基础 (2 周)

```
目标: 域注册 + DocumentDomain KEMS 操作
├── registry.py: DomainRegistry + DOMAIN-INDEX.md 同步
├── domain_types.py: Domain 基类 + DocumentDomain
├── kems.py: KemsPlane (STATE/MEMORY/signals 读写)
└── cli.py: l4-kernel domain list/info/check
```

### Phase 2 · 扩展 (2 周)

```
目标: 全部 7 种域类型 + 健康聚合
├── domain_types.py: Config/Tool/Workspace/Storage/Model/Engine
├── health.py: DomainHealth + 跨域 DASHBOARD
├── templates.py: 域骨架生成
└── cli.py: l4-kernel domain init/dashboard
```

### Phase 3 · 集成 (1 周)

```
目标: 迁移现有调用方
├── cockpit: _L4_DOMAINS → l4_kernel.DomainRegistry
├── cockpit: _scan_cards → l4_kernel.CardsPlane
├── cockpit: _search_vault → l4_kernel.KemsPlane.search()
├── metaos: cards_context → l4_kernel.CardsPlane
└── minerva: VaultSink → l4_kernel.KemsPlane
```

### Phase 4 · 智能 (远期)

```
目标: 跨域信号总线 + 自动路由
├── signals.py: SignalBus + 跨域路由规则
├── 智能信号分类: 紧急/重要/常规
├── 自动 CARDS 创建: 信号 → DEBT 卡片
└── 域联邦: 多机器 L4 数据同步
```

---

## 七、风险评估

| 风险 | 等级 | 缓解 |
|------|------|------|
| 与 ecos domain_manager 功能重叠 | 低 | 互补: Kernel=文件系统, ecos=MOF模型 |
| 调用方迁移成本 | 中 | 渐进迁移: 先新增, 再替换, 后删除旧代码 |
| DOMAIN-INDEX.md 格式变更 | 低 | 作为 SSOT, 格式变更由 Kernel 管理 |
| 域路径历史不一致 | 低 | Phase 1 统一到 DOMAIN-INDEX.md |

---

## 八、决策总结

| 决策 | 选择 | 理由 |
|------|------|------|
| 项目形式 | 独立 `projects/l4-kernel/` | 层级独立, 轻量依赖, 所有层可调用 |
| 覆盖范围 | 全部 19 域, 7 种类型 | 统一管理面, 避免碎片化 |
| 依赖策略 | 仅 pyyaml | 零外部依赖, 可被任何项目 import |
| 与 ecos 关系 | 互补 (文件系统 vs MOF 模型) | 不重复, 不替代 |
| Python 版本 | >=3.13 | 与主流项目一致 |
| 构建系统 | hatchling + uv | 与 7/8 项目一致 |
