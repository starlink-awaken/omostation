# Pitch: Dynamic Capability Load Balancing (Smart Partitioning)

## 🎯 The Why (Problem & Opportunity)
Currently, the Swarm Spine routes tasks based primarily on node availability and static BOS URI registrations. It treats all nodes equally. However, different physical nodes possess asymmetric hardware capabilities (e.g., a GPU workstation vs. a Macbook Air vs. a Raspberry Pi). Distributing a heavy vision-embedding task to a weak node while a GPU node sits idle is grossly inefficient.

## 🚧 The What (Solution Overview)
Evolve the SwarmOrchestrator to support `Smart Task Partitioning` based on dynamic hardware and capability telemetry.

1.  **Capability Telemetry:** Extend `SwarmNode` to report its hardware profile (VRAM, CPU cores, active accelerators) and specialized domains (e.g., `vision`, `heavy_compute`) during the UDP heartbeat.
2.  **Resource-Aware Routing:** Modify the A2A and BOS Router layers. When a task envelope contains specific capability requirements (e.g., `requires: ["gpu", "vram>8g"]`), the orchestrator will filter the available node pool.
3.  **Load Shedding:** Allow overloaded nodes to proactively broadcast "backpressure" signals, temporarily removing themselves from the active routing pool for heavy tasks.

## 📏 Boundaries & Appetites
-   **Appetite:** 2 Weeks (High complexity, requires extending core protocol).
-   **No-Gos:** Do not build a full Kubernetes-style container orchestrator. The scheduling relies on cooperative capability declarations, not strict cgroup enforcement.

## ⚠️ Rabbit Holes & Risks
-   **State Desynchronization:** Rapidly changing node capabilities (e.g., VRAM suddenly filling up) might not propagate fast enough via 5-second heartbeats, leading to routed tasks failing due to OOM on the target node. We need a fast-reject mechanism.