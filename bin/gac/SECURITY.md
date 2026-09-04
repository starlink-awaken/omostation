---
type: ssot
---

# mesh-router 安全合同

## 边界

`gac-mesh-router.py` 是本地 HTTP 路由代理，只监听注册表中的本机端口 `7437`，不承担公网暴露、身份认证或凭据存储职责。调用方必须在受控本机环境中访问它。

## 敏感操作

- 路由配置来自工作区 SSOT 和本地进程状态，不接受任意远程配置写入。
- 不在代码、日志或响应中保存 API key、token、密码或私钥。
- 变更路由规则前先运行 `uv run python "bin/gac/gac-mesh-router.py" --check`，再由人工确认启动。

## 审计入口

- 实现：`bin/gac/gac-mesh-router.py`
- 端口声明：`protocols/port-registry.yaml::7437`
- 受控验证：`uv run python "bin/gac/gac-mesh-router.py" --check`
