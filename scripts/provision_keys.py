#!/usr/bin/env python3
"""Provision hackathon team keys on the LiteLLM gateway (PLAN.md Phase 3).

TWO keys per team (the dual-key pattern PLAN §Phase 3 pre-approved, because
per-key-per-model USD caps are an enterprise feature in LiteLLM OSS):
  - `team-NN`          max_budget $15, models: ohack, ohack-mid, ohack-free
  - `team-NN-frontier` max_budget $20, models: ohack-frontier only
  = $35/team total, matching PLAN §3 exactly. Budgets are LIFETIME caps
  (budget_duration deliberately unset — they never reset).

Also: spare-01..05 (same shape), mentors ($30 + $20 frontier = $50 per PLAN §8),
and one uncapped `admin` key for organizers.

Existing aliases are skipped (safe to re-run). Full keys are written ONLY to
keys/keys.csv (gitignored); stdout shows prefixes.

Usage:
    python scripts/provision_keys.py --base-url https://ai.ohack.dev --master-key sk-...
    python scripts/provision_keys.py --dry-run
"""

import argparse
import csv
import sys
from pathlib import Path

import requests

MAIN_MODELS = ["ohack", "ohack-mid", "ohack-free"]
FRONTIER_MODELS = ["ohack-frontier"]
ALL_MODELS = MAIN_MODELS + FRONTIER_MODELS


def key_specs(main: float, frontier: float, mentor_main: float):
    """Yields (alias, max_budget, models) triples."""
    specs = []
    for i in list(range(1, 26)) + [f"spare-{j:02d}" for j in range(1, 6)]:
        base = f"team-{i:02d}" if isinstance(i, int) else i
        specs.append((base, main, MAIN_MODELS))
        specs.append((f"{base}-frontier", frontier, FRONTIER_MODELS))
    specs.append(("mentors", mentor_main, MAIN_MODELS))
    specs.append(("mentors-frontier", frontier, FRONTIER_MODELS))
    specs.append(("admin", None, ALL_MODELS))  # uncapped, organizers only
    return specs


def existing_aliases(base_url: str, headers: dict) -> set:
    aliases = set()
    page = 1
    while True:
        r = requests.get(f"{base_url}/key/list",
                         params={"page": page, "size": 100, "return_full_object": "true"},
                         headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        for k in data.get("keys", []):
            alias = k.get("key_alias") if isinstance(k, dict) else None
            if alias:
                aliases.add(alias)
        if page >= int(data.get("total_pages") or 1):
            break
        page += 1
    return aliases


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="https://ai.ohack.dev")
    ap.add_argument("--master-key", default="")
    ap.add_argument("--main-budget", type=float, default=15.0)
    ap.add_argument("--frontier-budget", type=float, default=20.0)
    ap.add_argument("--mentor-budget", type=float, default=30.0)
    ap.add_argument("--out", default="keys/keys.csv")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    specs = key_specs(args.main_budget, args.frontier_budget, args.mentor_budget)
    if args.dry_run:
        for alias, budget, models in specs:
            print(f"would create {alias}: "
                  f"{'uncapped' if budget is None else f'${budget:g}'}"
                  f" models={','.join(models)}")
        print(f"Dry run: {len(specs)} keys, nothing created.")
        return 0
    if not args.master_key:
        print("error: --master-key required", file=sys.stderr)
        return 2

    base_url = args.base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {args.master_key}"}
    skip = existing_aliases(base_url, headers)

    created = {}
    for alias, budget, models in specs:
        if alias in skip:
            print(f"  {alias}: already exists, skipping")
            continue
        body = {"key_alias": alias, "models": models}
        if budget is not None:
            body["max_budget"] = budget  # lifetime: budget_duration deliberately unset
        r = requests.post(f"{base_url}/key/generate", json=body, headers=headers, timeout=30)
        if r.status_code != 200:
            print(f"  {alias}: FAILED HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
            continue
        created[alias] = (r.json()["key"], budget)
        print(f"  {alias}: created ({created[alias][0][:10]}…)")

    # Collapse into one CSV row per team: main key + frontier key.
    rows = []
    for alias, (key, budget) in created.items():
        if alias.endswith("-frontier"):
            continue
        f_alias = f"{alias}-frontier"
        f_key, f_budget = created.get(f_alias, ("", None))
        rows.append({
            "team_id": alias,
            "key": key,
            "frontier_key": f_key,
            "quota_main": "" if budget is None else f"{budget:g}",
            "quota_frontier": "" if f_budget is None else f"{f_budget:g}",
        })

    if rows:
        out = Path(args.out)
        out.parent.mkdir(exist_ok=True)
        write_header = not out.exists()
        with out.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["team_id", "key", "frontier_key",
                                              "quota_main", "quota_frontier"])
            if write_header:
                w.writeheader()
            w.writerows(rows)
        print(f"\n{len(rows)} card rows appended to {out} — gitignored; keep it that way.")
    else:
        print("\nNothing new created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
