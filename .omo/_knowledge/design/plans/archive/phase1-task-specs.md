# Phase 1 任务规格书 + Agent 执行手册

> 日期: 2026-05-29 | 版本: v1.0 | 职责: Prometheus(规划+检查) → Agent(执行)
> 依据: `phase1-sprint-plan.md`

---

## Prometheus 角色定义

| 角色 | 做什么 | 不做什么 |
|------|--------|---------|
| **规划阶段** | 出任务规格书、出命令模板、定义验收标准 | 不写代码、不执行 bash |
| **执行阶段** | 不参与 | 不干预 Agent 执行 |
| **检查阶段** | 接收 Agent 产出 → 逐条对照验收标准 → 通过/驳回 | 不跳过验收、不妥协 |

---

## Agent 执行命令模板

以下命令可直接复制给 Agent。每个命令是自包含的——Agent 不需要额外上下文即可执行。

### Sprint 1 Wave 1.1: 环境修复 + 验证

```bash
# T1.1.1: Docker 镜像源配置
task(category="quick", description="T1.1.1: Docker mirror setup", prompt='''
Configure Docker to use a China-accessible mirror so `docker pull python:3.12-slim` works.

1. Edit Docker daemon config (~/.docker/daemon.json or Docker Desktop settings):
   - Add registry mirror (e.g., https://docker.m.daocloud.io or https://mirror.baidubce.com)
2. Restart Docker
3. Verify: docker pull python:3.12-slim succeeds
4. Report: "Docker mirror configured: <url>, pull test: PASS/FAIL"
''')

# T1.1.2: Docker Compose build + up
task(category="quick", description="T1.1.2: Docker Compose up", prompt='''
From the workspace root (/Users/xiamingxing/Workspace), run the integration docker-compose:

1. cd /Users/xiamingxing/Workspace
2. docker compose -f projects/SharedBrain/tests/integration/docker-compose.yml build --parallel
3. docker compose -f projects/SharedBrain/tests/integration/docker-compose.yml up -d
4. Wait for all services: docker compose ... wait sharedbrain agora agora-mcp eidos
5. docker compose ... ps (verify 5/5 healthy)
6. Report: status of each service (healthy/unhealthy) and any errors
''')

# T1.1.3: core-models import 验证
task(category="quick", description="T1.1.3: Verify core-models imports", prompt='''
Verify that all 3 Z-Spore adapter files import correctly.

Run from /Users/xiamingxing/Workspace/projects/SharedBrain:
```
python3 -c "
import sys; sys.path.insert(0, '.')
from nucleus.Z_Spore.archetypes.kairon_entity_adapter import Entity, KAIRON_MODELS_AVAILABLE
print(f'Entity adapter: KAIRON_MODELS_AVAILABLE={KAIRON_MODELS_AVAILABLE}')
from nucleus.Z_Spore.archetypes.kairon_relation_adapter import Relation
print('Relation adapter: OK')
from nucleus.Z_Spore.archetypes.kairon_knowledge_graph_adapter import KnowledgeGraph
print('KnowledgeGraph adapter: OK')
print('ALL 3 PASS')
"
```

Report pass/fail for each adapter.
''')

# T1.1.4: Agora registry 验证
task(category="quick", description="T1.1.4: Verify Agora registry", prompt='''
Verify that SharedBrain's 20 MCP tools are registered in the Agora registry.

Read the file: /Users/xiamingxing/Workspace/projects/kairon/packages/agora/src/agora/registry.yaml
Search for "sharedbrain" entries. Count them. Report the count and a sample of tool names.

Expected: at least 15+ sharedbrain-prefixed tools registered.
''')

# T1.1.5: 遗留任务清零确认
task(category="quick", description="T1.1.5: Verify delegated organ status", prompt='''
Verify all 4 delegated organs have their .organ_status file set correctly.

Run:
```
for d in D_Monitoring D_Gateway D_Harvest D_KnowledgeIntegration; do
  echo -n "organs/$d: "
  cat /Users/xiamingxing/Workspace/projects/SharedBrain/organs/$d/.organ_status 2>/dev/null || echo "MISSING"
done
```

Report: each organ name and its status. All 4 must say "delegated".
''')
```

### Sprint 1 Wave 1.2: 烟雾测试 + sharedbrain-bridge

```bash
# T1.2.1: 烟雾测试
task(category="quick", description="T1.2.1: Smoke test all services", prompt='''
Run the smoke test from /Users/xiamingxing/Workspace/projects/SharedBrain:
```
cd /Users/xiamingxing/Workspace/projects/SharedBrain
python3 tests/integration/smoke_test.py
```

If services are not running locally (not in Docker), modify the test URLs to localhost:7421 etc.

Report: which tests pass, which fail, and error messages.
''')

# T1.2.2-2.6: sharedbrain-bridge 包创建（合并为一个任务）
task(category="quick", description="T1.2.2-6: Create sharedbrain-bridge package", prompt='''
Create the sharedbrain-bridge Python package at /Users/xiamingxing/Workspace/projects/kairon/packages/sharedbrain-bridge/

This package bridges kairon and SharedBrain. Create these files:

## File 1: pyproject.toml
```toml
[project]
name = "sharedbrain-bridge"
version = "0.1.0"
description = "Bridge between kairon and SharedBrain — EU pricing, immune audit, batch sync"
requires-python = ">=3.10"
dependencies = ["core-models"]

[project.scripts]
sb-bridge = "sharedbrain_bridge.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

## File 2: src/sharedbrain_bridge/__init__.py
```python
"""SharedBrain Bridge — kairon ↔ SharedBrain integration layer.

Modules:
  - eu: EU pricing bridge (kairon pipeline → SharedBrain D-Economy)
  - immune: Immune audit bridge (kairon knowledge → SharedBrain D-Immunity)
  - sync: Batch sync bridge (kairon eidos ↔ SharedBrain D-Memory)
"""
```

## File 3: src/sharedbrain_bridge/eu.py
```python
"""EU Pricing Bridge — kairon pipeline → SharedBrain D-Economy.

Provides EU (Energy Unit) balance checks and consumption tracking
for kairon pipeline operations.
"""
import json
import logging
from urllib.request import Request, urlopen

_log = logging.getLogger(__name__)

DEFAULT_AGORA = "http://localhost:7430"
DEFAULT_SB = "http://localhost:7421"
PRICING = {
    "minerva_research": 10, "ontoderive_engine": 5,
    "eidos_validate": 2, "kos_index": 3,
    "kronos_ingest": 1, "sophia_compile": 5,
}

class EUBridge:
    def __init__(self, agora=DEFAULT_AGORA, sharedbrain=DEFAULT_SB):
        self.agora = agora
        self.sb = sharedbrain

    def check_balance(self, caller: str) -> dict:
        try:
            url = f"{self.sb}/api/v1/economy/balance?caller={caller}"
            resp = urlopen(Request(url, method="GET"), timeout=5)
            data = json.loads(resp.read().decode())
            return {"balance": data.get("balance", 100), "limit": data.get("limit", 1000), "ok": True}
        except Exception as e:
            return {"balance": 100, "limit": 1000, "ok": False, "error": str(e)}

    def consume(self, caller: str, operation: str) -> dict:
        cost = PRICING.get(operation, 1)
        balance = self.check_balance(caller)
        if balance["balance"] < cost:
            return {"success": False, "error": f"Insufficient EU: need {cost}, have {balance['balance']}"}
        try:
            payload = json.dumps({"caller": caller, "cost": cost, "operation": operation}).encode()
            req = Request(f"{self.sb}/api/v1/economy/consume", data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            resp = urlopen(req, timeout=5)
            return {"success": resp.status == 200, "cost": cost, "balance_after": balance["balance"] - cost}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

## File 4: src/sharedbrain_bridge/immune.py
```python
"""Immune Audit Bridge — kairon knowledge → SharedBrain D-Immunity."""
import json, logging
from urllib.request import Request, urlopen

_log = logging.getLogger(__name__)
DEFAULT_SB = "http://localhost:7421"

class ImmuneBridge:
    def __init__(self, sharedbrain=DEFAULT_SB):
        self.sb = sharedbrain

    def audit(self, content: str, title: str = "", source: str = "") -> dict:
        try:
            payload = json.dumps({"content": content, "title": title, "source": source}).encode()
            req = Request(f"{self.sb}/api/v1/immunity/audit", data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            resp = urlopen(req, timeout=10)
            return json.loads(resp.read().decode())
        except Exception as e:
            return {"risk": "UNKNOWN", "error": str(e)}
```

## File 5: src/sharedbrain_bridge/sync.py
```python
"""Batch Sync Bridge — kairon eidos ↔ SharedBrain D-Memory."""
import json, logging, hashlib
from pathlib import Path
from urllib.request import Request, urlopen

_log = logging.getLogger(__name__)
DEFAULT_SB = "http://localhost:7421"
SHAREDBRAIN_ORGANS = Path("/Users/xiamingxing/Workspace/projects/SharedBrain/organs")

class SyncBridge:
    def __init__(self, sharedbrain=DEFAULT_SB):
        self.sb = sharedbrain

    def get_active_organs(self) -> list[dict]:
        organs = []
        if not SHAREDBRAIN_ORGANS.exists():
            return organs
        for d in sorted(SHAREDBRAIN_ORGANS.iterdir()):
            if d.is_dir() and d.name.startswith("D-"):
                sf = d / ".organ_status"
                organs.append({"name": d.name, "status": sf.read_text().strip() if sf.exists() else "active"})
        return organs

    def batch_sync_to_memory(self, organs: list[dict] = None) -> dict:
        if organs is None:
            organs = self.get_active_organs()
        fp = hashlib.sha256(json.dumps(organs, sort_keys=True).encode()).hexdigest()
        try:
            payload = json.dumps({"organs": organs, "fingerprint": fp}).encode()
            req = Request(f"{self.sb}/api/v1/memory/sync", data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            resp = urlopen(req, timeout=10)
            return {"synced": resp.status == 200, "count": len(organs), "fp": fp}
        except Exception as e:
            return {"synced": False, "error": str(e), "count": len(organs), "fp": fp}
```

## File 6: src/sharedbrain_bridge/cli.py
```python
"""CLI entry point for sharedbrain-bridge."""
import sys
from sharedbrain_bridge.sync import SyncBridge
from sharedbrain_bridge.eu import EUBridge
from sharedbrain_bridge.immune import ImmuneBridge

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        sb = SyncBridge()
        organs = sb.get_active_organs()
        print(f"Active organs: {len(organs)}")
        for o in organs:
            print(f"  {o['name']}: {o['status']}")
    elif cmd == "sync":
        sb = SyncBridge()
        result = sb.batch_sync_to_memory()
        print(json.dumps(result, indent=2))
    elif cmd == "eu":
        eb = EUBridge()
        caller = sys.argv[2] if len(sys.argv) > 2 else "kairon"
        print(json.dumps(eb.check_balance(caller), indent=2))
    elif cmd == "audit":
        ib = ImmuneBridge()
        content = " ".join(sys.argv[2:]) or "test content"
        print(json.dumps(ib.audit(content), indent=2))
    else:
        print(f"Usage: sb-bridge <status|sync|eu|audit>")

if __name__ == "__main__":
    main()
```

Steps:
1. mkdir -p /Users/xiamingxing/Workspace/projects/kairon/packages/sharedbrain-bridge/src/sharedbrain_bridge/
2. Write all 6 files
3. cd /Users/xiamingxing/Workspace/projects/kairon/packages/sharedbrain-bridge && pip install -e .
4. Test: python -c "from sharedbrain_bridge import EUBridge, ImmuneBridge, SyncBridge; print('OK')"
5. Report: "sharedbrain-bridge package created: PASS/FAIL"
''')
```

### Sprint 2 Wave 2.1: LiteLLM 部署 + agentmesh 适配

```bash
# T2.1.1: LiteLLM Docker 部署
task(category="quick", description="T2.1.1: Deploy LiteLLM", prompt='''
Deploy LiteLLM as a Docker service for LLM API routing.

1. Clone or pull LiteLLM: docker pull ghcr.io/berriai/litellm:main-latest (or use a mirror)
2. Create a minimal config at /tmp/litellm_config.yaml with 1 test model
3. docker run -d -p 4000:4000 -v /tmp/litellm_config.yaml:/app/config.yaml ghcr.io/berriai/litellm:main-latest
4. Test: curl http://localhost:4000/health
5. Report: "LiteLLM deployed: PASS/FAIL, endpoint: http://localhost:4000"
''')

# T2.1.4: agentmesh Gateway LiteLLM 适配器
task(category="quick", description="T2.1.4: agentmesh LiteLLM adapter", prompt='''
Add a LiteLLM routing adapter to agentmesh Gateway.

Read the existing gateway code at /Users/xiamingxing/Workspace/projects/agentmesh/ to understand the adapter pattern, then:

Create file: /Users/xiamingxing/Workspace/projects/agentmesh/src/model-gateway/adapters/litellm.ts

```typescript
/**
 * LiteLLM Adapter — route LLM requests through LiteLLM proxy.
 * 
 * LiteLLM provides unified API for 100+ models with routing, fallback, and cost tracking.
 * This adapter sits between agentmesh Gateway and LiteLLM, adding quota management.
 */
export interface LiteLLMConfig {
  endpoint: string;        // http://localhost:4000
  defaultModel: string;    // e.g., "gpt-4o"
  fallbackModels: string[];// e.g., ["claude-3-5-sonnet", "gemini-2.0-flash"]
  maxRetries: number;      // default: 2
}

export interface LLMResponse {
  model: string;
  content: string;
  tokens: number;
  cost: number;
  latency_ms: number;
}

export interface QuotaCheck {
  model: string;
  remaining: number;
  resetAt: Date;
}

export class LiteLLMAdapter {
  private config: LiteLLMConfig;
  private quotas: Map<string, QuotaCheck>;

  constructor(config: LiteLLMConfig) {
    this.config = config;
    this.quotas = new Map();
  }

  async route(model: string, messages: any[]): Promise<LLMResponse> {
    // Try primary model, fallback on failure or quota exceeded
    const models = [model, ...this.config.fallbackModels];
    let lastError: Error | null = null;

    for (const m of models) {
      const quota = this.quotas.get(m);
      if (quota && quota.remaining <= 0) {
        continue; // skip model with no quota
      }

      try {
        const start = Date.now();
        const response = await this.callLiteLLM(m, messages);
        const latency = Date.now() - start;
        
        this.updateQuota(m, response);
        return { ...response, latency_ms: latency };
      } catch (e) {
        lastError = e as Error;
        continue;
      }
    }

    throw new Error(`All models failed. Last error: ${lastError?.message}`);
  }

  async checkQuota(model: string): Promise<QuotaCheck> {
    const existing = this.quotas.get(model);
    if (existing && existing.resetAt > new Date()) {
      return existing;
    }
    // Query LiteLLM for quota info
    const check: QuotaCheck = { model, remaining: 1000, resetAt: new Date(Date.now() + 3600000) };
    this.quotas.set(model, check);
    return check;
  }

  private async callLiteLLM(model: string, messages: any[]): Promise<any> {
    const response = await fetch(`${this.config.endpoint}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, messages }),
    });
    if (!response.ok) {
      throw new Error(`LiteLLM returned ${response.status}`);
    }
    const data = await response.json();
    return {
      model: data.model,
      content: data.choices[0].message.content,
      tokens: data.usage.total_tokens,
      cost: 0, // LiteLLM tracks cost separately
    };
  }

  private updateQuota(model: string, response: any): void {
    const current = this.quotas.get(model) || { model, remaining: 1000, resetAt: new Date() };
    this.quotas.set(model, { ...current, remaining: current.remaining - 1 });
  }
}
```

Don't modify any existing files. Just create this one. Report: "LiteLLM adapter created: /path/to/file"
''')
```

### Sprint 2 Wave 2.3: gbrain memU 集成（关键任务）

```bash
# T2.3.4: gbrain 兼容性验证（所有任务中最重要）
task(category="quick", description="T2.3.4: gbrain memU compatibility test", prompt='''
CRITICAL TASK: Verify that all 74 gbrain MCP tools are compatible with the memU backend BEFORE attempting migration.

1. Read the current gbrain backend code at /Users/xiamingxing/Workspace/projects/gbrain/ to understand the storage interface
2. Create a compatibility test script at /Users/xiamingxing/Workspace/projects/gbrain/tests/memu_compat_test.ts that:
   - Loads the memU Rust library (or uses a stub if memU isn't compiled)
   - Runs through each of the 74 MCP tools
   - Reports which tools are compatible and which need changes
3. If memU isn't compiled yet (likely), write the test with a stub that matches the memU API

Report:
- Number of compatible tools (X/74)
- List of incompatible tools with reasons
- Estimated migration effort (hours)

This task determines whether Sprint 2 Wave 2.3 is feasible. Do NOT attempt migration until this report is generated.
''')
```

### Sprint 3 Wave 3.2: 架构合规检查

```bash
# T3.2.3: 架构合规自动检查
task(category="quick", description="T3.2.3: Architecture compliance check", prompt='''
Check the 10 architecture laws against the current codebase.

Run these checks from /Users/xiamingxing/Workspace:

1. I0 layers: grep for non-agora cross-layer imports (any layer importing from another layer directly)
   ```bash
   # Check kairon packages don't import each other directly (should go through agora)
   grep -r "from kairon\.packages\." projects/kairon/packages/ --include="*.py" | grep -v agora | grep -v core-models | grep -v __init__
   ```

2. MCP protocol: verify all inter-project communication uses MCP
   ```bash
   grep -r "import requests\|from urllib" projects/kairon/packages/ --include="*.py" | grep -v "agora" | grep -v "test"
   ```

3. core-models authority: check for duplicate data model definitions
   ```bash
   grep -r "class Entity\|class Relation\|class KnowledgeGraph" projects/ --include="*.py" | grep -v core-models | grep -v "adapter\|stub\|test"
   ```

4. SharedBrain knowledge processing: check SB doesn't do knowledge work
   ```bash
   grep -r "research\|derive\|ontology\|knowledge_graph" projects/SharedBrain/organs/D_KnowledgeIntegration/ --include="*.py" 2>/dev/null | head -5
   ```

Report violations for each law. 0 violations = PASS.
''')
```

---

## 验收检查清单（Prometheus 用，Agent 完成后执行）

```
Phase 1 最终验收 — Prometheus 执行

□ P1.1 — kairon × SharedBrain 整合
  □ Docker 5/5 healthy? (docker compose ps)
  □ 烟雾 6/6 PASS? (pytest tests/integration/smoke_test.py -v)
  □ core-models 3/3 import OK? (python -c "from nucleus.Z_Spore...")
  □ Agora registry 含 SharedBrain 20 tools? (grep sharedbrain registry.yaml)
  □ 4/4 organs .organ_status = delegated? (cat organs/*/ .organ_status)

□ P1.2 — sharedbrain-bridge 包
  □ pip install -e . 成功? (pip install sharedbrain-bridge/)
  □ 3 modules import OK? (python -c "from sharedbrain_bridge import eu, immune, sync")
  □ CLI 4 commands work? (sb-bridge status|sync|eu|audit)
  □ Agora registry 含 sharedbrain-bridge 5 tools?

□ P1.3 — agentmesh LiteLLM 适配
  □ LiteLLM Docker running? (curl localhost:4000/health)
  □ agentmesh LiteLLM adapter file exists? (ls .../litellm.ts)
  □ TypeScript compiles? (bun run check)

□ P1.4 — gbrain memU 兼容性
  □ 兼容性报告存在? (ls tests/memu_compat_test.ts)
  □ X/74 tools compatible (X ≥ 60 = GO)

□ P1.5 — 架构合规
  □ 10 laws 0 violations? (check-compliance.sh)

□ P1.6 — 文档
  □ README.md updated?
  □ AGENTS.md updated?
  □ CONVERGENCE.yaml updated?
  □ LAYER-INDEX.md updated?

ALL □ CHECKED → Phase 1 GO
ANY □ UNCHECKED → Phase 1 NO-GO (fix and re-verify)
```

---

## 文件索引

| 文件 | 角色 | 用途 |
|------|------|------|
| `architecture-final-vision.md` | 蓝图 | 终极架构目标 |
| `evolution-roadmap-4phases.md` | 路线图 | 4 阶段总览 |
| `phase1-sprint-plan.md` | 细案 | Sprint/Wave/Task 结构 |
| **`phase1-task-specs.md`** (本文件) | **任务规格书** | **Agent 可执行的命令模板** |
| `sharedbrain-kairon-integration.md` | 专项计划 | SharedBrain 融合详细方案 |
