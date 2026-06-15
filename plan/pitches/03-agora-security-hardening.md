# Pitch: Eradicate Hardcoded Keys and Plaintext Credentials in Agora

## 🎯 The Why (Problem & Opportunity)
The `agora` module, serving as the central MCP service mesh and authentication hub, currently harbors severe security vulnerabilities: a hardcoded fallback key (`sharedbrain-default-key`) in `mcp_auth.py` and the storage of plaintext tokens in `~/.config/agora/tenants.yaml`. These P1 vulnerabilities provide an easy vector for unauthorized system access, token forgery, and complete bypass of the security perimeter, breaking the trust foundation of the Agentic Protocols.

## 🚧 The What (Solution Overview)
Harden the authentication and secret management infrastructure within `agora`.

1.  **Remove Default Keys:** Eliminate the hardcoded fallback key in `mcp_auth.py:88`. The system must refuse to start (fail-fast) if the required environment variable for the sovereign key is missing.
2.  **Secure Token Storage:** Implement PBKDF2 hashing for tokens before storing them in `tenants.yaml`. Ensure that the raw token is only returned to the user/agent once during generation.
3.  **Audit Key Material:** Perform a focused audit of the `agora` codebase to ensure no other sensitive cryptographic materials or credentials are inadvertently exposed or hardcoded.

## 📏 Boundaries & Appetites
-   **Appetite:** 3 Days (Low complexity, critical security).
-   **No-Gos:** Do not rebuild the entire OAuth2/JWT stack. The fix must be targeted at the specific storage and initialization vulnerabilities identified.

## ⚠️ Rabbit Holes & Risks
-   **Backward Compatibility:** Existing plain-text tokens in development environments will become invalid. A clear communication or a simple migration script for local dev environments must accompany this change.