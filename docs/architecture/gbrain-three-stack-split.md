---
status: draft
lifecycle: architecture
owner: governance-team
last-reviewed: 2026-07-07
related:
  - ../../../.omo/_knowledge/decisions/0156-p76-phase2-call-direction.md
  - ../../../.omo/_knowledge/decisions/STRAT-P76-strategic-roadmap.md
  - ../../../.omo/_knowledge/decisions/0155-p76-phase1-cleanup.md
  - ../../../docs/SOP-GOD-MODULE-SPLIT.md
---

# gbrain 三栈拆分架构图 (P76 Phase 2 / ADR-0156)

> **For agentic workers**: 本文档是 DRAFT 状态, 是 P76 Phase 2 设计交付物。
> 实施时间表在 Phase 3 (W6-W11)。

## 0. 当前形态 (2026-07-07 实测)

| 文件 | 行数 | 责任 |
|------|---:|------|
| `core/postgres-engine.ts` | **4514** | Postgres 关系层 + CRUD |
| `core/pglite-engine.ts` | **4509** | PGLite 兼容层 |
| `core/ai/gateway.ts` | 2895 | AI 模型路由 + bos:// 桥 |
| `migrate/migrations-early.ts` | 1341 | Schema 迁移 |
| `core/search/hybrid.ts` | 1302 | 混合检索 |

> 5 个 god module (>1300L) 全在 `gbrain`, SOP 拆分文档见 `docs/SOP-GOD-MODULE-SPLIT.md`。

## 1. 拆分后形态: gbrain-v2 三个仓

```
                    ┌──────────────────────────────────────┐
                    │         BOS URI 入口 (caller)         │
                    │   cockpit / agora / omo / etc.       │
                    └──────────────┬───────────────────────┘
                                   │
                                   ▼
              ┌─────────────────────────────────────────────┐
              │   I0 agora: bos://brain/<verb>/<action>     │
              │   (router — 不直接 import gbrain)            │
              └──────────────┬──────────────────────────────┘
                             │
        ┌────────────────────┼─────────────────────┐
        │                    │                     │
        ▼                    ▼                     ▼
  ┌───────────┐         ┌───────────┐         ┌───────────┐
  │ gbrain-   │         │ gbrain-   │         │ gbrain-   │
  │   core    │◀────────┤  vector   │         │   bos     │
  │ (TypeScript)         │  (Rust)   │         │ (Python)  │
  │         │         │           │         │           │
  │ Postgres │         │ LanceDB   │         │ bos://桥  │
  │ 关系层   │         │ 向量层    │         │ agora复用 │
  └─────┬────┘         └─────┬─────┘         └─────┬─────┘
        │                    │                     │
        └────────────────────┴─────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Phase 3 过渡桥  │
                    │ runtime/I0/     │
                    │ gbrain-bridge   │
                    │ (TypeScript)    │
                    └─────────────────┘
```

## 2. 每个仓的细节

### 2.1 gbrain-core (TypeScript)

**责任**: Postgres 关系层 + 全 CRUD
**当前行数**: 4514 (postgres-engine.ts) + 4509 (pglite-engine.ts) + 1341 (migrations-early.ts)
**目标行数**: 5 个 < 800L 文件

```
gbrain-core/
  src/
    connection/        # pool, lifecycle, 健康检查 (~600L)
    schema/            # tables, enums (~700L)
    query/             # SELECT/INSERT/UPDATE helpers (~500L)
    migration/         # versioned migrations (~700L)
    pglite-shim/       # 兼容层抽象 (~600L)
  test/
```

### 2.2 gbrain-vector (Rust, 性能关键)

**责任**: LanceDB 向量层
**触发条件**: 出现 pgvector 性能瓶颈或跨仓需求

```
gbrain-vector/
  src/
    lib.rs
    lance.rs        # LanceDB binding
    embed.rs        # 嵌入处理
    index.rs        # ANN 索引 (HNSW / IVF)
  Cargo.toml
```

### 2.3 gbrain-bos (Python)

**责任**: bos:// 桥 + agora 复用
**触发条件**: gbrain 仓被外部 (cockpit/omo) 直接 import

```
gbrain-bos/
  src/gbrain_bos/
    server.py        # FastAPI/uvicorn 服务
    bos_resolver.py  # bos://<domain>/.../... 解析
    types.py         # Pydantic models
    __init__.py
  pyproject.toml     # 与 agora 共用 bus-foundation
```

## 3. 迁移路径 (Phase 3 / W6-W11)

| Step | 行动 | 依赖 | 风险 |
|------|------|------|:---:|
| M-0 | gbrain-core 内部拆分 (SOP Phase 1) | SOP 文档 | 🟡 |
| M-1 | 注册 `bos://brain/*` 到 `bos-services.yaml` | (I0) | 🟢 |
| M-2 | gbrain-bos Python 服 — `bos://brain/embed/invoke` | M-1 | 🟡 |
| M-3 | runtime/omo 切到 `bos://brain/*` 路由 | M-2 | 🟠 |
| M-4 | gbrain-core 拆分 5 文件 (SOP Phase 1+2) | M-0 | 🟡 |
| M-5 | gbrain-vector Rust 独立仓 | M-4 | 🟠 |
| M-6 | 旧 `gbrain/` 仓退役 + redirect | M-5 | 🟠 |

## 4. 拆分对架构契约的影响

| 维度 | 拆分前 | 拆分后 |
|------|--------|--------|
| **L2 引擎小环** | ⚠️ runtime ↔ gbrain ↔ aetherforge 形成小环 | ✅ gbrain 经 I0 暴露, runtime 走 BOS |
| **god module** | 7 个 >1500L | ≤5 个, 后逐步降 |
| **BOS 域** | brain 域未注册 | `bos://brain/{embed,retrieve,rewrite}/<verb>` |
| **跨仓依赖** | gbrain 直接被 runtime/omo import | 全部走 BOS URI (P76-2-3 原则) |
| **I0 织层压力** | ↘ agora 不感知 | ↗ agora 多 3-5 个 brain 服务路由 |

## 5. 拆分对 governance 指标的影响

| 指标 | 拆分前 | 拆分后 (目标) |
|------|:---:|:---:|
| god module 文件数 | 7 | ≤2 |
| 跨 L2 直接 import 数 | ~5-8 | 0 |
| `LAYER-CALL-DIRECTION` violations | **9** | **0** |
| BOS URI 服务数 | 114 | +5 (brain/*) |
| gbrain 仓 PR lag | — | 降 (拆仓并行开发) |

## 6. 风险评估

| 风险 | 缓解 |
|------|------|
| 拆仓跨仓 PR 摩擦 | 沿用现有 per-session worktree + PR 流程 |
| Python ↔ TS bridge 序列化成本 | 用 msgpack/pickle 直通 (H1 数 ms) |
| Rust 编译 vs TS 部署 | gbrain-vector 拆为独立 docker image |
| 旧仓 redirect 兼容期 | 双仓共存 6 个月 + README 指向 |

## 7. 不在本设计范围

- ❌ TypeScript → Rust 整体迁移 (与反向警示 #1 冲突)
- ❌ 完全替换 Postgres + LanceDB (与项目稳定性目标冲突)
- ❌ 一周内完成 (与分层节奏冲突 — 至少 6 周)

## 8. 关联

- ADR-0156 (P76 Phase 2 收口) — 本设计的承载 ADR
- SOP-GOD-MODULE-SPLIT — Phase 2 拆分执行方法
- 项目-registry `projects:` 段 — gbrain 元数据
- `bin/check-layer-call-direction.py` — 守门工具

---

*最后更新: 2026-07-07 · P76 Phase 2 / DRAFT · 待 Phase 3 实施*
