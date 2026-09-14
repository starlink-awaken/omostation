---
type: retro
bet_id: BET-Y1Q4-T8-22
status: done
done_at: 2026-09-13
merged_reachable_commit: c582f07a7239d057db07a0345f0ac5e7c94a2d02
schema_version: retrospective/v1
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-14
---

# BET-Y1Q4-T8-22 复盘: TinyBOS 极简边缘具身协议

## 交付摘要

**状态**: 代码交付完成 (3/4 done_when 已满足)
**剩余**: 物理设备探活测试需硬件环境 (non-blocking)

### 已交付

1. **Rust main.rs** — 完整传感器管线 + Unix socket IPC
   - 传感器采样循环 (HRV/accelerometer/displacement 模拟)
   - codec 编码 → 4B 长度前缀 → Unix socket `/tmp/tinybos.sock`
   - mesh.rs 集成 (PeerInfo 注册 + stale 检测)
   - `--test-pipeline` 模式: 10 帧 + ping + roam, CI 可用
   - SIGTERM/SIGINT 优雅关闭
   - Release 二进制: 354KB (远低于 10MB 目标)

2. **Rust mesh.rs** — 完善 PeerInfo + MeshTable
   - `PeerInfo::new()` / `touch()` / `is_stale()` 方法
   - `MeshTable.prune_stale()` / `remove_dead()` / `touch_peer()`
   - 7 个单元测试

3. **Python TinyBOSBridge 测试** — 14 个新测试 (45 总计)
   - `TestTinyBOSBridgeInit`: 构造 + 属性
   - `TestTinyBOSBridgeOnTrigger`: handler 注册 + 调用
   - `TestTinyBOSBridgeProcessFrame`: HRV/跌倒/畸形帧
   - `TestSensorReading`: unix_timestamp + to_dict
   - `TestTinyBOSBridgeLifecycle`: stop 安全 + running flag

### 待后续 (non-blocking)

- 物理智能手环/家庭控制屏接入 (需硬件)
- WireGuard P2P 网格真实组网 (需 TUN 设备权限)
- 主工作站休眠热漫游验证 (需 NAS/Mac mini)

## 架构决策

- **Unix socket IPC**: Rust 守护进程通过 `/tmp/tinybos.sock` 推送帧, Python bridge 监听。4B u32 LE 长度前缀, 最大 4096B 限帧。
- **codec 字节级对齐**: Rust `struct.pack("<BQHB")` 与 Python `struct.pack("<BQHB")` 完全一致。注意: value_count 是 1 字节 (B) 不是 4 字节 (I)。
- **mesh.rs 无网络 I/O**: WireGuard 是设计意图, 当前仅管理面 (peer 注册表 + 路由)。真实组网需后续 wireguard crate 集成。
- **TinyBOSBridge async**: `_process_sensor_frame()` 是 async, 测试用 `asyncio.run()` 调用。

## 陷阱记录

1. **struct format BQHI vs BQHB**: Rust/Python 都用 B (1B) 做 value_count, 不是 I (4B)。用错导致解码全 0。
2. **_process_sensor_frame 是 async**: 不是 `_process_sensor_frame_sync`。测试须用 `asyncio.run()`。
3. **agora venv 依赖 ecos**: worktree 中 ecos submodule 未初始化导致 `uv run` 失败。测试须在主仓运行。
4. **UnixStream 不实现 Clone**: 须用 `try_clone()` 而非 `clone()`。
5. **libc::signal 需 unsafe + as *const () as usize**: 不能直接用 `sighandler_t::from()`。

## 验证

```bash
cd projects/surface/tinybos && cargo test           # 15 passed
cd projects/surface/tinybos && cargo build --release # 354KB binary
cd projects/surface/tinybos && cargo run -- --test-pipeline  # 10 frames OK
cd projects/agora && uv run pytest tests/test_tinybos_mesh.py -q  # 45 passed
```
