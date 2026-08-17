#!/usr/bin/env python3
"""Load test the OHack AI gateway (PLAN.md Phase 5).

Simulates N concurrent agent sessions doing streaming chat completions with
long prompts, a configurable fraction of which share a repeated prefix so
provider-side prompt caching gets exercised. Reports p50/p95 time-to-first-token,
p50/p95 total latency, and error rate.

Usage:
    python scripts/load_test.py --base-url https://ai.ohack.dev/v1 \
        --api-key sk-... --model ohack --sessions 25 --minutes 10
    python scripts/load_test.py --dry-run
"""

import argparse
import json
import random
import statistics
import string
import sys
import threading
import time

import requests

# ~8K tokens of shared prefix (roughly 4 chars/token). Deterministic so every
# run and every "cached" session sends byte-identical prefixes.
random.seed(1337)
SHARED_PREFIX = (
    "You are reviewing the following project notes for a nonprofit hackathon "
    "codebase. Keep them in mind for all answers.\n\n"
    + "\n".join(
        f"Note {i}: "
        + " ".join(
            "".join(random.choices(string.ascii_lowercase, k=random.randint(3, 9)))
            for _ in range(40)
        )
        for i in range(110)
    )
)

QUESTIONS = [
    "Summarize note 42 in one sentence.",
    "Write a Python function that parses a CSV of donations.",
    "What are three edge cases for a volunteer signup form?",
    "Draft a SQL schema for tracking food bank inventory.",
    "Explain the difference between REST and webhooks to a beginner.",
]


def one_request(base_url: str, api_key: str, model: str, use_cache_prefix: bool,
                timeout: float, results: list, lock: threading.Lock) -> None:
    if use_cache_prefix:
        content = SHARED_PREFIX + "\n\n" + random.choice(QUESTIONS)
    else:
        # Unique prefix defeats the cache on purpose.
        content = f"[session {random.random()}] " + SHARED_PREFIX[:2000] + "\n\n" + random.choice(QUESTIONS)
    body = {
        "model": model,
        "stream": True,
        "max_tokens": 256,
        "messages": [{"role": "user", "content": content}],
    }
    start = time.monotonic()
    ttft = None
    err = None
    try:
        with requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
            stream=True,
            timeout=timeout,
        ) as r:
            if r.status_code != 200:
                err = f"HTTP {r.status_code}: {r.text[:200]}"
            else:
                for line in r.iter_lines():
                    if line and ttft is None:
                        ttft = time.monotonic() - start
    except Exception as e:  # noqa: BLE001 - we want every failure counted
        err = f"{type(e).__name__}: {e}"
    total = time.monotonic() - start
    with lock:
        results.append({"ttft": ttft, "total": total, "error": err})


def session_worker(stop_at: float, args, results: list, lock: threading.Lock,
                   use_cache_prefix: bool) -> None:
    while time.monotonic() < stop_at:
        one_request(args.base_url, args.api_key, args.model, use_cache_prefix,
                    args.timeout, results, lock)
        time.sleep(random.uniform(0.5, 2.0))  # think time between agent turns


def pctl(values, p):
    if not values:
        return float("nan")
    return statistics.quantiles(values, n=100, method="inclusive")[p - 1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="https://ai.ohack.dev/v1")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--model", default="ohack")
    ap.add_argument("--sessions", type=int, default=25)
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--cache-fraction", type=float, default=0.6,
                    help="fraction of sessions sending the shared cacheable prefix")
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    n_cached = round(args.sessions * args.cache_fraction)
    print(f"Load test: {args.sessions} sessions ({n_cached} cache-prefix, "
          f"{args.sessions - n_cached} unique-prefix) for {args.minutes} min "
          f"against {args.base_url} model={args.model}")
    print(f"Shared prefix size: ~{len(SHARED_PREFIX) // 4} tokens")
    if args.dry_run:
        print("Dry run: no requests sent.")
        return 0
    if not args.api_key:
        print("error: --api-key required (use the admin or a spare team key)", file=sys.stderr)
        return 2

    results: list = []
    lock = threading.Lock()
    stop_at = time.monotonic() + args.minutes * 60
    threads = [
        threading.Thread(target=session_worker,
                         args=(stop_at, args, results, lock, i < n_cached),
                         daemon=True)
        for i in range(args.sessions)
    ]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(10)
            with lock:
                done = len(results)
                errs = sum(1 for x in results if x["error"])
            remaining = max(0, stop_at - time.monotonic())
            print(f"  ...{done} requests, {errs} errors, {remaining:.0f}s left")
    except KeyboardInterrupt:
        print("Interrupted; reporting on what we have.")

    with lock:
        ok = [x for x in results if not x["error"]]
        errors = [x for x in results if x["error"]]
    totals = [x["total"] for x in ok]
    ttfts = [x["ttft"] for x in ok if x["ttft"] is not None]

    print("\n=== Results ===")
    print(f"requests: {len(results)}  ok: {len(ok)}  errors: {len(errors)} "
          f"({100 * len(errors) / max(1, len(results)):.1f}%)")
    if ttfts:
        print(f"time-to-first-token  p50 {pctl(ttfts, 50):.2f}s   p95 {pctl(ttfts, 95):.2f}s")
    if totals:
        print(f"total latency        p50 {pctl(totals, 50):.2f}s   p95 {pctl(totals, 95):.2f}s")
    for msg in sorted({x["error"] for x in errors})[:10]:
        print(f"  error: {msg}")

    # PLAN.md Phase 5 thresholds
    failed = (len(errors) / max(1, len(results)) > 0.01) or (totals and pctl(totals, 95) > 5)
    print("THRESHOLDS:", "FAIL (see PLAN.md Phase 5: scale up Fly and re-run)" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
