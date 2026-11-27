---
schema: md/v1
status: active
lifecycle: history
type: change-request
owner: governance-team
last-reviewed: 2026-11-27
bet_id: BET-Y2Q4-T10-279
created: 2026-11-06
---

# compute-i9-01 Phase 0 阻断项与 Phase 1 变更申请

> 事实基线与全部读数见 `reports/COMPUTE-I9-01-INTEGRATION-DISCOVERY-20261029.md`（下称「矩阵」）。
> 本件只做三件事：把阻断项点名、把需要授权的变更逐条列成可批可拒的申请、把 Agent 不能自证的两道闸说清楚。
> **本件不执行任何变更**，也不改变 `BET-Y2Q4-T10-279` 的 `status`。

## 1. 阻断项现状（相对规格 2026-10-29 版）

| id | 规格记载的阻断 | 现在是否仍然阻断 | 依据 |
|----|----------------|------------------|------|
| B-1 | 节点为 Windows 11 Pro，Ubuntu 方案未获重装授权 | **否——前提已消失**（已装 Ubuntu 24.04.5 LTS 并常驻 7 h） | 矩阵 §1 表第 1 行 |
| B-2 | rootless 容器方案未落地 | **是**（rootful docker，`docker` 组不存在，user docker inactive） | 矩阵 §4.2 |
| B-3 | 第二执行面 `lb-worker` 未定性、未纳管 | **是**（rootful systemd + 自造 `lb-task/0.1` lease + 仓内零镜像） | 矩阵 §4.1 §5 |
| B-4 | 节点未进入任何受治理登记面 | **是**（`compute/nodes.yaml` 4 条无它、`project-registry.yaml` `compute_nodes:` 3 条无它、`workers.yaml` 12 id 无它、两个 IP 全仓零命中） | 矩阵 §5 |
| B-5 | 所有权与授权边界未核实 | **是**（tailnet 属个人账号、物理位于单位网段；资产归属无证据） | 矩阵 §4.4 D-1 |
| B-6 | Phase 0 交付物未入库 | **本件与其配套件即闭合此项** | 矩阵 §1 表第 2 行 |

## 2. Phase 1 变更申请（逐条可批可拒）

每条按四类步骤写：参照（证据出处）→ 判断（口径出处）→ 执行（改什么）→ 审批（谁批、可否回滚）。

### CR-1 决定 `lb-worker` 的去留

- 参照：矩阵 §4.1（unit 全文要点、`app.py` 40,896 B / 981 行 / sha256 前缀 `4e6eea40f201e8ac`、
  无 `.git`、协议名与 lease 实现在仓内零命中）；规格 §安全条「`services/lb-worker` 不作为本 BET 的
  最终集成实现；不得在其上直接开通生产流量」。
- 判断口径：规格非目标「不建立第二 Dispatcher/Broker/持久任务数据库」——现成事实是一个带队列
  （`LB_QUEUE_MAX=64`）、带自造 lease、带独立鉴权（`/etc/lb-worker/auth-key`）的执行面。
- 执行（三选一，均需授权）：
  (a) **纳管**：把 `app.py` 取回上游并登记为本仓服务面，再按 Phase 2 复用 TaskEnvelope/Claim/Lease；
  (b) **降级为 observe-only**：停 `enabled`、保留二进制作证据，另建受治理 Worker；
  (c) **拆除**：`systemctl disable --now lb-worker` + 归档 unit 与 `app.py`。
- 审批：principal。**不可自行执行**——(b)(c) 会让一个正在服务 `/health` 每 60 s 轮询面的进程消失
  （矩阵 §4.1 health 耦合；调用方位置尚未定位，D-4），属于「先断消费者再补方案」的外发动作。
- 回滚：unit 文件与 `app.py` 先备份到 `/root/`（或取回仓内），`systemctl enable --now` 即恢复。

### CR-2 收紧 8080 暴露面

- 参照：`lb-worker.service` 的 `Environment=` 段无 `LB_WORKER_HOST`；`app.py:968-969` 原作者注释
  警告「暴露到所有网卡」正是当前配置；`ss -tlnp` 读数 `0.0.0.0:8080`；`nft` 仅有 tailscale 自注入链、
  `INPUT policy accept`；单位网段 `192.168.77.109/24`。
- 判断口径：规格 §安全条「默认只读；任何写入仅限批准的工作目录和原生授权路径」+「不扫描未授权网段」
  ——一个以 root 执行作业、对整段可达的 HTTP 面不满足这两句。
- 执行：二选一（不叠加）——(a) `Environment=LB_WORKER_HOST=100.99.19.109`（只绑 tailscale0）
  或 `127.0.0.1` + SSH 隧道；(b) 在 Tailscale ACL 里把 `100.99.19.109:8080` 限到指定 principal 节点。
- 审批：principal + tailnet 管理员（同一人则一次）。**(a) 会改远端服务配置并需重启该服务**，
  属「部署远端服务」类动作，规格明文要求独立明确授权。
- 回滚：恢复原 unit 文件 + `daemon-reload` + 重启；改动只有一行 `Environment=`。

### CR-3 rootless 容器迁移

- 参照：矩阵 §4.2（rootful docker、两容器 healthy 7 h、compose 工作目录在 `/root/`、
  `docker` 组缺失、`--user` 侧 inactive）。
- 判断口径：规格 Phase 1 明文「rootless 容器」。
- 执行：为专用服务账号（现成候选 `ops`，uid 1000，已在 `sudo`/`lxd` 组——迁移前应先把它的
  sudo 能力去掉，否则 rootless 只是换个壳）启用 `dockerd-rootless`，把 `respire-*` compose
  迁出 `/root/`。
- 审批：principal。**涉及既有正在健康运行的业务容器搬迁**，会中断 `respire`，且 `/opt/respire`
  空目录与 compose 目录关系未定性（D-6）⇒ 需 `respire` 属主确认。
- 回滚：rootful 配置与 compose 目录原样保留即可回切；迁移本身不删数据（postgres 卷需先做快照）。

### CR-4 节点进入受治理登记面

- 参照：矩阵 §5（三张登记表面均无该节点；两 IP 全仓零命中）。
- 判断口径：规格 Phase 0「真实注册」+ ADR-0433 异构三节点调度 + `.omo/_truth/registry/compute/nodes.yaml`
  现有四条目形状。
- 执行：新增登记，字段照 `nodes.yaml` 现有条目（含 `runtime_root`/分区），并在
  `docs/project-registry.yaml` `compute_nodes:` 补一条；Worker 面按 `workers.yaml:132-146`
  契约形状声明（`workspace_admission`、`provider_conformance`），并发预算写 ≤2。
- 审批：**这条 Agent 可自主执行**（纯仓内登记、可整份 revert），但必须等 CR-1/CR-2/CR-3 的方向定了
  再写，否则登记进去的是一个语义不明的旁路面。故本件把它列为「待前置」而不是「立即做」。
- 回滚：删该条目即可，一次 `git revert`。

### CR-5 受限工作目录与资源/并发预算

- 参照：矩阵 §4.3（节点无任何检出、无工作目录）；§6 对照表（`LB_MAX_CONCURRENCY=24` 超
  Phase 2「首批总运行 Worker ≤ 2」12 倍）。
- 判断口径：规格 Phase 2「隔离 worktree、最小权限、网络白名单、资源预算、独立验证与人工审批」。
- 执行：在节点上建专用非 root 作业账号 + 限定目录（建议 `/srv/workers/<id>`，当前 `/srv` 为空），
  作业面并发硬限 ≤2、同仓写并发 ≤1，出站白名单（先解释 D-5 的 `39.105.203.11:8443` 再落白名单）。
- 审批：principal（在他人机器上创建账号/目录属部署动作）。
- 回滚：`userdel` + `rm -rf` 该目录（自建树，无既有数据）。

## 3. Agent 不能自证的两道闸

- 闸 1 —— 台账 `done_when[1]`：「Phase 1 … 提案完成，**并得到人类部署授权记录**」。
  本件即提案；授权记录必须是 principal 对 CR-1…CR-5 的逐条决定，不能由「全面推进」这类
  总括授权代替——规格 Phase 1 的原文是「未获**独立明确**授权，不重装系统、不格式化磁盘、
  不改 BIOS、不改防火墙、不部署远端服务」。
- 闸 2 —— 台账 `done_when[3]`：Phase 3 八项验证「均有独立回执」且「Golden Slice 有**人工验收**，
  不以 Agent 自报成功替代」。八项里 1/2/3/4/5/6/8 七项都需要在节点上真实启停作业与断网，
  全部依赖闸 1 先开。
- 结论：`BET-Y2Q4-T10-279` 的正确状态仍是 `in_progress`，`completion_evidence.overall_state`
  仍是 `evaluating`。本轮只把 `done_when[0]`（Phase 0 事实矩阵）从「无交付物」推进到「已入库」。

## 4. 顺带登记的三项记录缺陷（不在本 BET 范围，只点名不修）

1. 规格 `docs/superpowers/specs/2026-10-29-compute-i9-01-integration.md` 的「当前已知前置阻断」
   段（`last-reviewed: 2026-11-02`）已被 §1 B-1 否证。**本件不改该文件正文**：它已被台账
   `accepted_specifications[0].content_digest` 绑定，改正文会使摘要失配（`SPEC_FRONTMATTER_VERSION_MISMATCH`），
   正解是走一次规格修订（supersede 或新 `spec_version`），由 principal 决定。
2. 台账 `write_surfaces` 声明的 `reports/…` 与 `tasks/PROGRESS.md` 两个顶层目录在仓内**没有先例**
   （house convention 是 `docs/reports/`，338 件跟踪文件；`document-governance.yaml` 的 7 个 surface
   都不覆盖 `reports/**` 或 `tasks/**`）。本轮按台账声明原样落盘以保 D0 可过，命名偏差留此记录。
3. `lb-worker` 与 `respire` 都是「机器在跑、仓内不存在」的面，与 ADR-0456 F1 那一族
   「生产者/消费者/契约三方错位」同形；把它们纳入登记是 CR-1 与 CR-4 的前置，不是本轮产物。

## 5. 人类部署授权记录（2026-11-25）

> 闸 1 的解锁记录。形式：principal 于 2026-11-25 会话对 CR-1…CR-5 的**逐条选择**
> （四条 CR 各自独立选项问答，非总括授权，满足规格「独立明确授权」原文）。

| CR | 决定 | 生效前提 |
|----|------|----------|
| CR-1 `lb-worker` 去留 | **(a) 纳管** —— 取回 `app.py` 入仓登记为服务面，Phase 2 按 TaskEnvelope/Claim/Lease 契约改造；现有 `/health` 消费者不断（D-4 调用方未定位） | 节点恢复可达（只读取回） |
| CR-2 8080 暴露面 | **(a) 绑 tailscale0** —— unit 加 `Environment=LB_WORKER_HOST=100.99.19.109`，`daemon-reload` + 重启；unit 先备份到 `/root/` 与本仓；回滚 = 恢复原 unit 一行改动 | 节点恢复可达 |
| CR-3 rootless 迁移 | **授权执行** —— 前置依次：D-6 定性（`/opt/respire` 空目录与 compose 关系）→ postgres 卷快照 → 剥 `ops` sudo → `dockerd-rootless` + compose 迁出 `/root/`；respire 属主即 principal 本人（本项授权即属主确认可中断） | 节点恢复可达 |
| CR-4 节点入登记面 | **按本件 §2 CR-4 原约定由 Agent 自主执行**（纯仓内登记、可整份 revert）；方向已定，随本授权记录一并落盘 | 无（仓内）——已执行 |
| CR-5 受限作业面 | **授权执行** —— 前置：先查清 D-5（`39.105.203.11:8443` 出站归属）再落出站白名单；建专用非 root 账号 + `/srv/workers/<id>`，作业面并发 ≤2、同仓写 ≤1 | 节点恢复可达 |

- **授权落盘时运行态**：2026-11-25 实测节点双通道不可达（tailscale `100.99.19.109`
  offline last-seen 14d，`unit-node-04`；单位网段本机无路由）——与 2026-10-29 discovery
  时两通道 REACHABLE 的状态已变。CR-1/CR-2/CR-3/CR-5 均为**远端动作**，以节点恢复可达
  为执行前提；本授权不因等待失效。
- CR-2/CR-3/CR-5 授权中的部署动作在节点可达后由 Agent 执行时逐项留独立回执（含失败
  恢复路径），进 Phase 3 八项验证面。
- **闸 2（Golden Slice 人工验收）未因此次授权打开**：`BET-Y2Q4-T10-279` 保持
  `in_progress`，Phase 3 收口仍需 principal 人工验收。

## 6. 节点可达性回读与唤醒尝试（2026-11-28）

> 目的：把 §5「节点恢复可达」这个前置条件的**当前真实状态**写进仓内可复核的证据面，
> 并明确「哪些腿 Agent 已经做完、哪一条腿物理上做不了」。
> 本节只做只读探测 + 唤醒尝试，**不部署任何远端服务、不改任何远端配置**。

### 6.1 读数

| 面 | 观测点 | 读数 | 含义 |
|----|--------|------|------|
| tailnet 控制面 | 本机 `tailscale status --json` | peer `compute-i9-01` / `unit-node-04` / `100.99.19.109`，`Online: false`，`LastSeen: 2026-11-11T08:00:22.1Z` | 控制面认为已离线 16 天 |
| fleet-ops 运行态 | `~/.local/state/fleet-ops/state.json` | `compute-i9-01` = `down`，reason `ssh: connect to host 100.99.19.109 port 22: Operation timed out`，`fails: 4267`，`observed_at: 2026-11-27T23:36:01Z` | 连续失败 4267 次 |
| fleet-ops 告警 | `~/.local/state/fleet-ops/alerts.json` → `compute-i9-01/reach` | `status: firing`，`first_ts: 2026-11-11T10:44:50Z`，`count: 4266`，severity `warn` | 告警自 11-11 起持续 firing |
| lab 网段 L2 | lab 段内主机 `unit-ops-01`（192.168.77.31） | `ip neigh show 192.168.77.109` → `FAILED`；`ip route get` → `dev enp170s0` | **二层邻居解析失败** ⇒ 机器不响应 ARP |
| lab 网段 L3 | 本机 `nc -z 192.168.77.109 22 / 8080` | 均 closed/timeout；本机 `arp -an` 无该 IP 表项 | 无 TCP 端口、无 ARP 表项 |
| tailnet L3 | 本机 `ping 100.99.19.109` | 2 发 0 收，100% 丢包 | 不可达 |

判读：`FAILED` 的 ARP 邻居项 + 两条通道同时无响应，指向**机器处于下电或网卡链路未起**，
而不是防火墙/服务未监听/权限问题——服务未监听时 ARP 仍会解析成功。

### 6.2 唤醒尝试（三条路径，均未唤醒）

`fleet-ops/tools/wol.py` 的三条路径逐条试过：

| 路径 | 命令 | 结果 | 备注 |
|------|------|------|------|
| 工具经中继（bot-01） | `wol.py --relay bot-01 --host compute-i9-01` | ❌ | 中继机 `bot-01`（100.99.63.14）SSH 超时，包未发出 |
| 工具经中继（unit-ops-01） | `wol.py --relay unit-ops-01 --host compute-i9-01` | ❌ | 该机在 lab 段内，但工具的多行 snippet 经 `ssh` 传参后被远端 shell 拆行 ⇒ 远端 `python3 -c` 语法错误（实测报 `SyntaxError`），包同样未发出 |
| 手工单行 snippet 经 unit-ops-01 | 单行 `python3 -c` 在 `unit-ops-01` 上 `sendto(255.255.255.255:9)` ×3 | 远端回 `relayed`（rc=0） | **包确实发出**，但 2 分钟内 L2 邻居仍 `FAILED` |
| 本机定向广播 | `bind(192.168.77.2)` 后 `sendto(192.168.77.255:9)` ×3 + `255.255.255.255` ×3 | 发出 | 本机在 lab 段内（en7 = 192.168.77.2/24）；同样 2 分钟无 `FAILED` 解除 |

- 唤醒后连续 8 轮 × 15 s 轮询 `ip neigh show 192.168.77.109`（自 `unit-ops-01` 读），
  全部返回 `FAILED`；`ping 100.99.19.109` 全程 100% 丢包。
- 结论：**Wake-on-LAN 在该机型/该网卡上无效**。`fleet-ops` 清单里 11 台机器登记了
  `wol_mac`，但工具 docstring 自己记着「8 台 bot 群实测 Wake-on: g」——**i9 这台从未被验证
  过可唤醒**（BIOS/UEFI 的 Wake-on-LAN 选项与网卡 WoL 开关状态均未知）。
- 顺带发现（不在本 BET 范围，只点名）：`fleet-ops/tools/wol.py:54-63` 的 `wake_via_relay`
  用多行 `python3 -c` snippet 经 `ssh` 传参，远端 shell 会按行拆分导致语法错误 ⇒ **中继路径
  在任何机器上都不可能成功**，工具却把它报成 ❌ 而不是「包未发出」。这是被本次尝试
  顺带证伪的既有缺陷，修复归 `fleet-ops` 仓。

### 6.3 对 Phase 2 / Phase 3 的影响

- Phase 2 的四个远端腿（CR-1 纳管 `lb-worker` / CR-2 绑 tailscale0 / CR-3 rootless 迁移 /
  CR-5 受限作业面）全部要求在节点上执行——节点不在线，一条都做不了。
- Phase 3 的八项验证里有七项需要「在节点上真实启停作业与断网」，同样做不了。
- 因此本 BET 的正确状态仍是 `in_progress` / `overall_state: evaluating`：
  **Gate 1（人类部署授权）已开但被物理前置阻塞；Gate 2（Golden Slice 人工验收）仍未开。**

### 6.4 解锁需要的一次性人工动作

节点必须由人在现场或通过带外管理（IPMI / 智能插座 / 物理电源键）**上电**，
且需确认 BIOS/UEFI 里 Wake-on-LAN 处于启用状态（WOL 无效即意味着这两处之一未开）。
上电后按以下顺序恢复：

1. `ping 100.99.19.109` 通 → `ssh unit-node-04` 登录（别名见
   `fleet-ops/generated/ssh_config.fleet:313`）。
2. 复核 §2 CR-1…CR-5 的「生效前提」列：节点可达即解除 CR-1/CR-2/CR-3/CR-5 的等待态。
3. Agent 按 §5 授权记录逐条执行远端腿，每条留独立回执。
4. 进 Phase 3 八项验证，最后由 principal 做 Golden Slice 人工验收（Gate 2）。

