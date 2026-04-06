#!/usr/bin/env python3
"""
Fetch GET /v1/network-snapshot from the local faucet (:8090) and write pretty JSON to docs/.

Run from repo root:
  python scripts/save_network_snapshot.py
  python scripts/save_network_snapshot.py --full
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:8090/v1/network-snapshot"
FULL_QUERY = (
    "events_depth=25&events_max=500&blocks_extrinsics_depth=20&extrinsics_max=500"
    "&events_filter=subtensorModule,balances,system"
)
MAX_ATTEMPTS = 6
RETRY_SLEEP_SEC = 2
HTTP_TIMEOUT_SEC = 120


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Save network snapshot JSON into docs/network-snapshot*.example.json",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Extended depth + pallet filter (docs/network-snapshot.full.example.json)",
    )
    args = parser.parse_args()

    if args.full:
        url = f"{BASE_URL}?{FULL_QUERY}"
        out = root / "docs" / "network-snapshot.full.example.json"
    else:
        url = BASE_URL
        out = root / "docs" / "network-snapshot.example.json"

    rel = out.relative_to(root)
    print(f"GET {url}")
    print(f" -> {rel}")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            time.sleep(RETRY_SLEEP_SEC)
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as resp:
                raw = resp.read().decode("utf-8")
        except (urllib.error.URLError, OSError) as e:
            print(f"attempt {attempt}/{MAX_ATTEMPTS}: {e}", file=sys.stderr)
            continue
        if len(raw) < 10:
            print(f"attempt {attempt}/{MAX_ATTEMPTS}: empty body", file=sys.stderr)
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"attempt {attempt}/{MAX_ATTEMPTS}: invalid JSON: {e}", file=sys.stderr)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print("OK", out)
        return 0

    print(
        "curl failed or empty response after retries (is faucet up on 8090?)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
