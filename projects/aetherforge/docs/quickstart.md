# 快速开始

## 安装

```bash
pip install aetherforge
```

需要本地模型？先安装 [Ollama](https://ollama.com) 并拉取模型：

```bash
ollama pull llama3
```

需要云端 API？设置环境变量：

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-...
```

## 10 秒体验

```bash
aetherforge demo
```

这个命令会检测你的算力节点、LLM Provider、成本系统是否就绪。

## 调用 LLM

```bash
# 列出可用的模型
aetherforge gateway list

# 生成文本
aetherforge gateway generate "用一句话介绍自己"

# 指定模型
aetherforge gateway generate -m gpt-4 "写一首诗"
```

## 管理算力

```bash
# 查看所有算力节点
aetherforge mesh list

# 健康检查
aetherforge mesh health

# 自动路由到最优节点
aetherforge mesh generate "你好"

# 查看成本
aetherforge mesh cost
```

## 多 Agent 协作

```bash
# GroupChat 对话
aetherforge swarm chat "帮我设计一个产品方案"

# 层级任务执行
aetherforge swarm run "调研 AI Agent 框架并对比"
```

## 下一步

- 阅读 [Gateway 使用指南](guide/gateway.md)
- 阅读 [Mesh 使用指南](guide/mesh.md)
- 查看 [API 参考](api.md)
