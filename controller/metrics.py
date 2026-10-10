"""Where our numbers come from — shared by the baseline script and the safety controller.

Plain English: we read two scoreboards.
  1. LOCUST (the fake shoppers) — measures what a shopper actually feels: requests per second, how many
     fail, how long requests take. We read its running totals every 5 s and look at the DIFFERENCE,
     like reading a car's odometer twice. Fast enough for the safety referee.
  2. PROMETHEUS (via Grafana) — per-service detail (including p95), but only refreshed about every 60 s,
     so we use it for reports ("which service caused it"), not for the emergency stop.

Excluded on purpose:
  - "/prompt": the load generator also talks to an optional AI-chatbot add-on we did not start, so those
    calls always fail after a 4 s wait and are not a shop problem.
  - "TASK ..." rows: whole simulated browser journeys timed end to end, not single requests.
"""
import time

import requests

LOCUST_URL = "http://localhost:8080/loadgen/stats/requests"
PROM_URL = "http://localhost:8080/grafana/api/datasources/proxy/uid/webstore-metrics/api/v1/query"
IGNORED_ENDPOINTS = {"/prompt"}


def locust_counters():
    """Locust's running totals since it started, counting real shop requests only."""
    d = requests.get(LOCUST_URL, timeout=5).json()
    rows = [s for s in d["stats"] if s["name"] != "Aggregated" and s["name"] not in IGNORED_ENDPOINTS
            and not s["name"].startswith("TASK ")]
    return {
        "time": time.time(),
        "users": d.get("user_count"),
        "state": d.get("state"),
        "requests": sum(s["num_requests"] for s in rows),
        "failures": sum(s["num_failures"] for s in rows),
        "total_ms": sum(s["avg_response_time"] * s["num_requests"] for s in rows),
    }


def locust_window(prev, cur):
    """What shoppers felt BETWEEN two readings: requests/sec, error ratio (0-1), average response time (ms)."""
    dn = cur["requests"] - prev["requests"]
    dt = cur["time"] - prev["time"]
    if dn < 0:  # someone pressed "reset stats" in Locust — skip this window
        return {"users": cur["users"], "rps": None, "error_rate": None, "mean_ms": None}
    return {
        "users": cur["users"],
        "rps": round(dn / dt, 2) if dt else None,
        "error_rate": round((cur["failures"] - prev["failures"]) / dn, 4) if dn else None,
        "mean_ms": round((cur["total_ms"] - prev["total_ms"]) / dn) if dn else None,
    }


def prom(expr):
    """Run one PromQL query; returns {service_name: value}."""
    r = requests.get(PROM_URL, params={"query": expr}, timeout=10)
    r.raise_for_status()
    out = {}
    for row in r.json()["data"]["result"]:
        v = float(row["value"][1])
        out[row["metric"].get("service_name", "all")] = None if v != v else round(v, 4)  # NaN -> None
    return out


# PromQL in plain English:
#  calls/sec   = how many requests each service RECEIVED per second (SERVER spans = incoming requests)
#  error ratio = failed incoming requests / all incoming requests
#  p95         = 95% of requests to this service finished faster than this many ms
SERVER = 'span_kind="SPAN_KIND_SERVER"'


def per_service(window="5m"):
    calls = f'sum by (service_name) (rate(traces_span_metrics_calls_total{{{SERVER}}}[{window}]))'
    errs = (f'sum by (service_name) (rate(traces_span_metrics_calls_total{{{SERVER},status_code="STATUS_CODE_ERROR"}}[{window}]))'
            f' / {calls}')
    p95 = (f'histogram_quantile(0.95, sum by (service_name, le) '
           f'(rate(traces_span_metrics_duration_milliseconds_bucket{{{SERVER}}}[{window}])))')
    c, e, p = prom(calls), prom(errs), prom(p95)
    # A service with no failed requests has no error series at all -> that means 0%, not "unknown".
    return {s: {"calls_per_sec": c.get(s), "error_rate": e.get(s, 0.0), "p95_ms": p.get(s)} for s in sorted(c)}
