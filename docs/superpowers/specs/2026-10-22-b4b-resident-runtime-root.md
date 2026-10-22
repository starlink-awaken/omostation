---
schema_version: specification/v1
spec_version: 1.0.0
title: 服务注册表必须承载 per-service 运行根选择器，常驻族才能改道到运行时安装位
bet_id: BET-Y2Q4-T10-265
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-22
---

# 服务注册表必须承载 per-service 运行根选择器

> 范围：`bin/mof/gen-service-configs.py` 的运行根解析 + `.omo/_truth/registry/services.yaml`
> 的 per-service 字段 + 对应测试。不改 `repo_root` 的定位链、不动 launchd 命名空间策略、
> 不在本 spec 里执行 plist 改道（改道是合入后的独立动作，需单独授权已给，见 §5）。

## 1. 缺陷证据（实测，2026-10-22）

ADR-0456 B4b 的目标措辞是「把**常驻面**的路径改到运行时安装位」。当前生成器只认一个根：

- `bin/mof/gen-service-configs.py:28-54` 的 `workspace()` 惰性缓存 `repo_root.canonical_root()`；
- `_resolve_path()`（origin/main 基线 `:190`）对相对入口一律 `return str(workspace() / p)` —— **注册表里没有任何字段能表达"这一条不跟检出根"**。

于是把常驻族改道，只有三条路可走，前两条已被实测否证：

| 路线 | 为什么不行 |
|---|---|
| CLI flag（如 `--root install`） | E1 判据 `run_e1_drift()` 调的是 `[sys.executable, __file__, "--check", "--json"]`，**不带 flag**；门禁调用点同样无 flag（`gac-local-gate.py:199 --validate`、`:203 --check`、`governance-semantic-gate.py:218 --validate --json`）。flag 选根 ⇒ 生成与校验走两个根 ⇒ 11 条相对路径服务**逐条报 drift**。 |
| env 变量 | 同上，且更糟：`run_e1_drift()` 的 docstring 明确禁止传 `OMOSTATION_ROOT`（*"若在 worktree 里改根, 16 条相对路径服务会全部报 drift —— 那是测量方法造假, 不是现实"*）。env 选根 = 让 E1 的读数依赖调用环境。 |
| **注册表内容** | `--write` 与 `--check` 共用 `main()` 里同一个服务循环和同一个 `gen_launchd_plist(svc)`，字节比较就在该循环内（`existing.strip() != plist.strip()`）。选择器写在条目里，两侧**天然一致**，无需任何调用侧参数。 |

仓库里唯一的"安装位服务"先例是 `com.omostation.zhixing-projection-fullrefresh`，它用
`generate: false` + `config_source` + `content_digest` 走**观测登记**路径 —— 而它自己的 notes
就承认 *"generate:false 会跳过生成及 --check 的逐字节比较，零 drift 不能证明本条或整个 T237 完成"*。
把常驻族照此办理，E1 会从"真的在比"变成"不比了所以绿"，是**假绿**，不是完成。

另需固定两个基数事实（本轮不得据其推论）：

- 生成器自有服务集合 = **11 条**（`scheduler: launchd` + `enabled` + `generate` 非 false），入口**全部相对路径**
  （0 条绝对），分属 `com.l4`=8 / `com.omostation`=2 / `com.agora`=1；注册表总条目 378。
  常驻族 **label 共 10 条，其中 `enabled: true` 的只有 6 条**（decision / execute / signals / inbox / promote /
  event-ingest）；orchestrator / sediment / monitor / heartbeat 4 条为 `enabled: false`，生成循环根本不碰。
  11 条**全部无 `watch_paths`**；只有 morning-brief / mail.daemon / agora.daemon / republisher 4 条带 `outputs`，
  常驻族 6 条**没有 outputs** ⇒ 本轮真正需要改解析点的是 entrypoint 那一处（`gen_launchd_plist()` 里对 `_resolve_path()` 的调用），
  但 `runtime_root` 的语义必须覆盖该条目的**所有相对路径字段**（含 outputs），
  否则一个服务会一半在安装位一半在检出 —— 与 AGENTS.md §7「不许写半份镜像」同形。
- `--reality-check` 的 E2/E5 基线（2026-10-22 对 `origin/main` 那份注册表的实时读数）：
  **E1 0 / E2 0 / E5 2**（`e5_disabled_residual` 1 + `e5_enabled_missing` 1），`owned_declared` = `owned_installed` = 47。
  ⇒ E2 不是本 BET 的成果也不是本 BET 的验收；E5 的 2 条属另行准入面（T10-259 清单）。
  ⚠️ 本节初稿曾写"E2=5"，那是把 **`~/Workspace` 本地工作树**（落后 origin/main，缺 5 条 observe-only 回填）
  当成 main 状态读的错读（PITFALL-COO-006 同形）。基线一律对 `git show origin/main:` 的那份量。
- **注册表来源与运行根无关，但与时序有关**：`--check`/`--write` 读的注册表是
  `services_yaml_path()` = `workspace()` = `canonical_root()`，**不是当前检出**；`--registry` 只喂
  `--reality-check`。后果是两条时序判据：① 合入前在 worktree 里改注册表，本地 E1 读数不变（实测 0）；
  ② 合入后必须先让 `~/Workspace` 快进到含本改动的 commit，再执行 plist 改道 ——
  顺序反了，`--check` 会拿"没有 `runtime_root` 的旧注册表"去比"已改道的 plist"，
  当场造出 **6 条 drift**，那是时序不是回归。
- 本轮注册表增量的隔离实测：对 `origin/main` 那份与"加 6 条 `runtime_root`"的这份各跑一次
  `--reality-check`，上表全部读数**逐项相等**（`git diff --stat origin/main` 对该文件 = 6 insertions, 0 deletions）
  ⇒ 加字段本身不动任何桶。

## 2. 契约

- **C1 字段语义**：新增 per-service 可选字段 `runtime_root` ∈ {`checkout`, `install`}；
  **缺省即 `checkout`**，语义与今日逐字节等价（现有 11 条不加字段时生成的 plist 不变）。
- **C2 只由注册表内容决定**：生成器**不得**从 env、CLI flag、`__file__` 反推或 cwd 推断运行根。
  理由见 §1 表 —— 这是 E1 保持 0 的**结构前提**，不是风格偏好。
- **C3 调用时刻解析**：`install` 的根必须在**生成该条 plist 时**由 `repo_root.install_root()` 取，
  不得提升为模块级常量（AGENTS.md §7「写路径要在调用时刻解析」；import 时冻结会让晚声明的 profile
  停在旧根上且**没有测试会红**）。
- **C4 fail-closed**：条目声明 `runtime_root: install` 而 `install_root()` 返回 `None` 时
  **拒绝生成/写入并报错**，禁止静默退回检出根。"plist 写着安装位、跑的却是检出"正是 B4b 要消灭的那个谎。
- **C5 校验面收敛**：`validate_service_declaration()` 拒绝未知取值、并**只允许 `scheduler: launchd`**
  的条目携带该字段 —— 本生成器**不写 crontab**（cron 条目在这里只做准入校验，真正的 crontab 由
  `install-resident-cron.sh` 一类外部安装器写出），所以 `runtime_root` 挂在 cron 条目上没有任何消费者，
  那是半镜像而非能力。不新增 env 名、不改 `repo_root` 定位链、不改 `launchd_namespace` 命名空间策略
  （`NAMESPACE_KEY:303` / `EXEMPT_CLASSES:304` / `workspace_prefixes` at `services.yaml:6169`）。
- **C6 写面可控**：新增可重复 `--only <label>`，用于把 `--write` 的爆炸半径限定到指定条目；
  **不带 `--only` 时行为与今日完全一致**（默认不窄化，避免任何一次全量重写顺手改到别人的服务）。
- **C7 本 BET 只迁一族**：注册表改动限于 `com.l4.resident.*` 中 **`enabled: true` 的 6 条**加
  `runtime_root: install`。同族 4 条 `enabled: false` 保持缺省 —— 记为**已声明的边界**（它们若被重新
  启用，会先落在检出根，直到下一批覆盖）。
  `com.omostation.zhixing-projection-republisher` 属 codex-zhixing-controller 的 lane，**不碰**。
- **C8 名字已有多义，靠位置消歧**：`runtime_root` 在本仓别处已指 zhixing registration 的 JSON 字段
  （`tests/test_zhixing_host_sync.py:233`）与 `omo_state.py` 的自有概念。本字段**只作为
  `services.yaml` 服务条目内的键存在**，解析点唯一（§3 的 `service_root()`），不得被任何别处读到。

## 3. 实现点

| 面 | 改法 |
|---|---|
| `bin/mof/gen-service-configs.py` | ① 抽出 `service_root(svc)`（唯一读 `runtime_root` 的函数，`install` 走 `install_root()`、None 即抛 `ValueError`）② `_resolve_path()` 的相对分支由 `workspace()` 改为调用侧传入 `service_root(svc)` ③ `validate_service_declaration()` 加 C5 两条拒绝 ④ `main()` 加 `--only`（可重复），在 `main()` 服务循环入口按 label 过滤 |
| `.omo/_truth/registry/services.yaml` | 常驻族 6 条各加 `runtime_root: install` |
| `tests/unit/test_gen_service_runtime_root.py`（新，9 个用例） | ① 缺省等价：不加字段的条目，与显式 `checkout` 产出的 plist 逐字节相同，且根仍是 `workspace()`（含真实注册表 372 条未声明项的逐条核对）② `install` 命中：根取自 `install_root()`，entrypoint / watch_paths / outputs **全部**落进安装位，字符串里不出现检出根 ③ fail-closed：`install_root()` 为 `None` 时 `service_root()` 与 `gen_launchd_plist()` 都抛 `ValueError`（含"拒绝退回检出根"与条目名）④ 无调用侧泄漏：`gen_launchd_plist` 只收 `svc`（AST 断言签名）、`run_e1_drift` 的命令字面量恰为 `["--check","--json"]` 且 `subprocess.run` 不带 `env=`、清掉 profile env 并换 cwd 后输出逐字节不变 ⑤ 拒绝未知取值 / 非 launchd 条目，且缺省必须干净 ⑥ 尺自身反证：真实注册表整体无 `runtime_root` 违规（先断言），注入一条合成坏值必须恰好被点名一条 ⑦ `--only`：只写指名条目、拼错 label 返回 1 且不新增 plist、不带 `--only` 时行为不变（fake LaunchAgents 目录，不碰机器）＋ `--registry` 只喂 `--reality-check`（AST 断言 `args.registry` 的读者全在该分支内） |

registry 的 `note` 字段一律避免行内 `: `（AGENTS.md §7⑨：`_load_yaml` 类"解析失败退回空"会让登记面
整块消失而不报错）。

## 4. 验收

1. 上述用例跑绿，且**变异对照**（两处独立变异，实测读数）：
   - M1 把 `service_root()` 的 `install` 分支改回 `return workspace()` ⇒ **②③⑦ 红**（3 failed / 6 passed）；
   - M2 删掉 `validate_service_declaration()` 里 `runtime_root` 那一段 ⇒ **⑤⑥ 红**（2 failed / 7 passed）；
   - 两次变异后均按 sha 逐字节还原（`32fcd67a0e0c…`）。① ④ 在两次变异下保持绿是**预期**：
     ① 断言的正是"缺省行为没被改动"，④ 断言的是"没有新的选根缝"，M1/M2 都不引入缝。
2. **E1 保持 0**：合入并执行改道后，`python3 bin/mof/gen-service-configs.py --check --json` 的
   drift 计数为 0（这是本 BET 的存在理由 —— 授权措辞原文即"这是唯一能让 E1 保持 0 的路径"）。
   前置时序见 §1 末条：**先**让 `~/Workspace` 快进到含本改动的 commit，**再**改道；否则造出的是 6 条假 drift。
3. 常驻族 6 个 plist 的 `ProgramArguments` 全部落在 `install_root()` 之下，且服务**仍能加载**：
   复核判据用 launchd 自己的 `launchctl print` arguments + 进程 cwd（`lsof -p <pid> | grep cwd`），
   **不用** `ps -o args=`（可能显示指针解析后的路径，AGENTS.md T241）。
4. `launchctl kickstart -k` **不重读 plist**，改道必须 `bootout` + `bootstrap`（AGENTS.md T241）。
5. 回滚留档：改道前把 6 个 plist 原样复制到带时间戳的目录，回滚 = 复制回 + 同一对 `bootout`/`bootstrap`。
6. `make gac-local-gate` 绿；除本轮 write_surfaces 外无跟踪脏项（生成态不随功能 PR 走）。
7. **E2 / E5 明确不在验收内**，按 §1 基线读数（E2=5、E5=2）另行登记，本 BET 不得据其判定成败。

## 5. 中止判据

- 若 E1 归零只能靠给 `--check` 加 flag/env、或把条目改成 `generate: false` 跳过比较 → **停止**（§1 假绿）。
- 若需要动 `repo_root` 定位链、新增 env 名、或改 `launchd_namespace` 策略才能过验收 → **停止**。
- 若需要碰 `com.l4.resident.*` 之外的族（尤其 republisher / agora / mail）→ **停止**，那是别人的 lane。
- 若改道后某服务 `launchctl print` 显示加载失败且根因指向运行根 → **回滚**并保留证据，不强行收尾。
- 若既有用例因新字段转红，且只能靠改窄断言转绿 → **停止并保留原判据**。
- **不宣布 ADR-0456 B1/B3/B4/B5/B4b 或整个 plan 完成。**

## 6. 非目标

不把权威 ledger 翻到安装位；不迁移常驻族以外的服务；不清理 §1 列出的 5 个 E2 属主 plist（未登记项的
处置需逐条确认来源）；不改 `services.yaml` 的 `enabled` / `generate` 语义；不动 crontab；
不做 B4b 批次 2+（决策 3 与逐批授权面仍属 principal 决定）。
