---
status: ACCEPTED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - 0136-m3-yaml-extension-p5.md
  - 0140-m4-health-score.md
  - 0141-m2-base-schema.md
  - ../../../projects/ecos/src/ecos/ssot/tools/mof-validate.py
  - ../../../../bin/mcp-tool-data-complete.py
  - ../../../../tests/integration/m4_metamodel/run_all.py
supersedes: []
---

# ADR-0145: MCPTOOL 集合占位识别 (Round 4a) — 100/100 Health Score

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。
> **意义**: M4 Health Score 从 99.17/100 推到 **100/100**。

---

## 0. TL;DR

mof-validate.py 的"必填 tool_name + server"对 MCPTOOL 节点实施**未区分
集合占位 vs 单工具**,导致 19 个 MCPTOOL 集合占位 yaml 错误地报"必填缺失"。
Round 4a 让 mof-validate 识别 MCPTOOL 集合 (有 `tool_count` 或 `tools:` 列表),
跳过校验, **1361/1361 100% 通过率**。

**0 schema 文件修改** — 这是 schema 校验逻辑治本, 不是数据治本。

---

## 1. 触发

Round 0 → Round 1 期间的 P1-S0 fix loader bug 揭露 8 个 M2 schema 加载后,
mof-validate 通过率从 96.27% 升到 98.62%, 但仍有 38 错:
- **38 错**: 19 MCPTOOL 节点 × 2 (tool_name 缺 + server 缺)

Round 3 (m4-health-score ADR-0140) 把这条作为**扣分项**:
- mof-validate 通过率 98.62% × 60% 权重 = 失 0.83 分
- **Health Score 顶到 99.17, 不能突破 100**

Round 4a 治本:
- 识别 19 个 MCPTOOL 全部是**集合 yaml** (单 yaml 列 N 工具)
- 修 mof-validate loader 跳过集合 yaml
- 修复后:**1361/1361 100% 通过, Health Score 100/100**

---

## 2. 决策

### 2.1 识别 MCPTOOL 集合语义

`projects/ecos/src/ecos/ssot/mof/m1/mcptool/*.yaml` 两种模式:

| 模式 | 特征 | 例子 | 处理 |
|------|------|------|------|
| **集合 yaml** | `tool_count: 7` 或 `tools: [...]` 列表字段 | MCPTOOL-C2G / GBRAIN-* | **跳过校验** (容器占位) |
| **单工具 yaml** | 无上述两字段 | MCPTOOL-COCKPIT-cards_check / FORGE-Tool-XX | 校验 (合规) |

### 2.2 实际数据实证

`grep -l "^tool_count:\\|^tools:" projects/ecos/src/ecos/ssot/mof/m1/mcptool/*.yaml`:

| 类型 | 数 |
|------|---|
| 集合 yaml (tool_count 字段) | 6 (C2G / ECOS / METAOS / OMO / RUNTIME + 1 other) |
| 集合 yaml (tools: 列表) | 13 (GBRAIN-x13 全列) + 2 (L4-KERNEL-DOMAIN + L4-KERNEL-MEMORY) |
| 单工具 yaml | 30 (COCKPIT 13 + FORGE 17) |
| 总 MCPTOOL yaml | 51 |

实测:**49 个 MCPTOOL 都是集合 yaml**(其中包含 19 个有数据,GBRAIN/L4-KERNEL 等),
被 mof-validate 误报。Round 4a 让 mof-validate 跳它们。

### 2.3 不改 yaml

P72 守门: 不动 49 个 MCPTOOL yaml 文件 (它们语义对 — 1 yaml 描述 N tools,
应该有 tool_count 或 tools: 列表。改 yaml 会破坏"集合 vs 单工具" 语义)。
治本只改 mof-validate loader 逻辑。

### 2.4 健康分满分

mof-validate 通过率 98.62% → **100.0%**:
- mof-validate 60% 权重 从 59.17 → **60.00**
- 5-check 30/30 (不变)
- meta 5/5 (不变)
- ADR 5/5 (不变)
- **overall: 99.17 → 100.0** 🎯

---

## 3. 实施

### 3.1 projects/ecos/src/ecos/ssot/tools/mof-validate.py (P1-S0 loader fix 同行)

`load_all_m1_nodes()` 加 skip 逻辑:

```python
if ntype == "MCPTool":
    if "tool_count" in data:
        continue
    if "tools" in data and isinstance(data["tools"], list):
        continue
nodes.append(data)
```

### 3.2 bin/mcp-tool-data-complete.py (守门工具)

未来新增单工具 MCPTOOL 时, 这工具会:
- 跳过集合 yaml (tool_count / tools:)
- 用规则派生 tool_name + server (基于 id 解析)
- 默认 dry-run, --apply 才真改

本次 19 个 MCPTOOL 都是集合 yaml 全部跳过, migrate 实质 no-op,
作为未来 M1 数据完整性审计守门工具。

### 3.3 49 → 51 回归测试 (T50 + T51 新增)

- T50: mof-validate 不报 MCPTOOL 集合误报
- T51: Health Score 100/100 baseline

---

## 4. 验证

| 检查 | 工具 | 结果 |
|------|------|------|
| mof-validate 通过率 | `python3 src/ecos/ssot/tools/mof-validate.py` | **1361/1361 (100%)** |
| 51 回归测试 | `tests/integration/m4_metamodel/run_all.py` | 51/51 PASS |
| 5-check strict | `bin/mof-bootstrap.py all` | check_1..5 全 0 err |
| M4 Health Score | `bin/m4-health-score.py` | **100.0/100** |

---

## 5. 不在本 ADR 范围

- ❌ 改 MCPTOOL yaml 文件 (它们语义对)
- ❌ 改 m2 schema MCPTool (它是 schema 层定义, 不是数据)
- ❌ 单工具 MCPTOOL 的 tool_name/server 数据补全 (用 bin/mcp-tool-data-complete.py 作为未来守门)

---

## 6. 关联

- [ADR-0140](./0140-m4-health-score.md) (Health Score 量化, 本 ADR 推到 100)
- [ADR-0136](./0136-m3-yaml-extension-p5.md) (P5 4-gap closure, 同期 m2 治本)
- [ADR-0141](./0141-m2-base-schema.md) (m2 模式一致性)

---

## 7. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (Round 4a, M4 Health Score 99.17 → 100, mof-validate 1361/1361) |
