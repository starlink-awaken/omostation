# G-DEL.3 有线复测清单

> 目标：在 **ethernet** 路径上用 n≥1000（默认 10000）重测 p99&lt;100ms。  
> 当前阻塞：macmini `en0` Ethernet **inactive**，两端均走 Wi-Fi。

## 1. 硬件

1. 网线：Mac mini 有线口（或 USB 网卡）↔ 路由器/交换机  
2. 本机（MacBook）同样有线接入同一 L2 网段（避免一端 Wi-Fi）  
3. 确认：

```bash
# macmini
ssh 192.168.31.210 'ifconfig en0 | head -8'
# 期望 status: active 且有 inet

# 本机路由应走有线设备（非 Wi-Fi en0 若本机 en0=Wi-Fi）
route -n get 192.168.31.210
python3 bin/delivery/network_path.py 192.168.31.210
# 期望 link_class=ethernet, wired_available=true
```

## 2. 复测

```bash
python3 bin/delivery/measure_physical.py --auto-default-lan --start \
  --remote-root ~/Workspace --n-ops 10000 --sync-mode cross_host_put \
  --out .omo/_knowledge/audits/g-del3-wired-$(date -u +%Y%m%dT%H%M%SZ).json
```

## 3. 达标判据

- `env_class=physical_multi_host`
- `n_ops ≥ 1000` 且 `p99_status=ok`（可信）
- `p99_ms < 100`
- `env_evidence.network_paths[].link_class` 尽量为 `ethernet`

达标后：更新 `phase-scope.yaml` 的 `last_physical_measure`，PR closeout。

## 4. 若有线仍 p99≥100

再开协议议题（批处理 / 端到端 replicate），**不要**降低分位门槛或改回 n&lt;1000。
