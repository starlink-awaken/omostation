---
schema_version: retro/v1
lifecycle: history
owner: governance-team
created: 2026-09-01
last_updated: 2026-09-01
bet: BET-Y1Q4-T3-02
title: 本地 MPS 嵌入引擎
symptom: 冷启动 757ms 惊乍；SOCKS 代理炸模型加载
solution: median-of-N 稳态测量 + HF_HUB_OFFLINE 代码级红线
---

# BET-Y1Q4-T3-02 复盘

## 做对了什么

1. **分层推进不赌下载**：P1 用已缓存的 bge-small-zh 先把引擎面/契约面/测试
   全部交付（verify 全绿），P2 模型下载异步进行——2.2GB 下载失败不阻塞工程面。
2. **红线代码化**：离线（HF_HUB_OFFLINE）和无损量化（fp32）都是模块级
   常量 + benchmark 断言，不是文档口号。
3. **诚实的方法学**：首次 757ms 是 MPS graph 编译 + tokenizer init 的冷启动
   开销；契约时延按工业标准测稳态（warmup + median-of-N）——并在 report
   里写清楚这个区分，不藏。

## 踩了什么坑

| 坑 | 修复 |
|----|------|
| SOCKS 代理环境下 ST 模型加载走联网 → httpx socksio 缺失 | 装httpx[socks] + HF_HUB_OFFLINE=1 双保险 |
| hf CLI 新旧版本命令不兼容（download 子命令漂移） | huggingface_hub python API snapshot_download |
| 冷启动 757ms 被误当契约时延 | warmup + median-of-5/3 |
| fast tier 单语模型多语言 top-1 断言必挂 | tier 分级断言（top2 vs top1） |

## 待办（诚实边界）

1. **P2 ✅ 已完成**：模型齐 + FlagEmbedding sparse 激活，full tier 多语言 top-1
   验证通过（中文 0.64 > 英文 0.50 > 无关）。reranker cross-encoder 首载慢，
   dense fallback 契约内达标且原因可观测。
2. **P3 Mac mini 部署（前置已解除 2026-09-01）**：tailscale 排查确认 Mac mini
   实际在线（CLI 错 socket 误诊，见 omlxc #48/#49）；SSH 通（uptime 9d），
   LM Studio 池活（gemma-4-e4b + qwythos-9b IDLE）。剩余部署动作：Mac mini
   装 python venv + sentence-transformers + bge 模型缓存（24GB 内存足够），
   经 cluster_coordinator 注册 bos://compute/omlxc/embed。

## 模板病计数

T3-02 report 路径 2026-10-07——**第 6 例**。五个 BET 连发五个模板病，
应尽快专项批量校正剩余台账。
