# Phase 0-2 复盘 — 数字生命体基座建设

> 日期: 2026-08-08 | 跨度: 多session (2026-08-06~08) | PRs: 40+

## 做了什么

### Phase 0: 接血管 (6/9 ✅)
- ✅ ADR-0396 数字生命体架构 (13条决策形式化)
- ✅ MOS agent_belief三表 (Keystone: world_snapshot/calibration/outcome)
- ✅ MOS Bridge: outcome + reflection → MOS表
- ✅ 最小冷启动: TELOS预灌world_snapshot
- ✅ CLAUDE.md路由更新
- ⬜ Neo4j配置 (需Docker)
- ⬜ Aetherforge wire (需omo submodule)
- ⬜ iris live测试 (需连接器在线)

### Phase 1: 建大脑 (5/8 ✅)
- ✅ MOF M2 模型 ×5 (digital_agent/mental_model/capability_provider/permission_policy/swarm)
- ✅ Agent Registry (4 agents注册)
- ✅ Pattern Governor Bridge
- ⬜ Trust Policy Engine (需omo submodule)
- ⬜ Advisor Agent (需omo submodule)
- ⬜ L4 TELOS注入 (需l4-kernel submodule)

### Phase 2: 补领域 (7/8 ✅)
- ✅ 4新领域场景卡 (家庭/健康/教育/财务, 9→13 cards)
- ✅ 3新journey specs (家庭协调/健康改善/教育成长, 3→6 specs)
- ⬜ Documents预灌 (需iris live)

## 做对了什么

1. **"先接血管"策略正确** — MOS三表+Bridges先建, 让已有工具的数据流向认知层
2. **M2放root避免submodule** — .omo/_truth/registry/mof-m2-extensions/ 绕开ecos submodule
3. **冷启动脚本提前建** — P0-T7而不是P2-T7, 保证Phase 1的Advisor有数据读
4. **每个PR独立merge** — 不积压, 每个改动可追溯

## 做错了什么

1. **方案审查15处修正未全部应用** — 实施计划文档还是旧版本
2. **submodule管理效率低** — 大量时间花在worktree/branch/push的协调上
3. **iris CLI语法bug** — `--json`全局flag位置错误, 导致live测试推迟到一个PR才修

## 教训

1. **submodule改动优先用最小wire** — 不要深度修改submodule内部, 只做最小集成点
2. **方案审查修正要立即应用** — 不能积压, 积压=遗忘
3. **每次session结束前更新CLAUDE.md** — 否则新session不知道进展

## 下一步

Phase 0-2剩余8个tasks全部被基础设施阻塞:
- Neo4j Docker配置 (P0-T2)
- omo submodule: Trust Policy + Advisor + Aetherforge (P0-T3, P1-T4, P1-T5)
- l4-kernel submodule: TELOS注入 (P1-T7)
- iris live测试 (P0-T6, P2-T7)

**建议**: 新session集中处理submodule改动 (omo + l4-kernel), 这是Phase 1剩余的核心。
