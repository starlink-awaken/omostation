# X1 Standard: Swarm Trust & Node Identity (Ed25519)

> Status: MANDATORY | Applied: Phase 9
> Authority: L3 NodeIdentityManager

## 1. 核心协议
所有在 eCOS v6 蜂群中流转的 A2A 消息或远程资源请求必须通过 Ed25519 签名进行身份校验。

## 2. 身份标识 (Node ID)
- 每个节点在冷启动时必须通过 `NodeIdentityManager` 生成唯一的 UUIDv4。
- 节点的公钥 (Public Key) 必须在 UDP 发现阶段广播给 Master 节点。

## 3. 签名规范
- **Header**: 请求必须包含 `X-Swarm-Node-ID` 和 `X-Swarm-Signature`。
- **Payload**: 签名对象为经由 `sort_keys=True` 序列化的 JSON 负载。
- **Verification**: 接收端必须根据发送方的 `node_id` 查找对应的公钥进行解密校验。

## 4. 强制约束
1. 严禁发送未签名的跨节点指令。
2. 对于签名失败的请求，系统必须返回 401 Unauthorized 并触发 X1 安全预警。
