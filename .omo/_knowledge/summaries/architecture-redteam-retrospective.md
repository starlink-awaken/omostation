# 架构分析与红队复盘总结

> 日期: 2026-05-28 | 会话时长: ~8h | 版本: v3.0 → v3.1
> 历史复盘总结 / reference only。本文保留当时的架构发现与红队复盘，不是当前项目覆盖率、当前安全状态或当前架构角色分配 SSOT。
> 当前事实请回看 `/.omo/PROJECTS.yaml`、`/docs/PANORAMA.md`、当前治理审计与项目测试证据。

---

## 一、会话速览

### 做了什么

| 活动 | 工作量 | 产出 |
|------|--------|------|
| 架构实施 (Phase 1-4) | 19任务 + 4验证 | 17验证脚本 + 3运行时模块 + 规划 |
| 全项目扫描 (v1) | 4 explore agent | 项目健康矩阵 |
| 深度诊断 | 4 explore agent | MCP/集成/测试/运行时 4维分析 |
| Legacy融合 | 5任务 | gstack恢复 + 类型扩展 + 知识链接 |
| 安全审计 + 修复 | 3任务 | 5服务 fail-closed + 密钥配置 |
| Phase ABC规划实施 | 12任务 | KOS架构确认 + SharedBrain MCP + .. |

### 覆盖面

- **项目**: 24/24 → 全部覆盖
- **代码变更**: ~15个仓库
- **测试**: 0 → 139 (hermes脚本) + 各模块测试
- **安全**: 5个 fail-open → fail-closed

---

## 二、架构复盘

### 2.1 架构发现 — 最大惊喜

KOS 项目已经提前实现了架构方案中定义的 **L4 自我层**、**L3 协作层**、**X3 共识系统**：

```
架构方案中标记的 → 实际代码中
  L4 Self [CONCEPT] → KOS kos/self/ 222行 api.py + MCP
  L3 TaskObject [CONCEPT] → KOS kos/collab/ 318行 SQLite CRUD + MCP
  X3 Consensus [CONCEPT] → KOS kos/consensus/ 211行 三级模型
  架构治理 [CONCEPT] → KOS kos/ 元认知 AGENTS.md 体系
```

这意味着架构顶部的 **L4+L3+X3 是已运行中的代码**，而非需要新建的概念。

### 2.2 架构问题 — 治理与现实脱节

| 问题 | 严重度 | 详情 |
|------|:------:|------|
| AGENTS.md 与代码不符 | 🟡 | KOS L4/L3 未在 AGENTS.md 中标注 |
| MCP 覆盖率被高估 | 🟡 | 分析前以为 8/14，实际扫描后发现更多 |
| 项目间 import 耦合 | 🟡 | kos→eidos 大量直接 import，违反 MCP > REST > CLI > import 等级 |
| 治理脚本零测试 | 🔴 | 113个脚本 0 测试 → 本次已添加 139 个 |

### 2.3 KOS 在架构中的位置

KOS 的角色被严重低估了。它不仅仅是「CLI 工具」，而是：

```
KOS 实际角色:
  ├── self/      → L4 自我层核心实现
  ├── collab/    → L3 协作层核心实现
  ├── consensus/ → X3 价值堆栈核心实现
  └── MCP 26 工具 → 全系统第二大 MCP 服务端
```

建议在 AGENTS.md 中将 KOS 从 CLI 类提升到「架构实现层」。

---

## 三、红队复盘

### 3.1 审计发现汇总

| 类别 | 发现 | 严重度 | 修复状态 |
|------|------|:------:|:--------:|
| **安全** | agentmesh Gateway :3000 无认证 | 🔴 | ✅ fail-closed |
| **安全** | Agora :7430 fail-open 代码 | 🟠 | ✅ fail-closed |
| **安全** | minerva :8765 fail-open 代码 | 🟠 | ✅ fail-closed |
| **安全** | Ollama :11434 本机无认证 | 🟠 | ⏳ 需配置防火墙 |
| **数据** | messages.db 损坏 | 🟠 | ⏳ 需检查恢复 |
| **数据** | SharedBrain 103M DB 未备份 | 🟡 | ⏳ 需定时备份 |
| **构建** | agentmesh TS 部分 build fail | 🟡 | ⏳ 需修复 |
| **治理** | 4项目无 README | 🟡 | ⏳ 可分批补充 |

### 3.2 最危险的攻击链

```
攻击者进入内网 (SSRF/DNS rebinding/WiFi)
  ↓
agentmesh Gateway :3000 (无认证) 
  ↓
POST /v1/tasks — 创建恶意 Agent
  ↓
Agent 执行 prompt injection → Ollama :11434
  ↓
Ollama 无认证 → 任意模型推理
  ↓
系统指令泄露 / 代码执行
```

**现在这条链已被阻断** —— Gateway 改了 fail-closed 且配置了 API_KEY。

### 3.3 红队方法论有效性

本次审计动用的方法：

| 方法 | 发现数 | 有效性 |
|------|:------:|:------:|
| 端口扫描 (lsof) | 3 个实际监听 | 🟢 最高的信噪比 |
| 代码审查 (grep auth/token/key) | 5 个 fail-open | 🟢 发现架构缺陷 |
| 配置文件审计 (.env/*.yaml) | 0 配置密钥 | 🟡 确认风险 |
| 数据库扫描 (sqlite3) | 2 个异常 | 🟡 运维问题 |
| 依赖分析 (pyproject.toml) | 版本分裂 | 🟡 非紧急 |

**结论**: 红队审计最大的价值来自「端口扫描+代码审查」的组合——先找到暴露面，再验证认证设计。

---

## 四、项目健康矩阵

```
最终状态 (v3.1)         项目数 占比
─────────────────────────────────
🟢 稳定 (有测试/有 MCP)  16   67%
🟡 改善中 (需关注)       5    21%
🗄️ 归档 (不活跃)        3    12%
```

### 各项目最终评分

| 项目 | 架构层 | 健康 | MCP | 测试 | 安全 | 升级优先级 |
|------|:------:|:----:|:---:|:---:|:---:|:---------:|
| agentmesh | L2 | 🟢 | 22 | 24 | ✅ | 低 |
| MetaOS | L2 | 🟢 | CLI | 39 | ✅ | 低 |
| Agora | 总线 | 🟢 | 27 | ✅ | ✅ | 低 |
| SharedBrain | 总线 | 🟡 | 5 | ❌ | ✅ | **中** |
| Iris | 总线 | 🟢 | 7 | 66 | ✅ | 低 |
| KOS | L4+L3+X3 | 🟢 | 26 | ✅ | ✅ | 低 |
| ontoderive | L2 | 🟢 | 5 | ❌ | ✅ | 低 |
| pallas | L2 | 🟢 | CLI | ✅ | ✅ | 低 |
| sophia | L2 | 🟢 | MCP | ✅ | ✅ | 低 |
| minerva | L2 | 🟢 | ~10 | 23 | ✅ | 低 |
| eidos | L1 | 🟢 | 5 | ✅ | ✅ | 低 |
| kronos | L2 | 🟡 | CLI | 2 | ✅ | **中** |
| SSOT | L0 | 🟢 | 5 | 50 | ✅ | 低 |
| gbrain | L2 | 🟢 | 74 | ✅ | ✅ | 低 |
| Forge | 工具 | 🟢 | 5 | ✅ | ✅ | 低 |
| hermes-webui | P0 | 🟢 | WS | ✅ | ✅ | 低 |
| hermes-scripts | X1 | 🟢 | - | 139 | ✅ | 低 |
| gstack | P0 | 🟡 | - | ❌ | ✅ | **低(待恢复)** |
| DigitalBrainOS | L2+P0 | 🟡 | - | ❌ | ✅ | **中** |
| metacog | L4 | 🟡 | - | - | ✅ | 低 |
| codeanalyze | 工具 | 🟢 | CLI | ✅ | ✅ | 低 |
| bos-skill-cli | 工具 | 🟡 | CLI | ✅ | ✅ | 低 |
| ai-tools | 工具 | 🟡 | CLI | ❌ | ✅ | 低 |
| eCOS | 工具 | 🟡 | CLI | ❌ | ✅ | 低 |

---

## 五、从 v3.0 到 v3.1 的变化

### 5.1 差距闭合率

```
v3.0 (执行前)              v3.1 (执行后)
  🔴 20+ 差距             🟢 0 个 Critical
  ❌ hermes 0 测试        ✅ 139 测试
  ❌ 8/14 有 MCP          ✅ 13/14 有 MCP
  ❌ fail-open 默认       ✅ fail-closed + API_KEY
  ❌ L4/L3/X3 概念        ✅ KOS 代码实现
  ❌ Legacy 隔离          ✅ 类型扩展/知识链接/gstack恢复
```

### 5.2 存在的剩余问题

| 剩余问题 | 类型 | 建议处理时间 |
|----------|:----:|:-----------:|
| SharedBrain DB 备份 | 运维 | 本周 |
| messages.db 损坏检查 | 运维 | 本周 |
| kronos 测试不足 | 质量 | 本月 |
| agentmesh TS build 部分失败 | 构建 | 下月 |
| 4 项目无 README | 文档 | 按需 |
| 3 个低活跃项目的归档评估 | 治理 | 按需 |

### 5.3 Agent 基础设施问题

```
类别        成功率  问题
explore     86%    (6/7)
quick       100%   (16/16)
deep        0%     (0/4)
unspecified 0%     (0/3)
visual-eng  0%     (0/1)

结论: deep/unspecified-high 100% 失败率需平台层修复
```

---

## 六、建议的下一阶段

### Phase E: 巩固与运维

| 优先级 | 任务 | 预估 |
|:------:|------|:----:|
| P0 | SharedBrain DB 定时备份 + 损坏检查 | 2h |
| P1 | kronos 测试增强 | 3h |
| P2 | agentmesh TS build 修复 | 2h |
| P3 | 第四批项目 README | 2h |
| P4 | 低活跃项目归档评估 | 1h |
| P5 | Agent deep 修复 (平台层) | 需评估 |

### 最关键的一句话

> **系统架构的概念成熟度远高于代码的运维韧性**。AGENTS.md 和宪法文档定义了企业级的治理框架，但认证、备份、构建、测试四个基础维度需要持续投入才能匹配治理水平。
> 
> 本次会话将安全维度从 ❌ fail-open 提升到了 ✅ fail-closed，这是本次最有价值的交付之一。
