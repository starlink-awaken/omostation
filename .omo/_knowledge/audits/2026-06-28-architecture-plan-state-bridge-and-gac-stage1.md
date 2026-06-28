# 架构方案: MOF State-Bridge 失同步修复 + GaC Stage 1 执行绑定

> **日期**: 2026-06-28 | **作者**: 系统审计 → 架构推演
> **状态**: 方案设计 (待审批)
> **前置**: `2026-06-28-comprehensive-system-audit.md` (C8 + C4)

---

## 一、MOF State-Bridge 77 项失同步 (C8)

### 1.1 现状

| 类别 | 数量 | 说明 |
|------|:----:|------|
| M1 only | 8 | M1 OMOTask 节点无 .omo 配对 |
| .omo only | 69 | .omo task YAML 无 M1 配对 |
| 字段漂移 | 0 | ✅ 已配对的 88 对字段一致 |

### 1.2 .omo-only 69 项分类

| 类别 | 数量 | 处置策略 |
|------|:----:|---------|
| OPC-P6-SELF-EVOLUTION-nop-* | ~15 | **归档** (cron 自动生成的空操作时间戳, 无 M1 建模价值) |
| P44-P52 阶段任务 | ~30 | **归档** (历史阶段任务, 已完成, M1 未追溯) |
| QUEST-* | ~10 | **补 M1** (family-hub quest, 活跃任务应有 M1 建模) |
| TASK-* | ~8 | **补 M1** (杂项任务, 活跃任务应有 M1 建模) |
| IMPORTED-* | ~6 | **归档** (外部导入残留, 无对应 M1) |

### 1.3 M1-only 8 项处置

| ID | 策略 | 理由 |
|----|------|------|
| OMOTASK-IMPORTED-baf924 | **删除 M1 节点** | 导入残留, .omo 侧已清理 |
| OMOTASK-IMPORTED-8bdcf3 | **删除 M1 节点** | 同上 |
| OMOTASK-IMPORTED-a4cfe7 | **删除 M1 节点** | 同上 |
| OMOTASK-IMPORTED-a5a8ea | **删除 M1 节点** | 同上 |
| OMOTASK-IMPORTED-06fb03 | **删除 M1 节点** | 同上 |
| OMOTASK-IMPORTED-3384bb | **删除 M1 节点** | 同上 |
| OMOTASK-OPC-P6-SELF-EVOLUTION-nop-20260614T114209Z | **删除 M1 节点** | 单个 nop 时间戳, .omo 侧已清理 |
| OMOTASK-OPT-AUTO-DISCOVERY | **补 .omo task** | 规划节点, 应有 .omo 配对 |

### 1.4 推荐方案: 分步清理

```
步骤 1: 归档 .omo-only 历史任务 (~51 项)
  - OPC-nop-* → .omo/tasks/archive/ (批量 mv)
  - P44-P52, IMPORTED-* → .omo/tasks/archive/
  - 不删, 只移到 archive/ (mof-state-bridge 不扫描 archive/)

步骤 2: 删除 M1-only ghost (8 项 → 7 项删除)
  - rm 6 个 OMOTASK-IMPORTED-*.yaml + 1 个 nop
  - 1 个 OMOTASK-OPT-AUTO-DISCOVERY 补 .omo task YAML

步骤 3: 补 M1 节点 for 活跃 .omo-only 任务 (~18 项)
  - QUEST-* (10) + TASK-* (8)
  - 用脚本批量生成 M1 OMOTask 节点 (从 .omo YAML 读字段)
  - 或: 标记为 "M1 豁免" (非所有 .omo task 都需要 M1 建模)

步骤 4: 验证
  - mof-state-bridge --strict → 目标: m1_only=0, omo_only=0
```

### 1.5 关键决策点

**Q: 是否所有 .omo task 都需要 M1 建模?**

- **选项 A (严格)**: 是, 所有 task 必须有 M1 节点 → 需补 18 个 M1 节点
- **选项 B (务实)**: 只有 "需要跨层追溯的 task" 才需要 M1 → 标记其余为 "M1 豁免"
- **推荐: B** — QUEST 和 TASK 类任务可能不需要 M1 元模型建模, 用 task_policy 标记

**Q: 归档的 .omo-only 任务是否需要保留在 git 历史中?**

- **是** — 移到 `.omo/tasks/archive/` 而非删除, 保留审计追溯

---

## 二、GaC Stage 1 执行绑定 (C4)

### 2.1 现状

- 118 条 GaC 规则已声明, 但仅 CI gate (gac-validate --gate) 兜底
- 编辑时无强制执行 (agent 不自觉遵守, 靠 CI 事后拦截)
- roadmap 阶段 1 的 4 个子任务全部 pending

### 2.2 四个子任务方案

#### T1.1: AGENTS.md GaC 段导出 (安全, 立即可做)

```
方案:
  bin/gac-export-agents.py — 从 governance-checks.yaml::gac.rules 导出
  输出: 追加到根 AGENTS.md 的 GaC 规则速览段
  格式: 按维度 (X1-X4) + 层 (L0-L4) 分组的 markdown 表格
  风险: 无 (只读 + 追加文档)
  工作量: 2h
```

#### T1.4: CI gate gac-validate --gate (安全, 立即可做)

```
方案:
  .github/workflows/gac-validate.yml
  步骤: checkout → python3 bin/gac-validate.py --gate
  触发: push + PR (所有分支)
  阻塞: gac-validate 退出码 != 0 时 fail
  风险: 无 (已有 governance-check.yml, 只加一步)
  工作量: 30min
```

#### T1.2: 泛化 PreToolUse hook (中等风险, 需评估)

```
方案:
  .claude/hooks/pre-tool-use/gac-check.py
  逻辑:
    1. 读 governance-checks.yaml::gac.rules
    2. 按 check_type 匹配执行器:
       - port_hardcode → 扫描文件中的 :PORT 模式
       - import_nucleus → 扫描 from nucleus import
       - broad_except → 扫描 except: / except Exception:
       - ssot_pointer → 检查 system.yaml 引用
       - direct_omo_io → 检查 .omo/ 直写
    3. 命中规则 → 返回 warning (不阻塞, 阶段 1 先 advisory)
    4. 后续阶段升级为 blocking

  风险: hook 性能 (需 <1s), 误报率 (需白名单)
  依赖: .claude/hooks/ 目录需存在, Claude Code 支持 PreToolUse hook
  工作量: 1 天 (含测试 + 白名单调优)

  推演:
    - 不是所有 118 条规则都能 hook (只有 check_type=pattern_match 的可以)
    - 预估可 hook 的规则: ~20 条 (port/import/except/ssot/direct-io 类)
    - 其余 98 条仍靠 CI gate + 自觉
```

#### T1.3: MCP 工具内置注册表检查 (高风险, 需 omo 并发解除)

```
方案:
  omo MCP 扩展: check_gac_rule(rule_id, file_path) → 检查单文件
  workspace_edit hook: 编辑前自动调用 check_gac_rule

  风险:
    - omo 并发阻塞 (governance_surfaces/omo_lint 拆分未完成)
    - MCP 调用延迟 (每次编辑 +200ms)
    - 误报导致开发体验恶化

  依赖: omo 并发解除 (governance_surfaces 拆分完成)
  工作量: 3-5 天 (含 omo 拆分)

  推荐: **暂缓** — 等 omo 并发解除后再推
```

### 2.3 推荐推进顺序

```
立即可做 (安全, 根仓):
  T1.1 AGENTS.md 导出 ──→ T1.4 CI gate
  (2.5h)                    (30min)

评估后可做 (中等风险):
  T1.2 PreToolUse hook
  (1 天, 需 .claude/hooks/ 支持)

暂缓 (高风险, 需前置):
  T1.3 MCP 内置 check
  (3-5 天, 需 omo 并发解除)
```

### 2.4 GaC Stage 1 架构图

```
                    ┌─────────────────────────────┐
                    │  governance-checks.yaml     │
                    │  118 GaC rules (SSOT)      │
                    └──────────┬──────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐  ┌─────▼──────┐  ┌──────▼───────┐
    │ T1.1 AGENTS.md  │  │ T1.2 Hook  │  │ T1.4 CI gate │
    │ (advisory)     │  │ (advisory) │  │ (blocking)  │
    │ agent 读到规则  │  │ 编辑时提示  │  │ push/PR 拦截 │
    └────────────────┘  └────────────┘  └─────────────┘
                                         ┌──────────────┐
                                         │ T1.3 MCP     │
                                         │ (blocking)   │
                                         │ 需 omo 并发解除│
                                         └──────────────┘
```

---

## 三、总结: 推荐立即执行 vs 方案待批

### 立即可执行 (已在本 session 完成)

| # | 修复 | 状态 |
|---|------|------|
| ✅ | trace_log.jsonl 移出 git | done |
| ✅ | 3 项目 lint 修复 | done |
| ✅ | nucleus 2 处顶层 import → lazy | done |
| ✅ | omo 子模块 dirty 20 文件提交 | done |
| ✅ | gbrain detached HEAD → main | done |
| ✅ | MOF schema 9 项错误修复 | done |

### 方案待批 (需确认后执行)

| # | 修复 | 方案 | 需确认 |
|---|------|------|--------|
| 1 | MOF state-bridge 77 项 | 归档 51 + 删 ghost 7 + 补 M1 18 (或标记豁免) | 选项 A vs B |
| 2 | GaC T1.1 AGENTS.md 导出 | bin/gac-export-agents.py | 安全, 可直接做 |
| 3 | GaC T1.4 CI gate | gac-validate.yml | 安全, 可直接做 |
| 4 | GaC T1.2 PreToolUse hook | .claude/hooks/gac-check.py | 需评估 .claude/hooks/ 支持 |
| 5 | GaC T1.3 MCP check | omo MCP 扩展 | 暂缓, 需 omo 并发解除 |

---

*架构方案设计 · 2026-06-28 · MOF state-bridge + GaC Stage 1 推演*
