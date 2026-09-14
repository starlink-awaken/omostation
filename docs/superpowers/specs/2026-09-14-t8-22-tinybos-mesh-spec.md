---
schema_version: specification/v1
spec_version: 1.0.0
title: TinyBOS 极简边缘具身协议与家庭局域网算力网格漫游
bet_id: BET-Y1Q4-T8-22
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-14
---



# TinyBOS 极简边缘具身协议与家庭局域网算力网格漫游（BET-Y1Q4-T8-22）

> Closeout 补绑 spec（2026-09-14）：第一可交付已由 PR #3746 合入
> origin/main（`c582f07a7239d057db07a0345f0ac5e7c94a2d02`）。
> 本 spec 以台账 `goal/done_when/verify` 为准，将已交付范围固化为契约，
> `write_surfaces` 收敛到 `projects/surface/tinybos/`（Rust 边缘守护）、
> `transport/p2p_mesh.py`、`transport/tinybos_bridge.py`、
> `tests/test_tinybos_mesh.py` 与 retro。

## 背景（Context）

系统的感知边界止于工作站进程：可穿戴体征信号（心率变异、跌倒碰撞、
空间位移）无法直通发射为场景触发信号；工作站休眠即意味着守护中断。
本 spec 为 BET-Y1Q4-T8-22 建立契约：以内存开销 < 10MB 的超轻量
TinyBOS 边缘守护端承接物理信号采集与编码，以 Agora 侧 P2P 网格与
sensor 桥承接信号解码、场景映射与漫游通告，全程本地 Local-First，
不依赖第三方云端物联网平台中继。

## 目标（Goal）

交付 TinyBOS Rust 边缘守护进程骨架（codec/mesh/sensor 三模块）与
Agora P2P 网格 Python 接入模块；实现心率突变与跌倒加速度物理信号向
场景触发（`hrv_critical`、`fall_detected`）的自动映射；提供漫游通告与
状态摘要原语支撑工作站休眠时的守护任务漫游；单元测试覆盖边缘报文
编解码、P2P 网格连通与网络波动断线重连（30 测试）。

## 非目标（Non-Goals）

- 不依赖任何第三方云端物联网平台中继（坚持本地 Local-First 与 P2P 加密）。
- 不破坏现有 BOS 协议的 URL 寻址规范。
- 本可交付不包含 ARM 家庭微型主机交叉编译 CI 矩阵与真实 NAS 热漫游
  端到端演练（留待后续 bet 覆盖，见 retro 踩坑记录）。

## 交付物（Deliverables）

- `projects/surface/tinybos/`：`main.rs`（守护进程入口与模块结构）、
  `codec.rs`（二进制帧线协议：magic `tBOS`、SHA-256 摘要、编解码与
  全错误路径）、`sensor.rs`（HRV/加速度/陀螺/气压传感器帧编解码、
  跌倒检测、加速度模值）、`mesh.rs`（P2P 对等注册表与路由表）、
  `Cargo.toml`（release 体积优化，目标 < 10MB）。
- `projects/agora` 子模块：`transport/p2p_mesh.py`（MeshManager：
  帧收发、广播、handler 分发、漫游通告、状态摘要）、
  `transport/tinybos_bridge.py`（传感器帧解码、场景触发映射、
  Unix IPC 服务端）、`tests/test_tinybos_mesh.py`（30 测试，全部通过）。

## 验收（Acceptance）

- `uv run pytest projects/agora/tests/test_tinybos_mesh.py -q` exit 0（30 passed）。
- `make gac-local-gate` exit 0（以门禁实际结果为准；预存的
  `T7-07: 未知 track` 基线问题不属于本 bet 表面积）。
- 熔断：边缘节点离线或网络分区时进入离线数据缓冲模式，本地持久化至
  环形缓冲区，严禁阻塞或丢弃体征事件。
