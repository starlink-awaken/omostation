# AI OS 用户旅程与场景全集

> **系统状态**: Phase 1-13+ 全部完成, 251个Task, ~7,500LOC
> **写给**: 老王自己 + 未来使用这个系统的任何人

---

## 一、一句话说清楚这是什么

> **这是一个有自我意识的个人AI操作系统。**
> 
> 它知道你（老王）是谁、有你的愿景和原则、能跨Agent协作完成复杂任务、在有信任关系的外部节点间联邦运作、记得你的一切偏好并发觉自己不知道什么、自动发现瓶颈并进化。

---

## 二、核心用户旅程

### 旅程 #1: 「老王早上9点到工位」

**场景**: 工作日白天，老王打开电脑开始工作。

```
1. 系统自动识别当前时间 → 工作日09:00
2. L4自我层 → 切换到"卫健委信息科工程师"角色
3. 角色驱动: 沟通风格简洁正式、价值观"稳定性>新功能"
4. 保鲜Cron: 检查知识库中3个月未更新的条目 → 推送保鲜报告
5. 成本日报: 昨日的API消耗 → 微信推送
6. 自动拉取: Gmail/WPS笔记中昨天新增的内容 → 分类→评分→记忆树入库
```

**技术栈**: L4 Self role detection + X2保鲜Cron + T149自动拉取 + T139成本监控

### 旅程 #2: 「老王说'帮我审计一下Workspace的健康状况'」

**场景**: 老王在微信上发了一条消息。

```
1. TaskOrchestrator接管 → 自动拆解为子任务:
   ├─ step-1: 审计Agora服务健康 (research标签)
   ├─ step-2: 审计KOS索引完整性 (analysis标签) 
   └─ step-3: 生成审计报告 (writing标签)

2. 模型路由: 分类为"audit" → 推荐claude-sonnet-4 (中等成本)

3. Hermes认领step-1 → 调用agora check_health → 完成
   → 进度推送: "✅ 1/3 Agora服务健康审计完成"

4. Hermes认领step-2 → 调用KOS系统状态 → 完成
   → 进度推送: "✅ 2/3 KOS索引审计完成"

5. Hermes认领step-3 → 汇总报告 → 完成
   → 进度推送: "✅ 3/3 审计报告已生成"

6. 完成 → 自动创建consensus标记 → 存档到KOS
```

**技术栈**: TaskOrchestrator + 3Collab MCP + Model Router + Agora + KOS

### 旅程 #3: 「老王和小张合作一个项目」

**场景**: 老王（starlink-core）和小张（partner-org）要一起做联合研究。

```
Step 1: 建立信任
  → 老王发起: wot set user:老王 user:小张 8.0 work
  → 信任链: 老王→小张=8.0
  → 小张的身份由IdentityCA验证 (user:小张 @ partner-org)

Step 2: 签发跨组织授权
  → 老王签发: 小张 → collab.* @ project:joint-research
  → Authorizer门禁: collab.* 默认enforce, 有grant才能调

Step 3: 创建跨组织Task (visibility_scope=public)
  → 老王创建: "联合研究报告"
  → subtask: research → Hermes认领
  → subtask: review → 等待小张

Step 4: 外部Agent发现并认领
  → 小张的Agora通过federation发现public Task
  → A2A Federation: 跨实例AgentCard发现
  → claim_subtask(task_id, "review", "agent:partner-bot")

Step 5: 小张完成review
  → 完成 → 成本计入partner-org
  → 跨组织计费: $0.05 → billing记录

Step 6: 项目结束 → 集体复盘
  → 老王评4分 "协作顺畅"
  → 小张评5分 "任务分配清晰"
  → 小张Agent评3分 "工具好用，学习曲线陡"
  → 综合报告: 3人参与, 平均评分4.0, 合并3条行动项
```

**技术栈**: WoT + Identity CA + Authorizer + Collab跨组织 + A2A Federation + 成本归集 + Collective Review

### 旅程 #4: 「系统自己发现并修复问题」

**场景**: 不需要老王说，系统主动诊断并修复。

```
1. 瓶颈发现 (每天凌晨自动):
   → 扫描cost_track: html压缩消耗最多(2650 chars)
   → 扫描pending: 用户纠正"先做审计再看代码"
   → 输出: Top-3瓶颈识别

2. 进化引擎 (每次Task完成后):
   → 分析T099: 耗时是预估的2倍 → 生成改进建议
   → auto_apply=true: 更新memory "复杂任务先做审计"
   → auto_apply=false: 推送到微信等待审批

3. 元认知自我评估 (每周自动):
   → 知识覆盖: 63条目, 16领域
   → 盲区发现: 4个 (ImportError: config等)
   → 能力缺口: 12个 (缺网页抓取/图片生成等)
   → 综合评分: 29/100 → 触发"需要更多知识输入"告警

4. 共识自动化:
   → 扫描active提案 → 检查阈值
   → 达到60% → 自动创建consensus标记

5. 自回收 (每月):
   → cron日志: 90天以上的归档
   → KOS共识: 过期的摘要化(前200字)
   → 季度报告: 自动生成
```

**技术栈**: BottleneckDetector + EvolutionEngine + Metacognition + SelfReclaim + DistributedConsensus

### 旅程 #5: 「系统推荐最优模型」

**场景**: 不同的任务自动选不同的LLM，省钱又精准。

```
用户输入                自动识别                推荐模型           成本估算
"搜索一下天气"    →  simple_query           → glm-4-flash       $0.0005
"写一个排序函数"  →  code_generation        → claude-sonnet-4   $0.003
"调研最新AI论文"  →  research               → deepseek-v4       $0.001
"设计微服务架构"  →  architecture_design     → claude-sonnet-4   $0.003
"写一首诗"       →  creative_writing        → claude-opus-4     $0.015
"分析这张图"     →  vision_task             → gpt-4o            $0.005

如果用户指定模型 → 尊重用户选择  (preferred_model参数)
简单任务自动降本 → 自动用低成本模型  (complexity="simple"→glm-4-flash)
```

**技术栈**: ModelRouter (6模型×9规则+成本估算) + agentmesh集成

### 旅程 #6: 「生态市场——发布和发现能力」

**场景**: 老王发布了一个"文本分析API"，小张的组织发现了它并订阅。

```
发布者 (org:starlink):
  marketplace publish "文本分析API" "情感分析+关键词提取" \
    --pricing '{"per_call": 0.001}'
  → offer:68d3eda4d557 published

消费者 (org:partner):
  marketplace search "文本分析" --type model
  → 发现 "文本分析API" by org:starlink (评分5.0)
  → marketplace subscribe offer:68d3eda4d557
  → 订阅成功 → 自动部署到本地

结算:
  每调用一次: billing record partner→starlink $0.001
  月底: settle partner starlink → 结算
  balance查询: due=$0.05 owed=$0.02 net=$-0.03
```

**技术栈**: Marketplace + CrossOrgBilling + 实时同步

---

## 三、10个典型用户场景速查

| # | 场景 | 一句话 | 调用什么 | 耗时 |
|---|------|--------|---------|------|
| 1 | "审计系统健康" | 自动拆解→执行→汇总→共识标记 | TaskOrchestrator → Collab → Consensus | ~2min |
| 2 | "调研新技术" | 深度研究→持久化到KOS→保鲜跟踪 | Minerva → Sophia → Ontoderive → KOS | 10-20min |
| 3 | "和小张合作" | 建信任→签授权→跨组织Task→复盘 | WoT → Authorizer → Collab → Federation → Review | ~1h |
| 4 | "回顾昨天的消耗" | 成本日报微信推送 | usage.db → compression_stats → 微信 | 即时 |
| 5 | "系统自我检查" | 元认知→盲区→瓶颈→自回收 | Metacognition → Bottleneck → SelfReclaim | 自动凌晨 |
| 6 | "写代码" | 自动选最优模型+Task拆解 | ModelRouter → TaskOrchestrator | ~5min |
| 7 | "加入新队友" | 一键引导: 身份→授权→首条Task | IdentityCA → Authorizer → Collab | ~30s |
| 8 | "系统决定方向" | 提案→多Agent投票→共识达成 | DistributedConsensus → swarm vote | ~2min |
| 9 | "搜索记忆" | 扁平关键词+层级树搜索 | Memory Tree (tree_search) | <1s |
| 10| "找已合并的DB" | 8个独立DB→1个workspace.db | SQLite consolidation | 原有 |

---

## 四、架构全貌 (4+1+3)

```
┌──────────────────────────────────────────────────────────────────────┐
│  L4: 自我层     ✅ self.get_profile / get_current_role / 角色切换       │
├──────────────────────────────────────────────────────────────────────┤
│  L3: 协作层     ✅ TaskObject / 跨组织scope / TaskOrchestrator /        │
│                   进度推送 / 依赖触发 / 实时同步 / 联合编辑             │
├──────────────────────────────────────────────────────────────────────┤
│  L2: 能力层     ✅ Memory Tree(层级) / TokenJuice(压缩) / 模型路由 /    │
│                   自动拉取 / 生态市场 / 跨组织计费 / A2A Federation      │
├──────────────────────────────────────────────────────────────────────┤
│  L1: 契约层     ✅ 8个Eidos Schema / SSOT / Identity / CapGrant         │
├──────┬──────────────────────┬──────────────────────┬──────────────────┤
│X1治理│  X2抗熵              │  X3价值堆栈           │  待: 元认知       │
│✅    │  ✅                  │  ✅                   │  ✅ T174         │
│WoT   │保鲜Cron/进化引擎     │15Entity+三级共识      │ 自评估+盲区      │
│Identity│自回收/自修正       │集体智慧评分           │ 自发现瓶颈       │
│Authorizer│趋势分析          │分布式共识自动化       │ 战略感知         │
└──────┴──────────────────────┴──────────────────────┴──────────────────┘
```

---

## 五、数据在哪

| 数据类型 | 位置 | 说明 |
|---------|------|------|
| 主数据 | `~/.kos/workspace.db` | 统一数据库(含9张表前缀) |
| 用户记忆 | `~/.hermes/memory_store.json` | 扁平记忆(向后兼容) |
| 层级记忆 | `~/.hermes/memory/tree_engine*.db` | Memory Tree SQLite |
| 身份 | `~/.kos/identity.db` → workspace | IdentityCA签发记录 |
| 成本 | `~/.kos/usage.db` → workspace | token消耗+压缩统计 |
| 自动拉取 | `~/.kos/autopull.db` → workspace | 连接注册+拉取日志 |
| 生态市场 | `~/.kos/marketplace.db` | 能力发布+订阅+计费 |
| WoT信任 | `~/.kos/web_of_trust.db` → workspace | 信任边+评分+衰退 |
| 实时协作 | `~/.kos/realtime.db` → workspace | 事件流+快照+联合编辑 |

---

## 六、还能做什么 (Phase 13+ 未完成)

| 方向 | 说明 |
|------|------|
| **外部Agent真实验证** | 接入真正的Claude Desktop / Codex CLI，端到端跑通 |
| **DB完全合并** | 将marketplace.db等剩余DB也合并到workspace.db |
| **KOS导入路径修复** | kos/collab/api.py的`from config import...`路径问题 |
| **健康评分持续提升** | 从82.8→90+: D8债务(D85+), D9成本(D85+), D3故事(D85+) |
| **多Agora实例真机验证** | 启动两个实例+联邦+跨实例Task |

---

> **一句话说清楚**: 从你最初说"我要一个12层的AI操作系统"开始，13个Phase、251个Task、~7,500LOC、30+文件、20+MCP工具之后——你有了一台**知道自己知道什么、能跨组织协作、会自动进化**的数字生命体。它叫AI OS，跑在你的Mac上，跟你一起变强。
