"""Credentials CLI — 管理 API Key 和配额。

Usage:
    credentials list                     List all stored keys
    credentials add <provider> --key k   Add a key
    credentials remove <provider>        Remove a key
    credentials quota [provider]         Show quota status
    credentials budget <provider> --limit 50 --action block
"""

from __future__ import annotations

import argparse
import sys


def cmd_list() -> int:
    from llm_gateway.credentials import CredentialsManager
    cm = CredentialsManager()
    summary = cm.get_summary()
    if not summary["keys"]:
        print("No credentials stored.")
        print("💡 Add one: credentials add openai --key sk-...")
        return 0

    print(f"{'Provider':15s} {'Key':20s} {'Weight':8s} {'Active':8s}")
    print("-" * 55)
    for k in summary["keys"]:
        print(f"{k['provider']:15s} {k['key_preview']:20s} {k['weight']:8d} {'✅' if k['active'] else '❌':8s}")

    if summary["quotas"]:
        print(f"\n{'Provider':15s} {'Budget':12s} {'Spent':10s} {'Left':10s} {'Used':8s}")
        print("-" * 55)
        for p, q in summary["quotas"].items():
            print(f"{p:15s} ${q['monthly_limit']:<8.2f} ${q['spend']:<6.4f} ${q['remaining']:<6.4f} {q['usage_pct']:>6.1f}%")
    return 0


def cmd_add(provider: str, api_key: str, base_url: str = "", note: str = "") -> int:
    from llm_gateway.credentials import CredentialsManager
    cm = CredentialsManager()
    cm.add_key(provider, api_key, base_url=base_url, note=note)
    print(f"✅ Added key for {provider}")
    return 0


def cmd_remove(provider: str) -> int:
    from llm_gateway.credentials import CredentialsManager
    cm = CredentialsManager()
    keys = cm.list_keys(provider)
    if not keys:
        print(f"No keys found for {provider}")
        return 1
    for k in keys:
        cm.remove_key(provider, k["key_preview"].replace("...", ""))
    print(f"Removed keys for {provider}")
    return 0


def cmd_quota(provider: str = "") -> int:
    from llm_gateway.credentials import CredentialsManager
    cm = CredentialsManager()
    if provider:
        q = cm.get_quota(provider)
        src = q.get("source", "local")
        if q.get("status") == "unlimited":
            print(f"{provider}: unlimited (no budget set)")
        elif src == "codexbar":
            desc = q.get("reset_description", "")
            print(f"{provider}:")
            print(f"  Source:   codexbar (实时配额)")
            print(f"  Used:     {q.get('used', 0)}%")
            if desc:
                print(f"  Detail:   {desc}")
        else:
            print(f"{provider}:")
            print(f"  Budget:   ${q.get('monthly_limit', 0):.2f}/month")
            print(f"  Spent:    ${q.get('spend', 0):.4f}")
            print(f"  Left:     ${q.get('remaining', 0):.4f}")
            print(f"  Used:     {q.get('usage_pct', 0):.1f}%")
            print(f"  Action:   {q.get('action', 'warn')}")
    else:
        summary = cm.get_summary()
        if not summary["quotas"]:
            print("No budgets configured.")
            print("💡 Set one: credentials budget openai --limit 50 --action block")
            return 0
        for p, q in summary["quotas"].items():
            up = q.get('usage_pct', q.get('used', 0))
            bar = "█" * int(up / 5) + "░" * (20 - int(up / 5))
            src = q.get("source", "local")
            if src == "codexbar":
                print(f"  {p:12s} {bar} {up:5.1f}%  (codexbar)")
            else:
                print(f"  {p:12s} {bar} {up:5.1f}%  ${q.get('spend', 0):.2f}/${q.get('monthly_limit', 0):.2f}")
    return 0


def cmd_budget(provider: str, limit: float, action: str = "warn") -> int:
    from llm_gateway.credentials import CredentialsManager
    cm = CredentialsManager()
    cm.set_budget(provider, limit, action)
    print(f"✅ Budget set: {provider} ${limit:.2f}/month (action: {action})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="credentials", description="API Key & Quota Manager")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List all keys")

    add = sub.add_parser("add", help="Add a key")
    add.add_argument("provider", help="Provider name (e.g. openai)")
    add.add_argument("--key", "-k", required=True, help="API key")
    add.add_argument("--base-url", "-u", default="", help="Base URL")
    add.add_argument("--note", "-n", default="", help="Description")

    rm = sub.add_parser("remove", help="Remove keys for a provider")
    rm.add_argument("provider", help="Provider name")

    quota = sub.add_parser("quota", help="Show quota status")
    quota.add_argument("provider", nargs="?", default="", help="Provider (omit for all)")

    budget = sub.add_parser("budget", help="Set monthly budget")
    budget.add_argument("provider", help="Provider name")
    budget.add_argument("--limit", "-l", type=float, required=True, help="Monthly limit ($)")
    budget.add_argument("--action", "-a", choices=["block", "warn", "log"], default="warn",
                        help="Action when exceeded")

    args = parser.parse_args(argv)
    if args.cmd == "list":
        return cmd_list()
    elif args.cmd == "add":
        return cmd_add(args.provider, args.key, args.base_url, args.note)
    elif args.cmd == "remove":
        return cmd_remove(args.provider)
    elif args.cmd == "quota":
        return cmd_quota(args.provider)
    elif args.cmd == "budget":
        return cmd_budget(args.provider, args.limit, args.action)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
