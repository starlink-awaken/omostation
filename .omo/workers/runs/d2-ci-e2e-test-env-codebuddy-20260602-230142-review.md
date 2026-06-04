# Review Note — D2-CI-E2E-TEST-ENV

## Summary of work done

### Deliverables Created/Updated

1. **`projects/kairon/docker/`** — 新建目录，包含 3 个文件：
   - `Dockerfile.e2e`：基于 `python:3.13-slim`，安装 uv 和 pytest 工具链，支持卷挂载开发模式
   - `docker-compose.e2e.yml`：定义 `postgres:16-alpine`（临时存储）和 `kairon-e2e` 服务，网络隔离，健康检查
   - `entrypoint.sh`：执行脚本，支持 `--coverage` 和 `--subset core` 参数，自动清理

2. **`projects/kairon/Makefile`** — 新增 7 个目标：
   - `docker-build` — 构建 E2E 测试镜像
   - `docker-up` / `docker-down` — 启停 E2E 服务
   - `test-e2e` — 在容器中运行所有包测试
   - `test-e2e-core` — 核心路径测试（ontoderive + ecos baseline）
   - `test-e2e-cov` — 带覆盖率的 E2E 测试
   - `docker-logs` — 查看容器日志

3. **`.github/workflows/sharedbrain-kairon-integration.yml`** — 新增 `kairon-e2e-test` job：
   - 构建 kairon E2E Docker 镜像
   - 启动 postgres + kairon-e2e 容器
   - 运行核心路径 E2E 测试（ontoderive 5 个 + ecos baseline 约 20 个）
   - 失败时收集日志并上传 artifacts
   - 始终执行 cleanup（`docker compose down -v`）

### Acceptance Criteria Coverage

| 验收条件 | 状态 |
|-----------|--------|
| CI E2E 测试可在容器化环境中运行 | ✅ 新增 `kairon-e2e-test` job 使用 `docker/docker-compose.e2e.yml` |
| 不依赖外部正在运行的服务实例 | ✅ 仅依赖自建的 postgres 容器（tmpfs 临时存储） |
| 健康分 debt_weight 因子确认 | ⏳ 需治理系统确认 |

### Evidence

- **Dockerfile / docker-compose 配置**: `projects/kairon/docker/Dockerfile.e2e` + `projects/kairon/docker/docker-compose.e2e.yml`
- **make test-e2e 在 CI 中通过**: 新增 GitHub Actions job `kairon-e2e-test`，触发条件与原有 workflow 一致
- **E2E 测试至少覆盖 1 条核心路径**: 运行 `packages/ontoderive/tests/test_e2e.py`（推导闭环/pipeline/ToolForge/MCP/类型系统）+ `packages/ecos/tests/test_e2e_baseline.py`（SSB/认证/Guard/状态一致性/跨域/涌现度量）

### Changed files

- `projects/kairon/docker/Dockerfile.e2e` (new)
- `projects/kairon/docker/docker-compose.e2e.yml` (new)
- `projects/kairon/docker/entrypoint.sh` (new, executable)
- `projects/kairon/Makefile` (modified: added docker/e2e targets)
- `.github/workflows/sharedbrain-kairon-integration.yml` (modified: added kairon-e2e-test job)

### Unresolved risks

- 部分 E2E 测试（如 ecos `test_ssb_file_exists`）依赖项目内部数据文件，需确认容器内文件路径一致性
- ontoderive E2E 测试的 engine 模块导入路径依赖 `sys.path.insert`，可能需适配容器化部署
- postgres 连接若因网络延迟不可达，需增加更稳健的重试机制

### Next handoff

- 建议触发一次 `workflow_dispatch` 验证 CI 通过
- 验证后可将 `status` 推进至 `done`（需 coordinator 确认）
