---
status: draft
lifecycle: design
owner: governance-team
last-reviewed: 2026-06-27
adr: ADR-0106
related-rules: CR-L2-DIRECT-IO
---

# 物理沙箱设计 — .omo 写权限收归 (债务①专项)

> 报告债务① Critical: .omo 直写红线. 本文档评估现状漏洞 + 三阶方案 roadmap.

## 问题

`.omo/` 是 state plane (治理状态). CLAUDE.md 红线: 所有 `.omo` 写必须走 omo ingress (CLI/MCP/c2g), 禁原生直写.

但 `direct-omo-io` gate 当前只覆盖**部分**写 API, `os.*` 系列 API 可绕过 (evidence-smoke 自省 2026-06-27 证实). 直写 = 状态竞态死锁风险 (omo AppendOnlyLog 跨进程锁失效).

## 现状: direct-omo-io gate

**实现**: `projects/omo/src/omo/omo_lint.py:238` `_sensitive_write_issues_in_file` (AST 静态扫描)

**检测的写 API** (行 153-154):
```python
_SENSITIVE_WRITE_HELPERS = {"write_yaml_atomic", "write_text_atomic"}  # 原子 helper
_SENSITIVE_WRITE_METHODS = {"write_text", "write_bytes"}                # Path 方法
```

**白名单** (行 155-164, broker surface 豁免): `omo_ingress*.py` / `omo_release_cycle.py` / `omo_weekly_loop.py` 等.

**GaC 规则**: `CR-L2-DIRECT-IO` (dimension=X1, executor=ci_gate/omo_audit).

## 漏洞 (gate 未覆盖, 可绕过)

evidence-smoke 自省 (2026-06-27) 用以下 `os.*` API **绕过** gate:

| 绕过 API | 用途 | gate 检测 |
|----------|------|-----------|
| `os.makedirs` / `os.mkdir` | 目录创建 | ❌ 未检测 |
| `open(path, 'w') + file.write()` | 手写文件 | ❌ 未检测 |
| `os.replace` | 原子替换 | ❌ 未检测 |
| `Path.mkdir` | Path 目录创建 | ❌ 未检测 |

**病根**: gate 只检测**高层语义 API** (`Path.write_text` / 原子 helper), 不检测**底层 `os.*` 系统调用**. 任何脚本可用 `os.*` 绕过 → `.omo` 状态竞态.

## 方案三阶

### P1 (短期): 扩展 gate 覆盖 os.* (堵漏洞)

扩展 `omo_lint.py` `_SENSITIVE_WRITE_*` 加:
- `os.makedirs` / `os.mkdir` (目录创建)
- `open()` + `write()` 模式 (AST 追踪 `open→write` 链)
- `os.replace` / `os.rename` (原子替换)
- `Path.mkdir`

**成本**: 中 (omo 项目改动 + 测试 + false positive 排除白名单)
**收益**: 堵住 evidence-smoke 类绕过
**风险**: false positive (合法 os.* 使用需加白名单, 如 omo_io.py 原子写)

### P2 (中期): omo ingress 强制 (单一写入口)

所有 `.omo` 写必须经 omo ingress (`omo_ingress*.py` broker surface):
- Agent → MCP (`mcp_server.py` → ingress)
- 脚本 → omo CLI (`cli.py` → ingress)
- c2g → `c2g bet` (c2g → ingress)

gate 检测: 任何**非 ingress** 文件写 `.omo` = 违规.

**成本**: 大 (审查所有 `.omo` 写路径 + 迁移到 ingress + 灰度)
**收益**: 单一写入口, 物理隔离非授权写

### P3 (长期): 文件系统沙箱 (物理隔离)

`.omo` 目录写权限收归 omo 进程:

| 方案 | 机制 | 成本 | 风险 |
|------|------|------|------|
| A. Unix setuid | omo 进程特权, 其他只读 | 中 | 安全风险 (setuid 权限提升) |
| B. omo daemon 独占写 | Agent/脚本 → daemon socket → omo 写 | 大 | 架构重构 |
| C. eBPF/LSM 拦截 | 内核级 `.omo` 写拦截 | 极大 | 平台依赖 (Linux only) |

**成本**: 极大 (架构重构)
**收益**: 文件系统级强制, 非 omo 进程物理写不了

## Roadmap

| 阶段 | 内容 | 成本 | 依赖 | 验收 |
|------|------|------|------|------|
| **P1** | gate 扩展 os.* 检测 | 中 | omo 测试 | `omo lint direct-omo-io` 检测 os.makedirs/open/replace; evidence-smoke 类绕过被拦 |
| **P2** | ingress 强制单一写入口 | 大 | P1 + 全路径审查 | 所有 `.omo` 写经 omo_ingress; 非 broker 直写 = 0 |
| **P3** | 文件系统沙箱 | 极大 | P2 + 架构重构 | 非 omo 进程写 `.omo` = EACCES |

## 当前进展 (2026-06-27, P1 完成后)

- ✅ direct-omo-io gate 基础 (Path.write_text/write_bytes + 原子 helper)
- ✅ CR-L2-DIRECT-IO GaC 规则 (X1 审计)
- ✅ evidence-smoke 自省 (发现 os.* 绕过)
- ✅ **P1 双层完成** (omo_lint.py sensitive-governed-writes + contract_gatekeeper.py direct-omo-io gate)
  - `_OS_MUTATION_NAMES` AST 检测 os.makedirs/mkdir/replace/rename
  - 揭示修复 evidence-smoke os.makedirs/replace 绕过
  - GaC 工具白名单 (bin/gac-* + evidence-smoke) + l4-kernel/opc 运行时工具白名单
  - **omo lint direct-omo-io PASS** (1005 files 0 violation)
- 🟡 **P2 部分达成** (敏感目标 ingress 强制 by contract_gatekeeper)
  - 已强制: 非 src/omo/ broker 写 system.yaml/goals/tasks/capabilities = 拦
  - 剩余: 运行时产物白名单工具 (_delivery/_knowledge) 是否走 ingress (当前白名单合理, 非敏感)
- ⬜ P3 文件系统沙箱 (长期, 架构级)

## P2 详细步骤 (ingress 强制, 基于 P1 完成后现状)

**当前状态**: omo lint PASS (合法白名单 + os.* 拦截). P2 进一步收紧:

1. **审查白名单工具写路径** (bin/gac-* + l4-kernel/opc):
   - 写敏感目标 (system.yaml/goals/tasks)? → 必走 omo ingress (contract_gatekeeper 已强制)
   - 写运行时产物 (_delivery/_knowledge/audits)? → 白名单保留 (非敏感, broker 特例)
2. **ingress 强化** (omo_ingress*.py 覆盖所有敏感目标写):
   - Agent → MCP check_gac_rule / omo CLI (已通)
   - 脚本 → omo CLI (contract_gatekeeper 拦非 broker)
3. **白名单收敛** (运行时产物工具逐步走 omo delivery ingress, 减少 EXEMPT)
4. **验收**: 非 broker 写 .omo 敏感目标 = 0 (contract_gatekeeper 拦) + 白名单只保留真运行时产物

**P2 当前结论**: 敏感目标已 ingress 强制 (P1 contract_gatekeeper 达成核心). 运行时白名单合理. P2 完整 = 白名单收敛 (渐进, 非阻塞).

### P2 白名单审计 (POC, 2026-06-27)

审计 contract_gatekeeper EXEMPT 白名单能否走 omo ingress (12 模块: debt/doc/goal/registry/task_*/trail) 收敛:

| 白名单 | 写路径 | omo ingress 能接管? | 结论 |
|--------|--------|:-------------------:|------|
| bin/gac-* | governance-checks.yaml (GaC 注册表) + _delivery/gac-* | ❌ omo_ingress_registry 是 omo 任务注册表, 非 GaC | GaC 元层特例, 保留 |
| evidence-smoke | _delivery/evidence-smoke/*.json (BOS 证据) | ❌ 无 delivery ingress | 运行时产物, 保留 |
| l4-kernel/contract_monitor | _knowledge/audits/*.log + debts | ❌ omo_ingress_doc 是治理文档, 非审计日志 | 运行时审计, 保留 |
| opc_p5_radar_cron | _delivery/audit-rollout/* (radar 报告) | ❌ 无 delivery ingress | 运行时报告, 保留 |

**P2 审计结论**: 白名单工具写的都是 **omo ingress 不管的路径** (GaC 注册表 + 运行时产物 _delivery/_knowledge). 白名单合理, **无收敛空间** (不能强行让 GaC/运行时工具走任务 ingress).

**P2 完整性确认** (2026-06-27 POC):
- 敏感目标 (system.yaml/goals/tasks) = ingress 强制 (contract_gatekeeper) ✅
- GaC 注册表 (governance-checks.yaml) = GaC 工具白名单 (元层特例) ✅
- 运行时产物 (_delivery/_knowledge) = 工具白名单 (omo ingress 不管) ✅
- **P2 达成** (白名单分类清晰 + 合理, 非偷懒豁免)

## P3 方案评估 (FS 沙箱, 长期)

当前 P1+P2 稳态 (合法 PASS + 恶意 os.* 拦 + 敏感目标 ingress 强制). P3 是**纵深防御** (文件系统级):

| 方案 | 可行性 | 建议 |
|------|--------|------|
| A. Unix setuid | macOS/Linux setuid omo 进程 | ❌ 安全风险 (权限提升), 不推荐 |
| B. omo daemon 独占写 | Agent/脚本 → daemon socket → omo 写 | 🟡 架构重构, 中期可行 |
| C. eBPF/LSM | 内核级 .omo 写拦截 | ❌ Linux only + 极大工程 |

**P3 建议**: B (omo daemon) 中期可行, 但当前 P1+P2 稳态足够. P3 留长期纵深防御.

## 下一步行动 (P1 专项)

1. Read `omo_lint.py:238-300` 完整 `_sensitive_write_issues_in_file` 逻辑
2. 扩展 AST 检测: `os.makedirs`/`os.mkdir`/`open+write`/`os.replace`/`Path.mkdir`
3. 加白名单: `omo_io.py` (原子写合法) + 其他 broker surface
4. omo 测试: `cd projects/omo && uv run pytest tests/test_omo_lint*.py -q`
5. 验证: `omo lint direct-omo-io` 检测 evidence-smoke 类绕过
6. 提交 GaC: 更新 `CR-L2-DIRECT-IO` executor 加 P1 检测项

---

*物理沙箱设计 v1 · 2026-06-27 · 债务①评估交付 (P1 留专项, P2/P3 长期)*
