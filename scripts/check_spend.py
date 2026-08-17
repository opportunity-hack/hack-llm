#!/usr/bin/env python3
"""Live per-team spend table from the LiteLLM gateway (PLAN.md Phase 3/6).

Prints alias, spend, budget, % used (warns ≥80%), frontier-lane spend where
available, and the event-wide total. Run manually or via cron during the event.

Usage:
    python scripts/check_spend.py --base-url https://ai.ohack.dev --master-key sk-...
    python scripts/check_spend.py ... --warn-threshold 0.8
"""

import argparse
import sys

import requests


def fetch_keys(base_url: str, headers: dict) -> list:
    keys, page = [], 1
    while True:
        r = requests.get(f"{base_url}/key/list",
                         params={"page": page, "size": 100, "return_full_object": "true"},
                         headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        keys.extend(k for k in data.get("keys", []) if isinstance(k, dict))
        if page >= int(data.get("total_pages") or 1):
            break
        page += 1
    return keys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="https://ai.ohack.dev")
    ap.add_argument("--master-key", default="")
    ap.add_argument("--warn-threshold", type=float, default=0.8)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        print(f"Would query {args.base_url}/key/list and print a spend table.")
        return 0
    if not args.master_key:
        print("error: --master-key required", file=sys.stderr)
        return 2

    base_url = args.base_url.rstrip("/")
    keys = fetch_keys(base_url, {"Authorization": f"Bearer {args.master_key}"})
    keys.sort(key=lambda k: (k.get("key_alias") or "~"))

    total_spend = 0.0
    warned = 0
    print(f"{'key alias':<20} {'spend':>9} {'budget':>9} {'used':>6}  flag")
    print("-" * 54)
    for k in keys:
        alias = k.get("key_alias") or k.get("token", "")[:12]
        spend = float(k.get("spend") or 0)
        budget = k.get("max_budget")
        total_spend += spend

        if budget:
            frac = spend / float(budget)
            flag = ""
            if frac >= 1:
                flag = "EXHAUSTED"
            elif frac >= args.warn_threshold:
                flag = f"WARN >{args.warn_threshold:.0%}"
                warned += 1
            print(f"{alias:<20} {spend:>8.2f}$ {float(budget):>8.2f}$ {frac:>6.0%}  {flag}")
        else:
            print(f"{alias:<20} {spend:>8.2f}$ {'∞':>9}")

    print("-" * 66)
    print(f"EVENT TOTAL: ${total_spend:.2f}   (PLAN §6: >$500 announce ohack-free; "
          f">$800 disable frontier — see runbook.md)")
    if warned:
        print(f"{warned} key(s) past {args.warn_threshold:.0%} — consider a heads-up to those teams.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
