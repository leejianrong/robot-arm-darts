#!/usr/bin/env python3
"""Local spend guard for RunPod: the account has no spend cap we can set, so enforce one from here.

Watches only pods whose name starts with --prefix (others on the account are reported, never
touched). Every --interval seconds it adds up what those pods have cost (cost/hr x uptime), and
deletes them if that passes --cap-usd, if one outlives --max-hours, or if the account balance drops
under --min-balance. Needs RUNPOD_API_KEY in the environment (read by runpodctl, never printed).
The pod-side watchdog in scripts/rp stays the first line; this covers a pod it failed to reap.
"""

import argparse
import json
import subprocess
import sys
import time


def ctl(*args: str):
    out = subprocess.run(["runpodctl", *args], capture_output=True, text=True, timeout=60)
    if out.returncode:
        raise RuntimeError(out.stderr.strip()[:200] or f"exit {out.returncode}")
    return json.loads(out.stdout) if out.stdout.strip().startswith(("{", "[")) else out.stdout


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prefix", default="darts-")
    ap.add_argument("--cap-usd", type=float, default=2.0, help="most my pods may cost in total")
    ap.add_argument("--max-hours", type=float, default=2.5, help="longest any one pod may live")
    ap.add_argument("--min-balance", type=float, default=1.0)
    ap.add_argument("--interval", type=int, default=60)
    a = ap.parse_args()
    spent: dict[str, float] = {}
    fails = 0
    while True:
        try:
            me = ctl("user")
            pods = [p for p in ctl("pod", "list", "--all") if p["name"].startswith(a.prefix)]
            allpods = ctl("pod", "list")
            fails = 0
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            fails += 1
            print(f"GUARD WARN runpodctl failed ({fails}): {e}", flush=True)
            if fails >= 3:
                print("GUARD ERROR cannot see RunPod; spend is unmonitored", flush=True)
            time.sleep(a.interval)
            continue
        for p in pods:
            spent[p["id"]] = max(
                spent.get(p["id"], 0.0), p["costPerHr"] * p.get("uptimeSeconds", 0) / 3600
            )
        total = sum(spent.values())
        mine = sum(p["costPerHr"] for p in pods if p["desiredStatus"] == "RUNNING")
        other = me["currentSpendPerHr"] - mine
        print(
            f"GUARD {time.strftime('%H:%M:%S')} balance=${me['clientBalance']:.2f} "
            f"account=${me['currentSpendPerHr']:.2f}/h mine={len(pods)} pods ${mine:.2f}/h "
            f"mine_spent=${total:.2f}/${a.cap_usd:.2f} others=${max(other, 0):.2f}/h "
            f"({len(allpods)} running on account)",
            flush=True,
        )
        why = ""
        if total > a.cap_usd:
            why = f"spend ${total:.2f} over cap ${a.cap_usd:.2f}"
        elif me["clientBalance"] < a.min_balance:
            why = f"balance ${me['clientBalance']:.2f} under ${a.min_balance:.2f}"
        for p in pods:
            over = p.get("uptimeSeconds", 0) > a.max_hours * 3600
            if why or over:
                reason = why or f"alive over {a.max_hours} h"
                print(f"GUARD KILL {p['id']} {p['name']}: {reason}", flush=True)
                try:
                    ctl("pod", "delete", p["id"])
                except RuntimeError as e:
                    print(f"GUARD ERROR delete failed: {e}", flush=True)
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
