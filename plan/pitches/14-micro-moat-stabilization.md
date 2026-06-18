# Pitch: Micro-Moat Stabilization & Anti-Drift Fixes

## 🎯 The Why (Problem & Opportunity)
While the core spines (Memory, Swarm, Compute) are fully operational, the white-box forensic audit exposed several micro-architectural vulnerabilities:
1. **Token Estimation Drift:** Using `(len(text) + 3) // 4` for token counting is grossly inaccurate for non-English payloads or code, leading to incorrect budget interceptions.
2. **Signature Serialization Drift:** Swarm nodes sign a JSON representation of payloads. Due to subtle differences in JSON formatting across runtimes/environments, signature verification can fail falsely.
3. **HITL Non-Atomicity:** The Cockpit mutation approval endpoint executes state changes *before* unlinking the proposal file. If an IO error occurs, the proposal remains, risking duplicate executions (idempotency failure).

## 🚧 The What (Solution Overview)
Implement the "Micro-Moat" stabilization patches:

1.  **Tokenizer Integration:** Install `tiktoken` in the `runtime` and `llm-gateway` environments. Refactor token estimation to use `cl100k_base` encoding, falling back to the heuristic only if the library is unavailable.
2.  **Raw Payload Signing:** Modify `A2ANetworkTransport` to serialize the payload to raw bytes first, sign the *exact bytes*, and transmit them using HTTPX's `content=` parameter. Update the receiver (`agora/server/mcp.py`) to verify the signature against `request.body()` before JSON parsing.
3.  **Two-Phase Approval:** Refactor `api_approve_proposal` to first rename the `.yaml` proposal to `.processing`. If successful, execute the mutation and unlink. If execution fails, rollback the rename.

## 📏 Boundaries & Appetites
-   **Appetite:** 2 Days (Low complexity, precision fixes).
-   **No-Gos:** Do not change the underlying Swarm or Compute protocols; these are purely implementation-level robustness enhancements.

## ⚠️ Rabbit Holes & Risks
-   **Dependency Bloat:** Adding `tiktoken` introduces Rust binaries. We must ensure it's added properly to the project environments without breaking cross-platform compatibility.
-   **HTTP Framework Interference:** FastAPI/Starlette might consume `request.body()` if `request.json()` is called first. We must read the raw body *before* parsing JSON.