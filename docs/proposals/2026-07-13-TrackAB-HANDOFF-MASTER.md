# Track A/B · 全面交接总索引（durable，放 outputs 免被并发 clean）

> 生成: 2026-07-13/14 · 这是单一权威交接件。仓库内 git 不可靠（并发 agent starlink-awaken 会改写 HEAD、删分支、clean 未跟踪文件），故权威副本放 outputs 文件夹。
> 配套文件（同 outputs 目录）: `2026-07-13-B2-v2-distributed-state-sync-buspowered.md`

## 0. 战略主线（未变）
别再刷治理债 → 先让健康分"绿色变真"(Track A) → 再迈多机第一步(Track B)。ADR-0180(bus-foundation 也是声明≠执行)再次印证该主线。

## 1. 已完成 + 安全状态
| 项 | 状态 | 证据/位置 |
|----|------|-----------|
| A1 BOS 鸿沟重审 | ✅ | 真实断层 5(非102)；审计脚本曾入仓 |
| **A2 resolve 修复** | ✅ 代码入库+验证 | kairon `c167cc0`(cli.py×2+测试×2,仍是 HEAD 祖先✅) · agora `86aa438`(仍存在✅,分支 fix/a2-bos-resolve-2026-07-13) |
| C1 治理过度工程审计 | ✅ | GaC 184 超 cap(173) 11；见 §3 |
| B2 分布式同步设计 | ✅ v2 | outputs 里 B2-v2 文件(bus-foundation 驱动) |
| 工作树清理 | ✅ | 删野生 ecos/ + 6 锁 |

**A2 验证**: 4 断层 URI 活体 resolve 通过(_reachability:ok)、pytest 4 passed、静态审计 5→0。

## 2. Mac 单线程收尾（先停所有并发 agent！）
**⚠️ 前提**: 停掉 starlink-awaken 等所有写本仓的 agent；确认 `git rev-parse HEAD` 两次隔 30s 不变、无 index.lock。否则收尾持续被干扰。

```bash
# ① A2 push+PR
cd ~/Workspace/projects/agora
make -C ~/Workspace gac-local-gate        # 门禁(沙箱跑不了)
git push -u origin fix/a2-bos-resolve-2026-07-13
gh pr create -t "fix(bos): A2 resolve 断层收口" -b "kairon cli.py shim(c167cc0)+agora deprecate; 断层5→0; 回归4 passed"
# 合并后回根 bump 指针: git add projects/agora projects/kairon && git commit

# ② A3 活体重扫
cd ~/Workspace && uv sync --project projects/omo   # 修沙箱搞残的 venv
uv run --project projects/omo omo state sync --json # 重生 health.yaml 拿真实在线率
# 修 audit-rollout returncode:1; 预期在线率短期↓=不再造假(正确)

# ③ A3 注销 hermes(原子做,勿拆,否则造 decl-exec drift)
launchctl bootout gui/$(id -u)/ai.hermes.gateway
mkdir -p ~/.hermes/archived-plists && mv ~/Library/LaunchAgents/ai.hermes.gateway.plist ~/.hermes/archived-plists/
# 删 service-ctl.sh(:16,:31)+i0.py:38; broker 清 system.yaml+*capabilities.yaml 的 cap:hermes-gateway

# ④ A4 先减后加(broker) → ⑤ A5 结项复跑
```

## 3. C1 结论 + A4(先减后加)
GaC 规则 **184 条 > 冻结 cap 173(超11) → 冻结失效**。削减候选:
- 弱牙 9 条(仅审计不拦截): CR-X2-GAC-DRIFT / CR-X1-AGENT-AUDIT / CR-L2-MUTATION-BROKER / M4-HEALTH-SCORE / M4-DERIVED-PLANE-AUDIT / CR-META-METRIC-DEBT-FEATURE / CR-X-PROMOTION-LIFECYCLE / CR-CROSS-REPO / CR-PRINCIPLE-ENFORCEMENT
- cross-repo 3 重叠→合1; 11 条无 ADR 溯源; ~100 条 target=None; 6 条 draft(将自动转正需先确认 radar 验证)

**A4(决策已定)**: hermes deprecate + 注册 `runtime-probe-truth`+`decl-exec-consistency`(ADR-0179 §4 起草)。**先减后加不只抬 cap**: 先减(cross-repo -2 + 冻结无用弱牙 ≥-1)后加(+2),净 183,cap 校准到真实净额并恢复执行。ADR 编号顺延 **0181**(0180 被 bus-foundation 占)。经 governance-state-mutation broker(Mac)。

## 4. B2 v2 迭代要点(详见 outputs 的 B2-v2 文件)
ADR-0180 定 bus-foundation Omni-Bus 为标准;其 `ws_v2` 后端已有跨机 WebSocket+压缩+心跳+版本。**M1 传输从 raw gossip 改为 bus-foundation Event 平面(ws_v2)**。组合=SwarmOrchestrator(角色/发现)+ws_v2(跨机传输)+DeterministicConflictResolver(vector_clock 合并)。冲突/一致性/状态切片不变。B 比原估更省。**B 执行仍等 A5 绿灯。**

## 5. 战略升级 · decl/exec 元门禁
BOS 鸿沟(A1)、daemon 假绿灯(A3)、bus-foundation 空调用(ADR-0180)= **三个独立声明/执行鸿沟,各打各的点状 gate**。治本是**一条 decl/exec 一致性元规则**(A4 的 DECL-EXEC-CONSISTENCY 统摄三者),而非累加点状 gate——正好落实 C1"先减后加"。A4 落地时把这三个点状 gate 一并纳入合并评估。

## 6. 待你决定
- agy 在 agora 遗留的未提交改动(限流埋点等,已被 starlink 部分接管进 e341d3a)——核对去留。
- **停掉所有并发写本仓的 agent** 是后续一切的前提。

## 7. 环境限制(本沙箱做不到的,须 Mac)
push/merge(无 GitHub 凭证)、venv 命令(omo/gate 是 macOS 原生 venv,Linux 沙箱重建失败)、launchctl(hermes)、.omo broker 写入。这些是能力缺失,非谨慎。
