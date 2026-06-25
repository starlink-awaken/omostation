---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# Phase 17 Planning Gate 风险评估

> 日期: 2026-06-03
> 当前阶段: Phase 16 completed · Phase 17 planning gate
> 评估范围: 架构、代码、产品、治理四维度残余风险

---

## 执行摘要

| 风险域 | 最高严重度 | 是否阻塞 Phase 17 启动 |
|--------|:----------:|:----------------------:|
| 产品表面 (P0) | 🔴 High | **是 — 需明确约束范围** |
| 代码运行时 | 🟡 Medium | 否 |
| 架构耦合 | 🟢 Low | 否 |
| 文档一致性 | 🟡 Medium | 否 |
| 治理机制 | 🟢 Low | 否 |

**总体判定**: Phase 17 **可以启动**，但必须在 planning gate 中明确以下约束：
1. P0 工作范围严格限定为 gbrain capture/search CLI/API 入口，不追求完整 WebUI
2. Agora 服务启动作为 Phase 17 Wave 0 前置条件
3. LAYER-INDEX 更新作为 Wave 0 交付物

---

## 残余风险详细评估

### R1: P0 产品表面层缺失（🔴 High）

**发现**:
- hermes-webui (port 8787): **未运行**
- pallas, gstack, bos-skill-cli: **在代码库中不存在**
- 产品交互层定义的 4 个入口全部缺失

**与 Phase 16 的关系**:
- Phase 16 主题为 "Knowledge Capture/Search Product Surface Convergence"
- Phase 16 closeout 声称已产生 "fixture-backed walkthrough evidence" 和 "user-visible capture receipt, search hit"
- 但这些证据是**基于 fixture 的**（模拟数据），不是真实产品入口

**阻塞分析**:
- ❌ **不构成完全阻塞**: Phase 16 closeout 已接受 fixture-backed 证据作为收敛证明
- ⚠️ **构成范围约束**: Phase 17 的 "live gbrain capture/search pilot" 必须有真实 CLI/API 入口，不能再次仅用 fixture 证明

**建议**: 将 Phase 17 Wave 0 设为 "P0 入口基线"，要求至少一个可运行的 CLI 或 MCP tool 作为 capture/search 的用户入口。

---

### R2: Agora 服务未运行（🟡 Medium）

**发现**:
- Agora 代码完整（49 tests, app.py, cli.py, 配置文件齐全）
- 端口 7430/7431 **无监听**
- LAYER-INDEX 错误标记为 🟢 运行中

**影响**:
- 若 Phase 17 pilot 需要通过 MCP 路由调用 gbrain/kairon 能力，Agora 是必经之路
- Agora 未运行意味着所有 MCP tool 调用只能通过直接导入（绕过路由层）

**阻塞分析**:
- ❌ **不阻塞 planning gate**: planning gate 是规划审批，不要求运行时就绪
- ⚠️ **阻塞 Phase 17 Wave 1 执行**: 任何涉及 MCP 调用的 pilot 都需要 Agora 运行

**建议**: Agora 启动作为 Phase 17 Wave 0 的硬性前置条件（go/no-go 检查项）。

---

### R3: 文档状态漂移（🟡 Medium）

**发现**:
- LAYER-INDEX 中 4 个条目与实际状态不符（Agora 🟢, SharedBrain organs 🟢, D-Memory 🟢, D-Harvest 🟢）
- DECOMPOSITION.md 路径指针错误（`SharedBrain/_archived/` vs `projects/_archived/`）
- 33 个 kairon 包无包级 AGENTS.md

**影响**:
- 新开发者或 Agent 依赖 LAYER-INDEX 判断系统状态，可能做出错误决策
- 包级缺乏 AGENTS.md 增加 onboarding 成本

**阻塞分析**:
- ❌ **不阻塞 Phase 17**: 文档债务不影响功能交付
- ⚠️ **需在 Wave 0 解决**: LAYER-INDEX 更新应作为 Phase 17 的第一个交付物

---

### R4: 运行时适配器模式债务（🟡 Medium）

**发现**:
- engine-core, agora, ontoderive, kos, kronos 等核心包共有 ~49 处运行时 `try/except ImportError`
- 将集成失败从编译时推迟到运行时

**影响**:
- 开发期友好，但运维期难以诊断
- 不可分发（运行时才知道依赖是否满足）

**阻塞分析**:
- ❌ **不阻塞 Phase 17**: 这是长期技术债务，非短期阻塞
- 建议在 Phase 17 期间不新增适配器模式代码

---

### R5: metaos 运行时 sys.path.insert（🟡 Medium）

**发现**:
- `metaos/src/metaos/` 下有 4 个源文件使用 `sys.path.insert`
- 影响 `pip install -e .` 后的正常运行

**阻塞分析**:
- ❌ **不阻塞 Phase 17**: metaos 不是 Phase 17 pilot 的核心依赖

---

### R6: sharedbrain-standalone 零测试（🟡 Medium）

**发现**:
- 分解后的 `sharedbrain-standalone` 包有源代码但 0 测试
- 无其他包显式导入它

**阻塞分析**:
- ❌ **不阻塞 Phase 17**: 若 Phase 17 不涉及 SharedBrain 运行时，此包无关
- ⚠️ **若涉及**: 需在 pilot 前补充测试或明确排除 standalone 依赖

---

### R7: 历史架构债务已解决（🟢 Low）

以下问题在 Phase 9-16 期间已自然消除：

| 问题 | 历史状态 | 当前状态 |
|------|----------|----------|
| Agora → OntoDerive 硬耦合 | 12 处硬 import | 0 处 ✅ |
| KOS 零消费者 | 无人 import | 5 个活跃消费者 ✅ |
| 硬编码绝对路径 | 多处 `/Users/xiamingxing/` | 0 处 ✅ |
| ruff 大规模报错 | kos 5,263, ontoderive 1,307 | 全量 0 ✅ |

**结论**: 历史审计中的高严重度债务已基本解决，残余风险主要是**新发现或低级别**的。

---

## Phase 17 启动条件矩阵

| 条件 | 要求 | 当前状态 | 是否满足 |
|------|------|----------|:--------:|
| Phase 16 closeout 完成 | ✅ | 7/7 测试通过 | ✅ |
| 债务健康 = 100% | ✅ | 9/9 closed | ✅ |
| local brain readiness | gbrain 可运行 | 需验证 | 🟡 |
| user data boundary | 数据边界定义 | Phase 16 已定义 | ✅ |
| rollback conditions | 回滚条件明确 | Phase 16 已定义 | ✅ |
| 低风险评估 | 仅一个 pilot | 规划中 | 🟡 |
| Agora 服务就绪 | Wave 0 前置 | 未运行 | ❌ |
| P0 入口定义 | Wave 0 交付 | 未定义 | ❌ |

---

## 建议的 Phase 17 Wave 0 调整

基于风险评估，建议将 Phase 17 Wave 0 从"治理门禁"扩展为包含以下检查项：

```
Wave 0: Planning Gate 准入验证
├── [ ] Agora 服务启动（7430/7431 监听）
├── [ ] LAYER-INDEX 状态更新（与实际对齐）
├── [ ] P0 入口定义（CLI/API/MCP 至少一个）
├── [ ] gbrain local brain 可运行验证
├── [ ] sharedbrain-standalone 用途确认或排除
└── [ ] 风险 R1-R6 注册到 debt registry（watching 状态）
```

只有在 Wave 0 全部勾选后，才允许进入 Wave 1 的 live pilot 执行。

---

*评估时间: 2026-06-03*
*输入: architecture-health-snapshot, dependency-audit, code-quality-baseline, SB-decomposition-verification*
