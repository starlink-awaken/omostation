## [2026-08-07] P2: 调度器模型池治理决策 — 保留默认（P1b 范围修正）
- **决策**: 不修改 projects/agora 相关 dynamic-router.py 的 MODEL_POOL (L101-105)
- **理由**: PEAK/OFF-PEAK 机制未被完全理解，盲改可能破坏调度
- **现状**: MODEL_POOL 含 omlxc/coder, coder-fast, mid-local, mini-9b; L230 探测 ollama 过滤死引用
- **触发条件**（满足任一即启动映射决策）:
  1. omlxc/* 别名在 model-scheduler 或 dynamic-router 日志中出现路由失败/回落
  2. delegation-preflight.py 的 gateway_models_available WARN 升级为 FAIL
  3. PEAK/OFF-PEAK 调度机制被完全逆向（写 ADR 后）
- **状态**: 已记录，暂不实施（2026-08-07）

## [2026-08-07] P1: preflight 接线方案（已定稿，待 main 解禁后实施）
- **方案**: pre-commit hook 加 advisory 级 preflight（仿 gac-hygiene-check 的 `|| true` 模式）
- **理由**: 全量阻断会让「仅文档/仅 bin 提交」因 MLX 网关 down 而被卡；advisory 只 warn 不阻断，且 preflight 自身上下文敏感（检测 opencode 配置而非全仓）
- **实施点**: `.githooks/pre-commit` gac-hygiene-check 之后追加:
  ```bash
  if [ -x "$ROOT/bin/delegation-preflight.py" ]; then
    python3 "$ROOT/bin/delegation-preflight.py" --json 2>&1 | sed 's/^/[preflight] /' >&2 || true
  fi
  ```
- **前置**: ① main 解禁（P0 基线恢复或用户确认）② agent-workflow start（ADR-0203 RED LINE：治理面落地）③ worktree+PR（main 保护）
- **替代方案**（若不想动 hook）: start-work 流程内手动跑 preflight（已写进 delegation-guardrails skill Rule 1 第 4 步）
- **验证方式**: 故障注入 `--base-url http://127.0.0.1:1/v1` 已实测 EXIT=1 正确（2026-08-07）
