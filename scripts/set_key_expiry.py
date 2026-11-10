#!/usr/bin/env python3
"""Set (or audit) the expiry on hackathon keys that already exist on the gateway.

Why this exists: until 2026-11-08 neither scripts/provision_keys.py nor the
ohack.dev backend (`api/teams/gateway_keys.py`) gave keys an expiry. The
backend sent an `expires` field that LiteLLM's /key/generate does not have
(silently dropped); the card provisioner sent nothing. Every live key showed
`expires: None` — they would have authenticated forever. LiteLLM sets expiry
from `duration` ("<seconds>s") on /key/update, so this script sweeps
/key/list and PATCHes each matching key once.

Matches both key families by alias:
  - card keys:    team-NN, team-NN-frontier, spare-NN(-frontier), mentors(-frontier), admin
  - backend keys: fall26-<team_id>, fall26-<team_id>-frontier  (minted on team approval)

Idempotent: a key whose expiry is already within --tolerance seconds of the
target is left alone. Dry-run by default; --yes applies. Prints key prefixes only.

Usage:
    python scripts/set_key_expiry.py --base-url https://ai.ohack.dev --master-key sk-...            # audit
    python scripts/set_key_expiry.py --base-url https://ai.ohack.dev --master-key sk-... --yes      # apply
    python scripts/set_key_expiry.py ... --expires 2026-11-16T01:00:00Z --include-admin --yes
"""

import argparse
import re
import sys
from datetime import datetime, timezone

import requests

DEFAULT_EXPIRES = "2026-11-16T01:00:00Z"  # Sun Nov 15, 6 PM Arizona; same as the backend
CARD_ALIAS_RE = re.compile(r"^(team-\d{2}|spare-\d{2}|mentors)(-frontier)?$")
BACKEND_ALIAS_RE = re.compile(r"^fall26-.+$")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def duration_until(expires: datetime, now: datetime) -> str:
    seconds = int((expires - now).total_seconds())
    if seconds <= 0:
        raise SystemExit(f"error: --expires {expires.isoformat()} is in the past")
    return f"{seconds}s"


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


def wanted(alias: str, include_admin: bool) -> bool:
    if not alias:
        return False
    if alias == "admin":
        return include_admin
    return bool(CARD_ALIAS_RE.match(alias) or BACKEND_ALIAS_RE.match(alias))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="https://ai.ohack.dev")
    ap.add_argument("--master-key", default="")
    ap.add_argument("--expires", default=DEFAULT_EXPIRES,
                    help=f"UTC instant the keys stop working (default {DEFAULT_EXPIRES})")
    ap.add_argument("--tolerance", type=int, default=120,
                    help="skip keys already expiring within this many seconds of the target")
    ap.add_argument("--include-admin", action="store_true",
                    help="also expire the uncapped organizer `admin` key (default: leave it)")
    ap.add_argument("--only", default=None, metavar="REGEX",
                    help="restrict to aliases matching this regex (e.g. '^team-07' or "
                         "'^fall26-' for backend-minted keys only)")
    ap.add_argument("--yes", action="store_true", help="apply; without it this is a dry run")
    args = ap.parse_args()

    if not args.master_key:
        print("error: --master-key required", file=sys.stderr)
        return 2
    base_url = args.base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {args.master_key}"}
    target = parse_utc(args.expires)
    now = datetime.now(timezone.utc)
    duration = duration_until(target, now)

    only = re.compile(args.only) if args.only else None
    keys = fetch_keys(base_url, headers)
    todo, already, skipped = [], [], 0
    for k in keys:
        alias = k.get("key_alias") or ""
        if not wanted(alias, args.include_admin) or (only and not only.search(alias)):
            skipped += 1
            continue
        current = k.get("expires")
        if current:
            try:
                if abs((parse_utc(current) - target).total_seconds()) <= args.tolerance:
                    already.append(alias)
                    continue
            except ValueError:
                pass  # unparseable → treat as wrong and reset it
        todo.append((alias, k.get("token") or k.get("key"), current))

    print(f"{len(keys)} keys on the gateway; {skipped} not ours (left alone); "
          f"{len(already)} already expire at {target.isoformat()}; {len(todo)} to update.")
    for alias, _, current in todo:
        print(f"  {alias}: expires {current or 'never'} -> {target.isoformat()}")
    if not todo:
        return 0
    if not args.yes:
        print(f"\nDry run — re-run with --yes to send /key/update duration={duration} to these keys.")
        return 0

    failed = 0
    for alias, token, _ in todo:
        if not token:
            print(f"  {alias}: no token in /key/list payload, skipping", file=sys.stderr)
            failed += 1
            continue
        # Recompute per key: LiteLLM sets expires = now + duration at request
        # time, so a duration computed before a long sweep drifts early.
        duration = duration_until(target, datetime.now(timezone.utc))
        r = requests.post(f"{base_url}/key/update",
                          json={"key": token, "duration": duration},
                          headers=headers, timeout=30)
        if r.status_code != 200:
            print(f"  {alias}: FAILED HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
            failed += 1
            continue
        got = (r.json() or {}).get("expires")
        print(f"  {alias} ({str(token)[:10]}…): expires -> {got}")
    print(f"\nUpdated {len(todo) - failed}/{len(todo)} keys to expire at {target.isoformat()}."
          + (" Verify one with /key/info." if failed == 0 else f" {failed} FAILED — see above."))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
