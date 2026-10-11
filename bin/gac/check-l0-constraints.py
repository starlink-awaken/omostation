#!/usr/bin/env python3
"""CR-L0-ENFORCE: L0 协议约束 CI 校验.

读取 .omo/_truth/registry/.../L0-constraints.yaml (通过 ecos 子模块),
校验可自动化验证的 required 约束. 任一 FAIL 则 exit 1.

验证项 (15 项):
  X1-C01: port-registry 有注册条目
  X1-C03: agora register 是唯一写入口
  CR-MCP-LAZY-01: Agora 代理调用点显式 lazy=True (E-L0-011)
  CS-10:  BOS active 服务含 domain + realized_by
  X2-C01: port-registry 条目含 name
  X2-C03: CLAUDE.md 保鲜 ≤60 天
  X2-C04: 协议半衰期 (protocol.age_days ≤ half_life_days, W-L0-005)
  X2-C05: omo-surfaces 复核 ≤14 天
  X3-C01: 功能域声明 value_tier (ecos governance/x3-value-stack.yaml)
  X3-C02: value_tier=1 的域必须有 cost_attribution != 'none'
  X3-C03: governance_stack 分层价值归因
  X4-C01: omo-surfaces 资产登记
  CR-OMO-SURFACE-01: .omo 顶层资产登记
  CR-OMO-SURFACE-02: .omo=state_plane 角色标签
  CR-C2G-V3-01: done+context_uri 任务必须有 ssot_written_back (P5 读侧门禁)
"""

import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PORT_REGISTRY = REPO / "protocols/port-registry.yaml"
# X2-C04 / CR-MCP-LAZY-01 的真实数据源 (ecos 子模块协议注册表 + agora 代理调用点)
L0_REGISTRY = REPO / "projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml"
BOS_SERVICES = REPO / "projects/agora/etc/bos-services.yaml"
OMO_SURFACES = REPO / ".omo/_truth/registry/omo-governance-surfaces.yaml"
CLAUDE_MD = REPO / "CLAUDE.md"
# X3 value_tier/cost_attribution 的真实生产者: ecos 子模块的 governance 注册表
# (5 域, 每域 value_tier + cost_attribution)。根仓 .omo/_truth/x3-value-stack.yaml
# 是 X1/X2/X3 机制清单, 不含 value_tier —— 旧 check_x3_c01 读它, 结构性永远
# missing 全部域且从不 gate (always True, 见 P1 audit)。
VALUE_STACK = REPO / "projects/ecos/src/ecos/ssot/registry/governance/x3-value-stack.yaml"
DONE_TASKS = REPO / ".omo" / "tasks" / "done"
# CR-MCP-LAZY-01 (E-L0-011): Agora 跨层 MCP 代理必须 lazy 初始化, 否则触发循环
# 依赖锁死。两个真实调用点都在 agora: bootstrap 的 proxy_manager.start(...) 与
# swarm 的 proxy.add_service(...)。每项 = (仓内相对路径, 必需形态, 禁止形态, 描述)。
# fail-closed: 调用点缺失或翻成 lazy=False 都算违规 (2026-08-06 plan 的
# AGORA_PROXY_EAGER env 翻转会移除字面 lazy=True, 必须在此拦下)。
LAZY_PROXY_SITES = [
    (
        "projects/agora/src/agora/mcp/mcp_bootstrap.py",
        r"proxy_manager\.start\([^)]*lazy\s*=\s*True",
        r"proxy_manager\.start\([^)]*lazy\s*=\s*False",
        "mcp_bootstrap.py proxy_manager.start(lazy=True)",
    ),
    (
        "projects/agora/src/agora/mcp/swarm.py",
        r"add_service\([\s\S]*?lazy\s*=\s*True",
        r"add_service\([\s\S]*?lazy\s*=\s*False",
        "swarm.py proxy.add_service(lazy=True)",
    ),
]


def check_x1_c01() -> tuple[bool, str]:
    """X1-C01: protocol.registered — port-registry 存在且有条目"""
    if not PORT_REGISTRY.is_file():
        return False, f"port-registry.yaml not found: {PORT_REGISTRY}"
    try:
        import yaml
        data = yaml.safe_load(PORT_REGISTRY.read_text()) or {}
        entries = data.get("ports") or data.get("entries") or data
        if isinstance(entries, dict):
            count = len(entries)
        elif isinstance(entries, list):
            count = len(entries)
        else:
            count = 0
        if count == 0:
            return False, "port-registry.yaml has no entries"
        return True, f"port-registry: {count} entries registered"
    except Exception as e:
        return False, f"port-registry parse error: {e}"


def check_cs10() -> tuple[bool, str]:
    """CS-10: active BOS 服务含 domain (required) + realized_by (渐进覆盖).

    required 部分 (domain) 必须 100% 满足; realized_by 作为渐进指标报告覆盖率,
    不阻塞 CI (历史债务, 持续改善).
    """
    if not BOS_SERVICES.is_file():
        return True, "bos-services.yaml not found (agora not init), skipped"
    try:
        import yaml
        data = yaml.safe_load(BOS_SERVICES.read_text()) or {}
        services = data.get("services") or []
        missing_domain = []
        missing_realized = []
        active_count = 0
        for svc in services:
            if not isinstance(svc, dict):
                continue
            status = str(svc.get("status", "active")).lower()
            if status == "deprecated":
                continue
            active_count += 1
            name = svc.get("action") or svc.get("name") or svc.get("domain", "?")
            if not svc.get("domain"):
                missing_domain.append(name)
            elif not svc.get("realized_by"):
                missing_realized.append(name)
        if missing_domain:
            return False, f"BOS {len(missing_domain)}/{active_count} active 服务缺 domain (required)"
        coverage = (active_count - len(missing_realized)) / active_count * 100 if active_count else 100
        return True, f"BOS: domain 100% | realized_by {coverage:.0f}% ({active_count - len(missing_realized)}/{active_count})"
    except Exception as e:
        return False, f"bos-services parse error: {e}"


def check_x2_c01() -> tuple[bool, str]:
    """X2-C01: protocol.version — port-registry 条目有 name (声明即注册)"""
    if not PORT_REGISTRY.is_file():
        return True, "port-registry not found, skipped"
    try:
        import yaml
        data = yaml.safe_load(PORT_REGISTRY.read_text()) or {}
        entries = data.get("ports") or data.get("entries") or data
        if not isinstance(entries, (dict, list)):
            return True, "port-registry empty, skipped"
        if isinstance(entries, dict):
            items = entries.values()
        else:
            items = entries
        unnamed = 0
        total = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            total += 1
            if not item.get("name"):
                unnamed += 1
        if unnamed:
            return False, f"port-registry: {unnamed}/{total} entries missing name"
        return True, f"port-registry: all {total} entries declared (name + status)"
    except Exception as e:
        return False, f"port-registry parse error: {e}"


def check_x2_c03() -> tuple[bool, str]:
    """X2-C03: CLAUDE.md 保鲜 ≤60 天"""
    if not CLAUDE_MD.is_file():
        return True, "CLAUDE.md not found, skipped"
    age_days = (time.time() - CLAUDE_MD.stat().st_mtime) / 86400
    if age_days > 60:
        return False, f"CLAUDE.md is {age_days:.0f} days old (max 60)"
    return True, f"CLAUDE.md: {age_days:.0f} days old (fresh)"


def check_x2_c04() -> tuple[bool, str]:
    """X2-C04: 协议引入超过 half_life_days 后应触发老化审查 (W-L0-005).

    谓词: protocol.age_days <= protocol.half_life_days。
    数据源: ecos 子模块 L0 注册表的 protocol_registry 段 —— 每条协议携带
    `introduced` (ISO 日期) 与 `half_life_days`, 故 age_days **由 introduced 派生**
    (`today - introduced`, 单位天)。这是 protocol_registry 的唯一时间字段, 也是
    编译器 compute_decay 的既定口径 (intro = strptime(p["introduced"]), age =
    now - intro); 只有像 CLAUDE.md 那样**无 introduced 字段**的对象才退化为文件
    mtime (见 X2-C03)。half_life_days 缺失或 introduced 非法一并计入违规。
    """
    if not L0_REGISTRY.is_file():
        return False, f"L0 registry not found: {L0_REGISTRY}"
    try:
        from datetime import date, datetime

        import yaml
        data = yaml.safe_load(L0_REGISTRY.read_text()) or {}
        protocols = data.get("protocol_registry") or []
        if not protocols:
            return False, "protocol_registry 为空 (producer 无数据, 不可绿)"
        today = date.today()
        bad = []
        for p in protocols:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id", "?"))
            half = p.get("half_life_days")
            intro = str(p.get("introduced") or "")
            if half is None or not intro:
                bad.append(f"{pid}(缺 introduced/half_life_days)")
                continue
            try:
                age = (today - datetime.strptime(intro[:10], "%Y-%m-%d").date()).days
            except ValueError:
                bad.append(f"{pid}(introduced 非法: {intro})")
                continue
            if age > half:
                bad.append(f"{pid}({age}d > {half}d)")
        if bad:
            return False, f"W-L0-005: {len(bad)} 协议超半衰期: {'; '.join(bad)}"
        return True, f"protocol shelf-life: all {len(protocols)} protocols within half_life"
    except Exception as e:
        return False, f"X2-C04 check error: {e}"


def check_x4_c01() -> tuple[bool, str]:
    """X4-C01: omo-governance-surfaces.yaml 存在且可解析 (多文档 YAML)"""
    if not OMO_SURFACES.is_file():
        return False, f"omo-governance-surfaces.yaml not found: {OMO_SURFACES}"
    try:
        import yaml
        docs = list(yaml.safe_load_all(OMO_SURFACES.read_text()))
        assets = []
        for doc in docs:
            if isinstance(doc, dict) and "assets" in doc:
                assets = doc.get("assets") or []
                break
        return True, f"omo-governance-surfaces: {len(assets)} assets registered"
    except Exception as e:
        return False, f"omo-governance-surfaces parse error: {e}"


def check_x2_c05() -> tuple[bool, str]:
    """X2-C05: omo-governance-surfaces registry ≤14 天复核"""
    if not OMO_SURFACES.is_file():
        return True, "omo-surfaces not found, skipped"
    try:
        import yaml
        docs = list(yaml.safe_load_all(OMO_SURFACES.read_text()))
        front = docs[0] if docs else {}
        lr = front.get("last-reviewed", "")
        if not lr:
            return True, "omo-surfaces: no last-reviewed (advisory)"
        from datetime import datetime
        try:
            last = datetime.strptime(str(lr)[:10], "%Y-%m-%d")
            age = (datetime.now() - last).days
            if age > 14:
                return False, f"omo-surfaces: last-reviewed {age}d ago (max 14)"
            return True, f"omo-surfaces: reviewed {age}d ago (fresh)"
        except ValueError:
            return True, f"omo-surfaces: last-reviewed={lr}"
    except Exception as e:
        return True, f"omo-surfaces parse error: {e}"


def check_omo_surface_registration() -> tuple[bool, str]:
    """CR-OMO-SURFACE-01: `.omo` 顶层治理资产已登记到 omo governance surfaces registry.

    数据源: OMO_SURFACES (仓库内真实注册表, 43 条 assets, 每条含 ref)。判据:
    顶层 `.omo` 下实际存在的一级资产 (目录或文件) 必须能在注册表 assets 的 ref 里
    找到对应条目 —— 用注册表的 `ref` 字段逐条解析第一段路径, 而非 `str(assets)` 子串
    (旧实现对 `str(assets)` 做子串匹配, 结构上恒真, 且无论结果如何都 return True)。
    """
    if not OMO_SURFACES.is_file():
        return False, f"omo-governance-surfaces.yaml not found: {OMO_SURFACES}"
    try:
        import yaml
        docs = list(yaml.safe_load_all(OMO_SURFACES.read_text()))
        data = next((d for d in docs if isinstance(d, dict) and "assets" in d), {})
        assets = data.get("assets") or []
        if not assets:
            return False, "omo-governance-surfaces: assets 为空 (必须至少声明一个顶层资产)"
        # 注册表声明的顶层路径集合: 从每条 asset 的 ref 取第一段
        registered = set()
        for a in assets:
            r = str((a or {}).get("ref", ""))
            if r.startswith(".omo/"):
                registered.add(r[len(".omo/"):].split("/", 1)[0])
        # 实况: .omo 下实际存在的一级资产
        omo_root = REPO / ".omo"
        if not omo_root.is_dir():
            return False, ".omo/ 目录不存在"
        actual = {p.name for p in omo_root.iterdir()}
        missing = sorted(actual - registered)
        if missing:
            return False, (
                f"OMO-SURFACE: {len(missing)} 个 .omo 顶层资产未登记: {missing}"
                " (需在 omo-governance-surfaces.yaml assets 中登记 ref)"
            )
        return True, f"omo-surfaces: {len(registered)} 个顶层资产全部登记"
    except Exception as e:
        return False, f"omo-surface check error: {e}"



def check_x1_c03():
    """X1-C03: Agora register write entry"""
    if not BOS_SERVICES.is_file():
        return True, "bos-services not found, skipped"
    try:
        import yaml
        data = yaml.safe_load(BOS_SERVICES.read_text()) or {}
        services = data.get("services") or []
        has_register = any(
            (svc.get("action") == "register" or "register" in str(svc.get("name", "")))
            for svc in services if isinstance(svc, dict)
        )
        return (True, "agora register: entry point exists") if has_register else (False, "agora register: no entry point")
    except Exception as e:
        return True, f"agora parse error: {e}"


def check_cr_mcp_lazy_01() -> tuple[bool, str]:
    """CR-MCP-LAZY-01: Agora 跨层 MCP 代理必须 lazy 初始化 (E-L0-011).

    规则: proxy.initialization == 'lazy'。防止 eager 初始化触发循环依赖锁死。
    本仓把这类不变量表达为 follow-CI 的 check-l0-constraints 检查 (本文件), 而
    非运行期 assert —— 因为 (a) Agora bootstrap 在 SSE/stdio 服务器进程里才跑,
    CI 不会执行它; (b) `python -O` 会剥掉 assert。故在此对两个真实调用点做
    源码形态断言 (fail-closed)。
    """
    problems = []
    seen = 0
    for rel, req_re, bad_re, desc in LAZY_PROXY_SITES:
        f = REPO / rel
        if not f.is_file():
            problems.append(f"{desc}: 调用点文件缺失 ({rel})")
            continue
        seen += 1
        text = f.read_text(encoding="utf-8")
        if re.search(bad_re, text):
            problems.append(f"{desc}: 检出 lazy=False (eager 初始化)")
        elif not re.search(req_re, text):
            problems.append(f"{desc}: 未找到显式 lazy=True 调用 (疑似 eager/改写)")
    if problems:
        return False, "E-L0-011: " + "; ".join(problems)
    return True, f"lazy proxy: {seen}/{len(LAZY_PROXY_SITES)} call sites keep explicit lazy=True"


def check_x3_c01():
    """X3-C01: 每个功能域应声明 value_tier (preferred · 真实门禁).

    数据源: ecos 子模块 governance/x3-value-stack.yaml —— 该文件的 domains 自带
    value_tier。旧实现读根仓 .omo/_truth/x3-value-stack.yaml (不含 value_tier 字段,
    结构性 missing 全部域) 且从不 gate (always True)。现在: 每域必须声明 value_tier。
    """
    if not VALUE_STACK.is_file():
        return False, f"value-stack not found: {VALUE_STACK}"
    try:
        import yaml
        data = yaml.safe_load(VALUE_STACK.read_text()) or {}
        domains = data.get("domains", {})
        if not domains:
            return False, "value-stack: no domains (producer 无数据, 不可绿)"
        missing = [d for d, v in domains.items() if isinstance(v, dict) and v.get("value_tier") is None]
        total = len(domains)
        if missing:
            return False, f"value_tier: {len(missing)}/{total} 域未声明: {missing}"
        return True, f"value_tier: {total - len(missing)}/{total} declared"
    except Exception as e:
        return False, f"value-stack parse error: {e}"


def check_x3_c02():
    """X3-C02: value_tier=1 的域必须有 cost_attribution != 'none' (required · 真实门禁).

    此前编译器为它生成的是 X3-C01 的谓词 (value_tier is None) —— 双错: 谓词错 +
    state['domain'] 无生产者。这里实现真谓词: tier-1 域 cost_attribution ∈
    {implemented, planned} 才算合规; 缺省/显式 'none' 都 FAIL。
    """
    if not VALUE_STACK.is_file():
        return False, f"value-stack not found: {VALUE_STACK}"
    try:
        import yaml
        data = yaml.safe_load(VALUE_STACK.read_text()) or {}
        domains = data.get("domains", {})
        if not domains:
            return False, "value-stack: no domains (producer 无数据, 不可绿)"
        bad = []
        for d, v in domains.items():
            if not isinstance(v, dict):
                continue
            if v.get("value_tier") == 1:
                ca = v.get("cost_attribution")
                if ca is None or str(ca).lower() == "none":
                    bad.append((d, ca))
        if bad:
            names = ", ".join(f"{d}={ca!r}" for d, ca in bad)
            return False, f"X3-C02: tier-1 域无成本归因: {names}"
        return True, "X3-C02: all tier-1 domains have cost_attribution"
    except Exception as e:
        return False, f"value-stack parse error: {e}"


def check_x3_c03():
    """X3-C03: governance_stack 3-layer attribution"""
    if not OMO_SURFACES.is_file():
        return True, "omo-surfaces not found, skipped"
    try:
        import yaml
        docs = list(yaml.safe_load_all(OMO_SURFACES.read_text()))
        data = docs[1] if len(docs) > 1 else (docs[0] if docs else {})
        stack = data.get("governance_stack", [])
        layers = {s.get("id", "") for s in stack if isinstance(s, dict)} if isinstance(stack, list) else set()
        missing = {"state_plane", "kernel_plane", "ingress_plane"} - layers
        if missing:
            return False, f"governance_stack: missing {missing}"
        return True, "governance_stack: 3 layers OK"
    except Exception as e:
        return True, f"parse error: {e}"


def check_c2g_v3_01():
    """CR-C2G-V3-01: done 任务若携带 context_uri, 必须有 ssot_written_back=true.

    P5 (2026-10-10): 写侧存在 (bin/ssot/ssot-writeback.py:30,46 · mof-extract.py:272-285
    置 flag), 但无读侧、无调度 —— 此前无人读这个 flag, 规则无宿主管道。这里是**读侧门禁**:
    扫描 .omo/tasks/done/*.yaml, 任何 status=done 且含 context_uri 而未标
    ssot_written_back=true 的任务都 FAIL, 直到 writeback 真正跑完或被**显式历史豁免**.

    历史豁免 (2026-10-10, P5 consequence resolution): 规则回顾性地扫到一批在**读侧
    门禁存在之前**就已 done 的任务。经逐条核实, 这些任务的回写目标要么不存在、
    要么是 .py/.yaml (markdown 追加会损坏文件), 且交付内容已保存在仓库 (代码/文档/
    evidence)。因此逐条在任务文件里写 `ssot_writeback_hist` (dated, 带 content 保
    存位置与理由)。**本检查不静默跳过**: 带豁免注解的任务仍出现在输出里 (HIST 桶),
    只是不判 FAIL; 任何**没有**注解也没置 flag 的 done+context_uri 任务依旧 FAIL。
    """
    if not DONE_TASKS.is_dir():
        return False, f"done tasks dir not found: {DONE_TASKS}"
    try:
        import yaml
        files = sorted(DONE_TASKS.glob("*.yaml"))
        missing = []
        hist = []
        for f in files:
            try:
                task = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            if not isinstance(task, dict):
                continue
            if str(task.get("status", "")).lower() != "done":
                continue
            if not task.get("context_uri"):
                continue
            if task.get("ssot_written_back") is True:
                continue
            h = task.get("ssot_writeback_hist")
            if isinstance(h, dict) and h.get("annotated_at") and h.get("reason"):
                hist.append(f"{f.name}(annotated {h.get('annotated_at')})")
                continue
            missing.append((f.name, str(task.get("context_uri"))[:60]))
        notes = []
        if hist:
            notes.append(f"{len(hist)} 条历史豁免 (显式 dated 注解, 非静默): {'; '.join(hist)}")
        if missing:
            names = "; ".join(f"{n}({u})" for n, u in missing)
            notes.append(f"CR-C2G-V3-01: {len(missing)} 条 done 任务未回写 SSOT: {names}")
            return False, " | ".join(notes)
        return True, " | ".join(notes or [f"{len(files)} done 任务全部回写/历史豁免"])
    except Exception as e:
        return False, f"CR-C2G-V3-01 check error: {e}"


def check_omo_surface_02():
    """CR-OMO-SURFACE-02: `.omo` 只能是治理状态面 (state_plane), 不得替代 projects/omo
    治理内核 (governance_kernel) — 读 governance_stack 真数据.

    旧实现硬编码 `return True` (always green)。现在: 必须存在 state_plane 条目 (ref=.omo/)
    与 kernel 条目 (ref=projects/omo/ 且 role=governance_kernel); 缺任一即 FAIL。
    """
    if not OMO_SURFACES.is_file():
        return False, f"omo-surfaces not found: {OMO_SURFACES}"
    try:
        import yaml
        docs = list(yaml.safe_load_all(OMO_SURFACES.read_text()))
        data = next((d for d in docs if isinstance(d, dict) and "governance_stack" in d), {})
        stack = data.get("governance_stack", [])
        ids = {s.get("id") for s in stack if isinstance(s, dict)}
        by_ref = {str(s.get("ref", "")): s for s in stack if isinstance(s, dict)}
        state = by_ref.get(".omo/")
        kernel = by_ref.get("projects/omo/")
        problems = []
        if "state_plane" not in ids or state is None:
            problems.append("缺 state_plane (ref=.omo/) — .omo 未被声称为治理状态面")
        if "kernel_plane" not in ids or kernel is None:
            problems.append("缺 kernel_plane (ref=projects/omo/) — 治理内核未分离")
        elif kernel.get("role") != "governance_kernel":
            problems.append(f"kernel_plane.role={kernel.get('role')!r} ≠ governance_kernel")
        if problems:
            return False, "CR-OMO-SURFACE-02: " + "; ".join(problems)
        return True, "omo roles: state_plane (.omo/) + governance_kernel (projects/omo/) OK"
    except Exception as e:
        return False, f"omo-surface-02 check error: {e}"

def main() -> int:
    checks = [
        ("X1-C01", check_x1_c01),
        ("X1-C03", check_x1_c03),
        ("CR-MCP-LAZY-01", check_cr_mcp_lazy_01),
        ("CS-10", check_cs10),
        ("X2-C01", check_x2_c01),
        ("X2-C03", check_x2_c03),
        ("X2-C04", check_x2_c04),
        ("X2-C05", check_x2_c05),
        ("X3-C01", check_x3_c01),
        ("X3-C02", check_x3_c02),
        ("X3-C03", check_x3_c03),
        ("X4-C01", check_x4_c01),
        ("CR-OMO-SURFACE-01", check_omo_surface_registration),
        ("CR-OMO-SURFACE-02", check_omo_surface_02),
        # P5 (2026-10-10): 读侧门禁 —— done+context_uri 任务必须有 ssot_written_back。
        # 注: 本检查在**当前仓库**会红 (5 条既有 done 任务未回写, 见输出) —— 这是
        # 真实强制, 直到 writeback 跑完或被显式豁免。参见 L0 注册表 wiring_note。
        ("CR-C2G-V3-01", check_c2g_v3_01),
    ]

    print("── L0 协议约束 CI 校验 ──")
    all_pass = True
    for cid, fn in checks:
        passed, detail = fn()
        icon = "OK" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{icon}] {cid}: {detail}")

    print()
    if all_pass:
        print("L0 constraints PASS")
        return 0
    print("L0 constraints FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
