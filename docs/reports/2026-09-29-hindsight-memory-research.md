---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-29
type: ephemeral
created: 2026-09-29
---

# Hindsight 记忆系统调研报告 — 2026-09-29

- schema: research-report/v1
- 调研会话: lib-1 (外部资料核验) + exp-10 (workspace 记忆栈摸底), 均于 2026-09-29 完成
- 交付 run: `20260929T113834Z-governance-state-mutation-2ec5faa6`
- 结论先行: **不替换、不直连**; 可做 MIT 许可下的 stub adapter PoC 占位 (本交付已在 memory-os registry 落位)

## 1. 背景

文章把 vectorize-io/hindsight (AI 记忆系统) 描述为 31.3K★ 并对标本仓记忆栈, 需核验其
真实性、许可、与 omostation (MOS + KOS + gbrain + cards + inbox) 的适配关系。

## 2. 事实核查表

| 声称 | 核验结果 | 来源 / 时间 |
|---|---|---|
| GitHub 31.3K★ | **41,924★** (文章过时) | GitHub API, 2026-09-29 |
| 版本 | v0.10.2 (2026-09-29 发布); 71 contributors; 146 open issues (31 条 Hermes 集成) | GitHub, 2026-09-29 |
| 论文指标 91.4% | **arXiv 2512.12818 报告 91.4%** (TEMP 基准) | 论文正文 |
| 94.6% (常被引用) | 厂商自测 (v0.4.19), **不在论文内**, 非同行评审 | 论文 + 厂商 whitepaper 对读 |
| VT / 华盛顿邮报"复现" | 二者是**论文合著方**, 非独立复现 | 论文作者列 |
| TEMP R 四路检索 | **属实**: semantic + BM25 + graph BFS + temporal → RRF → cross-encoder | 代码 + 论文 |
| 四层记忆 | 论文口径: world / experience / opinion / observation; **Mental Model / Mission / Directives 是产品文档概念, 非论文口径** (易被混引) | 论文 vs 产品文档 |
| 许可 | **MIT** — 商用自托管干净 | 仓 LICENSE |
| 镜像体积 9GB / 500MB | ⚠️ **未验证** (GHCR 拉取需鉴权) | 二手来源 |
| 安全 | MCP endpoint + memory Postgres **默认无鉴权** | 上游文档 |
| 稳定性 | pre-1.0: retain/reflect 已知正确性 bug (unit-id 丢失 / 二次方减速 / skip 死循环) | 上游 issues |

## 3. 竞品坐标

- mem0 (66K★) — 最直接对手, 本仓已有 `stub_optional` 适配先例
- Zep / Graphiti — 时间图谱路线, 本仓 `optional_tier2`
- Letta / LangMem — agent 内存框架路线
- 本仓等价栈已存在: MOS 控制面 (ADR-0372) + KOS (12,553 文档, LanceDB Qwen3-Embedding-8B, `data/kos/kos-index.sqlite`) + gbrain (唯一合法 consolidate 引擎) + cards (`data/cards/cards.db`) + inbox; 四路召回含 FTS5 / vector / graph / **temporal as_of**; scope ACL+RBAC。本仓无 32KiT 限制, 反而更强。

## 4. 结论与红线

**定位**: Hindsight 是"检索更花哨的同构品", 不带本仓缺失的能力; 仅在自托管、MIT 干净的前提下
作为 PoC 候选观察对象。

**本交付落位**: `.omo/_truth/registry/memory-os.yaml` adapters 增设 `hindsight` stub
(`status: stub_optional`, `default: false`, `production_ready: false`) — 占位而非接入。

**未来若推进 PoC, 红线 (全部来自既有 SSOT)**:
1. 禁止裸 MCP 直连, 必须走 `bos://memory/mos/*` (ARCHITECTURE.md:103, `check-memory-os-surfaces.py` 守卫)
2. 远端 Postgres 须过 external-connection-fabric + 端口登记 (protocols/port-registry.yaml)
3. 不引入第二个 consolidate 引擎 (gbrain 唯一)
4. `forget` 必须全总线扇出, 不得只删单库
5. 其 `code_structure` / `task_debt` 结果永不与机构笔记后端 RRF 合并 (registry intent_routes 既有 note)

**顺带发现 (独立修复候选, 优先级更高)**: `kos/mcp/server.py:617` 语义路径静默回退 FTS5 —
语义召回可能一直没生效, 与 Hindsight 无关但影响本仓召回质量。

## 5. 出处

- github.com/vectorize-io/hindsight (API + issues + LICENSE, 2026-09-29)
- arXiv:2512.12818 (Hindsight 论文)
- 厂商 whitepaper / 文档 (94.6% 与产品四层口径来源)
- 本仓: `.omo/_truth/registry/memory-os.yaml`, `docs/architecture/memory-os.md`,
  `.agents/skills/memory-recall/SKILL.md`, `.agents/skills/kos-cold-start/SKILL.md`,
  ARCHITECTURE.md:103, `kos/mcp/server.py:617`
