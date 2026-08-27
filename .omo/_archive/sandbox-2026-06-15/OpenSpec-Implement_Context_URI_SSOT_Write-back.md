# OpenSpec: Context URI SSOT Write-back

## 1. 概念与目标 (Why)
闭环 C2G v2。当 OMO 任务最终被关闭时，顺着 `context_uri` 将执行阶段的设计变更反哺到最初的 OpenSpec 或设计文档中。

## 2. 任务列表 (What)
- [ ] P0-W0-C2G-SSOT-WRITEBACK: 在 `omo worker reclaim` 或 `mof-extract` 中植入钩子，解析 `context_uri`，将结果追加到原始 Markdown 文档底部。
