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

## 当前进展 (2026-06-27)

- ✅ direct-omo-io gate 基础 (`Path.write_text/write_bytes` + 原子 helper)
- ✅ `CR-L2-DIRECT-IO` GaC 规则 (X1 审计, executor=ci_gate/omo_audit)
- ✅ evidence-smoke 自省 (发现 os.makedirs+open+replace 绕过 → evidence-smoke 已修)
- ⬜ **P1 gate 扩展 os.\*** (下一步专项, 需 omo 测试 + 白名单调优)
- ⬜ P2 ingress 强制 (长期)
- ⬜ P3 文件系统沙箱 (长期)

## 下一步行动 (P1 专项)

1. Read `omo_lint.py:238-300` 完整 `_sensitive_write_issues_in_file` 逻辑
2. 扩展 AST 检测: `os.makedirs`/`os.mkdir`/`open+write`/`os.replace`/`Path.mkdir`
3. 加白名单: `omo_io.py` (原子写合法) + 其他 broker surface
4. omo 测试: `cd projects/omo && uv run pytest tests/test_omo_lint*.py -q`
5. 验证: `omo lint direct-omo-io` 检测 evidence-smoke 类绕过
6. 提交 GaC: 更新 `CR-L2-DIRECT-IO` executor 加 P1 检测项

---

*物理沙箱设计 v1 · 2026-06-27 · 债务①评估交付 (P1 留专项, P2/P3 长期)*
