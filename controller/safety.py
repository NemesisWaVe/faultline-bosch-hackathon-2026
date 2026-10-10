"""Safety controller — runs ONE experiment and acts as the referee.

Plain English: it breaks one thing (using chaos/inject.py), then every 5 seconds it looks at what
shoppers are experiencing. If errors or slowness stay above the limits for 30 seconds in a row, it
blows the whistle: undoes the fault immediately ("abort"). If nothing bad happens, the fault is undone
anyway when the time limit runs out. Afterwards it keeps watching until the shop is back to normal
and records how long that took ("recovery time"). Every experiment is logged to reports/experiments.jsonl.

Seat belts:  1) threshold abort (this file)   2) hard time limit (max_experiment_seconds)
             3) Ctrl+C restores immediately   4) chaos/stop_all.ps1 as the big red button

Run:  python controller/safety.py kill recommendation --duration 90
      python controller/safety.py delay product-catalog --ms 800 --duration 120
"""
import argparse
import json
import signal
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "controller"))
sys.path.insert(0, str(ROOT / "chaos"))
from inject import make_fault, state  # noqa: E402
from metrics import locust_counters, locust_window, per_service  # noqa: E402

CFG = yaml.safe_load((ROOT / "config" / "thresholds.yaml").read_text())
LOG = ROOT / "reports" / "experiments.jsonl"


def now():
    return time.strftime("%H:%M:%S")


def load_limits():
    """Turn the baseline + thresholds.yaml into concrete numbers: max error rate and max p95."""
    base = json.loads((ROOT / "reports" / "baseline.json").read_text())["shopper_view"]
    base_err = (base["error_rate"] or {}).get("mean", 0.0)
    base_lat = base["mean_ms"]["median"]
    err_cfg, lat_cfg = CFG["error_rate"], CFG["latency"]
    return {
        "baseline_error_rate": base_err,
        "baseline_mean_ms": base_lat,
        "max_error_rate": max(err_cfg["absolute_floor"], err_cfg["baseline_multiplier"] * base_err),
        "max_mean_ms": lat_cfg["baseline_multiplier"] * base_lat,
    }


_prev = {}  # last Locust totals, so each reading covers "since the previous check"


def read():
    """One reading of the shopper scoreboard; never crashes the referee if the scoreboard hiccups."""
    try:
        cur = locust_counters()
    except Exception as exc:
        return {"error_rate": None, "mean_ms": None, "rps": None, "note": f"read failed: {exc}"}
    prev, _prev["c"] = _prev.get("c"), cur
    return locust_window(prev, cur) if prev else {"error_rate": None, "mean_ms": None, "rps": None}


def breached(s, limits):
    reasons = []
    if s.get("error_rate") is not None and s["error_rate"] > limits["max_error_rate"]:
        reasons.append(f"errors {s['error_rate']:.1%} > {limits['max_error_rate']:.1%}")
    if s.get("mean_ms") is not None and s["mean_ms"] > limits["max_mean_ms"]:
        reasons.append(f"avg response {s['mean_ms']} ms > {limits['max_mean_ms']:.0f} ms")
    return reasons


def healthy(s, limits):
    """'Recovered' = within the tolerance of the baseline (with a small floor so 0% errors isn't impossible)."""
    tol = CFG["recovery"]["tolerance"]
    err_ok = s.get("error_rate") is not None and s["error_rate"] <= max(limits["baseline_error_rate"] * (1 + tol), 0.01)
    lat_ok = s.get("mean_ms") is not None and s["mean_ms"] <= limits["baseline_mean_ms"] * (1 + tol)
    return err_ok and lat_ok


def fmt(s, limits, streak=None):
    err = "  n/a " if s.get("error_rate") is None else f"{s['error_rate']:6.1%}"
    line = (f"errors {err} (limit {limits['max_error_rate']:.1%})  "
            f"avg {s.get('mean_ms')} ms (limit {limits['max_mean_ms']:.0f} ms)  rps {s.get('rps')}")
    if streak is not None:
        line += f"  breach {streak}/{CFG['consecutive_breaches_to_abort']}"
    return line


def run(kind, target, duration, **params):
    limits = load_limits()
    interval = CFG["check_interval_seconds"]
    needed = CFG["consecutive_breaches_to_abort"]
    duration = min(duration, CFG["max_experiment_seconds"])
    fault = make_fault(kind, target, duration, **params)  # refuses non-allowlisted targets

    record = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), **fault.describe(), "duration_limit_s": duration,
              **limits, "abort_fired": False, "abort_reason": None, "peak_error_rate": 0.0, "peak_mean_ms": 0,
              "timeline": []}
    restored = {"done": False, "at": None}

    def restore(why):
        if not restored["done"]:
            restored["done"], restored["at"] = True, time.time()
            fault.restore()
            print(f"{now()}  RESTORED {target} ({why}) -> container {state(target)}")

    def on_ctrl_c(*_):
        restore("manual stop, Ctrl+C")
        record["abort_fired"], record["abort_reason"] = True, "manual stop (Ctrl+C)"
        finish(record)
        sys.exit(1)
    signal.signal(signal.SIGINT, on_ctrl_c)

    print(f"{now()}  Limits: abort if errors > {limits['max_error_rate']:.1%} or avg response > {limits['max_mean_ms']:.0f} ms "
          f"for {needed * interval}s; hard stop after {duration}s")
    read()  # first reading = starting point for the 5 s windows
    print(f"{now()}  INJECT {kind} on {target} {params or ''}")
    t0 = time.time()
    fault.inject()

    streak = 0
    try:
        # ---- Phase 1: fault active, referee watching ----
        while time.time() - t0 < duration:
            time.sleep(interval)
            s = read()
            reasons = breached(s, limits)
            streak = streak + 1 if reasons else 0
            record["timeline"].append({"t": round(time.time() - t0), "phase": "fault", **s})
            record["peak_error_rate"] = max(record["peak_error_rate"], s.get("error_rate") or 0)
            record["peak_mean_ms"] = max(record["peak_mean_ms"], s.get("mean_ms") or 0)
            print(f"{now()}  [fault +{time.time() - t0:5.0f}s]  {fmt(s, limits, streak)}  container {state(target)}")
            if streak >= needed:
                record["abort_fired"], record["abort_reason"] = True, "; ".join(reasons)
                print(f"{now()}  !!! ABORT: limits breached for {needed * interval}s in a row ({'; '.join(reasons)})")
                restore("automatic abort")
                break
        else:
            print(f"{now()}  Time limit reached without breaching limits — undoing the fault as planned.")
    finally:
        restore("time limit / exit")
    record["fault_active_s"] = round(restored["at"] - t0)

    # ---- Phase 2: fault removed, measure recovery ----
    stable_needed = CFG["recovery"]["stable_seconds"]
    give_up = CFG["recovery"]["give_up_after_seconds"]
    t_restore, first_ok = restored["at"], None
    while time.time() - t_restore < give_up:
        time.sleep(interval)
        s = read()
        ok = healthy(s, limits)
        record["timeline"].append({"t": round(time.time() - t0), "phase": "recovery", **s})
        first_ok = (first_ok or time.time()) if ok else None
        print(f"{now()}  [recovery +{time.time() - t_restore:4.0f}s]  {fmt(s, limits)}  {'OK' if ok else 'not yet'}")
        if first_ok and time.time() - first_ok >= stable_needed:
            record["recovery_time_s"] = round(first_ok - t_restore)
            print(f"{now()}  RECOVERED: back to baseline {record['recovery_time_s']}s after the fault was removed "
                  f"(stable for {stable_needed}s)")
            break
    else:
        record["recovery_time_s"] = None
        print(f"{now()}  NOT RECOVERED within {give_up}s — this is a serious finding, check the services!")

    try:
        record["per_service_after"] = per_service("2m")  # which services were hurt (Prometheus detail)
    except Exception as exc:
        record["per_service_after"] = f"unavailable: {exc}"
    finish(record)


def finish(record):
    record["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"\nSUMMARY  {record['fault']} on {record['target']}: abort_fired={record['abort_fired']}  "
          f"peak errors {record['peak_error_rate']:.1%}  peak avg response {record['peak_mean_ms']} ms  "
          f"recovery {record.get('recovery_time_s')}s  -> logged to reports/experiments.jsonl")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Run one chaos experiment under the safety controller.")
    ap.add_argument("kind", choices=["kill", "pause", "delay", "loss"])
    ap.add_argument("target")
    ap.add_argument("--duration", type=int, default=90)
    ap.add_argument("--ms", type=int, default=300)
    ap.add_argument("--percent", type=int, default=20)
    a = ap.parse_args()
    extra = {"ms": a.ms} if a.kind == "delay" else {"percent": a.percent} if a.kind == "loss" else {}
    run(a.kind, a.target, a.duration, **extra)
