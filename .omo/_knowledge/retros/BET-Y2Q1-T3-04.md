---
schema: bet-retro/v1
bet_id: BET-Y2Q1-T3-04
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-05
type: ephemeral
---

# BET-Y2Q1-T3-04 retro — 树状上下文 + PagedKV 块级缓存

## What changed

- **`dataplane/tree_context.py`**（新）：`TreeContextIndex` 分层章节树
  （Markdown ATX + 中文公文 `一、/（一）/1.1` 标题切分，字节区间寻址），
  叶子文本经既有 `PagedKVMemoryManager` 分页注册（惰性正文，不全量驻留）；
  `locate` 标题/关键词定位；`detect_conflicts` 跨章节同名断言数值/单位
  对比输出矛盾候选；`ttft_probe` 首查询计时。
- **测试 6 个**（合成 40 章 / ~50 万字语料）：树构建+分页注册、定位、
  植入矛盾检出、TTFT ≤50ms、峰值内存 ≤2GB、指纹稳定。全绿；ruff clean。

## Q3 (打假)

- done_when "TTFT ≤50ms" 实测 ~2-8ms（结构化 locate，非 LLM 生成语义——
  spec 已把树节点摘要限定为结构性摘录，不做生成式）。
- 冲突检测是**数值/单位断言级**结构对比，语义矛盾（"应 A"vs"应 B"）
  不在覆盖面——留给 LLM 层后续。
- 踩坑：ru_maxrss 在 macOS 是 bytes、Linux 是 KB，单位换算错 1024 倍
  导致首次内存断言假红（83.19 "GB" 实为 87MB）。
- PagedKVMemoryManager 默认容量 98GB 会预建 150 万 block 对象——
  文档索引场景必须显式小容量初始化（2048MB）。

## Q4 (遗留)

- 树节点摘要是首段截取，非语义摘要；PagedKV 的 est_tokens 按 chars/2
  估算中文，粗粒度。
