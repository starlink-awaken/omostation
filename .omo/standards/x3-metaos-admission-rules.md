# X3 Standard: MetaOS Admission Gate & Value Alignment

> Status: ENFORCED | Applied: Phase 9
> Authority: MetaOS AdmissionGateway

## 1. 准入原则
任何接入 Agora 网格的 Agent 或远程服务必须满足 eCOS 五大治理部件。

## 2. 准入元数据 (metaos_admission)
- **C1 (价值观)**: 必须声明 `declared_values`，包含 `["human-centric", "objective", "transparent"]`。
- **C2 (权限隔离)**: `role` 必须属于受限白名单（如 `researcher`, `evaluator`, `generator`）。
- **C3 (过程监督)**: 必须声明 `supports_otlp: True` 以支持链路追踪。
- **C4 (可回溯性)**: 必须携带 `omo_audit_trail_id`。

## 3. 拦截逻辑
- 缺失元数据或元数据不合规的服务，ProxyManager 必须拒绝建立代理。
- 拦截原因必须记录在 `proxy_admission_rejected` 日志中。
