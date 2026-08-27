---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# Phase 17 Planning Gate 架构 Guardrails

> 日期: 2026-06-03
> 阶段: Phase 16 completed → Phase 17 planning gate
> 权威来源: `system-design-baseline.md`, `phase16-closeout.md`, `MASTER-BLUEPRINT.md`

---

## 核心原则

Phase 17 的启动必须满足 **"bounded expansion with proven surface"** 原则：

1. **只推进一个 live pilot** — gbrain capture/search
2. **必须有用户可见证据** — capture receipt, search hit, result summary
3. **继承 Phase 15/16 的 guardrails** — 不绕过治理 loop
4. **禁止 ecosystem expansion** — 不引入新领域、新包、新外部依赖

---

## Guardrails

### G1: 范围边界（不可突破）

| 允许 | 禁止 |
|------|------|
| 一个 gbrain capture/search CLI/API pilot | 第二个 pilot 或并行 pilot |
| fixture → live 的渐进验证 | 跳过 fixture 直接声称 live |
| 现有包的内部重构（如 kos, gbrain） | 新增 kairon workspace 包 |
| Agora 启动和路由配置 | 新增 MCP 协议或路由规则 |
| P0 CLI 入口（如 `wksp capture`） | WebUI 重写或全新前端 |
| user data boundary 内的数据 | 跨 boundary 数据迁移 |

**违反后果**: 立即触发 pause-and-reassess，回到 planning gate 重新审批。

### G2: 执行顺序（必须遵守）

```
Wave 0: 准入验证（go/no-go）
  ├── Agora 启动验证
  ├── P0 入口定义（CLI/API）
  ├── LAYER-INDEX 更新
  └── gbrain local readiness 验证
  
Wave 1: pilot 核心
  ├── capture 端到端（输入 → 存储 → receipt）
  ├── search 端到端（查询 → 命中 → 摘要）
  └── 用户可见证据收集
  
Wave 2: 收敛与验收
  ├── rollback 测试
  ├── boundary 压力验证
  └── closeout evidence 归档
```

**禁止**: Wave 0 未通过就进入 Wave 1。

### G3: 证据标准（每项必须有）

| 交付物 | 证据形式 | 存储位置 |
|--------|----------|----------|
| capture 功能 | CLI 输出截图 + 数据库记录 | `.omo/evidence/phase17/` |
| search 功能 | CLI 输出截图 + 命中日志 | `.omo/evidence/phase17/` |
| user visible | 终端录屏或文本回放 | `.omo/evidence/phase17/` |
| rollback | 回滚脚本执行日志 | `.omo/evidence/phase17/` |
| Agora 启动 | 端口监听验证 + health check | `.omo/evidence/phase17/` |

**证据必须可独立复现**:  reviewer 可以在干净环境中按照文档复现相同结果。

### G4: 风险 stop 条件

若以下任一情况发生，触发 **immediate stop**:

| 条件 | 触发场景 |
|------|----------|
| R1 恶化 | P0 入口在 Wave 1 后仍无用户可见输出 |
| R2 恶化 | Agora 启动后 24h 内再次崩溃 |
| R3 恶化 | LAYER-INDEX 更新后仍有一处以上严重不符 |
| R4 新增 | Phase 17 引入新的 `try/except ImportError` 运行时适配器 |
| 数据泄漏 | capture/search 越过 user data boundary |
| 不可逆变更 | 对 gbrain schema 的变更无 rollback 脚本 |

**stop 后流程**: 
1. 记录 stop 原因到 `.omo/tasks/blocked/`
2. 72h 内完成 impact assessment
3. 重新走 planning gate 审批才能恢复

### G5: 文档约束

1. **SSOT 铁律**: Phase 17 的所有规划文档只引用已有 facts，不复制 state/system.yaml 或 goals/current.yaml 中的内容
2. **不新建 shadow SSOT**: 分析文档（如本 guardrails）只提供约束和入口，不替代 `.omo/tasks/active/*.yaml`
3. **LAYER-INDEX 同步**: 每完成一个 Wave，LAYER-INDEX 必须更新；未更新的 Wave 不得进入下一 Wave

### G6: 债务治理约束

1. **新债务即时注册**: Phase 17 执行中发现的任何新债务，必须在 24h 内注册到 `.omo/debt/items/`
2. **历史债务不复活**: SB_DECOMPOSITION 等已 closed 债务不因文档指针错误而重新打开（文档修正走独立任务）
3. **debt_weight 监控**: 若 Phase 17 引入新债务导致 debt_weight 下降超过 0.05，触发评估

---

## 与 system-design-baseline.md 的对齐

| Baseline 决策 | 本 Guardrails 实现 |
|---------------|-------------------|
| "No ecosystem-expansion laundering under a product label" | G1 禁止列表 |
| "No resumption of broad expansion without Phase 15 policy baseline and Phase 16 adoption evidence" | G2 执行顺序 |
| "P0 product-surface convergence" | G3 证据标准 |
| "1L governed lifecycle loop" | G2 Wave 0 准入验证 |
| "No shadow SSOT" | G5 文档约束 |

---

## 审批链

| 步骤 | 审批者 | 产出 |
|------|--------|------|
| Planning Gate 提案 | 系统分析 | 本 guardrails + risk assessment |
| Wave 0 验收 | 治理机制 | `.omo/evidence/phase17/wave0/` |
| Wave 1 验收 | 人类审批 | `.omo/evidence/phase17/wave1/` |
| Wave 2 closeout | 治理机制 + 人类审批 | `.omo/summaries/phase17-closeout.md` |

---

*制定时间: 2026-06-03*
*版本: v1.0（Phase 17 planning gate 专用）*
