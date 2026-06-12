# omostation Changelog

> 多仓库统一发布. 工作区根 VERSION 文件权威.
> 9 项目 (agora / kairon / gbrain / omo / metaos / cockpit / runtime / ecos / aetherforge) 共享版本号.
> 详见 ADR-0007.

## [0.2.0] - 2026-06-12

### Added (治理框架 + 能力地图 + 文档完善)

- **债务治理**:
  - 9/9 权重债务全部解决 (debt_weight: 0.3→1.0)
  - debt_health: 62.5→100.0
  - 清理 5 个过时债务引用

- **X1-X4 治理框架**:
  - L0 治理模块 (ecos/l0/governance/)
  - X1-X4 检查器实现
  - 治理注册表 + 告警规则
  - cockpit MCP 治理工具 (6 个)

- **kairon 优化**:
  - 16 个包全部验证通过 (100%)
  - 能力地图 (CAPABILITY-MAP.md)
  - 使用指南 (USAGE-GUIDE.md)
  - atomic_write_json 工具

- **KOS 修复**:
  - manifest.json 重构 (10 域)
  - README 对齐实际配置
  - 索引清理重建

- **文档完善**:
  - 17 个项目能力地图
  - 17 个项目 CHANGELOG + CONTRIBUTING + LICENSE
  - ARCHITECTURE.md 更新

- **版本号统一**:
  - 11 个项目统一到 1.0.0

- **Git Hooks**:
  - 18 个项目配置 .githooks

- **治理仪表板**:
  - Web 化 (HTML + API)
  - 告警消息处理

### Architecture
- X1-X4 治理框架体系化
- L0 治理模块与 M1/M2 SSOT 对齐
- 能力地图覆盖 17 个项目

## [0.1.2] - 2026-06-09

### Added (AppendOnlyLog 全景方案 5 轮收口 — Round 1-5)
- **Round 1 — 抽象**:
  - `omo_io.AppendOnlyLog` 类 (SSOT JSONL 物理写盘)
  - `omo_io.read_jsonl` 公开 (容错读)
  - 19 个单元测试
- **Round 2 — 接通**:
  - `omo_audit` / `omo_bos_metrics` 内部用 AppendOnlyLog
  - 外部 API 0 改 (49 测试不变)
- **Round 3 — 样板**:
  - `omo_sync` 摆脱 `details` 字符串拍扁, 结构化 record
  - 6 个 omo_sync 单元测试
- **Round 4 — 收尾**:
  - `AppendOnlyLog.tail(n)` / `since(ts, field='ts')` 方法
  - `AppendOnlyLog` 跨进程锁 `fcntl_lock` (POSIX fcntl.flock 包装)
  - `omo observability log tail --type knowledge [--file X]` 多文件
  - `omo_alert` 接入 AppendOnlyLog (第 4 个 consumer)
- **Round 5 — L0 强化**:
  - 治理审计 88.3 (B) → 100.0 (A+), kairon ruff 9→0
  - 跨进程 fcntl_lock 集成测试 (3 tests, 100/100 0 丢行)
  - `model_driven.PipelineTracker` 加 `on_event` 钩子 (向后兼容)
  - `omo.model_driven_bridge` L1 → L0 事件流桥接 (5 tests)
  - `omo event emit` 子命令 (P3 样板, 第 5 个 consumer, 4 tests)
  - 100+ 单元测试 + 3 集成测试 + 1 跨项目桥接

### Architecture
- 详见 `.omo/_knowledge/management/append-only-log-pattern-2026-06-09.md`
- 5 个 AppendOnlyLog consumer: omo_audit / omo_bos_metrics / omo_sync / omo_alert / omo_event
- L1 → L0 事件流贯通: PipelineTracker.on_event → omo.model_driven_bridge → .jsonl

## [0.1.1] - 2026-06-07

### Changed
- Bump version to 0.1.1 (release.sh patch)
- P34-W3: 多仓库统一发布机制落地

## [0.1.0] - 2026-06-07

### Added
- P33-W0: BOS URI 北极星 + 5 Domain 边界定义
- P33-W1: 战役 2 起步 2 Domain (memory + governance) + 6 URI
- P33-W2: 战役 2 余下 3 Domain (analysis + persona + capability) + 15 URI = 21 总
- P33-W3: KOS 持久化 + endpoint 实测 + 命名协调
- P33-W4: agora 接管 URI 解析 + 11 POC stdio 服务
- P33-W5: forge 集市 + 工具热加载 + 6 forge tools
- P33-W6: 整体验收, 健康分 100.0 (A+) 守
- P34-W0: URI 扩 21→40 (5 Domain 细分)
- P34-W1: agora spawn 升级 (POC 到生产 stdio 协议)
- P34-W2: Analysis 域 12 URI 实战化
- P34-W3: 多仓库统一发布机制 (release.sh + VERSION + CHANGELOG + ADR-0007)

### Changed
- kairon 包合并: 3 组合并 (protocols-layer / sot-bridge / llm-gateway-kernel)
- kairon 包归档: metaos / wksp / kairon-governance 迁出
- agora 路由表: 12 条服务注册, agora 12/12 健康
- omo 治理: audit / sync / history / daemon 6 模块

### Fixed
- KOS 实体 ID 前缀: TR-* → CON-* (符合 KOS 校验)
- ruff errors: 283→0 (P32 全清)
- agora 路由与实际服务脱节: 18.2%→100%
- BOS URI 命名冲突: 接受 3 段 legacy + 4 段新

## Earlier versions

See git history. 6 项目独立维护.
