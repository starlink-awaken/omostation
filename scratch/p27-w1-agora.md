# Phase 27 Wave 1: Agora MCP Safe Mesh

## 愿景
强制执行 I0 层的代理隔离，所有的知识工具（L1 包）都必须隐藏在 `agora` 网关之后。
禁止跨包的代码级函数直连。

## 执行路线

- [x] 审计所有 L1 包的 MCP 入口，找出非标准的直连调用
- [x] 确保 `agora_mcp_gateway.py` (或同等入口) 能动态代理发现所有安装的工具
- [x] 为所有被暴露的子节点服务配置 Health Endpoint 以便 mesh 状态同步
- [x] 重构或移除绕过网关的老旧测试脚本和代码
