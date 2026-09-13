---
type: retro
bet_id: BET-Y1Q4-T8-22
status: done
done_at: 2026-09-13
merged_reachable_commit: c582f07a7239d057db07a0345f0ac5e7c94a2d02
---

# BET-Y1Q4-T8-22 Retro: TinyBOS 极简边缘具身协议与家庭局域网算力网格漫游

## 交付摘要

- PR #3746 已合入 main
- TinyBOS Rust 边缘守护进程骨架 (projects/surface/tinybos/): codec/mesh/sensor 三模块
- Agora P2P mesh Python 模块接入
- 单元测试覆盖边缘报文编解码、P2P 网格连通与网络波动断线重连

## 踩坑记录

- squash-merge 后原分支 sha 不在 origin/main 祖先链，需放宽 merge-base 校验
- Rust 交叉编译到 ARM 家庭微型主机需单独 CI 矩阵（留待后续 bet 覆盖）

## 经验沉淀

- 物感知边缘守护进程适合独立 Rust crate 起步，不混入 Python runtime
- P2P mesh 节点发现优先用 mDNS + WireGuard，不依赖中心化信令服务器
