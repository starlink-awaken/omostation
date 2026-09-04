---
type: ssot
last-reviewed: 2026-08-26
owner: governance-team
---

# LLM 引擎统一接入架构设计 (LLM-ENGINE-ARCHITECTURE)

> 状态: **implemented + 迭代优化 (全量违规归零)** | 作者: Atlas | 日期: 2026-08-05
> 触发: `cockpit research "大蒜能杀菌吗？"` 降级链全挂事故复盘

## 1. 事故复盘

`cockpit research` 输出降级缓存答案，耗时 180.1s：
- L1 minerva CLI (180s 超时) — 依赖 searxng:8080 未运行
- L2 ollama 降级 (立即失败) — 默认模型 qwen3.5:4b 本机不存在
- L3 本地缓存兜底 — 每级失败静默

## 2. 根因分类

- R1 无统一 LLM 接入层（各项目直连 ollama，绕过 AetherForge 网关）
- R2 模型名配置漂移无校验（cockpit/minerva/kos 三处三个值）
- R3 降级链反模式（fallback 不预检、失败不告警、超时硬编码）
- R4 治理红线无执行闸门（AGENTS.md 要求走网关，GaC 无拦截）

## 3. 目标架构: llm-router 统一接入层

```
resolve(model_id) → 存在性校验 → 路由
  ① omlxc 网关 (http://100.96.126.35:4000/v1)   ← Tier 1
  ② ollama 本地 (动态发现模型, 存在性校验)         ← Tier 2
  ③ none (打印原因)
```

原则: 本地推理走网关; 模型名动态发现不硬编码; 每级失败打印原因。

## 4. 落地与迭代成果

| Wave | 内容 | 状态 |
|------|------|------|
| W1 | base.py 动态发现 / research.py searxng 探活 / 降级告警 | ✅ |
| W1+ | opencode.json omlxc triage 注册 / 子代理切 opencode-go-b / deepseek 官方移除 | ✅ |
| W2.1 | llm_router.py (网关→ollama, raw=false, reasoning 兜底, coder-fast 默认) | ✅ |
| W2.2 | research/brain/brain_core 迁移 llm_router; metaos/kos/kronos 硬编码→可配置端点 | ✅ |
| W2.3 | llm_router --list 模型注册表 SSOT | ✅ |
| W3.1 | check-llm-gateway-only.py (纯静态, CI 兼容) + sgf-policy 注册 | ✅ |
| W3+ | 检查器语义精确化: 只拦硬编码调用, 豁免探活/可配置默认值, 多行调用检测 | ✅ |
| W3+ | searxng docker 化; minerva 全管线回归 (Quality 90/100); deepseek 官方→opencode-go | ✅ |

## 5. GaC 规则: CR-LLM-GATEWAY-ONLY

`bin/gac/check-llm-gateway-only.py` — 纯静态源码扫描, 只匹配硬编码推理调用
(httpx/requests/curl/urlopen 内联 11434), 豁免: api/tags 探活、os.environ.get
可配置默认值、注释/日志、多行调用检测。CI (GitHub runner) 无本地 LLM 可运行。

## 6. 遗留

- 独立子模块已完成可配置化; 默认值保留 ollama 开发路径, 运行时可通过
  OLLAMA_ENDPOINT / LLM_GATEWAY_URL 指向网关
- minerva cloud LLM 优先 opencode-go (zen/go 套餐内), 官方 deepseek 仅 fallback
- minerva 多阶段管线 180s: kairon 项目自身优化范畴
