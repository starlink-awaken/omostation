# 5+3+1 治理体系总览 (Governance Master Index)

> 2026-06-06 起稿 · 当前作为治理文档导航与路由入口，不维护运行时计数/健康分快照。
> 当前治理面 SSOT 见 `/.omo/standards/omo-governance-surfaces.md`、`/.omo/_truth/registry/omo-governance-surfaces.yaml`、`/.omo/_truth/x1-governance-policies.yaml` ~ `x4-consistency-rules.yaml`。

---

## 一、治理文档索引

### 宪法级 (不可变)
| 文档 | 说明 |
|------|------|
| 全局治理宪章 v1 (governance-charter-v1.md) | 治理原则与边界约束；运行时事实需回看 control/truth SSOT |
| L4-L3-Agent 桥接协议 (l4-l3-agent-bridge-canon.md) | L4被动/L3桥接/Agent执行器 |
| 5+3+1 分层索引 (LAYER-INDEX.md) | 分层骨架与 X1-X4 路由 |

### 策略级 (可变, 需审查)
| 文档 | 说明 |
|------|------|
| 强制执行机制 (governance-enforcement-v1.md) | 5层防御体系设计 |
| X4 治理一致性设计 (x4-governance-consistency-design.md) | 第四横切面 + 元规则 |
| 接口架构治理 (interface-governance-2026-06-06.md) | 接口治理原则与约束 |
| 统一接口层设计 (unified-interface-design-v1.md) | Interface Registry 方案 |
| 全量审计报告 (5+3+1-full-audit-2026-06-06.md) | 历史审计基线与问题发现 |
| 架构全局方案 (architecture-complete-plan.md) | 0→9项目路线 |

### 操作级
| 文档 | 说明 |
|------|------|
| OMO Goals (current.yaml) | 当前Phase + 目标 |
| Kairon 问题台账 | 21→0 债务追踪 |
| CLAUDE.md ×3 (Workspace/kairon/驾驶舱) | Agent启动指令 |
| AGENTS.md ×3 | 开发者指南 |

---

## 二、执行机制清单

### CI 自动检查
- `scripts/check-interfaces.py` — CLI一致性 + 端口冲突 + 文档保鲜
- `scripts/check-cross-deps.py` — 跨层import违规
- `.github/workflows/governance-check.yml` — 上述两项 + 每周cron

### Runtime MCP 工具 (cockpit)
- `workspace_context` — Agent启动上下文
- `cards_status/check` — 卡片管理
- `vault_search` — Vault知识检索

### X4 治理一致性 (元规则)
```
X4 = "规则是否被遵守"
  7项检查: CLI注册/端口冲突/跨层依赖/文档保鲜/CI覆盖/Phase门禁/Agent启动链
  度量化: 以治理门禁与审计结果为准，不在本页维护静态分数
  门禁: score≥90 且 0 critical → Phase可迁移
  定位: 横向切面 (非L0), L0协议定义规则, X4检查执行
```

---

## 三、X1-X4 四维切面

| 切面 | 定义 | 实现 |
|------|------|------|
| X1 安全 | 操作是否安全 | KEI沙箱, 审计链 |
| X2 保鲜 | 数据是否新鲜 | 过期检测, autoheal |
| X3 价值 | 投入是否合理 | LLM成本, Token |
| X4 一致性 | 规则是否被遵守 | CI检查, Phase门禁 |

---

## 四、当前状态

> 本页不再维护“当前状态”数字播报。
> 实时项目状态、健康分、任务进度、债务与 gate 结论请回看：
>
> - `/.omo/PROJECTS.yaml`
> - `/.omo/state/system.yaml`
> - `/.omo/goals/current.yaml`
> - `/.omo/debt/`
> - `/.omo/_delivery/`

## 五、快速导航

```
宪章 → governance-charter-v1.md
原则 → governance-charter-v1.md §0-§7
检查 → python3 scripts/check-interfaces.py
现状 → `/.omo/state/system.yaml` + `/.omo/goals/current.yaml`
X4  → x4-governance-consistency-design.md
```

---

*整理完成: 2026-06-06 · 2026-06-17 起仅维护导航与原则，不维护运行时快照*
