# OpenSpec: Fast-Track Task Compaction

## 1. 概念与目标 (Why)
Fast-Track (Mode B) 会产生大量微观任务，这会导致系统严重碎片化。通过周期性的合并，将微观变更总结为长周期的周报，同时清理垃圾数据。

## 2. 任务列表 (What)
- [ ] P0-W0-C2G-FAST-COMPACTION: 编写 omo_gc 的增强逻辑，每月或每周聚合 `FAST-*` closed 任务，生成 Markdown 周报，随后将原始 yaml 归档。
