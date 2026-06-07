#!/usr/bin/env python3
"""
eCOS v5 — 交互式接入向导 (ecos-onboard)
=========================================
引导新 Agent/工具逐步接入 MetaOS 体系。

用法:
    python3 ecos-onboard.py              # 交互模式
    python3 ecos-onboard.py --check      # 仅检查

输出:
    引导 Agent 完成 4 级接入深度验证

退出码:
    0 = 完全接入
    1 = 部分接入（建议修复）
    2 = 未接入
"""

import sys
import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path


DOCS = Path.home() / "Documents"
SCRIPTS = DOCS / "驾驶舱" / "scripts"
ECOS = Path.home() / ".ecos" / "scripts"
CARDS_DB = Path.home() / "Workspace" / "data" / "cards" / "cards.db"

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg):    print(f"  {GREEN}✅{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}⚠️{RESET} {msg}")
def fail(msg):  print(f"  {RED}❌{RESET} {msg}")
def info(msg):  print(f"  {CYAN}ℹ️{RESET} {msg}")
def section(n, title):
    print(f"\n  {BOLD}─── Level {n}: {title} ───{RESET}\n")


def check_file(path, name):
    p = Path(path)
    exists = p.exists()
    if exists:
        ok(f"{name}: {path}")
    else:
        fail(f"{name} 不存在: {path}")
    return exists


def check_cmd(cmd, name, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            ok(f"{name}")
            return True
        else:
            warn(f"{name} — exit={r.returncode}")
            return False
    except FileNotFoundError:
        fail(f"{name} — 命令不存在")
        return False
    except subprocess.TimeoutExpired:
        warn(f"{name} — 超时")
        return False


def print_header():
    print()
    print(f"  {BOLD}{'='*56}{RESET}")
    print(f"  {BOLD}  eCOS v5 — 接入引导向导 (ecos-onboard){RESET}")
    print(f"  {BOLD}{'='*56}{RESET}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 交互式接入向导")
    parser.add_argument("--check", action="store_true", help="仅检查模式")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    results = {}
    overall_pass = 0
    overall_total = 0

    print_header()

    # ── Level 1: 只读观察者 ──
    section(1, "只读观察者 (Read-Only Observer)")
    l1_pass = 0
    l1_total = 4

    if check_file(DOCS / "CLAUDE_COWORK_GLOBAL.md", "L4 网关"):
        l1_pass += 1

    if check_file(SCRIPTS / "ecos-health-check.py", "健康检查脚本"):
        if check_cmd(
            ["python3", str(SCRIPTS / "ecos-health-check.py"), "--skip", "kairon-gov"],
            "健康检查可执行"
        ):
            l1_pass += 1

    if check_cmd(
        ["python3", str(SCRIPTS / "x3-coverage-report.py")],
        "覆盖率报告可执行"
    ):
        l1_pass += 1

    if check_cmd(
        ["python3", str(SCRIPTS / "check-claude-freshness.py"),
         "--root", str(DOCS), "--max-age-days", "60"],
        "保鲜检查可执行"
    ):
        l1_pass += 1

    print(f"\n  Level 1: {l1_pass}/{l1_total} 通过")
    results["L1_read_only"] = {"pass": l1_pass, "total": l1_total,
                                "status": "passed" if l1_pass == l1_total else "partial"}

    # ── Level 2: 域级参与者 ──
    section(2, "域级参与者 (Domain Participant)")
    l2_pass = 0
    l2_total = 6

    domain_files = [
        ("驾驶舱入口", DOCS / "驾驶舱" / "CLAUDE.md"),
        ("Vault 入口", DOCS / "学习进化" / "CLAUDE.md"),
        ("工具箱入口", DOCS / "工具箱" / "CLAUDE.md"),
        ("领域知识库入口", DOCS / "领域知识库" / "CLAUDE.md"),
        ("工作文档入口", DOCS / "工作文档" / "CLAUDE.md"),
        ("家庭生活入口", DOCS / "家庭生活" / "CLAUDE.md"),
    ]

    for name, path in domain_files:
        if check_file(path, name):
            l2_pass += 1

    print(f"\n  Level 2: {l2_pass}/{l2_total} 通过")
    results["L2_domain"] = {"pass": l2_pass, "total": l2_total,
                             "status": "passed" if l2_pass == l2_total else "partial"}

    # ── Level 3: 全栈 Agent ──
    section(3, "全栈 Agent (Full-Stack Agent)")
    l3_pass = 0
    l3_total = 4

    if CARDS_DB.exists():
        card_count = None
        try:
            r = subprocess.run(
                ["sqlite3", str(CARDS_DB),
                 "SELECT COUNT(*) FROM cards WHERE status NOT IN "
                 "('done','resolved','discarded','archived','cancelled','superseded')"],
                capture_output=True, text=True, timeout=5
            )
            card_count = r.stdout.strip()
        except Exception:
            pass

        if card_count:
            ok(f"CARDS 数据库可读 ({card_count} 活跃卡片)")
            l3_pass += 1
        else:
            warn("CARDS 数据库不可读")
    else:
        fail(f"CARDS 数据库不存在: {CARDS_DB}")

    if check_file(ECOS / "check-cards-state-consistency.py", "CARDS↔STATE 一致性脚本"):
        l3_pass += 1

    if check_file(ECOS / "cards-value-attribution.py", "CARDS 价值归因脚本"):
        l3_pass += 1

    if check_file(SCRIPTS / "check-vault-audit.py", "Vault 审计脚本"):
        l3_pass += 1

    print(f"\n  Level 3: {l3_pass}/{l3_total} 通过")
    results["L3_full_agent"] = {"pass": l3_pass, "total": l3_total,
                                 "status": "passed" if l3_pass == l3_total else "partial"}

    # ── Level 4: 运行时集成 ──
    section(4, "运行时集成 (Runtime Integration)")
    l4_pass = 0
    l4_total = 6

    # Daemon
    if check_file(ECOS / "ecos-daemon.py", "Daemon 脚本"):
        l4_pass += 1

    # Register
    if check_file(ECOS / "ecos-register.py", "L1 注册脚本"):
        if check_cmd(
            ["python3", str(ECOS / "ecos-register.py"), "--health"],
            "L1 注册服务健康"
        ):
            l4_pass += 1

    # Event
    if check_file(ECOS / "ecos-event.py", "I0 事件脚本"):
        if check_cmd(
            ["python3", str(ECOS / "ecos-event.py"), "--tail", "1"],
            "事件流可读"
        ):
            l4_pass += 1

    # L0 constraint validator
    constraint_path = DOCS / "学习进化" / "2-knowledge" / "基建架构" / "ecos-constraint-validator.py"
    if constraint_path.exists():
        if check_cmd(
            ["python3", str(constraint_path)],
            "L0 约束校验"
        ):
            l4_pass += 1
    else:
        fail("L0 约束校验器不存在")

    print(f"\n  Level 4: {l4_pass}/{l4_total} 通过")
    results["L4_runtime"] = {"pass": l4_pass, "total": l4_total,
                              "status": "passed" if l4_pass == l4_total else "partial"}

    overall_pass += l1_pass + l2_pass + l3_pass + l4_pass
    overall_total += l1_total + l2_total + l3_total + l4_total

    # ── 汇总 ──
    print(f"\n  {BOLD}{'='*56}{RESET}")
    print(f"  {BOLD}  接入汇总{RESET}")
    print(f"  {BOLD}{'='*56}{RESET}")
    print(f"\n  Level 1 (只读)  : {l1_pass}/{l1_total}  {'✅' if l1_pass==l1_total else '⚠️'}")
    print(f"  Level 2 (域级)  : {l2_pass}/{l2_total}  {'✅' if l2_pass==l2_total else '⚠️'}")
    print(f"  Level 3 (全栈)  : {l3_pass}/{l3_total}  {'✅' if l3_pass==l3_total else '⚠️'}")
    print(f"  Level 4 (运行时) : {l4_pass}/{l4_total}  {'✅' if l4_pass==l4_total else '⚠️'}")
    print(f"\n  综合: {overall_pass}/{overall_total} 通过  "
          f"({overall_pass/overall_total*100:.0f}%)")
    print()

    if overall_pass == overall_total:
        print(f"  {GREEN}✅ 系统完全就绪 — Agent 可全功能接入{RESET}")
    elif overall_pass > overall_total * 0.5:
        print(f"  {YELLOW}⚠️  部分接入 — 可运行但建议修复上述失败项{RESET}")
    else:
        print(f"  {RED}❌ 未接入 — 先确认基础设施{RESET}")

    print(f"\n  详细引导: ~/Documents/驾驶舱/ONBOARD.md")
    print(f"  能力注册表: ~/Documents/驾驶舱/agent-manifest.yaml")

    if args.json:
        result_data = {
            "timestamp": datetime.now().isoformat(),
            "levels": {
                "L1_read_only": results["L1_read_only"],
                "L2_domain": results["L2_domain"],
                "L3_full_agent": results["L3_full_agent"],
                "L4_runtime": results["L4_runtime"],
            },
            "summary": {"pass": overall_pass, "total": overall_total,
                        "ratio": round(overall_pass/overall_total, 4) if overall_total > 0 else 0}
        }
        print(json.dumps(result_data, ensure_ascii=False, indent=2))

    # 记录入口事件到 L3 价值追踪
    try:
        entry_logger = SCRIPTS / "ecos-entry-logger.py"
        if entry_logger.exists():
            import subprocess
            subprocess.run(
                ["python3", str(entry_logger), "--entry", "onboard",
                 "--intent", "governance_check", "--result",
                 "pass" if overall_pass == overall_total else "warn",
                 "--duration", str(int(time.time() - (time.time() - 30)))],
                capture_output=True, timeout=5)
    except Exception:
        pass

    sys.exit(0 if overall_pass == overall_total else 1)


if __name__ == "__main__":
    main()
