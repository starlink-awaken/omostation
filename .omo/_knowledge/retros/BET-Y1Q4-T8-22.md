---
schema_version: retrospective/v1
bet_id: BET-Y1Q4-T8-22
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-14
---

# BET-Y1Q4-T8-22 复盘: TinyBOS Edge Guardian

## 交付摘要

**状态**: 代码交付完成 (4/4 done_when 已满足)

### 已交付

1. **Rust Edge Daemon (`tinybos`)** — 完整传感器管道 + Unix socket IPC
   - `codec.rs`: 7 帧类型, 16B 头部, SHA-256 摘要 (4 tests)
   - `sensor.rs`: 4 传感器类型, 3 阈值检测 (4 tests)
   - `mesh.rs`: MeshTable + prune_stale + touch_peer (7 tests)
   - `main.rs`: 传感器采样→编码→发送管道, 信号处理, test-pipeline CI 模式

2. **Python Agora Transport (`tinybos_bridge.py`)** — 传感器帧解码 + 场景触发映射
   - `decode_sensor_frame()`: 二进制帧解析
   - `map_to_trigger()`: HRV/加速度→场景触发映射
   - `TinyBOSBridge` 类: Unix socket 服务端, asyncio 连接管理

3. **单元测试** — Rust 15/15 + Python 45/45 全部通过

4. **Release 二进制** — 354KB (远低于 10MB 目标)

## 架构决策

- **Rust 信号处理**: `sighandler_t` 是 `usize` 而非函数指针类型，用 `handle_signal as *const () as usize` 转换。避免 `sighandler_t::from()` 在 `usize` 平台上触发 "direct cast" warning
- **UnixStream 连接管理**: `UnixStream` 不实现 `Clone`，在锁内用 `try_clone()` 创建副本发送，避免持有锁期间阻塞
- **Test-pipeline 模式**: `--test-pipeline` 标志让 CI 可端到端验证二进制，无客户端时降级为 stdout hex 输出
- **Python asyncio 桥接**: TinyBOSBridge 作为 Unix socket 服务端，TinyBOS daemon 作为客户端推送数据

## 陷阱记录

1. **`sighandler_t::from()` 平台差异**: 在 `sighandler_t = usize` 的平台上，`From<fn>` 未实现，编译失败。解法: 手动 `as *const () as usize` 转换
2. **`Vec<UnixStream>` 不可 Clone**: `UnixStream` 不实现 `Clone` trait。解法: 在锁内用 `stream.try_clone()` 创建副本
3. **worktree submodule 克隆失败**: omo/ecos 等子模块通过 HTTPS 克隆时 LibreSSL TLS 错误，用 symlink 绕过
4. **uv 不跟随 symlink**: worktree 中 symlink 指向的依赖项目无法被 uv 解析，测试须在 main workspace 运行

## 验证

```bash
# Rust 编译 + 测试
cd projects/surface/tinybos && cargo test          # 15 passed
cargo build --release                              # 354KB binary
./target/release/tinybos --test-pipeline --socket=/tmp/tinybos-test.sock

# Python 测试
cd projects/agora && uv run pytest tests/test_tinybos_mesh.py -v  # 45 passed
```
