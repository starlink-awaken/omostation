# 03 — API 网关选型与部署

> 核心问题：用 One-API / LiteLLM / 9Router 还是别的？放哪台机器？
> 更新日期：2026-05-20

---

## 一、需求分析

| 需求 | 说明 |
|------|------|
| 统一接口 | 多个厂商的 API Key 整合为单一 OpenAI 兼容端点 |
| 代理分离 | 国内厂商（DeepSeek/GLM/Kimi/MiniMax）直连，海外走代理 |
| 模型路由 | 按场景分配不同模型，失败自动 Fallback |
| 资源占用 | 在 Mac mini 24GB 上运行时尽量轻量（剩余 RAM 留给 Ollama） |
| 多设备 Token | MBP、Hermes、实验项目各自独立 Key，可限额度 |
| 本地部署 | 不自建 SaaS，不走外部网关 |

## 二、候选方案对比

### 2.1 方案一览

| 方案 | 语言 | 镜像大小 | RAM 需求 | Stars | 国内适配 |
|------|------|---------|---------|-------|---------|
| **New API** ⭐ | Go | ~30MB | 128-512MB | 34.7k | ✅ 原生中文 |
| One-API (原版) | Go | ~30MB | 128-512MB | 34k | ✅ 但已停更 |
| LiteLLM | Python | ~1.5GB | 4-8GB | 47.8k | ⚠️ 英文为主 |
| 9Router | Node.js | ~200MB | 512MB | 13.2k | ⚠️ |
| Bifrost | Go | ~50MB | 256MB | 5.1k | ❌ 太新 |
| Kong AI Gateway | Lua/C | ~300MB | 1-2GB | 40k+ | ❌ 大材小用 |

### 2.2 关键维度详细对比

#### 代理支持（国内最关键）

| 方案 | 机制 | 评分 |
|------|------|------|
| **New API** | `RELAY_PROXY=http://127.0.0.1:7890` 环境变量，**仅对海外渠道生效**，国内厂商直连 | ⭐⭐⭐⭐⭐ |
| LiteLLM | `HTTP_PROXY` 系统环境变量，所有流量都走代理，需额外配置排除国内厂商 | ⭐⭐⭐ |
| 9Router | `HTTP_PROXY` 环境变量，类似 LiteLLM | ⭐⭐⭐ |
| Bifrost | 无显式代理变量，需 Docker 网络层配置 | ⭐⭐ |

> ✅ **New API 的 RELAY_PROXY 是最优雅的方案**：只需设置一次，仅海外渠道走代理，国内厂商不受影响。

#### 模型路由与 Fallback

| 方案 | 加权路由 | 失败自动重试 | 模型映射 | 优先级 | 冷却机制 |
|------|---------|------------|---------|-------|---------|
| **New API** | ✅ 加权随机 | ✅ | ✅ | ✅ 渠道分组 | ✅ 自动冷却 |
| LiteLLM | ✅ 多策略 | ✅ | ✅ | ✅ | ✅ |
| 9Router | ✅ 三级回退 | ✅ | ✅ | ✅ | ✅ |

#### 多设备 Token 管理

| 方案 | 虚拟 Key | 额度限制 | 可视化 | IP 白名单 |
|------|---------|---------|-------|----------|
| **New API** | ✅ | ✅ 按量 | ✅ 仪表盘 | ✅ |
| LiteLLM | ✅ | ✅ Spent | ✅ 仪表盘 | ✅ |
| 9Router | ✅ | ✅ | ⚠️ 基础 | ❌ |

> ✅ 可以给 MBP、Hermes Agent、实验项目各分配一个独立 Token，额度一目了然。

### 2.3 最终推荐：🥇 New API

**选型理由：**

1. **Go 单二进制、零依赖** — 镜像仅 30MB，跑在 Mac mini 上完全无感
2. **`RELAY_PROXY` 代理分离** — 国内厂商直连，海外走 Clash，一次配置
3. **中文社区活跃** — 34.7k Stars，文档完善，国内问题秒解
4. **模型路由完整** — 加权 + Fallback + 冷却，满足所有场景
5. **Token 管理直观** — 给每台设备、每个项目独立 Key
6. **相比 One-API 原版** — 界面更新、维护更活跃、bug 修复快

**不选 LiteLLM 的原因：**
- Python 运行时太重（4-8GB RAM），Mac mini 的 24GB 中 Ollama 需要 ~10GB，再跑 LiteLLM 会抢资源
- 中文文档少，代理配置不直观
- 功能虽强但对单用户家庭场景严重过剩

## 三、部署位置决策

| 考虑因素 | Mac mini (24h) | MBP (随用随开) | Y7000P (Windows) |
|---------|---------------|---------------|-----------------|
| 24h 在线 | ✅ | ❌ 会关机 | ⚠️ 打游戏会关 Docker |
| 代理环境 | ✅ Clash 常开 | ✅ 但关机时不可用 | ✅ 但关机时不可用 |
| 资源占用 | ✅ 128MB 完全无感 | ✅ 但浪费移动端 | ⚠️ Windows Docker 性能差 |
| **结论** | **✅ 最佳位置** | ❌ | ❌ |

**最终位置：Mac mini M4 (100.x.x.1:3000)**

## 四、部署配置

### 4.1 Docker 部署

```bash
# 建数据目录
mkdir -p /Volumes/Work/DockerData/NewAPI

# 启动（一行命令，不需要 docker-compose）
docker run --name new-api -d \
  --restart always \
  -p 3000:3000 \
  -e TZ=Asia/Shanghai \
  -e RELAY_PROXY=http://127.0.0.1:7890 \
  -v /Volumes/Work/DockerData/NewAPI:/data \
  calciumion/new-api:latest
```

### 4.2 初始配置

```
1. 浏览器 → http://localhost:3000
2. 默认账号 root / 密码 123456 → 立即改密码
3. 添加渠道（5 个）：
```

| 渠道 | 类型 | API Key | 模型名 | 走代理？ |
|------|------|---------|--------|---------|
| DeepSeek V4 Flash | DeepSeek | sk-xxx | deepseek-v4-flash | ❌ 直连 |
| DeepSeek V4 Pro | DeepSeek | sk-xxx | deepseek-v4-pro | ❌ 直连 |
| GLM-4.7 | ChatGLM | xxx | glm-4.7 | ❌ 直连 |
| Kimi K2 | Moonshot | sk-xxx | kimi-k2 | ❌ 直连 |
| MiniMax M2.5 | MiniMax | xxx | minimax-m2.5 | ❌ 直连 |

```
4. 生成令牌：
   - MBP 主开发 Key（无限额或无限制）
   - Hermes Agent Key（单独统计用量）
   - 实验项目 Key（有限额）
```

### 4.3 模型路由策略

| 场景 | 主模型 | Fallback 顺序 |
|------|--------|--------------|
| 代码补全 | DeepSeek V4 Flash | → GLM-4.7 → Kimi K2 |
| 复杂推理 | DeepSeek V4 Pro | → GLM-4.7 |
| 架构设计 | GLM-4.7 | → DeepSeek V4 Pro |
| 长上下文 | Kimi K2 | → DeepSeek V4 Flash |
| 高并发批量 | MiniMax M2.5 | → DeepSeek V4 Flash |
| 离线/涉密 | 本地 Ollama (Mac mini/MBP) | 不经过 New API |

## 五、客户端接入

```python
# MBP / 任何设备上的 Python 代码
from openai import OpenAI

client = OpenAI(
    api_key="你分配的设备 Token",
    base_url="http://100.x.x.1:3000/v1"   # Mac mini Tailscale IP
)

# 调用时模型名用网关里的模型名
response = client.chat.completions.create(
    model="deepseek-v4-flash",   # 网关里配的模型名
    messages=[{"role": "user", "content": "hi"}]
)
```

```bash
# curl 测试
curl http://100.x.x.1:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-xxx" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hello"}]}'
```

## 六、注意事项

1. **`RELAY_PROXY` 只对海外渠道生效** — DeepSeek/GLM/Kimi/MiniMax 都是国内厂商，直连即可
2. **数据持久化** — SQLite 模式，映射到 `/Volumes/Work/DockerData/NewAPI`，重启不丢
3. **端口冲突** — 确保 Mac mini 的 3000 端口未被占用
4. **高可用** — Mac mini 24h 在线 + `--restart always`，无需额外守护
5. **升级** — `docker pull calciumion/new-api:latest && docker restart new-api`
