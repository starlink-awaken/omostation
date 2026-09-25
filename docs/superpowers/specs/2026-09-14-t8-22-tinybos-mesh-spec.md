---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: TinyBOS 极简边缘具身协议与家庭局域网算力网格漫游
bet_id: BET-Y1Q4-T8-22
created: 2026-09-14
risk_level: L2
human_gate: false
value_indicator_policy: false
---


# TinyBOS 极简边缘具身协议与家庭局域网算力网格漫游（BET-Y1Q4-T8-22）

> Spec binding v1.0.0（2026-09-15）：完整交付已由 PR #3770 合入
> origin/main。本 spec 将已交付范围固化为契约。

## 1. 背景（Context）

系统的感知边界止于工作站进程：可穿戴体征信号（心率变异、跌倒碰撞、
空间位移）无法直通发射为场景触发信号；工作站休眠即意味着守护中断。
本 spec 为 BET-Y1Q4-T8-22 建立契约：以内存开销 < 10MB 的超轻量
TinyBOS 边缘守护端承接物理信号采集与编码，以 Agora 侧 P2P 网格与
sensor 桥承接信号解码、场景映射与漫游通告，全程本地 Local-First，
不依赖第三方云端物联网平台中继。

## 2. 目标（Goal）

交付 TinyBOS Rust 边缘守护进程（codec/mesh/sensor/main 四模块）与
Agora P2P 网格 Python 接入模块；实现心率突变与跌倒加速度物理信号向
场景触发（`hrv_critical`、`fall_detected`）的自动映射；提供漫游通告与
状态摘要原语支撑工作站休眠时的守护任务漫游；单元测试覆盖边缘报文
编解码、P2P 网格连通与网络波动断线重连。

## 3. 非目标（Non-Goals）

- 不依赖任何第三方云端物联网平台中继（坚持本地 Local-First 与 P2P 加密）。
- 不破坏现有 BOS 协议的 URL 寻址规范。
- 本可交付不包含 ARM 家庭微型主机交叉编译 CI 矩阵与真实 NAS 热漫游
  端到端演练（留待后续 bet 覆盖，见 retro 踩坑记录）。

## 4. 架构

```
┌─────────────────────────────────────────────┐
│  TinyBOS Edge Daemon (Rust)                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ codec.rs │  │ sensor.rs│  │ mesh.rs  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       └──────────────┼──────────────┘         │
│                      ▼                        │
│               main.rs pipeline                │
│         Unix socket /tmp/tinybos.sock         │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Agora Transport Bridge (Python)             │
│  tinybos_bridge.py: decode → map → trigger   │
│  p2p_mesh.py: mesh codec + node management   │
└──────────────────────────────────────────────┘
```

## 5. 接口契约

### 5.1 帧编码格式 (codec.rs)

| 字段 | 大小 | 说明 |
|------|------|------|
| magic | 4B | `Tiny` 魔数 |
| version | 1B | 协议版本 (v1) |
| flags | 2B | 标志位 |
| frame_type | 1B | FrameType 枚举 |
| payload_len | 4B | payload 长度 (u32 LE) |
| digest | 4B | SHA-256 摘要前 4 字节 |
| timestamp | 8B | Unix 时间戳 (u64 LE) |
| reserved | 2B | 保留 |

FrameType 枚举：Ping, Pong, Heartbeat, Data, RoamRequest, RoamAck, Teardown

### 5.2 传感器帧格式 (sensor.rs)

| 字段 | 大小 | 说明 |
|------|------|------|
| sensor_type | 1B | B (1字节) |
| timestamp_ms | 8B | Q (u64 LE) |
| precision | 2B | H (u16 LE) |
| value_count | 1B | B (1字节) |
| values | N×4B | f32 LE 数组 |

传感器类型：0x01=HRV, 0x02=Accel, 0x03=Gyro, 0x04=Baro

### 5.3 IPC 协议

- 传输层：Unix domain socket (`/tmp/tinybos.sock`)
- 帧分隔：4B u32 LE 长度前缀
- 最大帧大小：4096B
- 心跳间隔：5s (Ping/Pong)

### 5.4 Mesh 管理面 (mesh.rs)

- `PeerInfo`: 节点标识 (id, addr, key)
- `MeshTable`: peer 注册表 + 路由管理
- `prune_stale()`: 移除超时未触达的 peer
- `touch_peer()`: 刷新 peer 活性时间戳

## 6. 场景触发映射 (tinybos_bridge.py)

| 传感器 | 条件 | 触发 |
|--------|------|------|
| HRV | rmssd < 20ms | `health-visit.hrv_critical` (critical) |
| Accel | 三轴 magnitude > 4g | `health-visit.fall_detected` (critical) |

## 7. 交付物（Deliverables）

- `projects/surface/tinybos/`：
  - `main.rs`：完整传感器管线 (simulate→encode→send)、Unix socket IPC、
    信号处理 (SIGTERM/SIGINT)、test-pipeline CI 模式 (10 帧 + ping + roam)
  - `codec.rs`：二进制帧线协议 (magic `Tiny`、SHA-256 摘要、7 帧类型、4 tests)
  - `sensor.rs`：HRV/加速度/陀螺/气压传感器帧编解码、3 阈值检测、4 tests
  - `mesh.rs`：PeerInfo/MeshTable + prune_stale/remove_dead/touch_peer、7 tests
  - `Cargo.toml`：libc 依赖 + release 体积优化 (opt-level=z, lto=true, strip=true)
  - **Release 二进制：354KB** (远低于 10MB 目标)
- `projects/agora` 子模块：
  - `transport/tinybos_bridge.py`：传感器帧解码、场景触发映射、Unix IPC 服务端
  - `transport/p2p_mesh.py`：MeshManager (帧收发、广播、handler 分发)
  - `tests/test_tinybos_mesh.py`：45 测试 (14 TinyBOSBridge 新增)，全部通过

## 8. 验收（Acceptance）

```bash
# Rust 编译 + 测试
cd projects/surface/tinybos && cargo test           # 15 passed
cargo build --release                              # 354KB binary
cargo run -- --test-pipeline                        # 10 frames OK

# Python 测试
cd projects/agora && uv run pytest tests/test_tinybos_mesh.py -q  # 45 passed
```

## 9. 陷阱记录

1. `sighandler_t::from()` 平台差异 — 用 `handle_signal as *const () as usize` 转换
2. `Vec<UnixStream>` 不可 Clone — 锁内用 `stream.try_clone()` 创建副本
3. Rust/Python struct format 对齐 — value_count 用 B (1字节) 非 I (4字节)

## 10. 完成证据

| 维度 | 状态 | 证据 |
|------|------|------|
| engineering | VERIFIED | PR #3770 merged, 15 Rust + 45 Python tests passed |
| operational | PROVEN | test-pipeline 端到端 10 帧编码/解码/验证通过 |
| value | NOT_PROVEN | 业务价值待单独证明 |
