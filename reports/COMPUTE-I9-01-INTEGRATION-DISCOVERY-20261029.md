---
schema: md/v1
status: active
lifecycle: history
type: discovery-report
owner: governance-team
last-reviewed: 2026-11-06
bet_id: BET-Y2Q4-T10-279
created: 2026-11-06
---

# compute-i9-01 Phase 0 Discovery 事实矩阵

> **BET 依据**：`BET-Y2Q4-T10-279` · 规格 `docs/superpowers/specs/2026-10-29-compute-i9-01-integration.md`
> **Phase 0 条款**：「核实节点硬件、固件、微码、操作系统、网络位置、所有权与授权边界」
> 「核实 OMOStation、Work-Agent、Fleet-Ops、Local-Ops 的真实注册、Runtime 接口、Worker admission
> 与 Claim/Lease 语义」「输出事实矩阵、阻断项、变更申请；证据不足时保持 `HOLD`」。
> **配套件**：阻断项与变更申请见 `reports/COMPUTE-I9-01-PHASE0-PHASE1-20261029.md`。

## 0. 取证方式与边界

- 采集时刻：`2026-11-06T07:51:29Z — 07:58:13Z`（节点本地 `CST +0800` 07:51 — 15:58）。
- 通道：`ssh` BatchMode key-only，两个别名都验过（`compute-i9-ts` = Tailscale
  `100.99.19.109`、`compute-i9` = 单位网 `192.168.77.109`），两者均 `REACHABLE`。
- 动作面：**全部为只读命令**（`uname` `lscpu` `free` `lsblk` `df` `ip` `ss` `systemctl cat/show/
  is-active` `tailscale status` `nft list ruleset` `docker ps/inspect` `journalctl -n` `wc`
  `sha256sum` `grep` `ls`）。未安装、未修改、未重启任何服务或配置，未执行任何写操作。
- 显式不做的三件事：未读取 `/etc/lb-worker/auth-key` 内容（只记在位与权限）；未探测
  `192.168.77.0/24` 其他主机或任何未授权网段（规格安全条明文禁止）；未在节点上执行任何
  Worker 作业或 health 触发。
- 本文只登记**读数**。凡需要推断才能成立的结论，一律进 §7「待核」并给出取证方法。

## 1. 两条过期前提被实测推翻

| # | 记录在案的前提 | 出处 | 实测读数 | 判定 |
|---|----------------|------|----------|------|
| 1 | 「节点现场为 Windows 11 Pro；Ubuntu/rootless 方案尚未获重装授权」 | 规格 §当前已知前置阻断 | `Ubuntu 24.04.5 LTS`，kernel `6.8.0-147-generic`，`up 7 hours`（boot `2026-11-06 08:50:59 CST`） | **前提不成立**：重装已发生，Phase 1 的「等授权重装」这一闸已消失 |
| 2 | Phase 0 交付物为事实矩阵与两份报告 + `tasks/PROGRESS.md` | 台账 `write_surfaces` | `git ls-tree origin/main reports/ tasks/` 为空；全盘 `/usr/bin/find` 无 `COMPUTE-I9*` 文件 | **从未入库**：2026-10-29 的 discovery 产出没有任何被版本控制的痕迹，本件是第一次落盘 |

第 1 条的后果不是「好消息」而是**新的不合格面**：规格 Phase 1 要的是 `Ubuntu + rootless`，
而实测 OS 到位、rootless **没到位**（§4）。所以阻断项从「等授权改 OS」换成「等授权把容器面
与 Worker 面改成 rootless，并决定 `lb-worker` 的去留」。

## 2. 硬件、固件与微码

| 项 | 读数 | 取证书 |
|----|------|--------|
| CPU | `Intel(R) Core(TM) i9-14900HX`，`CPU(s): 32`，`24` cores × `2` threads，1 socket，L3 `36 MiB`，`VT-x` | `lscpu` |
| 微码 | `Current revision: 0x00000133`，`Updated early from: 0x00000119` | `dmesg` |
| BIOS | vendor `American Megatrends International, LLC.`，version `5.27` | `/sys/class/dmi/id/bios_*` |
| 机型 | `product_name` 未取（读空），`Chassis: desktop`，`Icon name: computer-desktop` | `hostnamectl` |
| 内存 | `31 GiB` total，采集时 `used 0` / `available 30` | `free -g` |
| 交换 | **无 swap**（`swapon --show` 空） | `swapon` |
| 磁盘 | `nvme0n1 476.9G`，model `Great Wall GW3500 512GB`，`ROTA=0`（SSD） | `lsblk -d` |
| 文件系统 | `/` = `/dev/mapper/ubuntu--vg-ubuntu--lv` ext4 `466G`，`used 17G`，`avail 430G`，`4%`（LVM） | `df -hT` |
| 主机身份 | hostname `compute-i9-01`；`Machine ID` / `Boot ID` 已读取但本件不登记（主机唯一标识，非 Phase 0 契约需要，仓为 public） | `hostnamectl` |
| 时钟 | `Asia/Shanghai (CST, +0800)`，`System clock synchronized: yes`（chrony） | `timedatectl` |

## 3. 网络、暴露面与认证

- 接口：`enp2s0 UP 192.168.77.109/24 metric 100`（单位网段）+ 一枚电信前缀全局 IPv6（`240e:` 段，
  本件不登记地址本身——仓为 public，可路由主机地址入库即对外暴露）；`tailscale0 100.99.19.109/32`；`wlo1 DOWN`；
  `docker0 DOWN 172.17.0.1/16`；`br-20cda023df20 UP 172.18.0.1/16`（compose 网络）+ 两对 `veth`。
- Tailscale：`1.104.4`（commit `9382131983ca…`），tailnet 账号 `xiamingxing725@`，本节点
  `100.99.19.109 compute-i9-01 linux`；同 tailnet 在线 peer 含 `mbp`、`unit-studio-01`、`bot-01`
  以及另两台家庭/单位侧设备（其主机名与地址本仓从未登记，本件不逐个列出）。
- 防火墙：`ufw Status: inactive`；`nftables active`；`firewalld inactive`。
  `nft list ruleset` 只见 tailscaled 自注入的 `ts-input` / `ts-forward`（含
  `100.64.0.0/10` 非 tailscale0 来源 drop），**`chain INPUT policy accept`** ⇒
  除 ts 链外没有主机侧白名单。
- 监听面（`ss -tlnp`）：`0.0.0.0:22`（sshd）、`0.0.0.0:8080`（`python3` pid 1450 = lb-worker）、
  `127.0.0.1:8787`（`docker-proxy`，仅回环）、`127.0.0.53/54:53`（resolved）、
  tailscaled 的 `100.99.19.109:443/61468/64990`。
- SSH 认证：`PermitRootLogin prohibit-password`、`PasswordAuthentication no`、
  `/root/.ssh/authorized_keys` 3 行全为 `ssh-ed25519`。
- **`0.0.0.0:8080` 是本件最重要的一条**：`/opt/lb-worker/app.py:968` 的原作者注释写明
  「测试实例用 `LB_WORKER_HOST=127.0.0.1` 只绑回环，避免把可执行作业的服务暴露到所有网卡」，
  `:969` 的取值顺序是 `host or env LB_WORKER_HOST or "0.0.0.0"`；而 `lb-worker.service`
  的 `Environment=` 段**只设了 `LB_WORKER_PORT=8080`，没有设 `LB_WORKER_HOST`** ⇒
  生产实例落在该注释所警告的默认值上，配合 `INPUT policy accept`，该「可执行作业」的 HTTP 面
  对整个 `192.168.77.0/24` 可达。本轮只读到绑定状态，**未做外部可达性验证**（禁止扫段）。

## 4. 现有控制面与运行态

### 4.1 lb-worker（与规格停止条件直接冲突）

`systemctl cat lb-worker` 全文要点：

| 字段 | 值 |
|------|-----|
| Unit 描述 | `LocalBrain lb-task/0.1 Worker Daemon (compute-i9-01)` |
| 运行身份 | `User=root`、`WorkingDirectory=/opt/lb-worker`、`ExecStart=/usr/bin/python3 /opt/lb-worker/app.py` |
| 重启 | `Restart=always`、`RestartSec=5s`；`is-enabled=enabled`、`ActiveState=active`、`NRestarts=0`、`MainPID=1450`、`ExecMainStartTimestamp=Fri 2026-11-06 08:51:11 CST` |
| 资源护栏 | `CPUQuota=2800%`（32T 中留 4 核）、`MemoryMax=26G`、`MemoryHigh=24G`、`TasksMax=2000`、`LimitNOFILE=65535` |
| 环境变量 | `LB_WORKER_PORT=8080`、`LB_GUARD_AUTH=1`、`LB_GUARD_LEASE=1`、`LB_GUARD_CONCURRENCY=1`、`LB_MAX_CONCURRENCY=24`、`LB_QUEUE_MAX=64`、`LB_AUTH_KEY_FILE=/etc/lb-worker/auth-key`、`PYTHONUNBUFFERED=1` |
| 凭证在位 | `-rw------- root root /etc/lb-worker/auth-key`（内容未读） |

代码与版本控制面：`/opt/lb-worker/app.py` = `40,896` 字节 / `981` 行 / sha256 前缀
`4e6eea40f201e8ac`；`/opt/lb-worker` 内**无 `.git`**，全盘 `maxdepth 3` 找不到任何 `.git` 目录；
`/usr/bin/find` 未见 `*.sqlite*` / `*.db`。该 `app.py` 内出现协议名 `lb-task/0.1`（`:3` `:73`）
与 `lb-task/0.2`（`:66`），并有成规模的 `lease` 实现（`:225` `:229` `:236` `:289` `:293-298` 等）。

仓侧对账（全部零命中，取证见 §5）：`lb-worker`、`lb-task`、`lb-task/0.1`、`LB_MAX_CONCURRENCY`、
`LB_GUARD` 在本仓**既无源码、无服务定义、无 registry 登记、无文档镜像**；`services/lb-worker`
只作为规格 §安全条 的否定式引用存在（`:59` `:67`）。 ⇒ 这是一台**在跑、但仓内不存在**的执行面。

health 耦合：`journalctl -u lb-worker` 显示每分钟一条 `"GET /health HTTP/1.1" 200 -`
（15:52:34 / 15:53:34 / 15:54:34 / 15:55:34 / 15:56:34 / 15:57:34，间隔精确 60 s）；
节点侧 `crontab -l`（root 与 ops）为空、`/etc/cron.d` 只有 `e2scrub_all` 与 `sysstat`
⇒ 调用方不在节点上。`ss -tn state established` 里有一条来自 `100.68.80.44:57584`
（该 IP 正是 tailnet 里的 `mbp`）的入站会话，方向与 60 s 周期一致。

### 4.2 容器面（rootful，且 rootless 面不存在）

- `docker.service` `active`、`containerd.service` active；`systemctl --user` 侧 `docker`
  `inactive`；`getent group docker` **无该组** ⇒ rootful 单机形态。
- 运行中容器（`docker ps`）：`respire-deploy-server-1`（image `respire-server:local`，
  `Up 7 hours (healthy)`）、`respire-deploy-db-1`（`docker.m.daocloud.io/library/postgres:16-bookworm`，
  `Up 7 hours (healthy)`）；compose `working_dir=/root/respire-deploy`，
  `RestartPolicy=unless-stopped`；对外仅 `127.0.0.1:8787`。
- `/opt/respire` 为空目录（mtime `Nov  5 21:55`），与上述 compose 目录不同名、无内容 ⇒ 用途待核。

### 4.3 与 OMOStation 体系的关系：零接入

`command -v` 探测 `omo` `cockpit-work-agent` `fleet-ops` `local-ops` `bos` **全部为空**；
`/root/.omo` `/root/runtime` `/root/.config/omostation` `/root/Workspace` `/root/ws-*` 全部不存在
⇒ 节点上没有任何本仓 Runtime、没有任何工作目录/检出、没有任何受治理 Worker 注册的痕迹。
Phase 2 的「隔离 worktree、受限工作目录」目前**没有基座**。

### 4.4 用户与授权边界

- 可登录 shell 用户两个：`root`(uid 0) 与 `ops`(uid 1000，`groups=adm,sudo,lxd,cdrom,dip,plugdev`)
  ⇒ `ops` 具备 sudo 能力，非受限执行账号。
- 本机（`mbp`）持有该节点的 root 级 SSH 私钥，两个 ed25519 key 已在 `~/.ssh/config:193-207`
  登记为 `compute-i9` / `compute-i9-ts` 两个别名（配置文件在本机、不入库，故本件不写私钥文件名）；
  该段注释即写明「单位网 i9-14900HX 高性能 CPU 执行节点」。
- tailnet 归属为个人账号 `xiamingxing725@`，物理网络位置在单位网段 `192.168.77.0/24`。
  ⇒ 个人 tailnet 与单位网段**同时**是这台机器的可达面，这条是变更申请 CR-2 的依据。
- 物理资产归属（单位配发 vs 个人）**没有任何仓内或机器内证据**，不做推断，见 §7。

## 5. Phase 2 五项契约的仓内位点与节点命中

| 契约 | 仓内实现位点（引用即用） | 节点命中 |
|------|--------------------------|----------|
| TaskEnvelope | `projects/omo/src/omo/resident/dispatch.py:85` `create_task_envelope()`（`:95` 注明 TaskObject v1.0，字段 `:107-119`）；契约文档 `projects/runtime/protocols/task-object-v1.md:7,33,59-72`；适配器 `projects/runtime/src/runtime/taskobject_adapter.py:23` `:76` | 0 |
| Claim | `projects/omo/src/omo/workflow/lifecycle_claims.py:25` `claim_policy()` `:64` `:75`；登记 `.omo/_truth/registry/agent-workflows.yaml:227`；锁存储 `bin/gac/coordination_store.py:136` `claims` 表 `:223` `claim_resource(ttl_hours=24.0)` `:322` `release_resource` | 0 |
| Lease | `.omo/_truth/registry/workers.yaml:26-30` `lease_policy`（heartbeat 300 s / warning 900 s / expired 1200 s / reclaim 1800 s）、`:34` `auto_requeue_on_lease_expired: true`；代码 `projects/omo/src/omo/blackboard/client.py:210` `claim_lease(...)`；ADR `0299-workflow-mesh-worker-lease-and-reclaim.md` | 仅 `app.py` 内自造的同名语义（`lb-task/0.1`），与本仓 `lease_policy` 无任何对接 |
| Runtime Adapter | `bin/gac/{pi,codex,omp}-worker-adapter.py` `bin/gac/orca-worker-start.py`；契约形状 `workers.yaml:132-146`（`transports.cli_prompt.command`、`worker_ack_protocol: omo-worker-origin-ack/v1`、`provider_conformance.backend_ref: omlxc`、`route_ref: bos://compute/aetherforge/infer`、`workspace_admission`）；`projects/omo/src/omo/orchestration_contract.py:84` `OrchestratorAdapter(Protocol)` `:567` `OrchestrationContractCoordinator` | 0 |
| Harness | `bin/harness:3`（docstring「8 阶段 DAG, unique S」）；SSOT `.omo/_truth/registry/harness-policy.yaml:1` `:12` `:18` `:29` `require_bet_claimable` `:30` `:51` `lease: true` `:265`；checker `bin/gac/harness-compliance-check.py` | 0 |

节点侧登记对账（「真实注册」这一项的读数）：`.omo/_truth/registry/compute/nodes.yaml` 只有
`local-mac` `macmini` `y7000p` `cloud` 四条；`docs/project-registry.yaml:438` `compute_nodes:` 只有
`MBP-M5-Max` `mac-mini-M4` `Y7000P-4070` 三条；`workers.yaml` 12 个 worker id 里无 i9；
`protocols/` 无主机登记表；两个 IP 在仓内**任何位置都未出现**。
⇒ `compute-i9-01` 目前不是受治理节点，只是一个被 SSH 可达、跑着未登记 rootful worker 的机器。

## 6. 与规格非目标 / 停止条件的逐条对照

| 规格条款（原文要点） | 实测 | 判定 |
|----------------------|------|------|
| Phase 1「Ubuntu Server、**rootless** 容器」 | Ubuntu 到位；容器 rootful、`docker` 组不存在、user docker inactive | **部分达成，rootless 未达成** |
| Phase 2「首批总运行 Worker ≤ 2」 | `LB_MAX_CONCURRENCY=24` | **超 12 倍**（该面还是未登记的旁路 worker） |
| Phase 2「同一仓库写入并发始终 ≤ 1」 | `LB_GUARD_CONCURRENCY=1` 名义为 1，但作业落在哪仓、`app.py` 如何解释该 flag，仓内无源码可比 | **不可判定**（待核 D-3） |
| Phase 2「默认只读；写入仅限批准的工作目录」 | 节点无任何工作目录、无检出；worker 绑 `0.0.0.0:8080` 且以 root 执行 | **不满足准入前提** |
| 非目标「不建立第二 Dispatcher/Broker/持久任务数据库」 | `lb-worker` 自带队列（`LB_QUEUE_MAX=64`）+ 自造 lease + 独立鉴权（`auth-key`），协议 `lb-task/0.1` 与仓内零交集 | **既成事实的第二执行面** |
| 安全条「现有 `services/lb-worker` 的 rootful systemd + SQLite 不作为本 BET 的最终集成实现；不得在其上直接开通生产流量」 | rootful systemd 半条**已命中**（见 §4.1）；SQLite 半条在 `/opt/lb-worker` 与 maxdepth 3 内未发现 `.sqlite*`/`.db` | **部分命中，另一半待核 D-2** |

## 7. 待核清单（每条给取证方法，不靠推断关闭）

| id | 未知项 | 取证方法 | 需要谁的授权 |
|----|--------|----------|--------------|
| D-1 | 节点物理资产归属（单位配发 vs 个人）与可执行变更的责任边界 | 只能由持有人口头/单据确认；机器内无标记 | principal |
| D-2 | `lb-worker` 状态持久化位置（规格断言 SQLite，本轮未在 `/opt/lb-worker` 与 maxdepth 3 找到 `*.sqlite*`/`*.db`） | 读 `app.py` 的 state 初始化段（需先把该文件纳入版本控制或取回上游） | principal（涉及第三方代码归属） |
| D-3 | `LB_GUARD_CONCURRENCY=1` 与 `LB_MAX_CONCURRENCY=24` 的实际语义关系（前者是否真的把同仓写并发压到 1） | 读 `app.py` `:225-300` lease 段与调度段 | 同上 |
| D-4 | 每分钟 `GET /health` 的调用方代码位置（节点无 cron；established 指向 `mbp`） | 在 `mbp` 侧查 launchd/cron 与仓内 `bin/`+`projects/` 的 health 扫描器；本仓 `git grep` 对 `:8080` 零命中 | 无需（只读） |
| D-5 | 出站 `39.105.203.11:8443` 归属与用途（公网北京 IP，非 tailscale DERP 段） | `ss -tnp` 取发起进程 + DNS/证书反查 | 涉及外部访问，须显式授权 |
| D-6 | `respire`（容器 + `/root/respire-deploy` + 空目录 `/opt/respire`）与本 BET 的关系 | 由 `respire` 属主说明；本仓对 `respire` 零登记 | principal |
| D-7 | 微码 `0x133` 是否即 14900HX 稳定性问题的目标版本 | `dmesg` 已给 revision；对照 Intel 微码发布记录 | 无需（只读） |

## 8. Phase 0 结论

- Phase 0 的**事实矩阵已完成**（本件），阻断项与变更申请另件（`reports/COMPUTE-I9-01-PHASE0-PHASE1-20261029.md`）。
- 规格「证据不足时保持 `HOLD`」仍然成立的对象是 **Phase 2/3**，不再是「OS 未就位」：
  节点尚未登记、rootless 未到位、第二执行面 `lb-worker` 未定性、`D-1`~`D-3` 三项未知。
- 本件**不关闭** `BET-Y2Q4-T10-279`：其 `done_when` 第 2 项要求「得到人类部署授权记录」、
  第 4 项要求「Golden Slice 有人工验收，不以 Agent 自报成功替代」，二者都不是 Agent 可自证的对象。
