# Pitch: Eliminate Critical Data Integrity Risks in JSONL Storage

## 🎯 The Why (Problem & Opportunity)
Currently, the core knowledge engines (`gbrain` and `kairon`) rely on raw, non-atomic file I/O operations (`json.dumps + open("a")`) to write critical state to JSONL files. In an asynchronous, multi-agent environment, this introduces a P0 hazard: concurrent writes will inevitably lead to file corruption, data loss, and a cascading failure of the Single Source of Truth (SSOT). This architectural gap fundamentally compromises the reliability of the entire knowledge plane.

## 🚧 The What (Solution Overview)
Implement a robust, atomic, and schema-validated persistence layer for all JSONL interactions within the `gbrain` and `kairon` modules.

1.  **Atomicity:** Introduce an append-only, file-locking mechanism or a transactional write-and-swap strategy to guarantee that no write operation can corrupt existing data.
2.  **Schema Validation:** Enforce strict schema validation before any record is serialized and committed to disk, ensuring data integrity at the boundary.
3.  **Migration:** Refactor all identified non-atomic I/O paths (referenced in `DEBT-OMC-GBRAIN-PERSISTENCE` and `DEBT-OMC-KAIRON-JSONL`) to utilize this new persistence abstraction.

## 📏 Boundaries & Appetites
-   **Appetite:** 1 Week (Medium complexity, high urgency).
-   **No-Gos:** Do not introduce heavy external databases (e.g., PostgreSQL or MongoDB) as a replacement for JSONL in this phase. The solution must remain file-based to preserve the current architectural simplicity and portability, focusing solely on safety wrappers.

## ⚠️ Rabbit Holes & Risks
-   **Performance Overhead:** File locks might introduce latency bottlenecks if the I/O frequency is extremely high. We must ensure the locking mechanism is highly optimized.
-   **Incomplete Migration:** Overlooking legacy write paths during refactoring. A thorough static analysis is required to identify all direct `open()` calls targeting JSONL files.