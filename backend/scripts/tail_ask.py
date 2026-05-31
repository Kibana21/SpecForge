"""Live-tail Project Copilot ask streams from Redis — see exactly what the worker
is doing, with per-step elapsed timing.

Usage (from backend/):
  .venv/bin/python scripts/tail_ask.py            # follow the newest ask stream
  .venv/bin/python scripts/tail_ask.py <key>      # follow a specific stream_key
"""
import asyncio
import json
import sys
import time


async def main() -> None:
    from app.core.redis_client import get_redis
    r = get_redis()

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        key = arg if arg.startswith("ask:") else f"ask:{arg}"
    else:
        keys = [k async for k in r.scan_iter(match="ask:*", count=200)]
        if not keys:
            print("No ask:* streams yet. Ask a question in the UI, then re-run.")
            return
        newest, newest_id = None, ""
        for k in keys:
            try:
                info = await r.xinfo_stream(k)
            except Exception:
                continue
            last = str(info.get("last-generated-id", "0"))
            if last > newest_id:
                newest, newest_id = k, last
        key = newest
        print(f"Following newest stream: {key}")

    last_id = "0"
    t0 = time.monotonic()
    prev = t0
    print(f"--- tailing {key}  (Ctrl+C to stop) ---")
    print(f"{'elapsed':>8} {'+delta':>7}  event")
    while True:
        results = await r.xread({key: last_id}, block=5000, count=50)
        if not results:
            continue
        for _, messages in results:
            for msg_id, fields in messages:
                last_id = msg_id
                now = time.monotonic()
                raw = fields.get("e") or fields.get(b"e") or "{}"
                ev = json.loads(raw)
                t = ev.get("type")
                if t == "chunk":
                    detail = "· answer token"
                elif t == "trace":
                    tr = ev.get("trace", {})
                    detail = (f"· sections={len(tr.get('sections', []))} "
                              f"concepts={len(tr.get('selected_concepts', []))} "
                              f"facts={len(tr.get('facts', []))}"
                              + (" (partial)" if tr.get("partial") else " (FINAL)"))
                else:
                    detail = ev.get("text") or ev.get("message") or ""
                print(f"{now - t0:7.1f}s {now - prev:6.1f}s  [{t}] {detail[:88]}")
                prev = now
                if t in ("done", "error"):
                    print(f"--- stream ended ({now - t0:.1f}s total) ---")
                    return


if __name__ == "__main__":
    asyncio.run(main())
