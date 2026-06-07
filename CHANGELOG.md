# omostation Changelog

> 多仓库统一发布. 工作区根 VERSION 文件权威.
> 6 项目 (agora / kairon / gbrain / omo / metaos / cockpit / runtime) 共享版本号.
> 详见 ADR-0007.

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
