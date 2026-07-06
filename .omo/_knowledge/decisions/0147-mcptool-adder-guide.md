---
status: ACCEPTED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - 0145-mcptool-collection-skip.md
  - 0140-m4-health-score.md
  - 0141-m2-base-schema.md
  - 0146-8stage-stability-declaration.md
  - ../../../../docs/MCPTOOL-ADDER-GUIDE.md
  - ../../../../bin/mcp-tool-data-complete.py
supersedes: []
---

# ADR-0147: MCPTOOL M1 Adder Guide (Round 5b)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。

---

## 0. TL;DR

新增 `docs/MCPTOOL-ADDER-GUIDE.md`,把单工具 MCPTOOL 节点的增量添加入口标准化为
**5 步 / 5 分钟流程**: 写 yaml → 跑守护 (mcp-tool-data-complete.py + mof-bootstrap.py) →
跑 m4-health-score → commit + PR。

**核心约束**:
- 必须遵循 M3/M2/M1 三层 schema (m3.yaml MCPTool / m2 type MCPTool / m1 yaml 13 字段)
- 必须符合 M2BaseSchema (ADR-0141) 公共契约
- 与 collection MCPTOOL (ADR-0145) 严格区分
- 走 bin/mcp-tool-data-complete.py 守护, 不允许空 tool_name / 空 server

---

## 1. 决策

### 1.1 单一入口

新增 1 个 single-tool MCPTOOL yaml 是 M4 元模型时代最常见的 M1 增改动作。
文档化 5 步流程, 让开发者 (含 copilot) 不必读 5 个 schema 文件。

### 1.2 模板

`docs/MCPTOOL-ADDER-GUIDE.md` 提供 bash 模板, 一键生成合规 yaml:

```bash
TOOL=my_tool
SERVER=cockpit
cat > projects/ecos/src/ecos/ssot/mof/m1/mcptool/MCPTOOL-${SERVER^^}-$TOOL.yaml <<YAML
id: MCPTOOL-${SERVER^^}-$TOOL
type: MCPTool
m3_parent: StructuralElement.Component
...
YAML
```

### 1.3 自检 4 步

```
1. bin/mof-bootstrap.py all  → 5-check strict 全 0 err
2. bin/mcp-tool-data-complete.py → "✅ all complete" 或报需补字段
3. bin/m4-health-score.py --emit → 100.0/100 baseline 不退化
4. tests/integration/m4_metamodel/run_all.py → 51/51 PASS
```

### 1.4 提交 PR

新增 yaml 必走 PR review, 不直 push main (cross-cutting):
- Submodule 内 `git commit`
- 主仓 `git submodule update --init projects/ecos` 或 `git add projects/ecos`
- 主仓 `git commit` (bump 指针)
- `git push origin work/{branch}`
- PR 创建走 PR review (m4-cron-hook 自动派生 health score)

---

## 2. 与 m4-health-score / mof-bootstrap 关系

`docs/MCPTOOL-ADDER-GUIDE.md` 是 ADR-0145 + ADR-0140 + ADR-0141 的**实战入口**:
- ADR-0145 区分 single-tool vs collection (mof-validate skip)
- ADR-0140 量化 adder 后整体健康度
- ADR-0141 m2 BaseSchema 校验 yaml 公共契约

3 个 ADR 提供**机制**, adder guide 提供**流程**。

---

## 3. 不在本 ADR 范围

- ❌ 新增 collection MCPTOOL 模式 (走 ADR-0145 + 现有 process)
- ❌ 改 mof-validate.py 跳过逻辑 (不变)
- ❌ 改 m2 schema MCPTool 定义 (不变)

---

## 4. 关联

- [ADR-0145](./0145-mcptool-collection-skip.md) (single-vs-collection 区分基础)
- [ADR-0140](./0140-m4-health-score.md) (adder 后量化)
- [ADR-0146](./0146-8stage-stability-declaration.md) (Round 5a 同期)
- [docs/MCPTOOL-ADDER-GUIDE.md](./../../../../docs/MCPTOOL-ADDER-GUIDE.md) (本文档产出)

---

## 5. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (R5b, MCPTOOL adder 5 步流程文档化) |
