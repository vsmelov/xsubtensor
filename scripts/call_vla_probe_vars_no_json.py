#!/usr/bin/env python3
"""
POST /v1/vla-probe: 3 miners, vars static videos, AI verification.
Deliberately avoids `import json` — request body is a fixed UTF-8 string.
Response is saved as returned by the probe (already pretty-printed JSON).
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent

_BODY = """{
  "netuid": 3,
  "wallet_name": "vla-val",
  "hotkey": "default",
  "chain_endpoint": "ws://subtensor-localnet:9944",
  "n_miners": 3,
  "task": "Clean-up the guestroom",
  "using_ai_verification": true,
  "video_analyzer_url": "http://vla-video-analyzer:8000",
  "timeout": 600,
  "use_vars_static_videos": true
}"""


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8094/v1/vla-probe"
    out_path = (
        sys.argv[2]
        if len(sys.argv) > 2
        else str(_SCRIPT_DIR / "vla-probe-vars-3miners-last-run.json")
    )
    data = _BODY.encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        sys.stderr.write("HTTP %s %s\n" % (e.code, e.reason))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(raw)
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
