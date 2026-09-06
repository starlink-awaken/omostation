---
type: ssot
owner: governance-team
last-reviewed: 2026-09-06
---

# P100 — 统一内存机器上的 wired 天花板与自愈守护冲突

**Pattern observed**: 2026-09-05/06，Qwen3.8-Flash-Next 4bit (103.8GB) 在 M5 Max 128GB 上落地。
一次系统崩溃 + 一次 54 倍性能塌陷 + 一个未引爆的死机陷阱。

## Problem

Apple Silicon 统一内存机器上跑接近物理内存量级的模型时，有三个互相叠加的约束，
任何一个漏掉都会导致**系统级故障（不是应用报错）**：

1. **wired 天花板**：macOS 默认把 GPU 可 wire 的内存限制在物理内存的 ~75%
   （128GB 机器 = 96GB）。模型大于这个值就**在数学上不可能全驻留**。
2. **wired 不可换出**：wired 内存按定义不参与换页。留给系统的余量不够时，
   后果是硬卡死 / kernel panic，**不是变慢**——没有降级路径。
3. **自愈守护会反向填满内存**：为算力池写的 watchdog / reconcile 循环，
   会在你清场之后把服务和模型重新拉起来。

## Symptom

**症状一：系统崩溃。** 无预检裸跑大模型加载，叠加已常驻的服务，swap 暴涨后死机。

**症状二：性能塌陷 54 倍。** wired 限额低于模型体积时，超出部分走磁盘换页。
实测 0.6 tok/s，同硬件社区基准 33 tok/s。稀疏 MoE 尤其致命——每 token 路由到
不同专家，换页访问接近**全权重文件随机读**，不是 llama.cpp mmap n-gram 表那种
"冷页永不加载"的理想情况。

**症状三（最阴，未引爆）：延迟 5 分钟的死机。** 清场 → 提高 wired → 加载模型
**三步全部成功**，5 分钟后守护进程把服务拉起来，此时物理内存已被 wire 掉大半
且不可回收 → 硬卡死。故障与操作之间隔着一个探测周期，事后极难归因。

## Root Cause

三条都是"**声明面看起来成功了，执行面的物理约束在后面等着**"：

| 层 | 声明面 | 执行面真相 |
|---|---|---|
| 内存够不够 | `vm_stat` 显示可用充足 | mapped file cache 不算可用；wired 上限另有天花板 |
| 模型能不能装下 | 体积 < 物理内存 | 但 > wired 天花板 → 强制换页 |
| 清场干不干净 | 进程已 kill、内存已释放 | 守护进程在下一个探测周期把它拉回来 |

## Fix Pattern

### 1. 三重量化预检，缺一不可

```python
# 可用内存口径: free + inactive + speculative (不含 mapped file cache)
# wired 上限动态算, 不要顶格:
wired = min(模型体积 + 2GB, 可用内存 - 系统保留 8GB)
```

清场充分时给到全驻留；清场不足时自动收缩走 SSD 分页——**慢但不崩**，
这个降级方向是对的。

### 2. 提高 wired 天花板需要 sysctl，且必须可逆

```bash
sudo sysctl iogpu.wired_limit_mb=114688   # 112GB
sudo sysctl iogpu.wired_limit_mb=0        # 恢复默认
```

读当前值用 `sysctl -n iogpu.wired_limit_mb`（返回 `0` = 走系统默认 75%）。
注意 mlx 0.31 的 `mlx.core.metal` **只有 `set_wired_limit` 没有 getter**。
该设置不持久化，重启自动恢复——这是安全特性，别去做成持久化。

### 3. 进入独占模式前必须先停守护，顺序不能反

```
停守护 → 检查清场 → 提高 wired → 跑模型 → 恢复 wired → 恢复守护
```

先停守护再检查内存：清场不彻底时拒绝进入但守护已停，清完场直接重试即可。
**恢复守护这一步必须有人负责**——否则算力池永久失去自愈能力，
而且这个损失是静默的。

### 4. 盘位也算约束

模型放外置 USB 盘（~1GB/s）vs 内置 NVMe（~3GB/s+）：全驻留时只影响加载时间，
一旦发生换页则直接决定生死。大模型放内置盘，并记得排除 Time Machine。

## Detection

```bash
sysctl -n iogpu.wired_limit_mb          # 0 = 默认 ~75%
sysctl -n vm.swapusage                  # 持续增长 = 危险信号
launchctl list | grep -i <你的守护>      # 独占模式下必须是 stopped
```

## 本仓库落地

- 工具：`~/.local/bin/omlx-dedicated-mode` (status/enter/exit)
- 手册：`~/.local/share/omlx-docs/qwen38-flash-next-runbook.md`
- 守护源：`projects/omlxc/scripts/pipeline-watchdog.sh` (launchd, 300s)
  + `src/omlxc/daemon/composition.py:1302` resident reconcile (300s)

## Related

- [[p73-truth-driven-engineering-pattern]] — 声明/执行鸿沟的母题
- [[p78-triple-axis-diagnostic-pattern]] — 静态/运行时/决策三维查证
- [[p101-sentinel-value-masquerading-as-progress]] — 同批次挖出的诊断陷阱
