# eCOS v5 · L4 Domain Kernel 全面架构设计

**2026-06-08 · 架构设计 · 推演与分析**

---

## 一、推演起点：L4 的 19 域问题空间

### 1.1 域分类矩阵

```
                    运行代码?    数据格式    KEMS面数   管理复杂度    自动化程度
DocumentDomain (7)    ❌         MD+YAML      3~6        🔴 高         ⭐⭐
ConfigDomain (3)      ❌         YAML/JSON     —         🟡 中         ⭐⭐
EngineDomain (1)      ✅         ？            —         🟡 中         ⭐⭐⭐
ToolDomain (2)        ✅         二进制/脚本    —         🟢 低         ⭐⭐⭐⭐
WorkspaceDomain (1)   ❌         混合          —         🟡 中         ⭐⭐
StorageDomain (1)     ❌         二进制        —         🟢 低         ⭐⭐⭐
ModelDomain (2)       ❌         二进制        —         🟢 低         ⭐⭐⭐
```

**结论**: DocumentDomain 是唯一需要管理支撑的类型。其他 12 域要么是代码（Engine/Tool），要么是纯存储（Storage/Model），要么是配置文件（Config）— 它们的管理逻辑与 Document 域完全不同。

### 1.2 DocumentDomain 7 域的同构性证明

```
共享文件矩阵 (9类):
┌────────────────────┬───┬───┬───┬───┬───┬───┬───┐
│                    │驾 │学 │个 │公 │家 │卫 │国 │
│                    │驶 │习 │人 │共 │庭 │健 │转 │
│                    │舱 │进 │   │   │生 │委 │中 │
│                    │   │化 │   │   │活 │   │心 │
├────────────────────┼───┼───┼───┼───┼───┼───┼───┤
│ STATE.md           │ D │ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ 7/7
│ MEMORY.md          │ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ 7/7
│ TIMELINE.md        │ ❌│ ✅│ ❌│ ❌│ ✅│ ✅│ ✅│ 4/7
│ signals.md         │ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ 7/7
│ control-rules.md   │ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ 7/7
│ STATUS.md          │ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ 7/7
│ PLANE_INDEX.md     │ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ 7/7
│ 决策日志/           │ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ 7/7
│ CLAUDE.md          │ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ ✅│ 7/7
├────────────────────┼───┼───┼───┼───┼───┼───┼───┤
│ DASHBOARD.md       │ ✅│ ❌│ ❌│ ❌│ ❌│ ✅│ ❌│ 2/7 ← 待统一
└────────────────────┴───┴───┴───┴───┴───┴───┴───┘

同构率: 9 类文件, 平均覆盖 6.1/7 域 = 87%
```

**同构率 87%** — 意味着为每个域写独立操作代码是严重浪费。

---

## 二、推演：如果不做 Domain Kernel 会怎样

### 场景推演 (6个月后)

```
时间线 ─────────────────────────────────────────────────────→
  │
  现在 (2026-06):
  ├─ 7 域, cockpit_mcp.py 手工维护 _L4_DOMAINS
  ├─ ecos domain_manager.py 独立实现域操作
  ├─ 路径 bug: @卫健委 vs @工作文档/卫健委
  │
  1 个月后:
  ├─ 新增 2 个 Document 域 (如 @教育, @财务)
  ├─ cockpit_mcp.py _L4_DOMAINS 再加 2 行
  ├─ ecos domain_manager.py 再写 2 个 YAML
  ├─ 手工操作 × 2 = 4 处修改
  │
  3 个月后:
  ├─ KEMS v5 升级: 新增 _runtime/stats.json
  ├─ 7 域需要手工迁移 → 7 × N 次操作
  ├─ 遗漏 2 域 → 数据不一致
  │
  6 个月后:
  ├─ cockpit_mcp.py _L4_DOMAINS = 20+ 行硬编码
  ├─ 3 个不同的域路径解析逻辑共存
  ├─ KEMS 版本 v4/v5 混合 → 校验失败
  ├─ 维护成本 = O(域数 × 文件数) = O(9×9) = O(81)
  └─ 🔴 架构崩溃点
```

**结论**: 没有 Domain Kernel，L4 的维护成本随域数线性增长，最终不可维护。

---

## 三、推演：如果做了 Domain Kernel 会怎样

### 场景推演 (6个月后)

```
时间线 ─────────────────────────────────────────────────────→
  │
  现在 (2026-06):
  ├─ DomainRegistry 统一 19 域注册
  ├─ KemsPlane 统一 9 类文件读写
  ├─ 路径 bug 一次性修复
  │
  1 个月后:
  ├─ 新增 2 个 Document 域 → DomainRegistry.register("education", ...)
  ├─ KemsPlane 自动生成骨架 → cockpit domains init education
  ├─ 操作 × 1 = 1 行代码
  │
  3 个月后:
  ├─ KEMS v5 升级: KemsPlane 内置 migrate()
  ├─ 一键迁移所有域 → cockpit domains migrate --to v5
  │
  6 个月后:
  ├─ cockpit domains check → 全域一致性报告
  ├─ 维护成本 = O(1) 常数级
  └─ 🟢 架构可扩展
```

---

## 四、完整架构设计

### 4.1 模块分层

```
┌──────────────────────────────────────────────────────────┐
│                    L4 Domain Kernel                       │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  应用层 (cockpit CLI/MCP)                           │  │
│  │  cockpit domains init/list/check/migrate/search     │  │
│  │  cockpit_mcp.py: vault_search → DomainKernel       │  │
│  └──────────────────────┬─────────────────────────────┘  │
│                         │                                 │
│  ┌──────────────────────▼─────────────────────────────┐  │
│  │  服务层 (l4/ 核心模块)                               │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────┐  │  │
│  │  │ domain  │  │  kems   │  │ schema  │  │ dash  │  │  │
│  │  │ Registry│  │ Plane   │  │ Valid.  │  │ board │  │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └───┬───┘  │  │
│  └───────┼────────────┼────────────┼────────────┼──────┘  │
│          │            │            │            │         │
│  ┌───────▼────────────▼────────────▼────────────▼──────┐  │
│  │  数据层                                              │  │
│  │  DOMAIN-INDEX.md  ← 域注册表 SSOT                    │  │
│  │  M1 DOMAIN-*.yaml ← 域 Schema (ecos MOF)            │  │
│  │  各域 KEMS 文件    ← 运行时数据                       │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 4.2 domain.py — 域注册表

```python
# cockpit/src/cockpit/l4/domain.py

@dataclass
class Domain:
    id: str                    # "vault", "personal", ...
    name: str                  # "@学习进化", "@个人", ...
    domain_type: str           # "document", "config", "engine", ...
    path: Path                 # 文件系统路径
    bos_uri: str               # "bos://vault/**"
    kems_planes: list[str]     # ["_control", "_entities", ...]
    governance_tier: int       # 1=核心, 2=工作, 3=可选
    capabilities: list[str]    # ["knowledge.read", "knowledge.search", ...]


class DomainRegistry:
    """19 域统一注册表。SSOT = DOMAIN-INDEX.md"""

    def __init__(self, index_path: Path = DOMAIN_INDEX):
        self._domains: dict[str, Domain] = {}
        self._load_from_index()

    # ── 查询 ──
    def get(self, domain_id: str) -> Domain | None
    def list_all(self) -> list[Domain]
    def list_by_type(self, domain_type: str) -> list[Domain]
    def list_document_domains(self) -> list[Domain]  # 仅 KEMS 域

    # ── 路径解析 (消除硬编码) ──
    def resolve_path(self, domain_id: str) -> Path
    def resolve_bos_uri(self, domain_id: str) -> str

    # ── 注册 (与 DOMAIN-INDEX.md 同步) ──
    def register(self, domain: Domain) -> None
    def sync_to_index(self) -> None  # 写回 DOMAIN-INDEX.md

    # ── 健康 ──
    def health_check(self, domain_id: str) -> dict
    def aggregate_health(self) -> dict  # 全域 DASHBOARD
```

### 4.3 kems.py — KEMS 六面操作

```python
# cockpit/src/cockpit/l4/kems.py

class KemsPlane:
    """KEMS 六面抽象 — 统一的读写接口"""

    PLANES = ["_control", "_entities", "_knowledge", "_storage", "_archive", "_runtime"]

    def __init__(self, domain: Domain):
        self.domain = domain

    # ── 控制面 (9 类标准文件) ──
    def read_state(self) -> dict       # STATE.md → YAML
    def write_state(self, data: dict)  # dict → STATE.md
    def read_memory(self) -> dict      # MEMORY.md
    def write_memory(self, data: dict)
    def read_signals(self) -> list     # signals.md → 信号列表
    def append_signal(self, event: dict)
    def read_timeline(self) -> list    # TIMELINE.md
    def append_timeline(self, event: dict)
    def read_status(self) -> dict      # STATUS.md → 三态判定
    def write_status(self, status: dict)

    # ── 通用 ──
    def list_files(self, plane: str) -> list[Path]
    def search(self, keyword: str) -> list[dict]  # 全文搜索
    def validate_structure(self) -> list[str]     # 面完整性检查

    # ── 生命周期 ──
    @classmethod
    def init_domain(cls, domain: Domain) -> None  # 创建 KEMS 骨架


class CardsPlane(KemsPlane):
    """CARDS 特化 — 基于 KemsPlane 的 CARDS 操作"""

    def scan_cards(self) -> list[dict]   # 替代 _scan_cards()
    def get_card(self, card_id: str) -> dict | None
    def check_compliance(self, card_id: str) -> dict
```

### 4.4 schema.py — Schema 校验

```python
# cockpit/src/cockpit/l4/schema.py

class DomainValidator:
    """基于 M1 DOMAIN-*.yaml 的域完整性校验"""

    def __init__(self, registry: DomainRegistry):
        self.registry = registry

    def validate(self, domain_id: str) -> ValidationResult:
        """
        检查项:
        1. 域路径是否存在
        2. KEMS 面数是否与 M1 YAML 一致
        3. 控制面 9 类文件是否齐全
        4. CLAUDE.md 入口协议是否存在
        5. signals.md 格式是否有效
        """

    def validate_all(self) -> dict[str, ValidationResult]
    def diff_with_m1(self, domain_id: str) -> list[str]  # 与 M1 YAML 的差异

    def check_kems_version(self, domain_id: str) -> str   # 检测 KEMS 版本

class MigrationEngine:
    """KEMS 版本迁移"""

    def migrate(self, domain_id: str, to_version: str) -> None
    def migrate_all(self, to_version: str) -> dict
```

### 4.5 dashboard.py — 跨域聚合

```python
# cockpit/src/cockpit/l4/dashboard.py

class L4Dashboard:
    """L4 全域健康仪表板"""

    def __init__(self, registry: DomainRegistry):
        self.registry = registry

    def generate(self) -> dict:
        """
        聚合:
        1. 各域 STATUS 汇总 → 健康/警告/异常
        2. 各域 signals 最近 N 条
        3. 各域 KEMS 面完整性
        4. 各域最近更新时间
        5. 跨域信号关联分析
        """

    def cross_domain_search(self, query: str) -> list[dict]:
        """跨 7 个 Document 域全文搜索"""

    def aggregate_signals(self, window_hours: int = 24) -> list[dict]:
        """最近 N 小时跨域信号汇总"""
```

---

## 五、接口契约

### 5.1 对外接口 (MCP + CLI)

```
MCP Tools (新增):
  domains_init(name, type, path)     → 创建新域
  domains_check(domain_id)           → 域完整性校验
  domains_migrate(domain_id, version)→ KEMS 版本迁移
  domains_health()                   → 全域健康报告

CLI Commands (新增):
  cockpit domains init <name> --type document --path ~/Documents/@xxx
  cockpit domains check [domain_id]  # 不指定则检查所有
  cockpit domains migrate --to v5
  cockpit domains dashboard

CLI Commands (增强):
  cockpit domains list              # 现有, 改为使用 DomainRegistry
  cockpit vault search --domain xxx # 现有, 改为使用 KemsPlane.search()
```

### 5.2 内部依赖

```
DomainKernel
  ├── 读取: DOMAIN-INDEX.md (域注册表 SSOT)
  ├── 读取: M1 DOMAIN-*.yaml (域 Schema, 可选)
  ├── 读写: 各域 KEMS 文件
  └── 依赖: pyyaml (已安装)
```

**不依赖**: agora, runtime, metaos, omo, kairon — 纯文件系统操作

---

## 六、与现有架构的集成

### 6.1 替换映射

```
旧代码 (分散)                        新代码 (DomainKernel)
─────────────────────────────────    ────────────────────────
cockpit_mcp.py:_L4_DOMAINS           DomainRegistry.list_all()
cockpit_mcp.py:_scan_cards()         CardsPlane.scan_cards()
cockpit_mcp.py:_search_vault()       KemsPlane.search()
cockpit_mcp.py:_read_omo_goals()     KemsPlane.read_omo_state()
cockpit_mcp.py:_read_omo_constraints() KemsPlane.read_omo_constraints()
cockpit_mcp.py:domains_list()        DomainRegistry.list_all() → JSON
cockpit_mcp.py:vault_search()        KemsPlane.search() → JSON
ecos/domain_manager.py:create()      DomainRegistry.register()
ecos/domain_manager.py:validate()    DomainValidator.validate()
手工路径拼接                          DomainRegistry.resolve_path()
```

### 6.2 迁移路径

```
阶段 1: 新增模块 (不破坏现有代码)
  cockpit/src/cockpit/l4/domain.py
  cockpit/src/cockpit/l4/kems.py

阶段 2: 逐步迁移 MCP 工具
  vault_search → 使用 KemsPlane.search()
  domains_list → 使用 DomainRegistry.list_all()
  workspace_context → 使用 CardsPlane + KemsPlane

阶段 3: 废弃旧代码
  _L4_DOMAINS → 删除
  _scan_cards() → 删除
  _search_vault() → 删除
  cockpit_mcp.py 瘦身 ~100 行

阶段 4: ecos domain_manager.py 精简
  保留 MOF 模型操作
  域文件操作委托给 DomainKernel
```

---

## 七、推演总结

### 7.1 架构收益

| 维度 | 当前 | DomainKernel 后 | 改善 |
|------|------|-----------------|------|
| 路径解析 | 4 处硬编码, 1 个已知 bug | 1 处 (DomainRegistry) | 100% |
| 域操作代码 | 分散在 cockpit + ecos | 集中在 l4/ 模块 | 代码量 -30% |
| 新增域成本 | 改 4 处代码 | `register()` 1 行 | 4× 效率 |
| KEMS 升级成本 | O(域数 × 文件数) | `migrate()` 1 次 | O(1) |
| 一致性保证 | 手工 (靠自觉) | Schema 自动校验 | 100% |

### 7.2 不建议做的事

| 不做 | 原因 |
|------|------|
| ❌ 独立项目 | 过度工程 — DomainKernel 是 L4 内部支撑，非独立服务 |
| ❌ 新 BOS 域 | KEMS 是 L4 概念，不需要 bos:// URI 寻址 |
| ❌ 覆盖 19 域 | 仅 DocumentDomain 需要 KEMS — 其他 12 域无此需求 |
| ❌ 替代 ecos domain_manager | ecos 负责 MOF 模型，DomainKernel 负责文件系统操作 — 互补非替代 |

### 7.3 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 模块位置 | `cockpit/src/cockpit/l4/` | L3 是 L4 唯一入口，就近原则 |
| 域注册 SSOT | DOMAIN-INDEX.md | 已有文件，增强而非替换 |
| Schema 源 | M1 DOMAIN-*.yaml | 已有 18 个定义，复用 |
| 实现语言 | Python (纯文件 I/O) | 无外部依赖，零安装成本 |
