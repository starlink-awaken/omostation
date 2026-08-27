---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: phase 子目录历史总结批量归档, 当前阶段以 .omo/state/system.yaml 为准"
---
# Phase 1 Evidence Reconciliation — Appendix

> 日期: 2026-05-30 | 关联: `phase1-verification-report.md` 第 8-13 项

---

## 冲突说明

`phase1-verification-report.md`（v1，2026-05-29）记录运行时验证 3/5 PASS，
Docker Compose 因 OrbStack 端口冲突无法启动，smoke 测试 PENDING。

此后在 Phase 1 收尾阶段（同一会话），通过 21 项修复解决了所有运行时问题。

## 当前运行时验证 — 8/8 PASS

| # | 检查项 | 当前结果 | 证据 |
|---|--------|:--------:|------|
| 8 | Agora Web (7430) | ✅ 200 OK | `curl -s http://localhost:7430/` → `<!DOCTYPE html>` |
| 9 | SharedBrain API (7420) | ✅ 405 (POST-only 预期) | `curl -s http://localhost:7420/bos/rpc` → 405 |
| 10 | SharedBrain Health (8080) | ✅ `{"status":"ok"}` | `curl -s http://localhost:8080/health` → json |
| 11 | SharedBrain MCP (7421) | ✅ 容器 healthy | `docker ps` → `(healthy)` |
| 12 | Eidos MCP (8750) | ✅ 容器 healthy | `docker ps` → `(healthy)` |
| 13 | Docker Compose up | ✅ **4/4 Healthy** | `docker ps` → 全绿 |
| 14 | 烟雾测试 | ✅ **5/5 PASS** | `python3 -m pytest smoke_test.py -v` |
| 15 | E2E 全链路 | ✅ **11/11 PASS** | `python3 test-e2e-phase1.py` |

## 问题修复追溯

运行时验证 v1 失败的原因为 Docker 构建/配置问题，已在同一次 Phase 1 执行中修复：

| 修复 | 根因 | 状态 |
|------|------|------|
| Docker BuildKit IPv6 超时 | 改用 legacy builder | ✅ 已修复 |
| Python 版本不匹配 (3.11 vs 3.14) | Dockerfile 未同步 pyproject.toml | ✅ 已修复 |
| SharedBrain healthcheck 路径错误 | `/health/simple` → `/health` | ✅ 已修复 |
| stdio MCP 容器退出 | `stdin_open: true` | ✅ 已修复 |
| Agora 6 文件只读路径 | 加 `AGORA_DATA_DIR` env var | ✅ 已修复 |
| SharedBrain 3 文件缺失 | `domain_registry.py`, `bootstrap.py`, `__init__.py` | ✅ 已还原/新建 |

## 结论

Phase 1 运行时证据冲突已**事实消除**。原验证报告的 PENDING 状态过时（stale），
当前真实状态为 **PASS**。所有 8 项运行时检查通过，4 服务 Healthy，3 项测试套件全部通过。

## 更新后的验收总表

```
代码产出:   7/7 ✅
运行时:    8/8 ✅ (原 3/5 PASS)
烟雾测试:  5/5 ✅
E2E 全链路: 11/11 ✅
故障注入:   5/5 ✅
性能基线:   P50 1.2-14.8ms ✅
──────────────────
Phase 1: CLOSED — code_complete + runtime_verified
```
