---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q3-T9-01 specification
bet_id: BET-Y2Q3-T9-01
status: accepted
lifecycle: contract
owner: engineering-agent
last-reviewed: 2026-09-25
---


# BET-Y2Q3-T9-01 Spec — 织星驾驶舱 P2 体验迭代、漂移可观测与真实算力副驾

- spec_version: 1.0.0
- date: 2026-09-25
- track: T9-OBSERV
- workflow: project-code-change

## 背景

织星驾驶舱质量审计（`.omo/_knowledge/ops/zhixing-dashboard-audit.md`，综合评分 248/500）的 P0（5 项）与 P1（8 项）已于 2026-09-24 随 PR #4293/#4294 落地。剩余 P2 体验项、宿主漂移可观测性、以及知行主权副驾的算力接入缺口构成本 BET。

## 范围（In Scope）

1. **P2-5 数据源降级视觉提示**：`current.json` 的 `source_states` 存在 PARTIAL/UNAVAILABLE 源时，dashboard 页面顶部显示可Dismiss的降级横幅，标注降级源数量与最近刷新时间。
2. **P2-11 价值回路五阶段可视化时间线**：value 板块将"信号感知→信号分类→旅程执行→价值记录→进化反馈"五阶段渲染为横向时间线，各阶段挂接真实计数（来自 current.json 已有字段，无则标 UNKNOWN 不造假）。
3. **P2-7 搜索历史**：搜索 overlay 使用 localStorage 记录最近 8 条搜索词，显示"最近搜索"区块，可点击重搜、可清空。
4. **P2-3 暗色 popover 对比度**：修复暗色模式下自定义 popover/tooltip 的背景与文字对比度（WCAG AA 之上，背景提亮一档）。
5. **P2-10 know 与 learnings 差异化**：know（文档知识）板块头增加定位说明"受管文档与知识入口"，learnings（经验结晶）增加"复盘/模式/教训的结构化沉淀"说明，消除内容重叠观感。
6. **漂移检测可观测化**：`bin/gac/zhixing-host-sync.py check` 在漂移时除 stderr 外，向部署目录写结构化 JSON 报告 `host-drift-report.json`（时间戳+逐文件 state/sha/字节数），exit 语义不变；runbook 增补判读说明。
7. **知行副驾真实算力接入**：
   - `live_server.py` 新增只读端点 `GET /api/v1/compute/live`：以 ≤5s 超时调用本地 `omlxc` CLI（status/models），10s TTL 缓存，失败时降级返回 current.json 静态 compute 数据并标注 `live:false`。
   - 新增 `POST /api/v1/compute/infer`：仅绑定 127.0.0.1，调用本机 AetherForge OpenAI 兼容代理（`http://127.0.0.1:9290/v1/chat/completions`），模型白名单来自 omlxc 已加载模型，单次请求 token 上限 2048，速率限制 6 次/分钟/IP，错误时返回结构化错误不抛出栈。
   - 前端副驾抽屉升级：算力页签展示实时端点/模型/显存；新增"本地推理"页签提供最小对话框（系统提示词固定为助手、可查看最近 10 条本轮会话记录、清空按钮）。

## 非目标（Non-Goals）

- 不改动 omlxc daemon 与 AetherForge 服务本体配置。
- 不对 cockpit-ui 本体做改造。
- 副驾推理仅绑定 localhost，不做任何对外暴露；不实现多轮持久化会话（仅本轮内存态）。
- 不重构 template.html 整体布局与导航结构。

## 验收标准（Done When）

- 上述 7 项范围全部落地，dashboard 26 个导航板块页面无 JS 语法错误（`node --check` 全部内联脚本通过）。
- `python3 bin/gac/zhixing-host-sync.py check` exit 0（部署态 = 仓库态）。
- 漂移场景下 `~/.local/share/zhixing-dashboard/host-drift-report.json` 生成且字段完整。
- `curl http://127.0.0.1:43191/api/v1/compute/live` 返回 200 且含 `live` 字段；未鉴权跨源调用 infer 被拒绝。
- PR 合并入 origin/main，launchd 四个任务在线。

## 验证命令

```bash
python3 bin/gac/zhixing-host-sync.py check   # exit 0
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:43191/   # 200
```
