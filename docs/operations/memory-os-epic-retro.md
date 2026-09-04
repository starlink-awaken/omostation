---
lifecycle: history
owner: engineering-team
last_updated: 2026-08-05
related:
  - ../../.omo/_knowledge/decisions/0372-memory-os-control-plane.md
  - ../../.omo/_truth/registry/memory-os.yaml
  - ../../.omo/standards/memory-os-ops.md
  - ../architecture/memory-os.md
  - ./memory-os-phase8-closeout.md
  - ./memory-os-adapter-audit.md
title: Memory OS 史诗复盘（ADR-0372 · Phase 0–8 + 收口）
type: doc
---

# Memory OS 史诗复盘（ADR-0372 · Phase 0–8 + 收口）

> **时间窗**: 2026-08-04 → 08-05  
> **状态**: `memory-os.yaml` **phase8 · done**；主仓 PR **#959 / #970 / #974 / #978 / #980** 已合  
> **一句话**: 把「多套记忆基质」收成 **统一控制面 + 可门控图写读 + 三端入口**，并坚持**诚实生产路径**（无 `NEO4J_URI` 不装生产）。

## 1. 问题

eCOS 不缺记忆（Vault / KOS / gbrain / cards / inbox / OMO），缺的是：

1. 无统一控制面（Agent 自选 backend）
2. 双轨 Raw/Theta 声明与执行鸿沟
3. 巩固（dream）未产品化为 workspace 级入口
4. `bos://brain/events/*` 越域债
5. 市面产品替换主存会破坏审计与分层

**ADR-0372**: 建 **MOS 控制面**（编排 + 契约 + 适配器边界），**不**替换 Vault/KOS/gbrain 主存。

## 2. 架构终态

```text
Agent / Skill
  ├─ cockpit memory …
  ├─ /api/memory/* · /memory
  └─ bos://memory/mos/*
         ↓
    packages/mos (L2)
 write|recall|status|forget|consolidate|knowledge-ref
         ↓
   Raw (audit)  +  Theta (search)  +  Neo4j FACT (NEO4J_URI 门控)
```

| URI | 角色 |
|-----|------|
| write / recall / status | 核心 |
| forget / consolidate | 遗忘 / 巩固编排 |
| knowledge-ref | ADR-0315 引用元数据 |

门控：无 `NEO4J_URI` → TemporalShadow；不宣称 graphiti-core/Mem0 生产闭环。

## 3. 阶段与 PR

| 阶段 | 主题 | PR |
|------|------|-----|
| P0–P6 | 控制面 + Neo4j 写 + RBAC + `/memory` 面板 | #959 |
| P7 | Neo4j recall + `memory-os-neo4j-up.sh` | #970 |
| P8 | env 注入 / 端口 / surface check / ops 契约 | #974 |
| 接线 | CLI + BOS knowledge-ref + Agora MCP env | #978 |
| 文档 | BOS 表 / retro supersede / kairon README | #980 |

## 4. 交付物

- **包**: `projects/knowledge/kairon/packages/mos`
- **入口**: cockpit CLI/HTTP/UI · Agora `bos://memory/mos/*`
- **运维**: `bin/memory-os-env.sh` · `bin/memory-os-neo4j-up.sh` · `make memory-os-*`
- **SSOT**: `memory-os.yaml` · `memory-rbac.yaml` · `memory-os-ops.md` · port 7474/7687
- **skill**: `memory-recall`

## 5. 教训（可固化）

1. 声明 ≠ 执行：`NEO4J_URI` 门控 + status 可观测字段
2. 子模块指针对齐后必须 **checkout** 工作树
3. 入口要三端齐（CLI / HTTP / MCP），仅有 BOS 不够
4. 历史 phase retro「未做」需 supersede 注脚
5. Docker 不可用时 brew fallback 写进脚本
6. env 加载：进程 > 本机 config > cockpit .env > example（后写不得覆盖前写非空；**本机 config 必须能覆盖 example**）

## 6. 诚实边界

- graphiti-core / Mem0 非生产闭环
- 图 as_of 双时态未做
- OMO raw 生产落盘未完整
- `config/memory-os.env` 不进仓

## 7. 推荐后续（执行跟踪）

| 优先级 | 项 | 跟踪 |
|--------|-----|------|
| P0 | 本机 env 覆盖 example + dashboard 默认可连 | Phase 9 follow-up |
| P1 | 事件 producer 规范 memory 域 + SOP 对齐 dual-accept | Phase 9 follow-up |
| P1 | consolidate 指标跨进程可观测 | Phase 9 follow-up（FileStore 持久化） |
| P2 | live KOS/gbrain 写路径 | **Phase 10** — `MOS_LIVE_KOS` / `MOS_LIVE_GBRAIN` / `MOS_LIVE_GBRAIN_WRITE` |
| P2 | as_of bi-temporal | **Phase 10** — Neo4j + temporal `as_of`；CLI `--as-of` |
| P3 | Graphiti/Mem0 真接或正式 deprecate | backlog |

## 8. 冷启动与帮助

```bash
git submodule update --init projects/knowledge/kairon projects/cockpit projects/agora
cp docs/operations/memory-os.env.example config/memory-os.env
source bin/memory-os-env.sh
bash bin/memory-os-neo4j-up.sh
make memory-os-check
cockpit memory                 # 用法帮助 + status 摘要
cockpit memory status --json
cockpit memory recall --help   # 含 --as-of
cockpit bos resolve bos://memory/mos/status
```

| 文档 | 路径 |
|------|------|
| 架构导航 | `docs/architecture/memory-os.md` |
| 运维契约 | `.omo/standards/memory-os-ops.md` |
| 本机 Neo4j | `docs/operations/memory-os-neo4j-local.md` |
| Phase 10 复盘 | `docs/operations/memory-os-phase10-retro.md` |
| Agent skill | `.agents/skills/memory-recall/SKILL.md` |
| 包 README | `projects/knowledge/kairon/packages/mos/README.md` |
| 机器 SSOT | `.omo/_truth/registry/memory-os.yaml` |

权威入口：ADR-0372 · `memory-os.yaml` · `memory-os-ops.md` · `docs/architecture/memory-os.md`。
