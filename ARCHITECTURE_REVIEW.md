# eCOS v5 架构评审报告

**2026-06-08 | 评审范围: 8 核心项目 · 3 维度深度分析**

---

## 评审总览

| 维度 | 评级 | 关键问题数 |
|------|------|-----------|
| 分层与依赖 | 🟡 中等风险 | 2 循环依赖 + 2 未声明依赖 + 2 端口冲突 |
| 安全架构 | 🟡 中等风险 | 1 严重 (硬编码密钥) + 3 中等 + N 个低风险 |
| 测试与契约 | 🟡 中等风险 | runtime/ecos 测试不足 + 2 注册表缺口 |
| 文档覆盖 | 🟡 中等风险 | cockpit/runtime/ecos 缺部分文档 |
| **综合评级** | **🟡 中等风险** | **12 个待修复项** |

---

## 一、分层与依赖评审

### 1.1 依赖矩阵

```
         被依赖方
依赖方    agora cockpit kairon gbrain omo metaos runtime ecos
agora      -       -       Y      -     Y*     -       -      Y
cockpit    Y       -       -      -     Y      -       Y      -
kairon     Y       -       -      -     -      -       -      -
gbrain     -       -       -      -     -      -       -      -
omo        Y*      -       Y      -     -      -       -      -
metaos     Y†      -       -      -     -      -       -      -
runtime    -       -       -      -     -      -       -      -
ecos       Y       -       -      -     -      -       -      -

Y  = pyproject.toml 声明 + 代码 import
Y* = 仅代码 import（弱耦合）
Y† = 仅代码 import，未声明
```

### 1.2 🔴 循环依赖 (ecos <-> agora)

| 属性 | 详情 |
|------|------|
| **循环链** | ecos(L0) → agora(I0) → ecos(L0) |
| **ecos → agora** | `cli/dashboard.py`, `ssot/tools/mof-workflow.py`, `ssot/tools/_output.py` 共 6 处 import |
| **agora → ecos** | `pyproject.toml` 声明 `ecos` 为运行时依赖 |
| **违反原则** | L0 协议层不应依赖 I0 织层，打破分层隔离 |

**建议**: 短期将 ecos→agora 改为通过事件总线或回调注入；长期将 ecos dashboard 通过 MCP 调用 agora

### 1.3 🟡 未声明依赖 (metaos → agora)

| 属性 | 详情 |
|------|------|
| **文件** | `a2a/task_manager.py`, `a2a/__init__.py` |
| **import** | `agora.mcp.mcp_bootstrap.get_data_dir`, `agora.a2a.task_manager` |
| **影响** | agora 未安装时 metaos 崩溃 |

**建议**: 在 metaos `pyproject.toml` 中添加 `agora` 依赖

### 1.4 🟡 agora 对 kairon 的过度耦合

| 属性 | 详情 |
|------|------|
| **耦合包数** | eidos, kos, minerva, forge, kairon_events, kairon_observability (6 个包) |
| **影响** | agora 成为事实上的 "God Object" |

**建议**: 将直接 import 转为通过 MCP 协议调用

### 1.5 端口冲突

| 端口 | 冲突方 | 建议 |
|------|--------|------|
| 9090 | omo vs ecos | 迁移 omo→9091 或 ecos→9092 |
| 8080 | agora vs kairon(ontoderive) | 迁移 kairon/ontoderive |

---

## 二、安全架构评审

### 2.1 亮点

- **Agora 认证体系完善**: IdentityCA (HMAC+PBKDF2)、MCPAuthMiddleware (HMAC-SHA256 JWT)、OAuth2、TenantManager
- **KEI 沙箱**: `sys.addaudithook` 拦截文件/网络/子进程，JSONL 审计日志
- **密钥管理**: PBKDF2 哈希、`secrets.compare_digest`、`cryptography.fernet` 加密、系统密钥链集成
- **SSRF 防护**: `minerva/shared/security.py` 阻止私有 IP、云元数据端点
- **无裸 except**: agora 和 kairon 核心模块无裸异常捕获

### 2.2 🔴 硬编码默认密钥

| 属性 | 详情 |
|------|------|
| **文件** | `agora/src/agora/auth/mcp_auth.py:88` |
| **代码** | `SHAREDBRAIN_SOVEREIGN_KEY = os.environ.get("SHAREDBRAIN_SOVEREIGN_KEY", "sharedbrain-default-key")` |
| **影响** | 未配置环境变量时使用可预测的默认密钥，可被伪造 JWT |

**建议**: 移除默认值，密钥缺失时拒绝启动并输出明确错误

### 2.3 🟡 凭证明文存储

| 属性 | 详情 |
|------|------|
| **文件** | `agora/src/agora/auth/tenant.py:65` |
| **影响** | 自动生成 token 后明文写入 `~/.config/agora/tenants.yaml` |

**建议**: 存储前使用 PBKDF2 哈希，仅返回原始 token 一次

### 2.4 安全成熟度矩阵

| 项目 | 认证 | 输入验证 | 沙箱 | 密钥管理 | 全局状态 | 错误处理 |
|------|------|---------|------|---------|---------|---------|
| agora | 🟢 | 🟡 | — | 🟡 | 🟡 | 🟢 |
| runtime | 🔴 | 🟢 | 🟢 | 🔴 | 🟡 | 🟡 |
| kairon | 🟡 | 🟡 | 🟡 | 🟢 | 🔴 | 🟡 |
| omo | 🔴 | 🔴 | — | 🔴 | 🟡 | 🟡 |
| cockpit | 🔴 | 🔴 | — | 🔴 | 🔴 | 🟡 |
| metaos | 🔴 | 🔴 | — | 🔴 | — | — |
| ecos | 🔴 | 🔴 | — | 🔴 | — | — |

---

## 三、测试与契约合规性评审

### 3.1 测试健康度

| 项目 | 源文件 | 测试文件 | 比例 | 评级 |
|------|--------|---------|------|------|
| agora | 191 | 76 | 0.40 | 🟢 |
| cockpit | 77 | 73 | 0.95 | 🟢 |
| kairon | 781 | 200 | 0.26 | 🟡 conftest 冲突 |
| gbrain | 546 | 874 | 1.60 | 🟢 |
| omo | 103 | 114 | 1.11 | 🟢 |
| metaos | 37 | 30 | 0.81 | 🟢 |
| runtime | 301 | 35 | **0.12** | 🔴 **最低比率** |
| ecos | 211 | 37 | **0.18** | 🔴 低覆盖 |

### 3.2 🔴 runtime 测试严重不足
- 301 源文件，仅 35 测试文件 (0.12)
- executor 编排引擎 100+ 文件几乎无测试覆盖

### 3.3 🔴 kairon conftest 冲突
- eidos 与 core-models 的 conftest 冲突导致全量测试收集失败

### 3.4 🟡 L0 注册表缺口
- cockpit MCP (20 tools) 和 metaos MCP (11 tools) 未在 L0-registry 注册

---

## 四、优先修复路线图

### P0 · 立即修复

| # | 问题 | 项目 | 修复 |
|---|------|------|------|
| 1 | 硬编码默认密钥 | agora | 移除 `mcp_auth.py:88` 默认值 |
| 2 | kairon conftest 冲突 | kairon | 分离 eidos/core-models conftest |
| 3 | 端口冲突 9090/8080 | omo/ecos/kairon | 迁移冲突端口 |
| 4 | metaos 未声明依赖 | metaos | pyproject.toml 添加 agora |

### P1 · 短期修复

| # | 问题 | 项目 | 修复 |
|---|------|------|------|
| 5 | 循环依赖 ecos↔agora | ecos/agora | 事件总线解耦 |
| 6 | runtime 测试补充 | runtime | executor 引擎覆盖 |
| 7 | 凭证明文存储 | agora | PBKDF2 哈希化 |
| 8 | L0 注册表补充 | cockpit/metaos | 注册 MCP tools |

### P2 · 中期改进

| # | 问题 | 项目 | 修复 |
|---|------|------|------|
| 9 | agora→kairon 过度耦合 | agora | MCP 协议替代直接 import |
| 10 | ecos 测试补充 | ecos | 核心模块覆盖 |
| 11 | cockpit 文档 | cockpit | CLAUDE.md + AGENTS.md |
| 12 | runtime CLAUDE.md | runtime | 创建文档 |

---

## 五、架构优势

1. **分层清晰 (75% 合规)** — runtime/gbrain 是纯 leaf 节点
2. **认证体系成熟** — JWT+OAuth2+PBKDF2 认证栈
3. **沙箱机制完善** — KEI 运行时沙箱 + KOS Agent 沙箱双重隔离
4. **SSRF 防护到位** — minerva URL 验证器
5. **接口契约文化** — 7/8 项目有 INTERFACE.yaml
6. **治理体系完备** — .omo/ 四平面 + X 轴保障 + debt registry
