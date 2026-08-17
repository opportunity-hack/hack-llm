#!/usr/bin/env python3
"""Teardown: revoke ALL hackathon keys on the LiteLLM gateway (PLAN.md Phase 6).

Deletes every key whose alias matches the provisioning scheme
(team-*, spare-*, mentors, admin). Requires --yes for the real thing.

Usage:
    python scripts/revoke_all.py --base-url https://ai.ohack.dev --master-key sk-... --dry-run
    python scripts/revoke_all.py --base-url https://ai.ohack.dev --master-key sk-... --yes
"""

import argparse
import re
import sys

import requests

ALIAS_RE = re.compile(r"^(team-\d{2}|spare-\d{2}|mentors|admin)(-frontier)?$")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="https://ai.ohack.dev")
    ap.add_argument("--master-key", default="")
    ap.add_argument("--yes", action="store_true", help="actually revoke")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.master_key:
        print("error: --master-key required", file=sys.stderr)
        return 2
    base_url = args.base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {args.master_key}"}

    aliases, page = [], 1
    while True:
        r = requests.get(f"{base_url}/key/list",
                         params={"page": page, "size": 100, "return_full_object": "true"},
                         headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        for k in data.get("keys", []):
            alias = k.get("key_alias") if isinstance(k, dict) else None
            if alias and ALIAS_RE.match(alias):
                aliases.append(alias)
        if page >= int(data.get("total_pages") or 1):
            break
        page += 1

    print(f"{len(aliases)} matching keys: {', '.join(sorted(aliases))}")
    if args.dry_run or not args.yes:
        print("Dry run (pass --yes to revoke). Nothing deleted.")
        return 0

    for batch_start in range(0, len(aliases), 20):
        batch = aliases[batch_start:batch_start + 20]
        r = requests.post(f"{base_url}/key/delete",
                          json={"key_aliases": batch}, headers=headers, timeout=30)
        if r.status_code != 200:
            print(f"batch failed HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return 1
        print(f"revoked: {', '.join(batch)}")
    print("All hackathon keys revoked. Master key still works — rotate it too if the event is over.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
