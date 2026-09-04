---
type: ssot
---

# 真实场景 — Y1Q4 B1 知识流动最小闭环端到端

> 链路：`cockpit research "主题" → vault → knowledge search <800ms → daily 7日留存`

## 场景
用户输入"AI算力织网"，系统完成：
1. `cockpit research "AI算力织网"` 深度研究
2. 入 `vault` 本地最快检索
3. `knowledge search` 跨源聚合 <800ms
4. 生成 `daily` 并 7 日留存可查

## 验证
- `uv run pytest scenarios/Y1Q4-B1/test_e2e.py -q`
- 断言：`search latency <800ms` + `daily` 存在
