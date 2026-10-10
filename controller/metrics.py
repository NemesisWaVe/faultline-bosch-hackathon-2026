"""Where our numbers come from — shared by the baseline script and the safety controller.

Plain English: we read two scoreboards.
  1. LOCUST (the fake shoppers) — updates every ~2 s and measures what a shopper actually feels:
     requests per second, how many fail, how slow the slowest 5% are (p95). Fast enough for the
     safety referee, which checks every 5 s.
  2. PROMETHEUS (via Grafana) — per-service detail, but only refreshed about every 60 s, so we use it
     for reports ("which service caused it"), not for the emergency stop.

Excluded on purpose: the "/prompt" requests. The load generator also talks to an optional AI-chatbot
add-on that we did not start, so those calls always fail and are not a shop problem.
"""
import requests

LOCUST_URL = "http://localhost:8080/loadgen/stats/requests"
PROM_URL = "http://localhost:8080/grafana/api/datasources/proxy/uid/webstore-metrics/api/v1/query"
IGNORED_ENDPOINTS = {"/prompt"}


def locust_snapshot():
    """What shoppers feel right now: rps, error ratio (0-1), p50/p95 response time in ms."""
    d = requests.get(LOCUST_URL, timeout=5).json()
    rows = [s for s in d["stats"] if s["name"] != "Aggregated" and s["name"] not in IGNORED_ENDPOINTS]
    rps = sum(s["current_rps"] for s in rows)
    fails = sum(s["current_fail_per_sec"] for s in rows)
    pct = d.get("current_response_time_percentiles") or {}
    return {
        "users": d.get("user_count"),
        "state": d.get("state"),
        "rps": round(rps, 3),
        "error_rate": round(fails / rps, 4) if rps else None,
        "p50_ms": pct.get("response_time_percentile_0.5"),
        "p95_ms": pct.get("response_time_percentile_0.95"),
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
