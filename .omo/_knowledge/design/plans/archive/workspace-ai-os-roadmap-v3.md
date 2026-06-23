---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Workspace AI OS 全景路线图 v3 — Phase 9 至 终局

> 版本: v3.0 | 日期: 2026-05-25
> 范围: Phase 9-13+, 全屏覆盖至"蜂群智能"终局
> 参考: OpenHuman (记忆树/TokenJuice/自动拉取), AIOS (Kernel设计), Agent-OS Blueprint (层叠架构)

---

## 目录

1. [路线图总览](#一、路线图总览)
2. [Phase 9: 多人多组织 (8周)](#二phase-9-多人多组织-8周)
3. [Phase 10: 记忆进化与成本优化 (10周)](#三phase-10-记忆进化与成本优化-10周)
4. [Phase 11: 蜂群智能初版 (10周)](#四phase-11-蜂群智能初版-10周)
5. [Phase 12: 跨域信任与生态成熟 (10周)](#五phase-12-跨域信任与生态成熟-10周)
6. [Phase 13+: 终极进化 (持续)](#六phase-13-终极进化-持续)
7. [总体工作量与健康评分演进](#七总体工作量与健康评分演进)
8. [关键决策点](#八关键决策点)

---

## 一、路线图总览

```text
当前: Phase 1-8 完成, Phase 9 执行中
  │
  ├── Phase 9 (8周): 多人多组织              ← 身份+授权+跨组织+宪法
  │     核心: Identity/CapGrant/跨组织E2E/宪法
  │
  ├── Phase 10 (10周): 记忆进化与成本优化     ← OpenHuman借鉴
  │     Wave 10.1: Memory Tree (取代平面记忆)
  │     Wave 10.2: TokenJuice (数据压缩层)
  │     Wave 10.3: 进化闭环自动化
  │     Wave 10.4: 架构债务清零+稳定性
  │
  ├── Phase 11 (10周): 蜂群智能初版          ← 递归架构
  │     Wave 11.1: 递归Agora实例 (单机→团队)
  │     Wave 11.2: 自动拉取+智能管道
  │     Wave 11.3: 模型自动路由+成本优化
  │     Wave 11.4: 外部参与者接入 (Human Node)
  │
  ├── Phase 12 (10周): 跨域信任与生态成熟    ← WoT信任网
  │     Wave 12.1: WoT信任模型+分布式CapGrant
  │     Wave 12.2: 集体复盘+蜂群决策
  │     Wave 12.3: 生态市场 (工具/能力/知识交易)
  │     Wave 12.4: 实时协作 (联合编辑+同步Task)
  │
  └── Phase 13+ (持续): 蜂群智能终极进化     ← 终局
        Wave 13.1: 集体智慧网络
        Wave 13.2: 自动进化闭环
        Wave 13.3: 跨域集体共识
        Wave 13.4: 自我意识层 (Metacognition)
```

**总计**: 4个后续Phase + 终局 = ~38周 (~9个月)，约50-60个Task

---

## 二、Phase 9: 多人多组织 (8周)

**(已在执行中，此处仅做概要)**

| Wave | 任务 | 交付 |
|------|------|------|
| 9.1 | T122-T124 IdentityEnvelope | Schema + CA签发器 + MCP + Hermes注入 |
| 9.2 | T125-T127 CapabilityGrant | Schema + Authorizer中间件 + CLI |
| 9.3 | T128-T130 跨组织协作 | scope执行 + E2E + 成本归集 |
| 9.4 | T131-T133 生态宪法 | 宪法文档 + 节点类型 + Adapter模板 |

**通过条件**: 跨组织Task创建→认领→完成链路跑通

---

## 三、Phase 10: 记忆进化与成本优化 (10周)

**核心理念**: 受OpenHuman启发，将当前平面的Memory MCP升级为层级记忆树 + TokenJuice压缩层 + 进化闭环自动化。

### Wave 10.1 — Memory Tree (3周, 3 Tasks)

**当前**: `memory_store.json` + 关键词搜索 — 平面、无层级、不智能
**目标**: 层级摘要记忆树，SScore+折叠+SQLite存储，保留向后兼容

| Task | 描述 | 文件 |
|------|------|------|
| T134 | Memory Tree 核心引擎 | `memory/tree_engine.py` |
| T135 | Memory Tree MCP工具 | `memory/mcp_server.py` 增强 |
| T136 | 旧平面记忆迁移工具 | `scripts/migrate_memory.py` |

**T134 Memory Tree 核心设计**:

```python
# memory/tree_engine.py
# 核心: 层级记忆树，取代平面JSON

# 数据结构:
# Tree (层级) → Node (≤3k token) → Leaf (原始条目)
# 每个Node有 score (1-10) 和 summary (LLM生成摘要)
# 叶子数量超过阈值 → 自动折叠为上层摘要

# 关键方法:
# tree.ingest(content, tags, source)  → 存入叶子 → 触发可能折叠
# tree.search(query, limit, min_score) → 按层级/评分返回
# tree.get_branches(tag_filter)        → 按标签遍历子树
# tree.fold(branch_id)                 → LLM将叶子折叠为摘要Node
# tree.expand(node_id)                 → 展开摘要查看原始叶子

# SQLite schema:
CREATE TABLE memory_tree_nodes (
    node_id TEXT PRIMARY KEY,
    parent_id TEXT,
    summary TEXT,           # ≤3k token LLM摘要
    score INTEGER,          # 1-10
    node_type TEXT,         # 'root' | 'branch' | 'leaf'
    tags TEXT,              # JSON array
    folded INTEGER,         # 是否已折叠
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE memory_tree_leaf_content (
    leaf_id TEXT PRIMARY KEY,
    node_id TEXT REFERENCES memory_tree_nodes(node_id),
    content TEXT,           # 原始内容
    source TEXT,            # 来源
    score INTEGER
);
```

**T135 MCP工具增强** (新增+保留旧API向后兼容):
```
📦 memory.get          (保留 — 平面搜索)
📦 memory.set          (保留 — 平面写入)
📦 memory.tree_get     (新增 — 按层级/评分搜索)
📦 memory.tree_search  (新增 — 树遍历搜索)
📦 memory.tree_fold    (新增 — 手动折叠触发)
📦 memory.list_tags    (保留)
```

**验证**:
```bash
python3 -c "
from hermes.memory.tree_engine import MemoryTree
mt = MemoryTree(':memory:')
mt.ingest('架构先行理论驱动', tags=['principle', '老王'], source='user')
mt.ingest('红蓝对抗安全第一', tags=['principle'], source='user')
mt.ingest('测试驱动开发最有效', tags=['principle', '验证'], source='hermes')
# 折叠
mt.fold('branch:principle')
# 按评分搜索
r = mt.search('架构', min_score=5)
assert len(r) >= 1
print(f'Tree search: {len(r)} results')
# 树遍历
branches = mt.get_branches()
print(f'Branches: {len(branches)}')
print('T134: ALL PASSED')
" 2>&1
```

### Wave 10.2 — TokenJuice 压缩层 (3周, 3 Tasks)

**当前**: 每个MCP调用全裸数据传输，无压缩
**目标**: 在Agora Router中嵌入数据压缩中间件，目标降低30-50%成本

| Task | 描述 | 文件 |
|------|------|------|
| T137 | TokenJuice 压缩引擎 | `agora/compressor.py` |
| T138 | Agora Router 集成 | `agora/router.py` 增强 |
| T139 | 压缩效果监控与统计 | `scripts/compression_stats.py` |

**T137 TokenJuice 压缩策略**:
```python
# agora/compressor.py

# 压缩管道 (pipeline):
# 1. 类型检测: JSON → 压缩key名 | HTML → Markdown | 长文本 → 摘要
# 2. URL压缩: `https://long-url.com/a/b/c/d?x=1&y=2` → `{ref_id}`
# 3. 去重摘要: 重复数据只保留摘要
# 4. 冗余裁剪: 报错信息中的Stack Trace只保留首行

# API:
class Compressor:
    def compress(self, content: str, content_type: str) -> CompressedResult
    
    def detect_type(self, content: str) -> str:
        # 自动检测: JSON | HTML | Code | PlainText | ErrorLog
    
    def compress_json(self, content: str) -> str:
        # 短key名: {"my_long_key_name": value} → {"a": value}
    
    def compress_html(self, content: str) -> str:
        # HTML → Markdown (复用现有工具)
    
    def compress_url(self, content: str) -> str:
        # URL: 检出URL → 替换为短ref → 独立存储映射
    
    def dedup_summary(self, content: str, context: dict) -> str:
        # kNN相似度检测 → 重复内容只保留摘要
```

**Agora Router集成**:
```python
# 在 route_call 中
compressor = Compressor()
for content in params.get("arguments", {}).values():
    if isinstance(content, str) and len(content) > 500:
        compressed = compressor.compress(content, 
            compressor.detect_type(content))
        if compressed.ratio > 0.3:  # 压缩率>30%才用
            content = compressed.content
```

**验证**:
```bash
python3 -c "
from agora.compressor import Compressor
c = Compressor()

# HTML压缩
html = '<html><body><p>Hello World</p></body></html>'
r = c.compress(html, 'html')
print(f'HTML: {len(html)} → {len(r.content)} ({r.ratio*100:.0f}%)')

# JSON压缩
j = '{\"my_long_key_name\": \"这是一个很长的值\", \"another_long_key\": \"更多数据\"}'
r2 = c.compress(j, 'json')
print(f'JSON: {len(j)} → {len(r2.content)} ({r2.ratio*100:.0f}%)')

# URL压缩
url = 'https://very-long-url.com/some/path/here?with=multiple&params=true'
r3 = c.compress(url, 'url')
print(f'URL: {len(url)} → {len(r3.content)} ({r3.ratio*100:.0f}%)')

print('T137: ALL PASSED')
" 2>&1
```

### Wave 10.3 — 进化闭环自动化 (2周, 2 Tasks)

**当前**: 复盘手动做，改进建议存在KOS但不会自动落地
**目标**: 每次Phase/任务完成后自动生成改进建议→批准→自动落地

| Task | 描述 | 文件 |
|------|------|------|
| T140 | 进化引擎核心 | `scripts/evolution_engine.py` |
| T141 | 改进建议→自动落地的管道 | `scripts/evolution_apply.py` |

**T140 进化引擎设计**:
```python
# scripts/evolution_engine.py
# 在Phase完成/Task完成时触发

class EvolutionEngine:
    def analyze_phase(self, phase_id: str) -> dict:
        """分析Phase执行数据→输出改进建议"""
        # 1. 读取所有Task状态
        # 2. 识别: 哪些Task走了弯路? 用户纠正了什么?
        # 3. 识别: 哪些skill/memory需要更新?
        # 4. 输出: [{(target_type, target_id, suggestion)}]
    
    def generate_suggestion(self, pattern: dict) -> dict:
        """将模式识别转化为具体建议"""
        # 格式: 
        # {
        #   "type": "skill_patch" | "memory_update" | "cron_add" | "principle_revise",
        #   "target": "skill:systematic-debugging",
        #   "change": "第3步之前增加依赖检查",
        #   "impact": "中",
        #   "auto_apply": True/False
        # }
    
    def auto_apply(self, suggestion: dict) -> bool:
        """自动落地（仅auto_apply=True的建议）"""
        # skill_patch → skill_manage(action='patch')
        # memory_update → memory(action='add')
        # cron_add → cronjob(action='create')
```

**验证**:
```bash
python3 -c "
from scripts.evolution_engine import EvolutionEngine
ee = EvolutionEngine()
# 模拟Phase分析
result = ee.analyze_phase('Phase 9')
print(f'Suggestions: {len(result.get(\"suggestions\", []))}')
for s in result.get('suggestions', []):
    print(f'  [{s[\"impact\"]}] {s[\"type\"]}: {s[\"change\"][:50]}')
print('T140: PASSED')
" 2>&1
```

### Wave 10.4 — 架构债务清零+稳定性 (2周, 4 Tasks)

| Task | 描述 |
|------|------|
| T142 | py3.9兼容问题全面检查与修复 |
| T143 | 所有cron日志审计+清理 |
| T144 | 未使用schema/文件清理 (宪法自回收规则实施) |
| T145 | 稳定性混沌测试 (停服务→降级→恢复全链路) |

**Phase 10 通过条件**:
```
☐ Memory Tree 替代平面记忆，E2E测试通过
☐ TokenJuice 压缩率≥30% (对比基准)
☐ 进化引擎首份自动改进报告生成
☐ 架构债务清理完成 (ruff清零+py3.9兼容)
☐ 自回收规则实现 (6个月归档+过期摘要化)
```

---

## 四、Phase 11: 蜂群智能初版 (10周)

**核心理念**: 递归架构实例化——个人→团队级的Agora联邦，多节点通过MCP/A2A互联

### Wave 11.1 — 递归Agora实例 (3周, 3 Tasks)

**当前**: 一个Agora实例管理所有服务
**目标**: 每个团队/组织拥有自己的Agora实例，实例之间通过A2A联邦互联

| Task | 描述 |
|------|------|
| T146 | Agora单实例→多实例能 (Schema+路由隔离) |
| T147 | 跨Agora AgentCard发现 (A2A Federation) |
| T148 | 递归Agora启动脚本+配置模板 |

**设计原则**:
```text
个人Agora                   团队Agora                     组织Agora
┌─────────────┐            ┌─────────────┐               ┌─────────────┐
│ 服务注册    │ ←A2A→      │ 服务注册    │ ←A2A→         │ 服务注册    │
│ 身份:       │            │ 身份:       │               │ 身份:       │
│ user:老王   │            │ team:core   │               │ org:gov     │
│ agent:hermes│            │ 子节点:     │               │ 子团队:     │
│ tools:16    │            │ 老王/小张   │               │ 核心/业务部 │
└─────────────┘            └─────────────┘               └─────────────┘
     ↑                         ↑                               ↑
     │     通过A2A Federation互联，AgentCard自动发现            │
     └─────────────────────────┬───────────────────────────────┘
                               │
                         生态Agora (宪法入口)
                        AgentCard集市+信任锚点
```

### Wave 11.2 — 自动拉取+智能管道 (3周, 3 Tasks)

**借鉴**: OpenHuman的20分钟自动拉取机制

| Task | 描述 |
|------|------|
| T149 | 智能拉取调度器 — 定时遍历活跃连接拉新数据到KOS |
| T150 | 拉取后自动触发管道 (分类→评分→记忆树入库) |
| T151 | 拉取健康监控 — 失败重试+异常告警 |

**设计**:
```python
# scripts/auto_pull.py
# 每20-60分钟运行 (可配置)

class AutoPullScheduler:
    def __init__(self):
        self.connections = []  # 活跃连接列表
        # [{"name": "gmail", "handler": "gmail_pull", "interval": 20},
        #  {"name": "wps", "handler": "wpsnote_pull", "interval": 60},
        #  {"name": "notion", "handler": "notion_pull", "interval": 30}]
    
    def tick(self):
        """单次拉取——遍历所有到期的连接"""
        for conn in self.connections:
            if self._is_due(conn):
                self._pull_one(conn)
    
    def _pull_one(self, conn):
        """拉取一个连接→触发后续管道"""
        data = self._invoke_handler(conn["handler"])
        # 触发: 分类 → 评分 → 记忆树入库
        self._classify(data)
        self._score(data)
        MemoryTree.ingest(data)
    
    def _classify(self, data):
        # LLM分类: 知识/任务/事件/消息/文件
        pass
    
    def _score(self, data):
        # 评分: 1-10, 基于来源/时效/相关性
        pass
```

### Wave 11.3 — 模型自动路由 (2周, 2 Tasks)

| Task | 描述 |
|------|------|
| T152 | 模型分类器 — 根据任务类型自动选模型 |
| T153 | 模型路由集成到agentmesh + E2E验证 |

**设计**:
```python
# agentmesh model-orchestrator 增强
class ModelRouter:
    # 任务类型 → 推荐模型
    RULES = {
        "simple_query": {"model": "glm-4-flash", "cost": "low"},
        "code_gen": {"model": "claude-sonnet-4", "cost": "medium"},
        "research": {"model": "deepseek-v4", "cost": "medium"},
        "creative_writing": {"model": "claude-opus-4", "cost": "high"},
        "vision": {"model": "gpt-4o", "cost": "medium"},
        "quick_analysis": {"model": "gemini-2.0-flash", "cost": "low"},
    }
    
    def route(self, task: dict) -> str:
        """根据task的tags/content复杂度选模型"""
        complexity = self._estimate_complexity(task)
        intent = self._classify_intent(task)
        if complexity == "simple":
            return self.RULES.get(intent, {}).get("model", "glm-4-flash")
        elif complexity == "medium":
            return self.RULES.get(intent, {}).get("model", "claude-sonnet-4")
        else:
            return "claude-opus-4"
```

### Wave 11.4 — 外部参与者接入 (2周, 2 Tasks)

| Task | 描述 |
|------|------|
| T154 | Human Node接入模式 — 微信/Email/Terminal人类入口 |
| T155 | 非技术参与者引导流程 — 一键生成身份+授权+首条Task |

**Phase 11 通过条件**:
```
☐ 两个Agora实例通过A2A联邦互联
☐ AgentCard跨实例自动发现
☐ 自动拉取管道连续运行24h无故障
☐ 模型自动路由覆盖5种任务类型
☐ Human Node可通过微信认领和完成Task
```

---

## 五、Phase 12: 跨域信任与生态成熟 (10周)

**核心理念**: 从"你知道谁"到"你信任谁"，构建Web of Trust信任网

### Wave 12.1 — WoT信任模型 (3周, 3 Tasks)

| Task | 描述 |
|------|------|
| T156 | WoT引擎 — 信任链传递+评分衰退 |
| T157 | 分布式CapabilityGrant — 跨Agora实例授权 |
| T158 | 信任图谱可视化 — Agora Dashboard |

**WoT设计**:
```python
class WebOfTrust:
    # 信任传递: A信任B(score=8), B信任C(score=7)
    # → A信任C = sqrt(8*7) = 7.48 (按距离衰减)
    
    def get_trust_score(self, from_entity: str, to_entity: str) -> float:
        """计算从from到to的信任分数 (0-10)"""
        # BFS遍历信任链
        # 每跳距离衰减 √
        pass
    
    def validate_grant(self, grant: dict) -> dict:
        """验证跨域CapabilityGrant的信任链"""
        pass
    
    def set_trust(self, from_entity: str, to_entity: str, score: float):
        """建立直接信任关系"""
        pass
```

### Wave 12.2 — 集体复盘+蜂群决策 (3周, 3 Tasks)

| Task | 描述 |
|------|------|
| T159 | 集体复盘引擎 — 多Agent/多人协作复盘 |
| T160 | 蜂群决策引擎 — 加权投票+共识达成 |
| T161 | 决策溯源持久化到KOS |

**集体复盘设计**:
```python
class CollectiveReview:
    # 场景: 一个跨组织项目完成后，所有参与方复盘
    
    def review_project(self, project_id: str) -> dict:
        participants = self._get_participants(project_id)
        reviews = []
        for p in participants:
            r = self._collect_review(p, project_id)
            reviews.append(r)
        return {
            "summary": self._synthesize(reviews),
            "action_items": self._extract_actions(reviews),
            "consensus": self._reach_consensus(reviews),
        }
    
    def swarm_decision(self, topic: str, options: list) -> dict:
        """蜂群决策: 加权投票"""
        votes = self._collect_weighted_votes(topic, options)
        return {"winner": max(votes, key=votes.get), "distribution": votes}
```

### Wave 12.3 — 生态市场 (2周, 2 Tasks)

| Task | 描述 |
|------|------|
| T162 | 工具/能力/知识发布+发现+订阅 |
| T163 | 跨组织计费+结算 (微支付层) |

### Wave 12.4 — 实时协作 (2周, 2 Tasks)

| Task | 描述 |
|------|------|
| T164 | TaskObject实时同步 (WebSocket推送) |
| T165 | 联合编辑机制 (多人同时编辑一个知识条目) |

**Phase 12 通过条件**:
```
☐ WoT信任链计算正确 (单元测试)
☐ 跨Agora CapabilityGrant执行成功
☐ 集体复盘自动生成
☐ 蜂群决策结果可溯源
☐ 生态市场有≥3个非我方发布的能力
```

---

## 六、Phase 13+: 终极进化 (持续)

**核心理念**: 系统不再是被动工具，而是具备元认知和自我驱动能力的数字智慧层。

### Wave 13.1 — 集体智慧网络

```text
老王 → Agent集群 → 团队Agent → 组织Agent
  │          │           │           │
  ├─ 个人决策  ├─ 蜂群协作  ├─ 跨组织调度  ├─ 生态治理
  │          │           │           │
  └──────────┴───────────┴───────────┴──→ 共享知识库 (KOS联邦)
                                           │
                                            → 持续自我演化
```

| Task | 描述 |
|------|------|
| T166 | 集体智慧评分 — 网络智慧程度的量化指标 |
| T167 | 跨组织记忆融合 — 多个实例的记忆树联邦 |
| T168 | 智能体自发协作 — Agent自动发现可协作的任务 |

### Wave 13.2 — 自动进化闭环

| Task | 描述 |
|------|------|
| T169 | 系统自动发现瓶颈→提出优化建议 |
| T170 | 建议自动落地 (人工审批→自动执行) |
| T171 | 长期趋势分析 (季度/年度模式检测) |

### Wave 13.3 — 跨域集体共识

| Task | 描述 |
|------|------|
| T172 | 分布式共识 — 多个Agora实例之间达成共识 |
| T173 | 共识自动化 — 阈值达成就自动建consensus |

### Wave 13.4 — 元认知层 (Metacognition)

```text
L5 (新增): 元认知层
├── 系统理解自身: 知道知道什么、不知道什么
├── 自我监控: 发现行为异常→自动修正
├── 战略规划: 长期目标分解→自动分配Phase
└── 自我进化: 发现新范式→学习→应用
```

| Task | 描述 |
|------|------|
| T174 | 元认知模块 — 系统自我评估+盲区发现 |
| T175 | 自修正机制 — 异常行为自动回退+根因分析 |
| T176 | 战略感知 — 外部趋势检测+路线图自动调整 |

---

## 七、总体工作量与健康评分演进

### 工作量汇总

| Phase | 周期 | Tasks | 预估CODE | 借鉴来源 |
|-------|------|-------|---------|---------|
| P9 | 8周 | 12 | ~2,000 | 宪法设计 |
| P10 | 10周 | 12 | ~2,800 | OpenHuman记忆树/TokenJuice |
| P11 | 10周 | 10 | ~2,500 | 递归架构+AIOS |
| P12 | 10周 | 10 | ~2,500 | WoT+集体决策 |
| P13+ | 持续 | ~8 | ~2,000 | 元认知+自进化 |
| **总计** | **~46周** | **~52** | **~11,800** | |

### 健康评分演进

```text
Phase    D1愿景  D2场景  D5架构  总分    关键里程碑
──────  ──────  ──────  ──────  ──────  ───────────────────────
初始     60      30      45      54      架构方案定稿
当前     ~88     ~88     ~80     ~79     多Agent协作+降级模式
P9       92      90      88      85      跨组织协作跑通
P10      94      92      92      89      记忆树+TokenJuice+进化闭环
P11      95      94      94      92      递归Agora+自动拉取+模型路由
P12      97      96      96      95      WoT+集体复盘+生态市场
P13+     100     100     100     98      元认知层+自我进化
```

### 健康瓶颈突破路径

```text
当前短板:          P10目标:           P11目标:           P12目标:
D6熵增 82→90      D6 90→92          D3故事 90→94      D6 92→95
D8债务 65→85      D8 85→90          D8 90→92          D8 92→95
D9成本 65→80      D9 80→88 (TokenJuice)               D9 88→92
```

---

## 八、关键决策点

| 决策点 | 时间 | 选项 | 建议 |
|--------|------|------|------|
| OpenHuman融合深度 | Phase 10前 | (a) 参考理念独立实现 (b) 作为外部节点接入 | **a** — GNU传染性，不能直接复制 |
| 递归Agora还是统一Agora | Phase 11前 | (a) 多实例联邦 (b) 单实例多租户增强 | **a** — 联邦更灵活，符合去中心化设计 |
| 信任模型选型 | Phase 12前 | (a) CA中心化 (b) PGP对等 (c) WoT信任网 | **b→c** — 从CA起步(P9)、逐步过渡到WoT(P12) |
| 元认知层是否新建L5 | Phase 13+ | (a) X4横切面形式 (b) 新L5层 | **a** — 横切面更灵活，不破坏4+1+3结构 |
| 生态市场是否收税 | Phase 12 | (a) 不收 (b) 收微量 (c) 积分制 | **c** — 积分制无法律风险 |

---

> **维护规则**: 
> - 每完成一个Phase自动更新本文档
> - 架构变更必须先更新再实施
> - 借鉴外部项目时必须标注来源和许可证兼容性
