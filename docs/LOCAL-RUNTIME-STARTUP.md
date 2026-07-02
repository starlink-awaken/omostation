# eCOS v6 本地运行时一键启动

> **目标**: 把 eCOS v6 核心运行时服务从“手动逐个启动”变成“一条命令拉起”。
> **工具**: [`scripts/ecos-start.py`](../scripts/ecos-start.py)
> **SSOT**: [`protocols/port-registry.yaml`](../protocols/port-registry.yaml)

---

## 1. 启动哪些服务

| 服务 | 层 | 默认端口 | 入口 | 说明 |
|------|:--:|:--------:|------|------|
| `cockpit-dashboard` | L3 | `8090` | `uv run cockpit-dashboard` | 人类 Web 控制台 |
| `agora-mcp-sse` | I0 | `7431` | `uv run agora-mcp --sse` | Agent MCP SSE 入口 |
| `l4-kernel-mcp-sse` | L4 | `7456` | `uv run python -m l4_kernel.mcp_server --sse` | 自我层域管理 |
| `runtime-cron-http` | L1 | `7450` | `uv run python -m runtime.cron_service.server --http` | 调度与健康扫描 |
| `observability` | X | `3000` | `docker compose up -d` | Langfuse 可观测性 |

---

## 2. 前置依赖

- [uv](https://docs.astral.sh/uv/) — Python 项目管理
- [Docker](https://www.docker.com/) — observability 栈（可选）
- 各项目已完成 `uv sync`（脚本启动时会自动按需触发）

---

## 3. 用法

```bash
# 启动全部服务（默认）
python scripts/ecos-start.py

# 只启动核心服务，跳过 Langfuse
python scripts/ecos-start.py --no-observability

# 只启动指定服务
python scripts/ecos-start.py --services cockpit,agora,l4-kernel,runtime

# 预览会启动什么，但不真正启动
python scripts/ecos-start.py --dry-run
```

---

## 4. 运行流程

```
1. 端口冲突预检 → 若端口已被占用则跳过该服务
2. 依次启动各服务子进程
3. 轮询 /health 端点，等待服务 Ready
4. 输出汇总表与访问地址
5. 主进程进入日志 tail 模式
6. Ctrl+C 时统一 SIGTERM → 必要时 kill → 清理 docker compose
```

---

## 5. 访问入口

服务启动后，主要入口为：

- **Web Dashboard**: http://127.0.0.1:8090
- **Agora MCP SSE**: http://127.0.0.1:7431
- **Langfuse**: http://127.0.0.1:3000

---

## 6. 注意事项

- 脚本使用 `subprocess.Popen` 管理子进程，**需要在前台运行**；关闭终端会停止服务。
- 若某服务端口已被占用，脚本会跳过该服务并标记为 `ready`（假设已有实例在运行）。
-  observability 通过 `docker compose up -d` 启动，退出时通过 `docker compose down` 停止。
- 健康检查超时默认 60 秒，可通过 `--health-timeout` 调整。

---

## 7. 与其他启动方式的关系

| 方式 | 适用场景 |
|------|----------|
| `scripts/ecos-start.py` | 本地开发一键启动 |
| `runtime/scripts/service-ctl.sh` | runtime 服务单独精细控制 |
| `projects/observability/docker-compose.yml` | 仅启动可观测性 |
| `cockpit dashboard` | 仅启动 cockpit Web |
| CI / 生产 | 使用对应项目的部署流程，不依赖本脚本 |
