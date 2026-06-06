# P2-RED_TEAM 红蓝对抗方案

> 2026-06-06 | 状态: design-locked

## 目标
全系统渗透测试，挖掘集成层面的安全缺陷。

## 范围
| 领域 | 测试项 |
|------|--------|
| KEI 沙箱 | Python audit hook 绕过测试 |
| Agora MCP | 未授权工具调用 |
| agent-runtime | 路径沙箱逃逸 |
| 跨包通信 | 端口扫描/未授权访问 |
| 配置安全 | 硬编码密钥/token |

## 阶段

### Phase 1: 自动化扫描 (1h)
```bash
# 端口扫描 — 检测未授权暴露的服务
nmap -p 7420-7432,8765,9876 localhost

# KEI 沙箱绕过测试
KEI_CONFIG_PATH=test_strict.yaml python3 -c "
# 尝试绕过文件读取沙箱
open('/etc/passwd').read()
"

# Agora 未授权调用测试
curl -X POST http://localhost:7430/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name":"health_check","arguments":{}}'
```

### Phase 2: 手动渗透 (2h)
- 尝试跨包 MCP 工具未授权调用
- 检查代理注册表是否可被污染
- 尝试进程注入 (通过 terminal_run)

## 报告格式
结果记录到 `.omo/_knowledge/management/red-team-2026-06.md`

参考: `kei_sandbox.py`, `tools.py:check_path_sandbox`, `agora/auth/`
