# Pitch: Swarm Trust Network (Cross-Node Auth)

## 🎯 The Why (Problem & Opportunity)
Currently, cross-node A2A communication within the Swarm Spine relies on basic HTTP forwarding without rigorous cryptographic verification. In a distributed environment, this leaves the network vulnerable to rogue agents or unauthorized nodes impersonating legitimate workers, potentially leading to unauthorized budget consumption or data exfiltration.

## 🚧 The What (Solution Overview)
Implement a zero-trust architecture for the Swarm Spine using node identity signatures.

1.  **Node Identity Generation:** Each Swarm node automatically generates an Ed25519 keypair upon initialization (stored securely).
2.  **Signature Injection:** Modify `A2ANetworkTransport` to sign outgoing cross-node payloads using the node's private key.
3.  **Signature Verification:** Enhance the receiving endpoint (`/api/v1/a2a/send`) in `agora.server.mcp` to cryptographically verify the signature against the registered public key of the sending node before processing the message.

## 📏 Boundaries & Appetites
-   **Appetite:** 1 Week (Medium complexity, high security impact).
-   **No-Gos:** Do not introduce heavy PKI (Public Key Infrastructure) or third-party certificate authorities. We will use a lightweight, decentralised symmetric/asymmetric key exchange over the initial UDP discovery phase.

## ⚠️ Rabbit Holes & Risks
-   **Clock Skew:** Signature replay attacks must be mitigated using timestamp windows, which requires reasonable time synchronization (NTP) across nodes.
-   **Key Rotation:** Handling key compromise or rotation without breaking active Swarm communication requires careful state management.