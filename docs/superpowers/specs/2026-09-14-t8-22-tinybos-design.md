---
schema_version: specification/v1
spec_version: 1.0.0
title: TinyBOS 极简边缘具身协议 — P2P Mesh + 传感器桥接 + 家庭局域网算力漫游
bet_id: BET-Y1Q4-T8-22
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-14
---

# TinyBOS 极简边缘具身协议（BET-Y1Q4-T8-22）

## 背景（Context）

omostation 系统缺乏对物理世界的实时感知能力。当前所有智能决策仅基于数字信号（邮件、日历、代码仓库事件），无法感知穿戴设备心率、跌倒碰撞、空间位移等物理状态。当开发工作站休眠时，守护任务完全中断，无法实现 7×24 小时伴随式守护。

## 目标（Goal）

围绕 TinyBOS 极简边缘具身协议，构建三大核心能力：

1. **P2P Mesh 自组织网络** — 基于 WireGuard 的家庭局域网去中心化节点发现与路由，不依赖任何第三方云端物联网平台
2. **传感器桥接** — 实时采集心率变异率（HRV）、跌倒碰撞（加速度计）、空间位移，编码为场景触发信号直通发射
3. **家庭局域网算力漫游** — 当工作站休眠时，守护任务无损漫游至家庭微型主机（NAS/Mac mini），保持物理世界态势感知连续性

## 非目标（Non-Goals）

- 不依赖任何第三方云端物联网平台中继（坚持本地 Local-First 与 P2P 加密）
- 不破坏现有 BOS 协议的 URL 寻址规范
- 不实现完整的 ARM 交叉编译 CI 矩阵（留待后续 bet 覆盖）

## 交付物

- `projects/surface/tinybos/src/main.rs` — Rust 边缘守护进程入口（< 10 MB 内存）
- `projects/surface/tinybos/src/codec.rs` — 二进制帧编解码（magic + version + type + flags + digest）
- `projects/surface/tinybos/src/mesh.rs` — P2P Mesh 节点注册表与路由表
- `projects/surface/tinybos/src/sensor.rs` — 传感器信号类型定义与阈值检测
- `projects/agora/src/agora/transport/tinybos_bridge.py` — Python 侧传感器桥接器
- `projects/agora/src/agora/transport/p2p_mesh.py` — Python 侧 P2P Mesh 传输
- `projects/agora/tests/test_tinybos_mesh.py` — 单元测试覆盖编解码、网格连通与断线重连
- `.omo/_knowledge/retros/BET-Y1Q4-T8-22.md` — 交付复盘

## 验收标准

1. **Rust 帧编解码 roundtrip 正确**
   - 验证方式：`cd projects/surface/tinybos && cargo test`
   - 证据类型：测试通过

2. **P2P Mesh 节点注册与存活检测**
   - 验证方式：`cd projects/surface/tinybos && cargo test mesh::tests`
   - 证据类型：测试通过

3. **传感器帧 encode/decode 精度保持**
   - 验证方式：`cd projects/surface/tinybos && cargo test sensor::tests`
   - 证据类型：测试通过

4. **Python 侧桥接与 Mesh 模块可导入**
   - 验证方式：`uv run pytest projects/agora/tests/test_tinybos_mesh.py -q`
   - 证据类型：exit 0

5. **本地治理门禁通过**
   - 验证方式：`make gac-local-gate`
   - 证据类型：exit 0

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | Rust vs Go 实现边缘守护 | Rust | 内存开销 < 10 MB 目标，Rust 零成本抽象 + 无 GC 更适合资源受限环境 |
| 2 | WireGuard vs TLS 直连 | WireGuard | 内核级加密性能，LAN 自组织场景下密钥分发更简单 |
| 3 | mDNS vs 中心化信令 | mDNS | 去中心化原则，家庭局域网内零配置节点发现 |
| 4 | 独立 crate vs 混入 agora | 独立 crate | 物感知边缘守护进程与 Python runtime 解耦，独立演进 |

## 变更历史

| 日期 | 变更内容 | 变更人 |
|------|----------|--------|
| 2026-09-14 | v1.0.0 accepted — 初始 spec 绑定 | governance-team |
