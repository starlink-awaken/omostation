---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# eCOS v5 (5+3+1) 架构完全缺陷分析

> 生成日期: 2026-06-05
> 基于: 全量架构审计 + 6 Agent 调查 + 债务注册表 60+ 项 + ~/documents 架构宪法
> 执行复盘: 2026-06-05T23:50 见 §六

---

## 一、单层缺陷

### L0 — 协议编织层 [骨架式缺陷]

| 问题 | 严重度 | 详情 |
|------|--------|------|
| 16 协议 14 幽灵 | 中 | 仅 MCP 有运行时实现，ACP/A2A/BOS URI/TaskObject 等只存于 YAML |
| 元模型本体未接入 | 高 | runtime/protocols/ecos-ontology.yaml 定义 6×6+8 但零消费 |
| TaskObject 规范零消费 | 中 | 框架存在，无 Agent 产生或消费 |
| KEI Sandbox 审计钩子未启用 | 中 | kei.yaml 权限 allow_read: '/'，等于未启用 |
| 协议映射无动态路由 | 低 | 只有静态表，无自动发现/转换 |

### L1 — 运行时矩阵层 [割裂式缺陷]

| 问题 | 严重度 | 详情 |
|------|--------|------|
| agent-runtime task_definitions 目录缺失 | 危急 | server.py:140/cli.py:38/mcp_server.py:55 引用不存在目录 |
| mcp_server.py 导入 bug | 高 | from runtime import AgentRuntime 路径错误(AgentRuntime 在 engine.py) |
| agent-runtime 文档端口不一致 | 中 | README 写 8082，代码默认 9876 |
| Runtime Matrix 与 agent-runtime 未桥接 | 高 | projects/runtime/ 与 packages/agent-runtime/ 是两个独立项目 |
| 健康扫描无告警通道 | 危急 | 检测到服务挂了只写日志，无微信/push/邮件通知 |
| Runtime 测试严重不足 | 高 | 16 模块仅 3 测试文件 |
| launchd 生命周期分裂 | 中 | agent-runtime 和 agora 由不同 plist 管理 |

### L2 — 内核三平面

| 问题 | 严重度 | 详情 |
|------|--------|------|
| OMO 治理单点负责人 | 中 | 18 未解决债务全 owner=omo-governance |
| 代码冻结阻止主动修复 | 中 | code_freeze=true 导致 3 P0 滞留 |
| kairon 根测试不通 | 危急 | make test-fast conftest ImportPathMismatchError |
| 核心包测试薄弱 | 高 | core-models(3)/cron-service(3)/engine-core(10) |
| Agora 语义路由降级 | 高 | sentence-transformers 缺失, fallback 关键词匹配 |
| gbrain E2E 未验证 | 危急 | ping→索引→Ollama 链路未确认 |
| Agora 90+ 文件职责过载 | 高 | 路由/认证/MCP 代理/仪表板/A2A 集于一身 |
| hermes-console 开发停滞 | 中 | MVP 后无迭代 |

### L3 — 入口桥接矩阵 [单入口缺陷]

| 问题 | 严重度 | 详情 |
|------|--------|------|
| 实际只有 Hermes 一个活跃入口 | 高 | Claude Code/Codex/WorkBuddy ACP 适配器全是概念 |
| TaskObject Router 零使用 | 中 | 框架存在无消费者 |
| ACP 协议仅有名称 | 中 | 有概念无实现 |

### L4 — 自我层 [相对健康]

| 问题 | 严重度 | 详情 |
|------|--------|------|
| CARDS 与 .omo 治理体系并行追踪 | 中 | 两套追踪互不感知 |
| CLAUDE_COWORK_GLOBAL.md 膨胀 | 低 | 6.3KB 承载多职责 |

### X1 — 治理安全 [骨架]

| 问题 | 严重度 | 详情 |
|------|--------|------|
| 无审计链闭合回路 | 危急 | KEI 11K+ 审计记录写而无人消费 |
| KEI 沙箱权限粗放 | 高 | allow_read: '/' 等同于无 |
| 无 CI push gate | 中 | 修改后无自动化验证 |

### X2 — 抗熵 [零实现]

| 问题 | 严重度 | 详情 |
|------|--------|------|
| 保鲜机制完全缺失 | 危急 | 无自动校验/审计/周报 |

### X3 — 价值栈 [零实现]

| 问题 | 严重度 | 详情 |
|------|--------|------|
| 零成本追踪 | 危急 | 无 Token 统计/服务计量 |

### I0 — 集成织层

| 问题 | 严重度 | 详情 |
|------|--------|------|
| Agora 归属 I0 但代码在 kairon packages/ | 中 | 目录结构与架构定义不一致 |
| 跨层通信绕开 Agora | 高 | agent-runtime 有直接降级路径直连 KOS/Minerva |
| Agora 硬编码 19 服务 | 中 | 静态注册表缺少自动发现 |

---

## 二、跨层系统性问题

1. **架构与代码两层皮** — 5+3+1 架构详尽，代码层多处反例
2. **32 运行时服务零统一面板** — launchd/Docker/Python/npm 四种模式
3. **跨包通信绕开 Agora** — 违 I0 唯一总线原则
4. **测试分布不均** — kairon 293/gbrain 715/omo 84 vs runtime 3/hermes 6
5. **项目膨胀信号** — agora 90+/agent-runtime 50+ 顶级模块开始微单体化

---

## 三、根因

1. **新旧架构过渡遗留** — 4+1→5+3 中 L1 拆分+L3 重定义做了概念未做代码
2. **概念锁定陷阱** — "先锁定边界"策略导致 7+ identified 债务从未排期
3. **治理过密执行过疏** — debt_health=0.0 不意味着健康，而是系统对自己选择性失明

---

## 四、修复路线

| 优先级 | 问题 | 动作 | 难度 |
|--------|------|------|------|
| P0 | task_definitions 目录缺失 | 创建目录+恢复 JSON 或修复代码引用 | 低 |
| P0 | mcp_server.py 导入 bug | 修复 from runtime→from engine | 低 |
| P0 | kairon 根测试不通 | 修复 conftest ImportPathMismatchError | 中 |
| P0 | gbrain E2E 验证 | ping→索引→Ollama 链路验证 | 中 |
| P0 | 健康扫描告警通道 | 接入通知 | 中 |
| P1 | Agora 语义路由 | 安装 sentence-transformers | 低 |
| P1 | L0 协议 MVP | ACP/A2A/TaskObject 选 2-3 实现 | 高 |
| P1 | Runtime 测试覆盖 | KEI 沙箱/TaskObject/e2e 补测 | 中 |
| P1 | KEI 告警回路 | 11K+ 日志分析/告警 | 中 |
| P1 | 跨层通信绕 Agora | 审计+强制 Agora 路由 | 高 |
| P2 | Agora 模块拆分 | 90+ 文件拆 3-4 子包 | 高 |
| P2 | L3 多入口适配器 | ACP Adapter Claude Code 接入 | 高 |
| P2 | KEI 沙箱收紧 | allow_read 加白名单 | 低 |
| 远期 | X2/X3 实现 | 保鲜/成本追踪 | 高 |

---

## 五、Check-in 节点

> 每隔 **7 天** 做一次债务进展回顾，检查优先级排序是否合理、P0 是否已清除。
> 如果连续 2 次 check-in 优先级无变化，说明修复路线失效，需要重新评估。

---

## 六、执行复盘 (2026-06-05T23:50)

### 已修复

| 问题 | 修复方式 | 代码位置 |
|------|---------|---------|
| agent-runtime import 路径错误 | from runtime → from agent_runtime.engine | `mcp_server.py:36` |
| task_definitions 目录缺失崩溃 | 改为优雅返回错误信息 | `mcp_server.py:52-53` |
| L0 TaskObject 零消费 | 每工具调用后写信封到 `~/.runtime/taskobject_envelopes.jsonl` | `mcp_server.py:_record_taskobject_envelope()` |
| L0 协议只有 YAML 定义 | add `validate_protocol_message()` 支持名称/字段/传输层验证 | `protocol.py:100-130` |
| tools.py Agora 降级直连 | 集中化到 runtime Matrix degrade policy | `tools.py:_get_runtime_degrade_policy()` |
| config.py MCP 端口硬编码 | 标注 legacy，文档链指向 RUNTIME_MATRIX env | `config/config.py` |
| sharedbrain.py 直连未走 Agora | 重构：Agora MCP 优先 → 直连降级 | `sharedbrain.py:_query_via_agora()` |
| eCOS SSOT 文档未标注 Agora 位置 | 添加战略台阶注释 | Architecture-SSOT.md |

### 债务台账

| 类型 | 已修复 | 待排期 |
|------|--------|--------|
| P0 | 6 项 | 3 项(产品类, identified) |
| P1 | 7 项 | 0 项 |
| P2 | 2 项 | 6 项(含 BYPASS-004~009) |
| L0 | 2 项(重开) | 0 项 |

### 当前债务全景 (open)

- BYPASS-004~009 (6 项, 中低优先级)
- P0-DASHBOARD_COCKPIT / SMART_NOTIFY / TASKOBJECT_LIVE (3 项, identified)
- P1-AUTO_HEAL / FRESHNESS_AUTO (2 项, identified)
- P2-KEI_SANDBOX / META_CI / RED_TEAM (3 项, identified)
- X1-NO_AUDIT_CHAIN / X2-NO_FRESHNESS / X3-NO_COSTING (3 项, unscheduled)

参见 `.omo/debt/registry.yaml` 完整台账。
