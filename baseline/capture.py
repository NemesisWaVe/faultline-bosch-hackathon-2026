"""Baseline capture — measures what "healthy" looks like before we break anything.

Plain English: with the fake shoppers running and nothing broken, we take a reading every 5 seconds
for a few minutes. The averages become our reference point: later, "too slow" or "too many errors"
always means "compared to this baseline".

Run:     python baseline/capture.py              (default 300 s)
         python baseline/capture.py --seconds 120
Output:  reports/baseline.json
"""
import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "controller"))
from metrics import locust_snapshot, per_service  # noqa: E402


def container_health():
    out = subprocess.run(["docker", "ps", "-a", "--filter", "label=com.docker.compose.project=opentelemetry-demo",
                          "--format", "{{.Names}}|{{.Status}}"], capture_output=True, text=True).stdout
    return dict(line.split("|", 1) for line in out.splitlines() if "|" in line)


def summarize(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    vals.sort()
    return {"mean": round(statistics.mean(vals), 4), "median": round(statistics.median(vals), 4),
            "p90_of_samples": round(vals[int(0.9 * (len(vals) - 1))], 4), "max": round(max(vals), 4)}


def main(seconds, interval=5):
    health = container_health()
    unhealthy = {n: s for n, s in health.items() if not s.startswith("Up") or "unhealthy" in s}
    if unhealthy:
        print("WARNING: not everything is healthy, baseline may be wrong:", unhealthy)

    samples, start = [], time.time()
    print(f"Capturing baseline for {seconds}s (one reading every {interval}s). Don't break anything!")
    while time.time() - start < seconds:
        s = locust_snapshot()
        s["t"] = time.strftime("%H:%M:%S")
        samples.append(s)
        err = "n/a" if s["error_rate"] is None else f"{s['error_rate']:.1%}"
        print(f"  {s['t']}  users {s['users']}  rps {s['rps']:5.1f}  errors {err:>6}  p50 {s['p50_ms']} ms  p95 {s['p95_ms']} ms")
        time.sleep(interval)

    window = f"{max(2, round(seconds / 60))}m"
    result = {
        "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": seconds,
        "load_users": samples[-1]["users"],
        "note": "Locust '/prompt' requests excluded (optional AI-chatbot add-on not deployed).",
        "shopper_view": {k: summarize([s[k] for s in samples]) for k in ("rps", "error_rate", "p50_ms", "p95_ms")},
        "per_service": per_service(window),
        "containers": health,
        "samples": samples,
    }
    out = ROOT / "reports" / "baseline.json"
    out.write_text(json.dumps(result, indent=2))

    sv = result["shopper_view"]
    print("\nBASELINE (what healthy looks like):")
    print(f"  traffic      {sv['rps']['mean']:.1f} requests/sec with {result['load_users']} fake shoppers")
    print(f"  error rate   {sv['error_rate']['mean']:.2%} on average" if sv["error_rate"] else "  error rate   n/a")
    print(f"  p95 latency  {sv['p95_ms']['median']:.0f} ms (median of readings)")
    print(f"Saved to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=300)
    main(ap.parse_args().seconds)
