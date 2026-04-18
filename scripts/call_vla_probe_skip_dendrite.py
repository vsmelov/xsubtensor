#!/usr/bin/env python3
"""
POST /v1/vla-probe — режим skip_dendrite (без цепи и dendrite).

Фронт шлёт только смысловые поля; chain / analyzer URL задаются на сервере probe через env.

Пишет ответ в scripts/vla-probe-skip-dendrite-last-run.json

Логи: по умолчанию печатает URL, размер тела, результат или ошибку.
  python call_vla_probe_skip_dendrite.py -v   — ещё и полный JSON тела запроса
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent

# Минимум для фронта (остальное — env контейнера vla-probe / vla-video-analyzer)
_BODY: dict = {
    "task": "Clean-up the guestroom",
    "skip_dendrite": True,
    "n_miners": 3,
    "use_vars_static_videos": True,
    "using_ai_verification": True,
    "timeout": 900,
}


def _log(msg: str) -> None:
    print(f"[vla-probe-client] {msg}", file=sys.stderr, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="POST skip_dendrite to vla-probe")
    ap.add_argument(
        "url",
        nargs="?",
        default="http://127.0.0.1:8094/v1/vla-probe",
        help="probe URL (на хосте обычно :8094 → контейнер :8091)",
    )
    ap.add_argument(
        "-o",
        "--output",
        default=None,
        metavar="PATH",
        help="куда сохранить JSON ответа (по умолчанию scripts/vla-probe-skip-dendrite-last-run.json)",
    )
    ap.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print full request JSON body to stderr",
    )
    args = ap.parse_args()

    url = args.url
    out_path = args.output or str(_SCRIPT_DIR / "vla-probe-skip-dendrite-last-run.json")

    body_str = json.dumps(_BODY, ensure_ascii=False, indent=2 if args.verbose else None)
    data = body_str.encode("utf-8")
    if args.verbose:
        _log("request body:\n" + body_str)
    else:
        _log("request body keys: %s" % list(_BODY.keys()))

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": str(len(data)),
        },
        method="POST",
    )

    _log("POST %s (payload %d bytes, client timeout 1200s)" % (url, len(data)))
    t0 = time.perf_counter()

    raw = ""
    code = 0
    err_detail = None

    try:
        with urllib.request.urlopen(req, timeout=1200) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = resp.status
            _log("response HTTP %d in %.2fs, %d chars" % (code, time.perf_counter() - t0, len(raw)))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        code = e.code
        err_detail = "HTTPError %d: %s" % (e.code, e.reason)
        _log("response HTTP %d in %.2fs (%s), body len=%d" % (e.code, time.perf_counter() - t0, e.reason, len(raw)))
    except urllib.error.URLError as e:
        err_detail = "URLError: %s" % e.reason
        _log("FAILED after %.2fs: %s" % (time.perf_counter() - t0, err_detail))
        _log(
            "hint: is Docker up? is vla-probe published on 127.0.0.1:8094? "
            "try: curl -sS http://127.0.0.1:8094/health"
        )
        traceback.print_exc(file=sys.stderr)
        Path(out_path).write_text(
            json.dumps(
                {"ok": False, "client_error": err_detail, "url": url},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        _log("wrote error stub to %s" % out_path)
        return 2
    except Exception as e:
        err_detail = "%s: %s" % (type(e).__name__, e)
        _log("FAILED after %.2fs: %s" % (time.perf_counter() - t0, err_detail))
        traceback.print_exc(file=sys.stderr)
        Path(out_path).write_text(
            json.dumps(
                {"ok": False, "client_error": err_detail, "url": url},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        _log("wrote error stub to %s" % out_path)
        return 3

    out_file = Path(out_path)
    out_file.write_text(raw, encoding="utf-8")
    _log("wrote %s" % out_file)

    try:
        obj = json.loads(raw)
        print("ok=", obj.get("ok"), "skip_dendrite=", obj.get("skip_dendrite"))
        if obj.get("ok") and obj.get("miners"):
            for m in obj["miners"]:
                ai = m.get("ai_verification") or {}
                print(
                    "  slot",
                    m.get("vars_video_slot"),
                    "ai_ok=",
                    ai.get("ok"),
                )
    except json.JSONDecodeError:
        _log("response is not valid JSON (first 200 chars): %r" % (raw[:200],))

    return 0 if code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
