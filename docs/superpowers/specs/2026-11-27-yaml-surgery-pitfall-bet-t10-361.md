---
schema: md/v1
schema_version: specification/v1
bet_id: BET-Y2Q4-T10-361
spec_version: 1.0.0
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-27
accepted: "2026-11-27 Principal 会话「继续」—— T360 收官日两起实战教训, 当日立条防失真"
title: 大 YAML 手术纪律 + 已修复三连闸 pitfall 立条
created: 2026-11-27
---

# BET-Y2Q4-T10-361: 大 YAML 手术纪律 + 已修复三连闸

## 背景与问题

2026-11-27 T360 收官日两起实战事故:
1. python 写回事故把 T360 digest 前缀拼进全台账 **466 处** binding
   (135 长度非法 hex), CI 三红; 修矩阵时 `yaml.safe_dump` 全文件重排
   5042+/7451-, `git diff --stat` 识破秒回滚。
2. waiver frontmatter 修复版改完没提交, CI 依旧红, 白挖一轮根因。

## 方案

1. pitfalls.md 立两条: 「大 YAML 局部手术禁文本 replace 与 safe_dump
   全文件」+「已修复三连闸 (status/diff/head SHA)」。
2. AGENTS §7 判据簇覆盖列追加两短语。

## 验收标准

1. 两条 pitfall 在档 (rg 「大 YAML 局部手术」「已修复三连闸」命中)。
2. 台账 YAML 解析通过; T361 条目 digest 格式合法 (sha256:64hex)。
3. 全台账 digest 全表扫描零非法 (手术纪律自我践行)。

## 非目标

- 不动 T360 及此前任何已 merge 条目内容 (只追加新条目)。

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | 立条时机 | 当日 | 教训 <12h; 隔夜细节失真 (T360 spec 先例) |
| 2 | 两条合一 BET | 合一 | 同日同战役同文件面, 拆分徒增治理开销 |
