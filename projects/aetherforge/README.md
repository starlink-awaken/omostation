# AetherForge — 以太锻造炉

> 算力网格 · LLM 网关 · 群体智能引擎 · 三位一体

AetherForge 融合三个核心包为一个统一的技术栈：

```
                    ┌──────────────────────────┐
                    │     Agent 智能应用         │
                    └──────────┬───────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
        ┌─────┴─────┐  ┌──────┴──────┐  ┌─────┴──────┐
        │   swarm   │  │   gateway   │  │    mesh    │
        │ 群体智能   │  │ LLM Provider │  │  算力网格   │
        │ 编排/拍卖/  │  │ 6 Provider   │  │ 拓扑/资源池/ │
        │ 生命周期   │  │ 调度/熔断    │  │ Worker管理  │
        └───────────┘  └─────────────┘  └────────────┘
                               │
                    ┌──────────┴──────────┐
                    │   eCOS L0 MOF 治理   │
                    └─────────────────────┘
```

## 三包速览

| 包 | 来源 | 定位 | 成熟度 |
|:---|:-----|:-----|:------:|
| **aetherforge-gateway** | llm-gateway | LLM Provider 抽象 — 6个Provider实现 + 调度 + 熔断 | ✅ ~90% |
| **aetherforge-swarm** | swarm-engine | 多智能体任务编排 — 拍卖/DAG/生命周期/经济账本 | ✅ ~80% |
| **aetherforge-mesh** | compute-mesh | 算力基础设施 — 拓扑发现/资源池/Worker管理 | 🚧 ~15% |

## CLI

```bash
aetherforge gateway list              # 列出模型
aetherforge gateway generate "你好"    # LLM 生成
aetherforge swarm auction-status      # 拍卖市场状态
aetherforge mesh status               # 算力节点状态
aetherforge mesh topology scan        # 拓扑发现
```

## 许可证

MIT
