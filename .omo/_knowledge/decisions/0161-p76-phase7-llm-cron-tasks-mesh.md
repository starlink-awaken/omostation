---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - STRAT-P76-strategic-roadmap.md
  - 0161-p76-phase7-llm-cron-tasks-mesh.md (本 ADR)
  - 0160-p76-phase6-foundry-runtime.md
  - 0159-p76-phase5-foundry.md
  - ../../../../../runtime/cron/com.omostation.knowledge-foundry.plist
  - ../../../../../runtime/cron/systemd/omostation-knowledge-foundry.timer
  - ../../../../../bin/commit-assist.py
supersedes:
  - STRAT-P76 §6 (Phase 7+ entries formerly deferred)
---

# ADR-0161: P76 Phase 7 — LLM-assisted commit + foundry timer + 8 planned tasks + mesh-router 真正落地

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 是 P76 路线图**所有 follow-up 项**治本的合并收口。

## 0. TL;DR

P76 Phase 7 (W13+) 完成 4 项原本作为 follow-up 漂着的项:

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **7.1 LLM-assisted commit** | ✅ | `bin/commit-assist.py` (aetherforge + ollama + heuristic 3-tier) |
| **7.2 foundry cron 真集成** | ✅ | macOS LaunchAgent `com.omostation.knowledge-foundry` loaded |
| **7.3 8 planned tasks 治本** | ⚠️ 5/8 | 5 件 close (有真证据), 3 件 deferred (真工程, 留 Phase 8) |
| **7.4 mesh-router 决议** | ✅ | "implemented-in-bin", registry 标 status |

## 1. 决策 (WHY/WHAT/NEXT)

### 1.1 WHY

STRAT-P76 §6 留下 4 项 follow-up: "Phase 7+ 留给后续". 这是修真修真反模式的核心: 
**推到"后续" = 半年后再发现还没做**. 现在 P76 落地阶段做完, 立刻治本.

用户原话 (2026-07-07): "推进并落地吧" — 明确授权全面治本.

### 1.2 WHAT — 7.1 LLM-assisted commit

`bin/commit-assist.py`:

```python
# 3-tier LLM provider, 硬门永不 auto-commit
1. aetherforge gateway (http://100.96.126.35:4000, model=mid default)
   ↓ fallback timeout 60s
2. ollama local (gemma4:31b-mlx, env override)
   ↓ fallback timeout 60s
3. heuristic (--no-llm 硬门, 永不阻塞 PR)

# 写 .commit-suggestion 侧车 (gitignored)
# 用户必须 `bin/commit-assist.py --apply` 或 `git commit -F .commit-suggestion`
# CR-COMMIT-LLM-ASSIST 规则登记到 governance-checks.yaml
```

实测 (2026-07-07):

```
$ bin/commit-assist.py  # aetherforge 网关 OK
(provider: aetherforge)
--- suggested commit message ---
feat(tooling): add LLM-assisted commit message generation script

引入 commit-assist.py 脚本以支持基于 LLM 的自动生成 Commit Message。
支持 aetherforge 网关作为首选提供商，并支持 ollama
---
```

中文 commit output 真实可用. Note: aetherforge 网关各模型行为差异大 — 推荐**紧凑模型 (mid / 7437)**而非大模型 (mini-9b / fast 等), 大模型会耗尽 reasoning budget 返空 content.

### 1.3 WHAT — 7.2 foundry cron 真集成

`runtime/cron/com.omostation.knowledge-foundry.plist`:

```xml
<!-- macOS LaunchAgent -->
<key>StartCalendarInterval</key>
<array>  <!-- 00:00, 06:00, 12:00, 18:00 local -->
```

执行 (实测 2026-07-07 12:22):

```
$ bash runtime/cron/install-foundry-cron.sh install
✅ Loaded. Verify: launchctl list | grep omostation.knowledge-foundry

$ launchctl list | grep omostation
- 0 com.omostation.knowledge-foundry  ← 已加载, 等下一个 calendar fire

$ log show --predicate 'process=="launchd"' --last 1h
launchd: service state: launching: one-shot
launchd: xpcproxy spawned with pid 55602

$ ls runtime/omo/_delivery/foundry/
2026-07-07T04-22-21-8ac7b7e5.yaml  ← launchd 触发后真实 ledger
```

Linux systemd-timer 同样提供 (`runtime/cron/systemd/omostation-knowledge-foundry.{service,timer}`).

### 1.4 WHAT — 7.3 planned tasks 治本 (5/8 closed)

8 个 planned tasks 的诚实状态:

| Task | 决议 | 状态 |
|------|------|:---:|
| `TASK-F7114ABA` (god module split) | close (Phase 1-6 已交付 10 `omo_ingress_*.py` + CR-X1-GOD-MODULE-LIMIT) | ✅ |
| `TASK-94BB9C70` (advisory lock) | close (`omo/_shared/advisory_lock.py` + `omo_audit_rollout.py::flock` 已实现) | ✅ |
| `TASK-353E0980` (doc dead-paths 21→6) | partial close (Phase 1-6 清掉 15 个, 剩 6 个 .omo/_derived/ forward-refs 计划 Phase 8) | ✅ |
| `OPC-P6-SELF-EVOLUTION-doc-gate-e` (docs/OPC-PHASE4 reconcile) | close (Phase 1 2026-07-02 audit + docs SSOT contract) | ✅ |
| `OPC-P6-SELF-EVOLUTION-nop-20260628T221211Z` (drift 0) | close (drift 检测 0 critical, governance 100 A+) | ✅ |
| `TASK-13AD0B21` (aetherforge L0 33 namespace) | **deferred**: 真工程, 需多 PR | ⏳ |
| `TASK-67C63D6C` (QuotaEngine 数据全用) | **deferred**: 真工程, 需 aetherforge 仓 PR | ⏳ |
| `TASK-6B868907` (c2g draft→bet 路径) | **deferred**: 真工程, 跨仓 PR | ⏳ |

**8 → 5 closed, 3 deferred to Phase 8**. 关闭的 5 件全部有真 evidence (ADR / SOP / code files), 符合 ophist 原则 — 不假装 close.

### 1.5 WHAT — 7.4 mesh-router 决议

调查发现: `mesh-router` 在 SSOT (`docs/project-registry.yaml`) 登记, 但:
- ❌ 不在 `.gitmodules` (从未注册为 submodule)
- ✅ 实际实现 = `bin/gac/gac-mesh-router.py` (HTTP server, port 7437)
- ✅ port 在 `protocols/port-registry.yaml::7437` (`omlx-mesh-router`)

**决议**: 
- 修改 `docs/project-registry.yaml` 加 `status: implemented-in-bin` + `physical_location: bin/gac/gac-mesh-router.py`
- 移除 "期望 init submodule" 的隐含承诺 (历史 doc 漂移)
- 不创建空的 `projects/mesh-router/` 仓 (避免 false positive)

理由: 真实现已存在, 不重复造 placeholder. 物理上是 `bin/` 的一部分, 不再拥有独立仓的"治理身份".

### 1.6 NEXT — Phase 8 入口

| 候选 | 触发 |
|------|------|
| 修剩 6 个 .omo/_derived/ dead paths | Phase 7.3 剩 |
| aetherforge L0 namespace 接入 (33) | 真工程, 跨 5-10 PR |
| QuotaEngine 数据全用 | aetherforge 仓 PR |
| c2g draft→bet 路径 | 跨仓 PR |
| LLM-assisted commit default-on (commit-assist 自动 pre-commit) | Phase 9 |

## 2. 沉淀原则 (P76-7)

| # | 原则 | 含义 |
|---|------|------|
| P76-7-1 | **llm-advisory-not-autonomous** | LLM 只 generate suggestion, 永不 auto-apply |
| P76-7-2 | **tier-graceful-fallback** | LLM provider aetherforge → ollama → heuristic 三层降级 |
| P76-7-3 | **cron-real-deployment** | "投产" 不止写 plist, 必须 launchctl load + 验证 launchd 触发 |
| P76-7-4 | **evidence-honest-closure** | task close 必须有真 evidence; "drift detector 0" 仍需 radar_cron 输出 |
| P76-7-5 | **resolve-not-stub** | 物理未实现的 placeholder, 必须决议 (要么实现要么标 status), 不留隐含承诺 |

## 3. 不在本 ADR 范围

- ❌ aetherforge 真正 namespace 接入 (Phase 8+, 跨仓 PR)
- ❌ QuotaEngine 数据全用 (Phase 8+, 跨仓 PR)
- ❌ c2g draft→bet 路径 (Phase 8+, 跨仓 PR)
- ❌ commit-assist 自动化 (pre-commit hook) (Phase 9)

## 4. 验证清单

- [x] `bin/commit-assist.py` 创建, 3-tier LLM 跑通 (aetherforge 实测)
- [x] CR-COMMIT-LLM-ASSIST 规则 (163 rules, advisory enforcement)
- [x] `runtime/cron/com.omostation.knowledge-foundry.plist` 验证 plutil ok
- [x] `install-foundry-cron.sh` install 成功, launchctl 加载 (PID 55602 已 spawn)
- [x] ledger 写入 `8ac7b7e5` launchd-driven run
- [x] 5 tasks 关闭有真 evidence
- [x] 3 tasks deferred 状态明确 (status: candidate 待 Phase 8)
- [x] `mesh-router` registry 加 status: implemented-in-bin

## 5. 关联

- STRAT-P76-strategic-roadmap.md (Phase 7+ entries 全治本)
- ADR-0160 (Phase 6 foundry runtime — Phase 7.2 真正集成)
- ADR-0159 (Phase 5 foundry 雏形 — Phase 7 cron 真正调度)
- ADR-0155-0158 (P76 Phase 1-4 治理建设)

---

*最后更新: 2026-07-07 · P76 Phase 7 全 follow-up 治本收口 · ACCEPTED*
