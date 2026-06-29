---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-06-29
related-contract: doc-ssot-contract.md
---

# 文档呈现模式: digest + pointer + lint

> 事实类型 (GaC 规则 / BOS 服务 / ...) 需在入口文档 (AGENTS.md / README.md) 可见,
> 但完整内容硬编码违背 SSOT. 本模式解决这个张力.
>
> 关联契约: [`doc-ssot-contract.md`](doc-ssot-contract.md) (SSOT 正交契约).

## 问题

事实类型有自己的 SSOT (yaml registry), 但 agent / 开发者需要在入口文档快速看到全貌.
直接 paste 完整表到 markdown → SSOT 违背 (改一处要改多处) + 信息过载 + 漂移.

## 模式 (3 件套)

### 1. digest 文件 (完整 generated 索引)
事实类型的完整索引生成到 `docs/generated/<fact-type>.md`. 由工具从 SSOT registry
生成 (有 regenerate 机制, 非手编辑).

### 2. 入口文档 pointer only
入口文档 (AGENTS.md / README.md) 只保留 marker 段:
- SSOT 指针 (registry 路径)
- digest 指针 (`docs/generated/` 路径)
- validate / drift / regenerate 命令
- 明确声明 "Do not paste the full inventory"

### 3. lint 强制 (机器防 embedded)
`bin/doc-ssot-lint.py` 扫入口文档的 marker 段 (`<!-- X-START -->` / `<!-- X-END -->`),
检测 embedded table:
- 段内含完整表 → findings (报错)
- 段内只 pointer → 通过

## 实例: GaC 规则 (2026-06-29 落地)

| 件套 | 位置 |
|:-----|:-----|
| SSOT | `.omo/_truth/registry/governance-checks.yaml::gac.rules` |
| digest | `docs/generated/agent-gac-rules.md` (`bin/gac-export-agents.py` 生成) |
| 入口 pointer | `AGENTS.md` `GaC-RULES-START/END` 段 |
| lint 强制 | `bin/doc-ssot-lint.py` (扫 `GaC-RULES` 段, embedded table → findings) |
| 契约声明 | `doc-ssot-contract.md` SSOT 映射表 ("AGENTS.md pointer only") |

工具链: `gac-export-agents.py` (生成 digest + AGENTS pointer) → `doc-ssot-lint` (强制
pointer only) → `make gac-local-gate` (CI 门禁).

效果: AGENTS.md 从 319 行 (含 132 行 GaC 表) → 134 行 (纯 pointer), -185 行.

## 接入模板 (新事实类型)

新增事实类型 (如 BOS 服务表 / port 表 / capability 表) 按 5 步:

1. **SSOT 确认**: 事实有唯一 yaml registry (如 `_truth/registry/<fact>.yaml`)
2. **digest 生成器**: 写 / 扩 `bin/<fact>-export.py`, 从 SSOT 生成 `docs/generated/<fact>.md`
3. **入口 pointer**: 入口文档加 marker 段 (`<!-- <FACT>-START -->` + pointer + 命令 + `<!-- <FACT>-END -->`)
4. **lint 强制**: `bin/doc-ssot-lint.py` 加该 marker 段的 embedded 检测
5. **契约行**: `doc-ssot-contract.md` SSOT 映射表加该事实的呈现策略行

## Anti-patterns (避免)

- ❌ **直接 paste 完整表** — 违背 SSOT, 改一处改多处, 必漂移
- ❌ **只 pointer 无 lint 强制** — 靠人工守, 必然回退到完整表
- ❌ **只 lint 无 digest** — agent 看不到全貌, 要跳 SSOT yaml (过载)
- ❌ **通用 schema 字段** (如 `doc_presentation`) — YAGNI, 每个事实类型按本模式接入即可,
  无需抽象通用呈现策略字段 (2026-06-29 教训: 架构方案先看已有基础设施覆盖多少)

## 闭环验证

- [ ] 入口文档行数稳定 (无完整表膨胀)
- [ ] `doc-ssot-lint` 扫该 marker 段 0 findings
- [ ] digest 文件可 regenerate (不手编辑)
- [ ] 契约 SSOT 映射表含该事实策略行
- [ ] CI (`make gac-local-gate`) 含该 lint 检测

## 关联

- 契约: [`doc-ssot-contract.md`](doc-ssot-contract.md) (SSOT 正交契约)
- 实例: GaC 规则 (`bin/gac-export-agents.py` + `docs/generated/agent-gac-rules.md`)
- 执行器: `bin/doc-ssot-lint.py` (强制), `bin/gac-export-agents.py` (生成)
- ISA 来源: 架构层面 ISA 分析 (ISC-3 模式文档化, 2026-06-29)
