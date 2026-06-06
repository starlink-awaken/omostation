> [!WARNING]
> **DEPRECATED**: 本文档描述的 4+1+3 架构或旧版 eCOS 映射已过时。请参考最新的 **eCOS v5.0 (5+3+1)** 宪法大纲：`~/Documents/学习进化/2-knowledge/基建架构/phase6-完成化/pat-45-eCOS-v5-architecture.md`。


# 4+1+3 架构图

> 系统架构 Mermaid 图，展示 P0/L4/L3/L2/L1 + X1/X2/X3 跨层关系。

```mermaid
graph TB
    subgraph P0["P0 产品交互层"]
        HW["hermes-webui :8787<br>WebSocket, ~20 tools"]
        PL["pallas<br>7 CLI commands"]
        GS["gstack<br>10 orchestrators"]
        BSK["bos-skill-cli<br>Skill TUI"]
    end

    subgraph L4["L4 自我层"]
        KS["KOS self<br>roles/vision/cognitive"]
        MC["metacog<br>Cognitive KB"]
    end

    subgraph L3["L3 协作层"]
        KC["KOS collab<br>TaskObject CRUD"]
        PLK["phase-lock<br>EG5"]
        PTR["PipelineTracer<br>Execution tracing"]
    end

    subgraph L2["L2 能力层"]
        AM["agentmesh<br>22 MCP tools"]
        OD["ontoderive<br>21 CLI + 5 MCP"]
        MN["minerva<br>L0-L4 research"]
        SP["sophia<br>12-state compiler"]
        FG["Forge<br>111 tools, 5 MCP"]
        GB["gbrain<br>74 MCP ops"]
        KR["kronos<br>ETL pipeline"]
        IR["Iris<br>7 MCP tools"]
        CA["codeanalyze<br>CLI"]
        MO["MetaOS<br>39 tests"]
    end

    subgraph L1["L1 契约层"]
        ED["eidos<br>Schema + 5 MCP"]
        SS["SSOT<br>5 MCP tools"]
        PJ["pipeline:json<br>v1.1"]
    end

    subgraph X1["X1 治理"]
        AR["arcnode<br>17 constraints"]
        CI["CI<br>pre-commit + Actions"]
        DB["dashboard<br>42 constraints"]
        AG["Agora<br>27 MCP + degrade"]
        SEC["Security<br>fail-closed"]
    end

    subgraph X2["X2 抗熵"]
        FX["freshness cron"]
        BK["backup cron<br>43 files"]
        ZA["zombie audit<br>archived"]
    end

    subgraph X3["X3 价值堆栈"]
        CS["KOS consensus<br>L1/L2/L3"]
        TZ["PipelineTracer"]
        PC["provenance_chain<br>traceability"]
    end

    P0 --> L4
    L4 --> L3
    L3 --> L2
    L2 --> L1
    X1 -.-> P0
    X1 -.-> L4
    X1 -.-> L3
    X1 -.-> L2
    X1 -.-> L1
    X2 -.-> X3
```

## 层说明

| 层 | 名称 | 作用 | 项目数 |
|----|------|------|:------:|
| **P0** | 产品交互层 | 用户与系统交互的所有入口 | 4 |
| **L4** | 自我层 | 系统的身份、愿景、认知框架 | 2 |
| **L3** | 协作层 | 多 Agent 协作、任务分解、共享工作平面 | 3 |
| **L2** | 能力层 | 系统拥有的能力和工具（最厚的层） | 10 |
| **L1** | 契约层 | 数据格式、Schema、协议 | 3 |
| **X1** | 治理 | 约束、规则、审计、安全 | 5 |
| **X2** | 抗熵 | 保鲜、复盘、回收 | 3 |
| **X3** | 价值堆栈 | 共识、追溯、半衰期 | 3 |

## 跨层关系

- 实线 `-->` : 上层消费下层能力（P0 → L4 → L3 → L2 → L1）
- 虚线 `-.->` : X1 治理约束所有 P0/L 层
- 虚线 `X2 -.-> X3` : 抗熵保障价值堆栈的持续积累

> 参考: [4+1+3 架构全映射](../summaries/4-plus-1-plus-3-architecture-mapping.md)
