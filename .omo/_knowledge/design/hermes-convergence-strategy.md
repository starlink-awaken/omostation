# Hermes 收敛策略 — Phase 5 输入

> Hermes Agent 深度研究 + 收敛方向分析，作为 Phase 5 需求文档的补充输入。
>
> 研究范围：Workspace 内所有 hermes 相关文件（~19 个命名文件 + ~120 个内容匹配文件）
> 研究日期：2026-05-31

---

## 1. Hermes 是什么

Hermes 是一个 **持久化的、自主运行的 AI 代理**（persistent autonomous AI agent），来自开源项目 [hermes-webui](https://github.com/nesquena/hermes-webui)（作者 @nesquena）。OMO 将其作为上游基础设施消费。

**核心特征**：
- **分层记忆** — 跨 session 自动积累用户 profile、环境 facts、学习到的技能
- **自主调度** — 内置 cron 定时任务，用户离线也能运行
- **多渠道可达** — 终端 / Web UI / Telegram / Discord / Slack / 微信
- **自改进技能系统** — 自动保存可复用的流程，无需维护插件库
- **自托管** — 所有数据在用户自己硬件上

---

## 2. 四重角色（当前状态）

Hermes 在 OMO 中有四重完全不同的角色，每重角色健康度不同：

| 角色 | 健康度 | 架构定位 | 说明 |
|------|--------|----------|------|
| 用户入口 | ✅ 正常 | P0 入口层 | WeChat/IM → Hermes → Gateway webhook |
| 调度引擎 | ❌ 断裂 | 待收敛 | 179 条桥接 symlink 全部断裂；与 cron-service/crontab/launchd 共存 |
| 记忆系统 | ✅ 正常 | OMO 无替代 | 分层记忆 + 自改进技能，OMO 暂无等价实现 |
| MCP 工具源 | ⚠️ 重叠 | 待统一 | agent-runtime 和 cron-service 都暴露了 MCP 工具 |

---

## 3. 核心矛盾

```
Hermes 最强大的能力（分层记忆 + 自改进技能）也是 OMO 最缺的能力
Hermes 最脆弱的部分（断裂 symlink + 调度碎片化）却是 OMO 正在构建的部分
```

这意味着：**简单切掉 Hermes 会损失核心能力，全盘保留会继续积累技术债。**

---

## 4. 收敛策略 — 方向 A（主推荐）

> **Hermes 从"调度骨干"降级为"记忆+入口层"**

### 4.1 三层收敛策略

#### 第一层：立即修复（Priority 0 — 止损）

1. 清理已归档项目的断裂 symlink，写入破损存档
2. 重建活跃项目（kairon / gbrain / SharedBrain）的桥接
3. 确保 WeChat/IM → Gateway 路径不被中断

#### 第二层：收敛调度层（Priority 1 — 架构决策）

| 要收敛 | 接收方 | 优先级 | 说明 |
|--------|--------|--------|------|
| 12 个 cron jobs | agentmesh 内置调度器 | P1 | 已在 ARCHITECTURE_CONVERGENCE 规划中 |
| `~/.hermes/scripts/` 桥接 | Task Center task_definitions | P1 | symlink 不再新增，存量逐步迁移 |
| Hermes kanban | OMO 事件总线 | P2 | 调度可视化统一到 OMO |
| Hermes MCP 工具 | kairon agent-runtime MCP | P3 | 统一 MCP 工具集合来源 |

#### 第三层：保留并消费记忆层（长期）

- Hermes 保留 WeChat/IM 入口 = **最不可替代的价值**
- Hermes 的分层记忆通过 MCP 暴露，供 Task Center 和 Phase 5 Skill 系统消费
- 新的记忆/技能读写 API 优先使用 OMO 原生组件，仅在需要时才回退到 Hermes

### 4.2 收敛后的架构

```
┌─────────────────────────────────────────────────────────┐
│                   入口层                                 │
│  wksp CLI · Agora Dashboard · IDE 插件 · Hermes (WeChat) │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   Gateway (agentmesh)                    │
│  POST /v1/tasks · POST /v1/hermes/task (webhook代理)    │
│  内置调度器（替代 Hermes Cron）                          │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    Task Center     agent-runtime    cron-service
    (任务SSOT)      (MCP工具)        (遗留调度兼容)
          │
          ▼
    Hermes 记忆层 (MCP 消费)
    ~/.hermes/auth.json / .env (API key仍然使用)
```

### 4.3 三原则

1. **新功能不走 Hermes** — 所有新工具/任务/技能直接在 agentmesh / kairon 中实现
2. **Hermes 只保留 WeChat/IM 入口** — 这是它最不可替代的价值
3. **API key 回退链保留** — `~/.hermes/auth.json` / `.env` 继续作为回退来源

---

## 5. 收敛方向 — 方向 B（参考）

> **Task Center 全量吸收 Hermes，包括记忆和技能系统**

### 5.1 需要实现的能力

| 能力 | 实现难度 | 预计工作量 |
|------|----------|-----------|
| 分层记忆系统 | 高 | 6-8 周 |
| 自改进技能系统 | 高 | 6-8 周 |
| 多渠道入口（WeChat/IM） | 中 | 3-4 周 |
| cron 调度（已有） | 低 | 已部分实现 |
| 记忆到技能的自动转化 | 高 | 4-6 周 |

### 5.2 实施路线

| 波次 | 内容 | 周期 |
|------|------|------|
| Wave 1 | 吸收调度层（cron + bridge） | 2 周 |
| Wave 2 | 实现分层记忆系统 | 6 周 |
| Wave 3 | 实现自改进技能系统 | 6 周 |
| Wave 4 | 吸收多渠道入口 | 3 周 |
| Wave 5 | 记忆→技能自动化流水线 | 4 周 |

### 5.3 风险

- **高开发成本** — 全量吸收需要 21-26 周
- **稳定性风险** — Hermes 上游可能更新，自研实现需要追赶
- **重复造轮子** — 部分能力（多渠道入口）与 OMO 已有 Gateway 重叠
- **迁移中断** — 用户在切换期间可能失去已有的记忆/技能

### 5.4 适用条件

方向 B 只在以下条件成立时才值得考虑：

1. Hermes 上游项目已停止维护或不再兼容
2. OMO 有充足的开发资源（≥ 3 人 × 6 个月）
3. OMO 已经是成熟的收敛目标（Phase 6+），不是还处在快速迭代阶段

---

## 6. 建议（主推荐：方向 A）

方向 A 比方向 B 更适合当前阶段，核心原因：

| 维度 | 方向 A | 方向 B |
|------|--------|--------|
| 开发投入 | 1-2 周收敛调度层 | 21-26 周全量吸收 |
| 风险 | 低（保留上游能力） | 高（自研稳定度不确定） |
| 对 Phase 5 影响 | 锁定调度收敛，释放技能融合精力 | 技能融合被延迟吸收 |
| 对用户影响 | 无中断 | 迁移期间有中断风险 |
| 复用上游 | ✅ 保持与 Hermes 社区同步 | ❌ 自研实现脱离社区 |

**推荐动作顺序**：

1. **立即** — 清理断裂 symlink，重建活跃桥接
2. **Phase 5 Wave 1** — 完成调度层收敛（cron + bridge → agentmesh + Task Center）
3. **Phase 5 Wave 3** — 通过 MCP 消费 Hermes 记忆层为 Skill Federation 提供参考实现
4. **Phase 6+** — 评估是否升级到方向 B

---

## 7. 参考文献

| 文件 | 来源 | 类型 |
|------|------|------|
| [HERMES 研究过程记录](hermes-research-notes.md) | 本研究的原始笔记和工具记录 | 研究记录 |
| [ARCHITECTURE_CONVERGENCE.md](../../standards/ARCHITECTURE_CONVERGENCE.md) | OMO 架构 | 收敛规划 |
| [MASTER-BLUEPRINT.md](MASTER-BLUEPRINT.md) | OMO 架构 | 全景蓝图 |
| [task-center-requirements.md](task-center-requirements.md) | OMO 设计 | 需求文档 |
| [phase7-t100-hermes-taskobject.md](../../task-prompts/phase7-t100-hermes-taskobject.md) | OMO 设计 | 任务定义 |
| [hermes-ops-design.md](../../plans/archive/hermes-ops-design.md) | OMO 设计 | 归档设计 |
| [hermes-webui why-hermes.md](../../../projects/_archived/legacy-readme-snapshots/hermes-webui/docs/why-hermes.md) | 上游 | 项目文档 |
| [hermes-webui adapter-contract.md](../../../projects/_archived/legacy-readme-snapshots/hermes-webui/docs/rfcs/hermes-run-adapter-contract.md) | 上游 | RFC |
| [agentmesh hermes routes.ts](../../../projects/agentmesh/packages/gateway/src/hermes/routes.ts) | agentmesh | 实现 |
| [kairon engine.py](../../../projects/kairon/packages/agent-runtime/src/agent_runtime/engine.py) | kairon | 实现 |

---

## 附录 A. 收敛检查清单

### Phase 5 完成后验收

| # | 检查项 | 验收标准 |
|---|--------|----------|
| 1 | 断裂 symlink 已清理 | `find ~/.hermes/scripts/ -xtype l` 返回 0 条 |
| 2 | 活跃项目桥接已重建 | `ls -la ~/.hermes/scripts/` 指向活跃项目 |
| 3 | 12 个 cron jobs 迁移完成 | agentmesh 调度器运行 ≥ 7 天无异常 |
| 4 | 新工具不写 `~/.hermes/scripts/` | 审计无新增 hermes 桥接脚本 |
| 5 | Hermes kanban 数据可查 | 调度可视化不依赖 `hermes kanban` |
| 6 | Hermes 记忆层可消费 | Task Center 可通过 MCP 读取记忆数据 |
| 7 | WeChat/IM 入口正常 | 用户可正常通过 IM 提交任务 |

### 方向 B 参考检查清单

| # | 检查项 | 验收标准 |
|---|--------|----------|
| 1 | 分层记忆系统完成 | 跨 session 记忆自动持久化，LLM 可查询 |
| 2 | 自改进技能系统完成 | 新流程自动保存为可复用技能 |
| 3 | 多渠道入口完成 | WeChat/Telegram/Discord 均可提交任务 |
| 4 | 内存→技能流水线完成 | 记忆自动聚类 → 新技能提案 |
| 5 | Hermes 依赖完全移除 | 无 hermes 进程运行，用户无感知 |

---

*维护: 2026-05-31 · Hermes 版本: hermes-webui (upstream by @nesquena)*
