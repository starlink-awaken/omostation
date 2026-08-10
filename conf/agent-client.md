# 把 omlx 端点接进 Agent / 编码客户端

`omlx-serve.sh` 起的是 **OpenAI 兼容** 服务，任何支持「自定义 OpenAI base URL」的客户端都能直连。

## 0. 起服务（用全局 omlx CLI）

```bash
omlx serve coding        # http://127.0.0.1:8080/v1  (默认主力 = devstral)
omlx health coding       # 探活
```

换主力只需一行，客户端配置不动（current 软链由 CLI 管理）：

```bash
omlx use coding qwopus-holo3-op6-mtp   # 例如切到更快的 holo3
omlx use coding devstral-small-2-8bit  # 切回默认
```

## 1. 冒烟测试

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"写个快速排序"}],"temperature":0.1}'
```

## 2. Cline / Continue / Cursor / Zed

| 客户端 | 配置位 | 关键项 |
|--------|--------|--------|
| Cline (VS Code) | API Provider: **OpenAI Compatible** | Base URL `http://127.0.0.1:8080/v1`，API Key 随便填，Model 填真实模型名或 `current` |
| Continue | `~/.continue/config.json` 见下 | `apiBase` 指向端点 |
| Cursor | Settings → Models → OpenAI Base URL | 覆盖为 `http://127.0.0.1:8080/v1` |
| Zed | assistant 设置 openai `api_url` | 同上 |

Continue 示例 (`~/.continue/config.json`)：

```json
{
  "models": [
    {
      "title": "omlx-coding",
      "provider": "openai",
      "model": "current",
      "apiBase": "http://127.0.0.1:8080/v1",
      "apiKey": "local",
      "completionOptions": { "temperature": 0.1, "topP": 0.9 }
    }
  ]
}
```

## 3. 多端口分工（128GB 可同时常驻）

```bash
omlx serve coding         # :8080  默认主力(devstral, 非推理, 393K)
omlx serve coding-fast    # :8081  holo3 MoE, 57.9 tok/s
omlx serve reasoning      # :8083  GLM-4.7 规划/推理
omlx status               # 看谁在跑、占多少内存
# embedding/vision 需先 pip3 install mlx-embeddings mlx-vlm，再用各自 server
```

客户端里把「对话模型」指 8080、「自动补全/快速模型」指 8081、RAG 的 embedding 指 8090，即可一机多模型协同。

## 4. Agent 调参要点

- 工具调用/确定性任务：`temperature` 0.0–0.2。
- 长上下文：服务端开 `--kv-bits 8`（脚本已自动加），否则 262K/393K 上下文的 KV cache 会吃满内存。
- Agent 循环复用同一 system prompt 时，优先选支持 prompt cache 的运行方式，省重复 prefill。
- 重复惩罚别开太重，编码里结构性重复是正常的。
