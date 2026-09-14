---
schema_version: bet-retro/v1
bet_id: BET-Y1Q4-T6-25
retro_type: delivery
date: 2026-09-12
---

# BET-Y1Q4-T6-25 复盘 — OpenHuman 本地桥接器升级与多源健康生物标记物 Schema 归一化

## 交付摘要

| 项目 | 状态 |
|------|------|
| **Spec** | `docs/superpowers/specs/2026-09-12-t6-25-openhuman-bridge-biometric-normalizer-design.md` ✅ |
| **Ledger** | `accepted_specifications` 绑定 SHA-256 ✅ |
| **代码** | 6 文件新增/重构 ✅ |
| **测试** | 27/27 通过 ✅ |

## 交付物

| 文件 | 行数 | 说明 |
|------|------|------|
| `connector.py` | 527 | 重构: 看门狗状态机 + 指数退避重试 + SQLite fallback |
| `token_juice.py` | 236 | 新建: HTML/JSON/XML 压缩管道 (≥60% 降噪) |
| `biomarkers.py` | 543 | 新建: 4 类 source_type 归一化 + 多源融合 |
| `health_importer.py` | 193 | 新建: Family-Hub 文档写入 + BOS 投影 |
| `test_openhuman_bridge.py` | 506 | 新建: 27 单元测试全覆盖 |
| `bos-services.yaml` | +18 | 追加 `bos://persona/health-profile/ingest` 路由 |

## 关键设计决策

1. **看门狗状态机**: `alive → degraded (3次) → dead (5次) → revive (2次成功)` — 三态故障检测 + 自愈恢复
2. **指数退避重试**: 1s → 2s → 4s，全部失败后降级 SQLite 本地缓存
3. **TokenJuice 压缩**: 纯本地正则压缩，无外部依赖，HTML 压缩率 ≥40%
4. **BiomarkerNormalizer**: 统一 `NormalizedBiomarker` dataclass，4 类 source_type 各自解析器 + 按分钟去重融合
5. **HealthImporter**: 按 (date, category) 分组写入 Markdown，BOS 事件日志本地追加

## 测试覆盖

- 看门狗: alive/degraded/dead/revive 状态转移 (5 tests)
- 重试+fallback: 成功重试/fallback/缓存往返/指数退避 (4 tests)
- TokenJuice: HTML/JSON/XML/text 压缩率 + analyze + 空数据 (7 tests)
- BiomarkerNormalizer: Apple Health XML/CGM JSON/Garmin CSV/Fitbit JSON/merge/roundtrip (7 tests)
- HealthImporter: 空批/写入/dry_run/多类别 (4 tests)

## 风险与后续

- **健康数据本地化**: 全部处理在本地完成，无云端泄露
- **Oxigraph 降级**: 与 T6-26 共享 SQLite 降级模式
- **后续**: T6-26 (Semantica 图引擎) 依赖本 BET 完成
