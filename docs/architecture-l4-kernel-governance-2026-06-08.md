# L4 Kernel · 配置与治理体系

**2026-06-08 · 配置模型 + 治理逻辑 + 定时任务 + L0约束 + 数据面交互**

---

## 一、配置模型

### 1.1 配置层次

```
┌──────────────────────────────────────────────┐
│  环境变量 (最高优先级)                          │
│  L4_DOMAIN_INDEX, L4_HEALTH_INTERVAL, ...    │
├──────────────────────────────────────────────┤
│  项目级配置 (pyproject.toml / .env)             │
│  运行时参数、日志级别                           │
├──────────────────────────────────────────────┤
│  域级配置 (_control/control-rules.md)           │
│  每个域的 CR01-CRN 控制规则                    │
├──────────────────────────────────────────────┤
│  系统默认值 (l4-kernel 内置)                    │
│  _BUILTIN_DOMAINS, 标准模板                    │
└──────────────────────────────────────────────┘
```

### 1.2 配置 Schema

```python
# l4_kernel/config.py (新增)

@dataclass
class L4Config:
    """L4 Kernel 运行时配置。"""
    
    # 域注册
    domain_index_path: Path = Path.home() / "Documents" / "@驾驶舱" / "_control" / "DOMAIN-INDEX.md"
    
    # 健康检查
    health_scan_interval_hours: int = 24          # 定时健康扫描间隔
    freshness_warning_days: int = 30              # STATE.md 新鲜度警告阈值
    freshness_critical_days: int = 90             # STATE.md 新鲜度严重阈值
    signal_stale_warning_days: int = 7            # signals 无更新警告阈值
    status_alert_max_days: int = 7                # STATUS ALERT 持续最大天数
    
    # Schema 校验
    schema_validation_on_write: bool = True       # 写入时自动校验
    schema_validation_on_read: bool = False       # 读取时自动校验
    
    # 信号总线
    signal_retention_days: int = 90               # 信号保留天数
    cross_domain_signal_enabled: bool = True      # 跨域信号写入 @驾驶舱
    pattern_detection_window_hours: int = 72      # 模式检测时间窗口
    
    # CLAUDE.md 注入
    claude_inject_compact_mode: bool = True       # 使用精简版注入
    claude_auto_inject_on_init: bool = True       # 创建域时自动注入
    
    # 日志
    log_level: str = "INFO"
    log_file: Path | None = None
    
    @classmethod
    def from_env(cls) -> "L4Config":
        """从环境变量加载配置。"""
        return cls(
            domain_index_path=Path(os.environ.get(
                "L4_DOMAIN_INDEX",
                str(cls.domain_index_path)
            )),
            health_scan_interval_hours=int(os.environ.get("L4_HEALTH_INTERVAL", "24")),
            freshness_warning_days=int(os.environ.get("L4_FRESHNESS_WARN", "30")),
            # ... 其他字段类似
        )
```

---

## 二、治理逻辑

### 2.1 治理模型

```
L4 Kernel 治理 = 域生命周期管理 + Schema 合规 + 新鲜度保障 + 信号闭环

┌─────────────────────────────────────────────────────────────┐
│                     L4 治理四维                              │
│                                                             │
│  X1 审计链    X2 抗熵       X3 价值栈      X4 一致性         │
│  ─────────    ────────      ────────       ────────         │
│  操作日志     STATE 新鲜度   域活跃度       KEMS Schema      │
│  signals 信号  STATUS ALERT  CARDS 完成率   控制面文件完整性  │
│  KEI audit    定时扫描       跨域 DASHBOARD  与 M1 对比      │
│  OMO debt     信号闭环检测    维护成本评估    CLAUDE.md 校验  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 治理规则引擎

```python
# l4_kernel/governance.py (新增)

class GovernanceEngine:
    """L4 治理规则引擎。
    
    为每个域评估 X1-X4 四个维度的合规状态。
    """
    
    def __init__(self, registry: DomainRegistry, config: L4Config | None = None):
        self.registry = registry
        self.config = config or L4Config()
        self.health = DomainHealth(registry)
        self.signals = SignalBus(registry)
    
    def evaluate_domain(self, domain_id: str) -> GovernanceReport:
        """评估单个域的治理状态。
        
        Returns:
            GovernanceReport {
                domain_id, x1_audit, x2_freshness, x3_value, x4_consistency,
                overall_status, violations, recommendations
            }
        """
    
    def evaluate_all(self) -> dict[str, GovernanceReport]:
        """评估所有域的治理状态。"""
    
    def enforce(self, domain_id: str) -> list[dict]:
        """强制执行治理规则（自动修复可修复的问题）。
        
        可自动修复:
        - 创建缺失的控制面文件（从模板）
        - 更新 frontmatter 缺失字段
        - 写入 signals 信号
        
        需要人工:
        - STATUS CRITICAL 升级
        - 域结构重组
        """
```

### 2.3 治理报告格式

```python
@dataclass
class GovernanceReport:
    domain_id: str
    domain_name: str
    
    # X1 审计链
    x1_audit: dict  # {passed: bool, issues: list, last_audit_ts}
    
    # X2 抗熵
    x2_freshness: dict  # {score: float, warnings: list, criticals: list}
    
    # X3 价值栈
    x3_value: dict  # {activity_score: float, cards_completion_rate, maintenance_cost}
    
    # X4 一致性
    x4_consistency: dict  # {schema_errors: int, schema_warnings: int, m1_diff: list}
    
    # 综合
    overall_status: str  # "STABLE" | "ALERT" | "CRITICAL"
    violations: list[dict]
    recommendations: list[str]
```

---

## 三、定时任务逻辑

### 3.1 定时任务体系

```
┌──────────────────────────────────────────────────────────────┐
│                    L4 定时任务体系                            │
│                                                              │
│  频率          任务                   输出                    │
│  ────────      ──────────────────     ──────────────────      │
│  每小时        signals 模式检测       pattern_report.json     │
│  每日 02:00    域新鲜度扫描            freshness_report.json  │
│  每日 06:00    全域健康聚合            health_dashboard.md    │
│  每日 07:00    CLAUDE.md 校验          injection_status.json  │
│  每日 08:00    Schema 合规扫描         compliance_report.json │
│  每周一 09:00   治理报告生成            governance_report.md   │
│  每月 1日      域归档检查              archive_report.json    │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 定时任务注册 (cron_service)

```yaml
# runtime/cron_service/l4_kernel_jobs.yaml (新增)

jobs:
  # ── 每小时 ─────────────────────────────────────────────────
  - name: "l4-signal-pattern-detect"
    schedule: "0 * * * *"
    script: "l4-kernel signal patterns --json"
    deliver: "local"
    timeout: 30
    enabled: true

  # ── 每日 ───────────────────────────────────────────────────
  - name: "l4-freshness-scan"
    schedule: "0 2 * * *"
    script: "l4-kernel domain check --freshness --json"
    deliver: "local"
    timeout: 60
    enabled: true

  - name: "l4-health-aggregate"
    schedule: "0 6 * * *"
    script: "l4-kernel dashboard --json"
    deliver: "local"
    timeout: 30
    enabled: true

  - name: "l4-claude-validate"
    schedule: "0 7 * * *"
    script: "l4-kernel claude validate --all --json"
    deliver: "local"
    timeout: 30
    enabled: true

  - name: "l4-schema-compliance"
    schedule: "0 8 * * *"
    script: "l4-kernel domain check --all --json"
    deliver: "local"
    timeout: 60
    enabled: true

  # ── 每周 ───────────────────────────────────────────────────
  - name: "l4-governance-report"
    schedule: "0 9 * * 1"
    script: "l4-kernel governance report --all --output ~/Documents/@驾驶舱/_control/DASHBOARD.md"
    deliver: "local"
    timeout: 120
    enabled: true

  # ── 每月 ───────────────────────────────────────────────────
  - name: "l4-archive-check"
    schedule: "0 9 1 * *"
    script: "l4-kernel domain check --archive --json"
    deliver: "local"
    timeout: 60
    enabled: true
```

### 3.3 定时任务调度逻辑

```python
# l4_kernel/scheduler.py (新增)

class L4Scheduler:
    """L4 Kernel 定时任务调度器。
    
    可独立运行或集成到 runtime cron_service。
    """
    
    def __init__(self, registry: DomainRegistry, config: L4Config | None = None):
        self.registry = registry
        self.config = config or L4Config()
        self.health = DomainHealth(registry)
        self.signals = SignalBus(registry)
        self.injector = ClaudeInjector(registry)
    
    def run_hourly(self) -> dict:
        """每小时执行: 信号模式检测。"""
        patterns = self.signals.detect_patterns()
        # 发现模式 → 写入 @驾驶舱 signals
        for p in patterns:
            if p["level"] in ("🔴",):
                self.signals.emit(
                    "cockpit", p["level"], p["message"],
                    source="l4-scheduler", cross_domain=True
                )
        return {"task": "signal_pattern_detect", "patterns_found": len(patterns)}
    
    def run_daily_health(self) -> dict:
        """每日健康聚合。"""
        report = self.health.aggregate_health()
        violations = self.health.get_violations()
        
        # 为每个有 violation 的域发射信号
        for domain_id, vlist in violations.items():
            self.signals.emit_violation_signal(domain_id, vlist)
        
        return {"task": "daily_health", "violations": len(violations)}
    
    def run_daily_freshness(self) -> dict:
        """每日新鲜度扫描。"""
        results = self.health.check_all_freshness()
        alerts = 0
        for domain_id, r in results.items():
            if not r["fresh"]:
                for issue in r["issues"]:
                    self.signals.emit(
                        domain_id, issue["level"], issue["message"],
                        source="l4-freshness-scan"
                    )
                alerts += 1
        return {"task": "freshness_scan", "alerts": alerts}
    
    def run_weekly_governance(self) -> dict:
        """每周治理报告。"""
        dashboard = self.health.generate_dashboard()
        injection_status = self.injector.validate_all()
        
        # 写入 @驾驶舱 DASHBOARD
        cockpit = self.registry.get("cockpit")
        if cockpit and cockpit.exists():
            dashboard_path = cockpit.path / "_control" / "DASHBOARD.md"
            dashboard_path.write_text(dashboard)
        
        return {
            "task": "governance_report",
            "injection_rate": injection_status["rate"],
            "dashboard_written": bool(cockpit and cockpit.exists()),
        }
```

---

## 四、L0 MOF 对本层的约束逻辑

### 4.1 约束来源

```
L0 ecos MOF                     L4 Kernel
─────────────────────────       ─────────────────────────
M3 元元模型                     约束框架定义
  Element → 所有域必须继承        Domain.__init_subclass__
  Layer枚举 → 域必须有layer       Domain.layer 必填
  
M2 元模型                       域类型 Schema
  domain_type 枚举                DomainRegistry.list_by_type()
  kems_planes 可选属性            DocumentDomain.validate_kems_planes()
  governance_tier 1-3            Domain.governance_tier
  capabilities 列表               Domain.capabilities
  
M1 节点实例                      运行时校验
  DOMAIN-*.yaml (18+3个)         KemsValidator.validate_all()
  kems_planes 声明               与 M1 声明对比
  entry_points 定义              域访问入口校验
```

### 4.2 M2→L4 约束映射

```python
# l4_kernel/mof_constraints.py (新增)

class MofConstraints:
    """L0 MOF 模型对 L4 域的约束校验。
    
    读取 ecos MOF M1 DOMAIN-*.yaml，
    对比 L4 Kernel 中的 DomainRegistry，
    确保运行时状态与模型定义一致。
    """
    
    def __init__(self, mof_m1_path: Path, registry: DomainRegistry):
        self.mof_m1_path = mof_m1_path  # ecos/ssot/mof/m1/domain/
        self.registry = registry
    
    def load_m1_domains(self) -> dict[str, dict]:
        """从 M1 YAML 加载域定义。"""
        domains = {}
        for yaml_file in self.mof_m1_path.glob("DOMAIN-*.yaml"):
            data = yaml.safe_load(yaml_file.read_text())
            domains[data["id"]] = data
        return domains
    
    def check_consistency(self) -> list[dict]:
        """检查 M1 模型与 L4 运行时的一致性。
        
        检查项:
        1. M1 中定义的域是否在 DomainRegistry 中注册
        2. kems_planes 声明是否与实际目录一致
        3. domain_type 是否与运行时类型一致
        4. entry_points 是否可访问
        5. capabilities 是否已实现
        """
        m1_domains = self.load_m1_domains()
        issues = []
        
        for domain_id, m1_data in m1_domains.items():
            # 检查 1: 注册
            l4_domain = self.registry.get(domain_id.removeprefix("DOMAIN-"))
            if not l4_domain:
                issues.append({
                    "domain_id": domain_id,
                    "check": "registration",
                    "severity": "warning",
                    "message": f"M1 domain {domain_id} not found in L4 DomainRegistry",
                })
                continue
            
            # 检查 2: KEMS planes
            m1_planes = set(m1_data.get("properties", {}).get("kems_planes", []))
            l4_planes = set(l4_domain.kems_planes)
            if m1_planes and m1_planes != l4_planes:
                missing = m1_planes - l4_planes
                extra = l4_planes - m1_planes
                issues.append({
                    "domain_id": domain_id,
                    "check": "kems_planes",
                    "severity": "error" if missing else "warning",
                    "message": f"KEMS planes mismatch: M1={m1_planes}, L4={l4_planes}",
                    "missing_in_l4": list(missing),
                    "extra_in_l4": list(extra),
                })
            
            # 检查 3: domain_type
            m1_type = m1_data.get("properties", {}).get("domain_type")
            if m1_type and m1_type != l4_domain.domain_type:
                issues.append({
                    "domain_id": domain_id,
                    "check": "domain_type",
                    "severity": "error",
                    "message": f"Type mismatch: M1={m1_type}, L4={l4_domain.domain_type}",
                })
        
        return issues
    
    def enforce_m1_constraints(self) -> dict:
        """强制执行 M1 约束。
        
        可自动修复:
        - 注册 M1 中有但 L4 中缺失的域
        - 更新 kems_planes
        
        需要人工:
        - domain_type 不一致
        """
        issues = self.check_consistency()
        fixed = []
        
        for issue in issues:
            if issue["check"] == "registration":
                # 自动注册
                domain_id = issue["domain_id"].removeprefix("DOMAIN-")
                m1_data = self.load_m1_domains()[issue["domain_id"]]
                props = m1_data.get("properties", {})
                domain = Domain(
                    id=domain_id,
                    name=m1_data.get("name", domain_id),
                    domain_type=props.get("domain_type", "document"),
                    path=Path(props.get("storage", "")),
                    bos_uri=props.get("bos_uri_pattern", f"bos://{domain_id}/**"),
                    kems_planes=props.get("kems_planes", []),
                    governance_tier=props.get("governance_tier", 3),
                    capabilities=props.get("capabilities", []),
                )
                self.registry.register(domain)
                fixed.append({"action": "register", "domain_id": domain_id})
        
        return {"issues": len(issues), "fixed": len(fixed), "details": fixed}
```

### 4.3 M3 顶层约束

```python
# M3 元元模型约束:
# Element → 所有 L4 Domain 必须继承自 Domain 基类 ✅ (已实现)
# Layer枚举 → domain_type 必须合法 ✅ (DomainType Literal)
# Relation.Contains → DocumentDomain 必须包含 kems_planes ✅ (已在 M2 中)
# Relation.Constrains → KemsValidator 实现约束校验 ✅ (7条规则)
# Relation.Audits → DomainHealth 实现审计检查 ✅ (check_freshness)
```

---

## 五、与 Documents 数据面的双向交互

### 5.1 交互模型

```
┌──────────────────────────────────────────────────────────┐
│                    L4 数据面 (~/Documents/@*/)             │
│                                                          │
│  被动数据 · 文件系统 · 不运行代码                           │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  _control/                                         │  │
│  │  ├── STATE.md        ←→ KemsPlane.read/write_state │  │
│  │  ├── MEMORY.md       ←→ KemsPlane.read/write_memory│  │
│  │  ├── signals.md      ←→ SignalBus.emit             │  │
│  │  ├── TIMELINE.md     ←→ KemsPlane.append_timeline  │  │
│  │  ├── STATUS.md       ←→ KemsPlane.read/write_status│  │
│  │  ├── control-rules.md←→ (只读, 人工修改)            │  │
│  │  └── CLAUDE.md       ←→ ClaudeInjector.inject      │  │
│  ├── _entities/         ←→ KemsPlane.list_files       │  │
│  ├── _knowledge/        ←→ KemsPlane.search           │  │
│  ├── _storage/          ←→ DocumentDomain.get_stats   │  │
│  ├── _archive/          ←→ KemsPlane.list_files       │  │
│  └── CARDS/ (cockpit)   ←→ CardsPlane.scan_cards      │  │
└──────────────────────────────────────────────────────────┘
         ↕ 读写                          ↕ 读写
┌──────────────────────────────────────────────────────────┐
│              L4 Kernel 管理面 (projects/l4-kernel/)        │
│                                                          │
│  主动操作 · Python API · 提供统一接口                      │
│                                                          │
│  KemsPlane    ← 六面读写抽象                              │
│  CardsPlane   ← CARDS 特化                               │
│  SignalBus    ← 信号发射与聚合                            │
│  DomainHealth ← 健康聚合与新鲜度                          │
│  KemsValidator← Schema 校验                              │
│  ClaudeInjector ← 约束注入                               │
│  MofConstraints ← L0 模型一致性                          │
└──────────────────────────────────────────────────────────┘
         ↕ import                      ↕ import
┌──────────────────────────────────────────────────────────┐
│              上层调用方 (L3/L2/L1)                        │
│                                                          │
│  cockpit → MCP tools + CLI                               │
│  metaos  → cards_context (Agent prompt 注入)             │
│  minerva → VaultSink (研究写入)                          │
│  omo     → 域审计 + 治理                                 │
│  runtime → cron 定时扫描                                 │
└──────────────────────────────────────────────────────────┘
```

### 5.2 读路径 (数据面 → Kernel → 上层)

```
用户/Agent 需要读取域数据:
  │
  ▼
cockpit MCP / CLI
  │
  ├── cockpit workspace context
  │   → l4_kernel.DomainRegistry.get("cockpit")
  │   → KemsPlane.read_state()
  │   → CardsPlane.scan_cards()
  │   → 返回: Phase + CARDS + 约束 + 引导
  │
  ├── cockpit vault search "关键词"
  │   → l4_kernel.DomainRegistry.get("vault")
  │   → KemsPlane.search("关键词")
  │   → 返回: [{title, path, snippet}, ...]
  │
  └── cockpit health --full
      → l4_kernel.DomainHealth.aggregate_health()
      → l4_kernel.DomainHealth.generate_dashboard()
      → 返回: 全域 DASHBOARD
```

### 5.3 写路径 (上层 → Kernel → 数据面)

```
Agent 完成研究 / 用户更新状态:
  │
  ▼
cockpit MCP / minerva VaultSink
  │
  ├── minerva 研究完成
  │   → l4_kernel.KemsPlane(domain).search(category)
  │   → l4_kernel.KemsPlane(domain).write_state(...)  ← 更新 STATE
  │   → 写入 _storage/ 目录
  │   → l4_kernel.SignalBus.emit("vault", "✅", "研究归档完成")
  │
  ├── cockpit 更新 CARDS
  │   → l4_kernel.CardsPlane.check_compliance(card_id)
  │   → 通过 → 修改文件
  │   → l4_kernel.SignalBus.emit("cockpit", "ℹ️", f"卡片 {card_id} 状态更新")
  │
  └── Agent 直入目录修改文件
      → 定时: l4_kernel.KemsValidator.validate_all()
      → 发现偏离 → SignalBus.emit("⚠️", "Schema violation")
      → Agent 下次 cockpit context → 看到 violation → 修复
```

### 5.4 双向同步机制

```python
# l4_kernel/sync.py (新增)

class DomainSync:
    """L4 Kernel ↔ 数据面双向同步。
    
    确保:
    1. Kernel 中的域注册与 DOMAIN-INDEX.md 一致
    2. KEMS 控制面文件与 Schema 一致
    3. CARDS 状态与 OMO Phase 一致
    """
    
    def __init__(self, registry: DomainRegistry):
        self.registry = registry
    
    def sync_registry_to_index(self) -> dict:
        """Kernel → DOMAIN-INDEX.md: 将注册表写入索引文件。"""
    
    def sync_index_to_registry(self) -> dict:
        """DOMAIN-INDEX.md → Kernel: 从索引文件加载域注册表。
        
        用于:
        - 首次启动
        - 索引文件被外部修改后
        """
    
    def sync_schema_to_control(self, domain_id: str) -> dict:
        """Schema → 控制面: 用标准模板修复控制面文件。
        
        - 缺失文件 → 从模板创建
        - frontmatter 不完整 → 补全
        - 信号格式错误 → 修复
        """
    
    def sync_control_to_schema(self, domain_id: str) -> dict:
        """控制面 → Schema: 从实际文件反推 Schema。
        
        用于:
        - 新域建模 (从已有域提取 Schema)
        - 检测 Schema 与实际的差异
        """
```

### 5.5 交互时序

```
典型的一天:

00:00  ─── 自动 ───
       l4-scheduler.run_hourly() → signal pattern detect

02:00  ─── 自动 ───
       l4-scheduler.run_daily_freshness()
       → 扫描所有域 STATE.md 新鲜度
       → 发现 @卫健委 STATE.md 30天未更新 → emit ⚠️

06:00  ─── 自动 ───
       l4-scheduler.run_daily_health()
       → 聚合所有域健康度
       → 生成 DASHBOARD.md → 写入 @驾驶舱

07:00  ─── 自动 ───
       l4-scheduler → claude validate --all
       → 检查所有域 CLAUDE.md 是否有 Schema 约束

09:00  ─── 用户 ───
       cockpit workspace context
       → l4-kernel 返回:
         - Phase 47 目标
         - 活跃 P0 CARDS
         - ⚠️ @卫健委 STATE.md 需更新
         - DASHBOARD 链接

10:00  ─── Agent ───
       Agent 进入 @卫健委/ 目录
       → 读 CLAUDE.md (含 l4-kernel Schema 约束)
       → 更新 STATE.md (自动遵守 frontmatter 规范)
       → 执行 l4-kernel domain check work-weijian
       → 通过 ✅

12:00  ─── 自动 ───
       l4-scheduler.run_hourly()
       → signal pattern detect
       → 检测到 @卫健委 ✅ 信号 → 问题已闭环
```

---

## 六、实现清单

| 模块 | 文件 | 状态 |
|------|------|:---:|
| 配置模型 | `src/l4_kernel/config.py` | 🔜 |
| 治理引擎 | `src/l4_kernel/governance.py` | 🔜 |
| 定时调度 | `src/l4_kernel/scheduler.py` | 🔜 |
| M2 约束 | `src/l4_kernel/mof_constraints.py` | 🔜 |
| 双向同步 | `src/l4_kernel/sync.py` | 🔜 |
| Cron jobs | `runtime/cron_service/l4_kernel_jobs.yaml` | 🔜 |
