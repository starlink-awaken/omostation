# 算力池全面优化 — 2026-08-20

## 摘要

对 omlxc 算力池进行全面审计、修复与优化。系统可用率从 ~75% 提升至 91%。

## 修复清单

### 代码修复 (已合并到 main)

1. **probe reasoning_content bug** (`src/omlxc/adapters/lmstudio.py`)
   - discover probe max_tokens 从 1 改为 100
   - 修复了模型返回思考 token 时 probe 失败的问题
   - commit: 待确认

2. **per-backend probe timeout** (`src/omlxc/config/schema.py` + `composition.py`)
   - 新增 `probe_timeout_seconds` 字段 (默认 10s, 最大 120s)
   - mac-mini 配置为 30s (Tailscale relay 延迟)
   - commit: 8579a63

3. **SSH control channel**
   - MBP: `~/.local/bin/lms` 符号链接 + authorized_keys
   - mac-mini: `~/.local/bin/lms` 符号链接 + authorized_keys
   - 后端配置添加 `control_endpoint` + `known_hosts_file`

### 配置优化

4. **模型双后端 HA**
   - 22 模型全部配置双后端 (omlx-app + LM Studio)
   - 45 placements, 41 可用 (91%)

5. **模型精简**
   - 淘汰 4 个低价值模型: reasoning-lite, qwen-3.5-9b-flash, qwen-3.5-9b-pro, vision-large
   - 新增 2 个高价值模型: deepseek-v4-flash, qwen3.6-35b-a3b

6. **qwen3.8-27b 三变体测评**
   - 基座 mlx: TTFT 507ms, 输出最详细
   - optimized-quality: TTFT 804ms
   - optimized-speed: TTFT 1817ms (最慢)
   - 结论: 保留基座 mlx, 两个 MTP 变体通过同一基座服务

## 节点状态

| 节点 | 状态 | 可用 placement |
|------|------|----------------|
| MBP M5 Max 128G | ✅ healthy | 全部可用 |
| mac-mini M4 24G | ✅ healthy | 全部可用 |
| y7000P RTX 4070 | ❌ offline | 需物理访问 |

## 架构发现

### AetherForge 已有云端兜底

AetherForge 已经具备完整的云端 API 兜底能力:
- **云供应商**: anthropic, openai, gemini, deepseek, azure, bedrock, vertex, ollama
- **路由模式**: local / hybrid / cloud
- **fallback_chain**: `["coding", "reasoning", "mythos-fast"]`
- **复杂度分流**: `complexity_chains` 按任务复杂度路由

因此"云端 API 兜底"不需要在 omlxc 层实现,AetherForge 已经处理。

### omlxc 与 AetherForge 的职责边界

| 关注点 | AetherForge | omlxc |
|--------|-------------|-------|
| 模型标识 | 逻辑别名 | 物理 ID |
| 物理放置 | 不参与 | 全权 |
| 后端选择 | 不参与 | 全权 |
| 云端兜底 | 拥有 | 不涉及 |
| 本地容量 | 不感知 | 全权 |

## 后续建议

### P0 (立刻做)
- y7000P 物理开机
- mac-mini 常驻 2-3 个小模型 (gemma-4-e2b, qwen3-vl-8b)

### P1 (本周)
- 验证 AetherForge hybrid 模式 cloud fallback
- 清理 LM Studio 重复注册 (5 个重复模型, ~60GB)

### P2 (有空)
- 自动模型生命周期
- 可观测性仪表盘
- Ollama 集成扩展

## 测评数据

### qwen3.8-27b TTFT 对比

| 任务 | mlx | quality | speed |
|------|-----|---------|-------|
| 简单中文 | 507ms | 804ms | 1817ms |
| 代码生成 | 451ms | 798ms | 957ms |
| 推理 | 348ms | 758ms | 788ms |
| 长上下文 | 1310ms | 2381ms | 2432ms |

### 系统负载

- 累计路由决策: 339 次
- 累计推理请求: 339 次
- 加载/卸载操作: 21 次
