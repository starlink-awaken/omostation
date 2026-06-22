# ecos Workflow 快速上手指南

> 不依赖外部脚本，开箱即用验证工作流引擎。

## 1. 看看有什么

```bash
ecos workflow list
ecos workflow list -s    # 带最近运行状态
```

## 2. 创建你的第一个工作流

```bash
# 创建简化版本
ecos workflow create hello --path /tmp/hello.yaml
```

编辑 `/tmp/hello.yaml`:

```yaml
name: hello
description: 我的第一个工作流
execution:
  backend: default
  mode: sequential
  on_failure: continue
steps:
  - name: 打招呼
    action: custom_greet
    command: echo "Hello eCOS Workflow!"
  - name: 检查环境
    action: custom_env
    command: python3 -c "import sys; print(f'Python {sys.version}')"
  - name: 列出目录
    action: custom_ls
    command: ls -la /tmp | head -5
```

## 3. 验证 + 测试

```bash
# 验证语义
ecos workflow validate hello --path /tmp/hello.yaml || true

# Mock 测试（不执行真实命令）
ecos workflow test /tmp/hello.yaml || true

# 实际执行
ecos workflow run /tmp/hello.yaml
```

## 4. 派生工作流

基于已有工作流创建新的：

```bash
ecos workflow fork WORKFLOW-ECOS-DAILY-HEALTH --as my-health
ecos workflow edit my-health
ecos workflow validate my-health
ecos workflow test my-health
ecos workflow run my-health --dry-run
```

## 5. 参数传递

```bash
ecos workflow run WORKFLOW-ECOS-DAILY-HEALTH -p mode=quick -p verbose=true
```

## 6. 子工作流

在工作流中调用另一个工作流：

```yaml
steps:
  - name: 执行健康检查
    action: workflow_run
    workflow: WORKFLOW-ECOS-DAILY-HEALTH
    params:
      verbose: true
  - name: 完成
    action: custom_done
    command: echo "全部完成"
```

## 7. 运行历史与统计

```bash
ecos workflow logs --recent 10
ecos workflow logs --status failed --verbose
ecos workflow stats
```

## 8. 检查引擎状态

```bash
ecos workflow status      # 全局状态
ecos workflow backends    # 注册后端
ecos workflow actions     # 可用 action
```

## 9. Agent 使用（MCP）

通过 Agora MCP 直接调用：

```
workflow_list()
workflow_run(name="WORKFLOW-ECOS-DAILY-HEALTH", dry_run=true)
workflow_validate(name="WORKFLOW-ECOS-DAILY-HEALTH")
workflow_logs(recent=5)
```

## 10. 可视化

```bash
# 查看工作流定义（含步骤/后端/模式/约束）
ecos workflow describe WORKFLOW-ECOS-DAILY-HEALTH
```

---

## 架构速览

```
用户/Agent
  ├─ CLI:      cockpit workflow ecos <子命令>
  ├─ MCP:      agora → ecos-workflow (8 tools)
  ├─ Web:      :8090/api/ecos/workflow/ (8 endpoints)
  └─ BOS:      bos://ecos/workflow/{list|describe|run|logs}
```

**工作流定义 → 执行链路：**

```
M1 YAML → loader → validator (X1-X4) → executor → backend_registry → backend
                                                                    ├─ default (subprocess)
                                                                    ├─ dynamic (LLM)
                                                                    ├─ agora (BOS路由)
                                                                    ├─ symphony (状态机)
                                                                    ├─ swarm (多Agent)
                                                                    ├─ runtime (生命周期)
                                                                    └─ metaos (DAG)
```

---

## 快速导入示例工作流

```bash
# 创建并导入示例
mkdir -p /tmp/wf-demo
cat > /tmp/wf-demo/pipeline.yaml << 'EOF'
name: demo-pipeline
description: 完整演示管线
execution:
  backend: default
  mode: sequential
steps:
  - name: 系统信息
    action: sys_info
    command: uname -a
  - name: 磁盘使用
    action: disk_usage
    command: df -h / | tail -1
  - name: 内存状态
    action: mem_status
    command: vm_stat | head -5
EOF

# 导入并执行
ecos workflow import /tmp/wf-demo/pipeline.yaml
ecos workflow test demo-pipeline
ecos workflow run demo-pipeline
```
