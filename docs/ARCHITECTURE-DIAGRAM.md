# eCOS v6 架构全景图

> 基于 5+4+1+1 架构模型 · 2026-06-16 · Phase 42
>
> 配套文档：
> - [PANORAMA.md](./PANORAMA.md) — 系统全景文字描述
> - [LAYER-INDEX.md](../LAYER-INDEX.md) — 项目分层索引
> - [I0-AGORA-CALLCHAIN.md](./I0-AGORA-CALLCHAIN.md) — I0 层调用链
> - [ARCHITECTURE-EVOLUTION.md](./ARCHITECTURE-EVOLUTION.md) — 架构演进对比

---

## 1. 5+4+1+1 拓扑总图

```mermaid
graph TB
    subgraph X["X1-X4 治理维 (横切)"]
        X1[X1 审计链]
        X2[X2 抗熵]
        X3[X3 价值栈]
        X4[X4 一致性]
    end

    subgraph M0["M0 横切框架"]
        MD[model-driven<br/>7阶段生命周期引擎]
    end

    subgraph L4["L4 自我层"]
        DASH["@驾驶舱<br/>24域 · CARDS · DASHBOARD v6.4"]
        L4K[l4-kernel<br/>43 MCP tools :7455]
    end

    subgraph L3["L3 入口层"]
        COCKPIT[cockpit CLI<br/>25+ 子命令]
        DASHBOARD[agora-dashboard<br/>Next.js Web]
        HTTP[cockpit HTTP<br/>FastAPI :8090]
    end

    subgraph I0["I0 织层"]
        AGORA[agora MCP Mesh<br/>42+ tools · SSE :7431]
        BOSRouter[BOSRouter<br/>Trie 前缀匹配]
        PROXY[ProxyManager<br/>限流/熔断/缓存]
    end

    subgraph L2["L2 引擎面"]
        OMO[omo<br/>治理/债务/Phase]
        META[metaos<br/>决策/免疫/路由]
        KAI[kairon<br/>19+ 包 · 知识引擎]
        GBR[gbrain<br/>TS 知识脑 · 67 MCP]
    end

    subgraph L1["L1 运行时"]
        RUNTIME[runtime<br/>Matrix/Scheduler/KEI沙箱]
        KEI[KEI Sandbox]
    end

    subgraph L0["L0 协议层"]
        ECOS[ecos<br/>SSB签名链/MOF元模型]
        MOF[M1 984 YAML / M2 45 schema]
    end

    USER((人类/Agent)) --> COCKPIT
    USER -.->|SSE| AGORA
    COCKPIT --> HTTP
    COCKPIT -.->|bos://| AGORA
    DASHBOARD --> HTTP
    HTTP -.->|bos://| AGORA

    AGORA --> BOSRouter
    AGORA --> PROXY
    BOSRouter -->|memory| KAI
    BOSRouter -->|governance| OMO
    BOSRouter -->|governance| META
    BOSRouter -->|analysis| KAI
    BOSRouter -->|persona| GBR
    BOSRouter -->|capability| RUNTIME
    BOSRouter -->|ecos/agora| ECOS

    PROXY -.->|MCP代理| L4K
    PROXY -.->|MCP代理| RUNTIME
    PROXY -.->|MCP代理| COCKPIT

    OMO --> ECOS
    META --> ECOS
    KAI --> GBR
    KAI --> ECOS
    RUNTIME --> KEI
    RUNTIME --> ECOS
    L4K --> DASH

    MD -.->|模型驱动| ECOS
    MD -.->|模型驱动| AGORA
    MD -.->|模型驱动| COCKPIT
    MD -.->|模型驱动| L4K

    X1 -.->|审计| AGORA
    X2 -.->|保鲜| OMO
    X3 -.->|成本控制| META
    X4 -.->|一致性| ECOS
```

---

## 2. BOS URI 命名空间路由图

```mermaid
graph LR
    AGORA[agora :7431<br/>BOS URI 网关]

    subgraph MEMORY["bos://memory/"]
        KOS[kos/search<br/>kos/ingest<br/>kos/schema]
        KRONOS[kronos/ingest<br/>kronos/scan]
        VAULT[vault/search]
    end

    subgraph GOV["bos://governance/"]
        OMOST[omo/state<br/>omo/debt<br/>omo/audit]
        METAS[metaos/decide<br/>metaos/immune<br/>metaos/route]
        EIDOS[eidos/validate]
        PROTO[protocols-layer/trigger]
    end

    subgraph ANALYSIS["bos://analysis/"]
        MIN[minerva/research<br/>minerva/ask<br/>minerva/summarize]
        ONTO[ontoderive/derive<br/>ontoderive/validate<br/>ontoderive/explain]
        CODE[codeanalyze/scan<br/>codeanalyze/analyze<br/>codeanalyze/metrics]
        IRIS[iris/discover<br/>iris/scan<br/>iris/recall]
    end

    subgraph PERSONA["bos://persona/"]
        CM[core-models/schema<br/>core-models/validate]
        SB[sharedbrain-bridge/recall<br/>sharedbrain-bridge/sync]
        HP[health-profile/query<br/>health-profile/update]
    end

    subgraph CAP["bos://capability/"]
        AR[agent-runtime/execute<br/>agent-runtime/status]
        FORGE[forge/registry<br/>forge/publish<br/>forge/lint]
    end

    AGORA --> MEMORY
    AGORA --> GOV
    AGORA --> ANALYSIS
    AGORA --> PERSONA
    AGORA --> CAP
```

---

## 3. `workspace iterate` 用户旅程

```mermaid
sequenceDiagram
    participant U as 人类
    participant C as cockpit CLI
    participant A as agora :7431
    participant L4 as l4-kernel
    participant L2 as omo/metaos
    participant L1 as runtime/KEI
    participant L0 as ecos/MOF

    U->>C: workspace iterate "宏大构想"
    C->>L4: V2P 意图降维
    L4->>L1: 生成 Pitch.md (L1 沙箱)
    C->>A: C2G 门禁下注
    A->>L2: omo + metaos 治理扫描
    L2->>L0: eidos 律法校验
    L0-->>L2: 合规/违规
    L2-->>A: 门禁结果
    A->>L2: BMAD 全知铺展 (kairon)
    L2->>L1: OSC 约束设计
    L1->>L1: GSD 执行 / TTY 退让
    L1->>L0: OPC 基线体检
    L0-->>L1: 通过/失败
    L1->>L4: SWR 回写 SSOT
    C-->>U: 结果报告
```

---

## 4. 入口收敛后拓扑

```mermaid
graph LR
    subgraph Entry["唯一入口"]
        CLI[cockpit CLI]
        SSE[agora MCP SSE :7431]
        WEB[cockpit HTTP :8090]
    end

    CLI -->|subprocess| AGORA[agora I0 织层]
    SSE -->|SSE| AGORA
    WEB -->|FastAPI| AGORA

    AGORA --> L4[l4-kernel<br/>bos://l4-kernel/domains]
    AGORA --> L3[cockpit MCP<br/>bos://cockpit/context]
    AGORA --> L2[kairon/omo/metaos/gbrain]
    AGORA --> L1[runtime<br/>bos://runtime/health]
    AGORA --> L0[ecos/MOF]

    style Entry fill:#e1f5e1
```

> 已下线入口：cockpit MCP stdio、l4-kernel MCP stdio、runtime MCP stdio。

---

## 5. 分层职责速查

| 层 | 项目 | 端口 | 核心能力 |
|:--:|:--|:--:|:--|
| L4 | `l4-kernel` + `@驾驶舱` | :7455 | 24 域注册表、CARDS、KEMS 健康 |
| L3 | `cockpit` / `agora-dashboard` | :8090 | CLI/MCP/Web 入口 |
| I0 | `agora` | :7431 | BOS URI 路由、限流熔断、MCP 代理 |
| L2 | `kairon` / `gbrain` / `omo` / `metaos` | — | 知识引擎、记忆脑、治理、编排 |
| L1 | `runtime` | — | Matrix 调度、KEI 沙箱 |
| L0 | `ecos` | — | SSB 签名链、MOF 元模型 |
| M0 | `model-driven` | — | 7 阶段生命周期引擎 |
| X1-X4 | `.omo/standards/` | — | 审计、抗熵、价值、一致性 |
