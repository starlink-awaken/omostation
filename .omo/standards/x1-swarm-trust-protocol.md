---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
---

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
- **Payload**: 签名对象为原生的 Body 字节流，必须包含 `timestamp` 字段。
- **Verification**: 接收端必须根据发送方的 `node_id` 查找对应的公钥进行解密校验。

## 4. 重放攻击防护 (Phase 15)
- **Time Window**: 接收端必须校验 `timestamp` 与当前系统时间的偏差，超过 300 秒的消息必须被拒绝。
- **Fingerprint Cache**: 接收端必须在内存中维护已验证签名的指纹库（Seen List）。在 TTL 窗口内重复出现的相同签名将被视为重放攻击。

## 5. 强制约束
1. 严禁发送未签名的跨节点指令。
2. 任何时间戳失效或指纹重复的请求，系统必须返回 401 Unauthorized 并触发 X1 安全预警。
