"""Layer 5: Worker 管理 — 注册/心跳/通信总线/任务分发/结果聚合。

职责:
  - Worker 注册与身份管理
  - 心跳监控与健康检查
  - 任务分发通道
  - 结果聚合与返回

依赖: aetherforge-gateway (LLMRequest/LLMResponse),
      aetherforge-swarm (WorkerDispatcher)

TODO: 实现 registry.py + dispatcher.py + heartbeat.py
"""
