# L4 Kernel · 全面设计

**2026-06-08 · 完整架构 · 从约束到实现**

---

## 一、设计目标

### 1.1 一句话定位

**L4 Kernel 是 L4 自我层的操作系统内核 — 它为 19 个域提供统一的管理面，让上层通过 API 而非文件路径操作 L4 数据。**

### 1.2 四个核心目标

| 目标 | 现状 | 目标态 |
|------|------|--------|
| 域注册 | 硬编码在 cockpit_mcp.py | DomainRegistry 19 域统一管理 |
| KEMS 操作 | 分散在 cockpit/ecos 两处 | KemsPlane 统一读写接口 |
| 健康聚合 | 无 | DomainHealth 跨域 DASHBOARD |
| Agent 约束 | CLAUDE.md 纯文本 | Schema 注入 CLAUDE.md + 事后校验 |

---

## 二、完整模块架构

```
projects/l4-kernel/
│
├── src/l4_kernel/
│   │
│   ├── registry.py          ✅ DomainRegistry — 19域统一注册表
│   │   ├── Domain (基类)
│   │   ├── DomainRegistry (CRUD + 路径解析 + 健康聚合)
│   │   └── 内置 19 域默认注册表
│   │
│   ├── domain_types.py      ✅ 7 种域类型特化
│   │   ├── DocumentDomain  (KEMS六面 + 存储统计)
│   │   ├── ConfigDomain    (YAML/JSON 读写 + Schema 校验)
│   │   ├── ToolDomain      (脚本列表 + 可执行检查)
│   │   ├── WorkspaceDomain (文件索引 + 搜索)
│   │   ├── StorageDomain   (磁盘使用 + 挂载检查)
│   │   ├── ModelDomain     (模型列表 + SHA256)
│   │   ├── EngineDomain    (进程检查 + 配置 + 日志)
│   │   └── wrap_domain()   (工厂函数)
│   │
│   ├── kems.py              ✅ KEMS 六面统一操作
│   │   ├── KemsPlane       (STATE/MEMORY/signals/TIMELINE/STATUS)
│   │   └── CardsPlane      (CARDS 扫描/获取/合规检查)
│   │
│   ├── templates.py         ✅ 标准模板 + Schema 校验
│   │   ├── 5 个标准模板     (MEMORY/STATUS/signals/control-rules/STATE)
│   │   ├── KemsValidator   (7 条校验规则)
│   │   └── init_domain_kems() (域骨架生成)
│   │
│   ├── health.py            🔜 DomainHealth — 跨域健康聚合
│   │   ├── DomainHealth
│   │   ├── aggregate_health()
│   │   ├── check_freshness()    (X2 新鲜度)
│   │   ├── cross_domain_search()
│   │   └── generate_dashboard()
│   │
│   ├── signals.py           🔜 跨域信号总线
│   │   ├── SignalBus
│   │   ├── route_signal()       (信号 → 域路由)
│   │   └── aggregate_signals()  (跨域信号汇总)
│   │
│   ├── claude_injector.py   🔜 CLAUDE.md 约束注入
│   │   ├── generate_entrypoint()  (生成含 Schema 的 CLAUDE.md)
│   │   ├── inject_all_domains()   (批量更新所有域)
│   │   └── diff_entrypoint()      (对比当前与模板)
│   │
│   ├── cli.py               ✅ CLI 入口
│   │   ├── l4-kernel domain list/info/check/init
│   │   ├── l4-kernel health
│   │   └── l4-kernel kems search/validate
│   │
│   └── __init__.py          ✅ 公开 API
│
├── tests/
│   ├── test_registry.py     ✅ 21 tests
│   ├── test_kems.py         ✅ 24 tests
│   ├── test_domain_types.py ✅ 31 tests
│   ├── test_templates.py    ✅ 12 tests
│   ├── test_health.py       🔜
│   └── test_signals.py      🔜
│
├── pyproject.toml           ✅ hatchling, Python 3.13+, pyyaml
├── Makefile                 ✅ test/lint/fmt/install
├── INTERFACE.yaml           ✅
├── CLAUDE.md                ✅
├── AGENTS.md                ✅
└── README.md                ✅
```

---

## 三、待实现模块详细设计

### 3.1 health.py — 跨域健康聚合

```python
class DomainHealth:
    """跨域健康聚合与 DASHBOARD 生成。"""

    def __init__(self, registry: DomainRegistry):
        self.registry = registry

    def aggregate_health(self) -> dict:
        """
        返回:
        {
          "total": 19,
          "existing": 16,
          "missing": 3,
          "health_rate": "84.2%",
          "by_type": { ... },
          "document_domains": {
            "vault": {
              "status": "STABLE",
              "kems_valid": true,
              "violations": 0,
              "freshness_score": 0.95,
              "last_signal_ts": "2026-06-08T10:00:00Z",
            },
            ...
          }
        }
        """

    def check_freshness(self, domain_id: str) -> dict:
        """X2 新鲜度检查。
        - STATE.md last-reviewed > 30 天 → ⚠️
        - signals.md 最近 7 天无更新 → ⚠️
        - STATUS.md 在 ALERT 状态 > 7 天 → 🔴
        """

    def cross_domain_search(self, query: str) -> list[dict]:
        """跨 8 个 DocumentDomain 全文搜索。"""

    def generate_dashboard(self) -> str:
        """生成 Markdown 格式的全域 DASHBOARD。"""

    def get_violations(self) -> dict[str, list[dict]]:
        """获取所有域的 Schema violations。
        返回: {domain_id: [violation, ...]}
        """
```

### 3.2 signals.py — 跨域信号总线

```python
class SignalBus:
    """跨域信号路由与聚合。

    信号分类:
    - domain 内信号: 写入域的 signals.md
    - 跨域信号: 写入 @驾驶舱 signals.md (来源域/波及域)
    - 系统信号: 写入 OMO state
    """

    def __init__(self, registry: DomainRegistry):
        self.registry = registry

    def emit(self, domain_id: str, signal_type: str, message: str,
             cross_domain: bool = False) -> None:
        """发射信号到域 signals.md。

        如果 cross_domain=True，同时写入 @驾驶舱。
        """

    def aggregate_recent(self, window_hours: int = 24) -> list[dict]:
        """聚合最近 N 小时所有域的信号。"""

    def detect_patterns(self) -> list[dict]:
        """检测跨域信号模式。
        - 多个域同时出现 ⚠️ → 可能是系统性风险
        - 同一域连续 🔴 → 升级为 CRITICAL
        """
```

### 3.3 claude_injector.py — CLAUDE.md 约束注入

```python
class ClaudeInjector:
    """将 l4-kernel Schema 约束注入域的 CLAUDE.md。

    这是路径 2 (Agent 直入) 约束机制的核心。
    """

    SCHEMA_RULES = """
    ## §0.1 控制面强制规范 (l4-kernel Schema)

    修改以下文件时，必须遵守:

    - **STATE.md**: frontmatter 必含 title, status, type, owner, created
    - **MEMORY.md**: 同上
    - **signals.md**: 信号类型 = ✅⚠️🔴ℹ️ | 格式 = `| 类型 | 日期 | 信号 |`
    - **STATUS.md**: 当前状态 = STABLE|ALERT|CRITICAL | 必须含三态定义表
    - **control-rules.md**: CR ID = CR01-CR99 | CR01-CR03 为内核规则(不可删)

    ## §0.2 操作后校验

    修改任何控制面文件后，执行:
    ```
    l4-kernel domain check {domain_id}
    ```

    如果 check 报 error (红色)，必须修复后重新操作。
    warning (黄色) 建议修复，info (灰色) 可忽略。
    """

    def __init__(self, registry: DomainRegistry):
        self.registry = registry

    def generate(self, domain_id: str) -> str:
        """为指定域生成增强版 CLAUDE.md。"""

    def inject_all(self) -> dict[str, bool]:
        """批量更新所有 DocumentDomain 的 CLAUDE.md。
        保留现有内容，在 §0 和 §1 之间插入 Schema 约束。
        """

    def diff(self, domain_id: str) -> list[str]:
        """对比当前 CLAUDE.md 与模板的差异。"""

    def validate_all_entrypoints(self) -> dict[str, bool]:
        """检查所有域的 CLAUDE.md 是否包含 Schema 约束。"""
```

---

## 四、CLI 命令完整设计

```
l4-kernel domain list [--type=<t>] [--json]    # 列出域
l4-kernel domain info <domain_id>               # 域详情
l4-kernel domain check [domain_id] [--json]     # Schema 校验 (不指定=全部)
l4-kernel domain init <name> --type document --path <path> [--owner <o>]
l4-kernel domain health [--json]                # 全域健康报告

l4-kernel kems state <domain_id>                # 读取 STATE
l4-kernel kems memory <domain_id>               # 读取 MEMORY
l4-kernel kems signals <domain_id> [--recent N] # 读取信号
l4-kernel kems status <domain_id>               # 读取三态判定
l4-kernel kems search <keyword> [--domain <id>] # 全文搜索
l4-kernel kems validate <domain_id>             # KEMS 结构校验

l4-kernel cards list [--domain <id>] [--priority P0]
l4-kernel cards get <card_id>
l4-kernel cards check <card_id>

l4-kernel claude inject [domain_id]             # 注入 Schema 到 CLAUDE.md
l4-kernel claude inject --all                   # 批量注入
l4-kernel claude diff [domain_id]               # 对比差异
l4-kernel claude validate --all                 # 检查是否已注入

l4-kernel signal emit <domain_id> <type> <msg>  # 发射信号
l4-kernel signal list [--domain <id>] [--recent N]
l4-kernel signal patterns                       # 检测跨域模式

l4-kernel dashboard [--json]                    # 生成全域 DASHBOARD
```

---

## 五、集成计划

### 5.1 cockpit 集成

```python
# cockpit/src/cockpit/scripts/cockpit_mcp.py

# 替换前:
_CARDS_DIR = Path.home() / "Documents" / "驾驶舱" / "CARDS"
_VAULT_DIR = Path.home() / "Documents" / "@学习进化"
_L4_DOMAINS = { ... }  # 硬编码 14 域

# 替换后:
from l4_kernel import DomainRegistry
from l4_kernel.kems import KemsPlane, CardsPlane

_registry = DomainRegistry()

def _search_vault(keyword: str, domain: str = "vault"):
    d = _registry.get(domain)
    if not d:
        return []
    kems = KemsPlane(d.path)
    return kems.search(keyword)

def _scan_cards():
    cockpit = _registry.get("cockpit")
    cards = CardsPlane(cockpit.path)
    return cards.scan_cards()
```

### 5.2 cockpit pyproject.toml

```toml
[project.optional-dependencies]
l4 = ["l4-kernel"]

[tool.uv.sources]
l4-kernel = { path = "../l4-kernel", editable = true }
```

### 5.3 runtime cron 集成

```yaml
# l4_scheduled_jobs.yaml 新增:
- name: "l4-domain-health-scan"
  schedule: "0 6 * * *"
  script: "l4-kernel health --json"
  deliver: "local"
  timeout: 60
  enabled: true

- name: "l4-claude-validate"
  schedule: "0 7 * * *"
  script: "l4-kernel claude validate --all"
  deliver: "local"
  timeout: 30
  enabled: true
```

### 5.4 ecos-link 注册

```bash
# 新增 l4-kernel 到 ecos-link
ecos-link install  # 自动包含 l4-kernel CLI
```

---

## 六、实施路线

| Phase | 内容 | 状态 | 测试 |
|-------|------|:---:|:---:|
| P1 | registry.py + domain_types.py + kems.py + templates.py | ✅ | 88 |
| P2 | health.py + signals.py | 🔜 | ~30 |
| P3 | claude_injector.py | 🔜 | ~15 |
| P4 | cockpit 集成 (替换 _L4_DOMAINS) | 🔜 | — |
| P5 | runtime cron 集成 | 🔜 | — |

---

## 七、架构原则总结

1. **被动 API** — l4-kernel 不主动运行，由上层调用
2. **护栏非防火墙** — 提供正确路径，检测偏离，不强行阻止
3. **信号驱动** — 所有变更通过 signals.md 记录，形成自愈闭环
4. **双路径约束** — agora 路径强约束 (API)，Agent 路径弱约束 (CLAUDE.md + 事后扫描)
5. **零外部依赖** — 仅 pyyaml，可被任何项目 import
6. **渐进式约束** — 创建时建议 → API 强制 → 扫描检测 → 聚合报告
