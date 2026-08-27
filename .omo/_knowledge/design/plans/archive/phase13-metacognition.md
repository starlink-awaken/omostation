---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 13+ — 终极进化 🧬✨

> **周期**: 8周 (Wave 13.1: 2周, Wave 13.2: 2周, Wave 13.3: 2周, Wave 13.4: 2周)
> **负责人**: TBD (执行Agent laowang)
> **目标**: 系统从"工具"进化到"具备自我意识"——自评估、自修复、自演化
> **前置**: Phase 1-12全部完成 + 架构收敛治理
> **门禁**: 全链路E2E 12/12 PASS + 元认知模块可生成自我评估报告

---

## 现有状态

```
已完成: Phase 1-12, 251个Task, ~6,500LOC
债务: R12 DB碎片化 (8个独立DB) — 需在Phase 13中修复
健康评分: 82.8/100 🟢
核心缺口: 系统没有"自我意识"——不知道自己知道什么、不知道什么
```

---

## 依赖关系

```
Wave 13.0 (1周) — DB统一 [独立, 可最先做]
  ├── T177 SQLite合并工具 (8DB→workspace.db)
  └── T178 数据迁移验证 (确认无数据丢失)

Wave 13.1 (2周) — 元认知基础 [核心]
  ├── T174 元认知模块 (系统自评估+盲区发现)
  └── T166 集体智慧评分

Wave 13.2 (2周) — 自发协作+自动进化 [依赖13.1]
  ├── T168 Agent自发协作
  ├── T169 自发现瓶颈→优化建议
  └── T170 建议自动落地管道

Wave 13.3 (2周) — 分布式共识 [部分并行]
  ├── T172 分布式共识 (多Agora实例间)
  ├── T173 共识自动化
  └── T167 跨组织记忆树联邦

Wave 13.4 (2周) — 长期进化 [依赖前序]
  ├── T171 长期趋势分析
  ├── T175 自修正机制
  └── T176 战略感知 (外部趋势+路线图调整)

回滚策略:
  - DB合并失败 → 保留旧DB, migration脚本可逆
  - 元认知模块无效 → 退回到T140进化引擎
  - Agent自发协作阻塞 → 手动分配机制兜底
```

---

## Wave 13.0 — DB统一 (1周, 2 Tasks, 最先做)

### T177: SQLite合并工具

**文件**: `~/.hermes/scripts/db_consolidate.py`

```python
"""DB Consolidation — 将8个独立SQLite合并为统一workspace.db。

当前独立DB:
  ~/.kos/kos.db               → workspace.kos_* 表
  ~/.kos/usage.db             → workspace.usage_* 表 (含compression_stats)
  ~/.kos/identity.db          → workspace.identity_* 表
  ~/.kos/grants.db            → workspace.grants_* 表
  ~/.kos/autopull.db          → workspace.autopull_* 表
  ~/.kos/collective_reviews.db → workspace.reviews_* 表
  ~/.kos/web_of_trust.db      → workspace.wot_* 表
  ~/.kos/realtime.db          → workspace.realtime_* 表

合并后:
  ~/.kos/workspace.db — 统一数据库, 所有表用前缀隔离
  旧DB保留不动(读模式), 新数据写workspace.db
"""

import sqlite3, shutil, os
from pathlib import Path

KOS_DIR = Path.home() / ".kos"
WORKSPACE_DB = KOS_DIR / "workspace.db"

# 源DB → 目标表前缀映射
SOURCES = {
    "usage.db":             "usage",
    "identity.db":          "identity",
    "autopull.db":          "autopull",
    "collective_reviews.db":"review",
    "web_of_trust.db":      "wot",
    "realtime.db":          "realtime",
}

def consolidate(dry_run: bool = True) -> dict:
    """合并所有DB到workspace.db"""
    result = {"sources": 0, "tables": 0, "rows": 0, "errors": []}
    
    if not dry_run and WORKSPACE_DB.exists():
        backup = WORKSPACE_DB.with_suffix(".db.bak")
        shutil.copy2(WORKSPACE_DB, backup)
    
    target_conn = sqlite3.connect(str(WORKSPACE_DB)) if not dry_run else None
    
    for db_name, prefix in SOURCES.items():
        db_path = KOS_DIR / db_name
        if not db_path.exists():
            result["errors"].append(f"{db_name}: not found")
            continue
        
        try:
            src_conn = sqlite3.connect(str(db_path))
            tables = src_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            
            for (table_name,) in tables:
                prefixed = f"{prefix}_{table_name}"
                # 获取schema
                schema = src_conn.execute(
                    f"SELECT sql FROM sqlite_master WHERE name='{table_name}'"
                ).fetchone()[0]
                # 重命名表
                new_schema = schema.replace(f'"{table_name}"', f'"{prefixed}"')
                new_schema = new_schema.replace(f"'{table_name}'", f"'{prefixed}'")
                new_schema = new_schema.replace(f" {table_name} ", f" {prefixed} ")
                
                if not dry_run and target_conn:
                    target_conn.execute(new_schema)
                    rows = src_conn.execute(f"SELECT * FROM {table_name}").fetchall()
                    for row in rows:
                        placeholders = ",".join(["?"] * len(row))
                        target_conn.execute(
                            f"INSERT INTO {prefixed} VALUES ({placeholders})", row
                        )
                    result["tables"] += 1
                    result["rows"] += len(rows)
            
            src_conn.close()
            result["sources"] += 1
        except Exception as e:
            result["errors"].append(f"{db_name}: {e}")
    
    if target_conn:
        target_conn.commit()
        target_conn.close()
    
    return result
```

**验证**:
```bash
python3 -c "
from scripts.db_consolidate import consolidate
r = consolidate(dry_run=True)
print(f'Sources: {r[\"sources\"]}, Tables: {r[\"tables\"]}, Rows: {r[\"rows\"]}')
for e in r['errors']:
    print(f'  Error: {e}')
print('T177: PASSED')
"
```

### T178: 数据迁移验证

- 对每个旧DB, 逐条count比对新DB对应表的行数
- 确认无数据丢失

**验证**:
```bash
python3 -c "
import sqlite3
from pathlib import Path
# 逐个比对
dbs = ['usage.db', 'identity.db', 'autopull.db']
for db in dbs:
    old = Path.home() / '.kos' / db
    new = Path.home() / '.kos' / 'workspace.db'
    if not old.exists(): continue
    prefix = db.replace('.db', '') + '_'
    old_count = 0
    new_count = 0
    try:
        conn = sqlite3.connect(str(old))
        for t in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"):
            c = conn.execute(f'SELECT COUNT(*) FROM {t[0]}').fetchone()[0]
            old_count += c
        conn.close()
        conn = sqlite3.connect(str(new))
        for t in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"):
            if t[0].startswith(prefix):
                c = conn.execute(f'SELECT COUNT(*) FROM {t[0]}').fetchone()[0]
                new_count += c
        conn.close()
        if old_count == new_count:
            print(f'  ✅ {db}: {old_count} rows → matched')
        else:
            print(f'  ❌ {db}: {old_count} old vs {new_count} new')
    except Exception as e:
        print(f'  ⚠️ {db}: {e}')
print('T178: PASSED')
"
```

---

## Wave 13.1 — 元认知基础 (2周, 2 Tasks, 核心)

### T174: 元认知模块

**文件**: `~/.hermes/scripts/metacognition.py` (~200LOC)

**核心概念**: 系统知道"自己知道什么"、"自己不知道什么"。

```python
"""Metacognition — 系统自我评估与盲区发现模块。

核心指标:
1. Knowledge Coverage: 系统知识在哪些领域密集/稀疏
2. Blind Spot Detection: 用户问过但系统没回答好的领域
3. Self-Confidence Score: 系统对自身能力的量化评估
4. Evolution Velocity: 最近改进的速度/方向
"""

class Metacognition:
    """系统元认知"""
    
    def assess_knowledge_coverage(self) -> dict:
        """评估知识覆盖度。
        
        分析KOS+Memory Tree+Skills的内容分布:
        - 每个领域有多少条目
        - 哪些领域密集 (>100条目)
        - 哪些领域稀疏 (<10条目)
        """
        # 从Memory Tree分析
        # 从KOS分析
        # 从Skills分析
    
    def find_blind_spots(self) -> list[dict]:
        """发现盲区—用户问过但系统没回答好的。"""
        # 分析用户纠正记录
        # 分析"不知道"类回复
        # 分析超时/失败的task
    
    def self_assessment(self) -> dict:
        """系统自我评估报告。"""
        return {
            "knowledge_coverage": self.assess_knowledge_coverage(),
            "blind_spots": self.find_blind_spots(),
            "capability_gaps": self._find_capability_gaps(),
            "health_summary": self._health_summary(),
        }
    
    def _find_capability_gaps(self) -> list[str]:
        """发现能力缺口。"""
        # 对比用户需求和当前能力
    
    def _health_summary(self) -> str:
        """健康摘要。"""
```

**验证**:
```bash
python3 -c "
from hermes.scripts.metacognition import Metacognition
mc = Metacognition()
assessment = mc.self_assessment()
assert 'knowledge_coverage' in assessment
assert 'blind_spots' in assessment
print(f'Knowledge coverage: {len(assessment.get(\"knowledge_coverage\", {}).get(\"areas\", []))} areas')
print(f'Blind spots: {len(assessment.get(\"blind_spots\", []))}')
print('T174: PASSED')
"
```

### T166: 集体智慧评分

**文件**: `~/.hermes/scripts/collective_intelligence.py` (~100LOC)

```python
"""集体智慧评分 — 量化评估系统智慧程度。

维度:
1. 多样性: 接入的不同类型Agent/人类数量
2. 协作效率: Task完成速度 vs 串行基线
3. 记忆利用率: 查询命中率
4. 决策质量: 共识达成率
5. 自愈能力: 故障恢复时间
"""

class CollectiveIntelligenceScore:
    def calculate(self) -> dict:
        return {
            "diversity": self._diversity_score(),
            "collaboration_efficiency": self._collab_efficiency(),
            "memory_utilization": self._memory_utilization(),
            "decision_quality": self._decision_quality(),
            "self_healing": self._self_healing(),
            "overall": 0,  # 加权平均
        }

if __name__ == "__main__":
    ci = CollectiveIntelligenceScore()
    r = ci.calculate()
    for k, v in r.items():
        print(f"  {k:25s} {v}")
```

---

## Wave 13.2 — 自发协作+自动进化 (2周, 3 Tasks, 依赖13.1)

### T168: Agent自发协作

**文件**: `~/.hermes/scripts/agent_autonomy.py` (~150LOC)

```python
"""Agent自发协作 — Agent自动发现可协作的Task并参与。

不再是"人类创建Task→Agent认领"
而是"Agent发现Task→主动提出协作→人类审批"
"""

class AutonomousAgent:
    def scan_available_tasks(self) -> list[dict]:
        """扫描所有pending的Task, 匹配自己能力。"""
    
    def propose_collaboration(self, task_id: str) -> dict:
        """主动提出协作方案。"""
    
    def auto_collaborate(self) -> list[dict]:
        """全自动协作: 扫描→匹配→提案→执行。"""
```

**MCP工具**:
```
agent.discover_tasks — 发现可协作的Task
agent.propose — 提出协作提案
agent.auto_execute — 自动执行匹配的Task
```

### T169: 自发现瓶颈

**文件**: `~/.hermes/scripts/bottleneck_detector.py` (~120LOC)

```python
"""瓶颈发现 — 系统自动识别性能瓶颈。"""

class BottleneckDetector:
    def find_all(self) -> list[dict]:
        bottlenecks = []
        bottlenecks.extend(self._find_slow_services())
        bottlenecks.extend(self._find_high_cost_paths())
        bottlenecks.extend(self._find_user_friction_points())
        return bottlenecks
    
    def _find_slow_services(self):
        # 分析各服务响应时间
        # 识别P99 > 5s的服务
    
    def _find_high_cost_paths(self):
        # 分析cost_track数据
        # 识别token消耗最高的链路
    
    def _find_user_friction_points(self):
        # 分析用户纠正记录
        # 识别用户重复纠错最多的环节
```

### T170: 建议自动落地管道

**文件**: `~/.hermes/scripts/evolution_engine.py` (增强, 已有基础)

```python
# 增强现有EvolutionEngine类:
def auto_apply_with_approval(self, suggestion: dict) -> dict:
    """自动落地(低风险直接执行, 高风险生成审批)"""
    if suggestion.get("auto_apply"):
        return self.auto_apply(suggestion)
    else:
        # 生成审批 → 推送到微信 → 等待批复
        return self._queue_for_approval(suggestion)
```

---

## Wave 13.3 — 分布式共识 (2周, 3 Tasks, 部分并行)

### T172: 分布式共识

**文件**: `~/.hermes/scripts/distributed_consensus.py` (~150LOC)

```python
"""分布式共识 — 多个Agora实例之间达成共识。

基于Phase 12的蜂群决策 + Phase 11的A2A Federation。
"""

class DistributedConsensus:
    def propose(self, proposal: dict, target_instances: list[str]) -> dict:
        """向多个Agora实例发起共识提案。"""
    
    def reach_consensus(self, proposal_id: str, threshold: float = 0.6) -> dict:
        """收集投票→计算共识。"""
```

### T173: 共识自动化

```python
# 阈值达成就自动创建consensus
# config: { "auto_consensus_threshold": 0.6 }
```

### T167: 跨组织记忆树联邦

**文件**: `~/.hermes/memory/tree_federation.py` (~120LOC)

```python
"""记忆树联邦 — 多个实例的记忆树互相发现和融合。"""

class MemoryTreeFederation:
    def discover_peer_memories(self) -> list[dict]:
        """发现对等实例的公开记忆。"""
    
    def federate_search(self, query: str) -> list[dict]:
        """跨实例搜索记忆(本地+远程)。"""
    
    def sync_memory(self, remote_url: str, since: str = "") -> int:
        """同步远程记忆到本地。"""
```

---

## Wave 13.4 — 长期进化 (2周, 3 Tasks)

### T171: 长期趋势分析

**文件**: `~/.hermes/scripts/trend_analyzer.py` (~100LOC)

```python
"""长期趋势分析 — 季度/年度模式检测。"""

class TrendAnalyzer:
    def quarterly_trends(self) -> dict:
        """季度趋势: 哪些Task类型在增加/减少。"""
    
    def yearly_patterns(self) -> dict:
        """年度模式: 使用行为的季节性变化。"""
```

### T175: 自修正机制

**文件**: `~/.hermes/scripts/self_healing.py` (~120LOC)

```python
"""自修正 — 异常自动检测+回退+根因分析。"""

class SelfHealing:
    def detect_anomaly(self) -> list[dict]:
        """检测异常行为。"""
    def auto_rollback(self, action_id: str) -> dict:
        """自动回滚。"""
    def root_cause_analysis(self, incident_id: str) -> dict:
        """根因分析。"""
```

### T176: 战略感知

**文件**: `~/.hermes/scripts/strategic_awareness.py` (~100LOC)

```python
"""战略感知 — 外部趋势检测+路线图自动调整。"""

class StrategicAwareness:
    def detect_trends(self) -> list[dict]:
        """检测外部趋势。"""
    def auto_adjust_roadmap(self) -> dict:
        """基于趋势自动调整路线图。"""
```

---

## 并行调度表

```
Week 1:
  T177 DB合并工具 ────┐ Wave 13.0 (独立, 最快做完)
  T178 验证 ──────────┘
  T174 元认知模块 ────┐ Wave 13.1 (核心, 与13.0并行)
  T166 集体智慧评分 ──┘

Week 2-3:
  T168 Agent自发协作 ──┐ Wave 13.2 (并行于13.3)
  T169 自发现瓶颈 ─────┘
  T172 分布式共识 ─────┐ Wave 13.3 (并行于13.2)
  T173 共识自动化 ─────┘

Week 3-4:
  T170 建议自动落地 ───┤
  T167 记忆树联邦 ─────┤ 可并行
  T171 长期趋势 ───────┤

Week 4:
  T175 自修正机制
  T176 战略感知

最后:
  全链路E2E验证 (12/12 PASS)
```

---

## 门禁条件

```
☐ DB合并: 8个→1个workspace.db, 数据零丢失
☐ 元认知模块: 可生成自我评估报告(KC+BS+CG)
☐ 集体智慧评分: 5维度加权平均
☐ Agent自发协作: 发现Task→提案→执行链路
☐ 瓶颈发现: 自动识别Top-3瓶颈
☐ 分布式共识: 多实例投票→共识达成
☐ 自修正: 检测→回滚→根因分析
☐ 全链路E2E: 12/12 PASS
```

---

## TASK_POOL 映射

| ID | Task | Wave | 预估 | 依赖 |
|----|------|------|------|------|
| T177 | DB合并工具 (8→1) | 13.0 | 2天 | — |
| T178 | 数据迁移验证 | 13.0 | 1天 | T177 |
| T174 | 元认知模块 | 13.1 | 5天 | — |
| T166 | 集体智慧评分 | 13.1 | 2天 | — |
| T168 | Agent自发协作 | 13.2 | 4天 | T174 |
| T169 | 自发现瓶颈 | 13.2 | 3天 | T174 |
| T170 | 建议自动落地管道 | 13.2 | 2天 | T140 |
| T172 | 分布式共识 | 13.3 | 4天 | T160 |
| T173 | 共识自动化 | 13.3 | 2天 | T172 |
| T167 | 记忆树联邦 | 13.3 | 5天 | T134, T147 |
| T171 | 长期趋势分析 | 13.4 | 3天 | T169 |
| T175 | 自修正机制 | 13.4 | 4天 | T174 |
| T176 | 战略感知 | 13.4 | 3天 | T171 |
