"""Dependency mapper — draws a map of which services in the shop talk to which.

Plain English: before breaking anything we need to know "if X goes down, who else is hurt?".
We build that map two ways and compare them:
  1. STATIC view  — read the app's configuration (compose files): who is *configured* to talk to whom.
  2. RUNTIME view — ask Jaeger (the tracing tool) who *actually* called whom in real traffic.
Edges seen in only one view are interesting findings (config says yes, traffic says no, or vice versa).

Run:     python mapper/build_map.py            (app must be running for the runtime view)
Outputs: reports/dependency_map.json, reports/dependency_map.png
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import networkx as nx
import requests
import yaml

from draw_map import draw_map  # the picture is drawn in mapper/draw_map.py

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DEMO_DIR = Path(r"C:\Users\ASUS\opentelemetry-demo")
COMPOSE_ARGS = ["--env-file", ".env", "--env-file", ".env.override",
                "-f", "compose.yaml", "-f", "compose.full.yaml",
                "-f", "compose.observability.yaml", "-f", "compose.extras.yaml"]
JAEGER_DEPS_URL = "http://localhost:8080/jaeger/ui/api/dependencies"

# Support tools: monitoring, feature flags, docs. They connect to everything, so drawing them
# would hide the real shop structure. They are also on our never-break list (CLAUDE.md §5).
SUPPORT = {"otel-collector", "opamp-server", "flagd", "flagd-ui", "jaeger", "prometheus",
           "grafana", "opensearch", "telemetry-docs"}
# Where traffic enters the shop. Kept on the map so judges can see the request path.
ENTRY = {"load-generator", "frontend-proxy"}


def load_compose():
    """Ask Docker to merge all compose files exactly as it does at startup (avoids our own merge bugs)."""
    out = subprocess.run(["docker", "compose", *COMPOSE_ARGS, "config", "--format", "json"],
                         cwd=DEMO_DIR, capture_output=True, text=True, check=True).stdout
    return json.loads(out)["services"]


def static_edges(services):
    """Edge A->B if A's settings mention B as a host name, or A lists B in depends_on."""
    names = set(services)
    edges = {}
    for name, svc in services.items():
        env_text = " ".join(str(v) for v in (svc.get("environment") or {}).values() if v)
        tokens = set(re.findall(r"[a-z0-9][a-z0-9-]*", env_text))  # whole words only ("ad" != "load")
        for other in names - {name}:
            if other in tokens:
                edges[(name, other)] = "config"
        for other in (svc.get("depends_on") or {}):
            edges.setdefault((name, other), "startup-order")
    return edges


def runtime_edges(lookback_minutes=15):
    """Ask Jaeger which services actually called each other recently. Returns {} if Jaeger is unreachable."""
    end_ms = int(time.time() * 1000)
    try:
        r = requests.get(JAEGER_DEPS_URL, timeout=10,
                         params={"endTs": end_ms, "lookback": lookback_minutes * 60 * 1000})
        r.raise_for_status()
        data = r.json().get("data") or []
    except Exception as exc:  # app not up yet, or path changed — static view still works
        print(f"[warn] runtime view unavailable ({exc}); using static view only")
        return {}
    return {(d["parent"], d["child"]): d.get("callCount", 0) for d in data if d["parent"] != d["child"]}


def load_overrides():
    """Manual corrections from config/map_overrides.yaml (see that file for the format)."""
    path = ROOT / "config" / "map_overrides.yaml"
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def build():
    services = load_compose()
    static = static_edges(services)
    runtime = runtime_edges()
    overrides = load_overrides()

    g = nx.DiGraph()
    for (a, b), kind in static.items():
        # Skip support tools, and arrows INTO traffic sources: the proxy only serves the
        # load generator's web page — no shop feature depends on it (this also removes the only loop).
        if a in SUPPORT or b in SUPPORT or b in ENTRY - {"frontend-proxy"}:
            continue
        g.add_edge(a, b, source="static", static_kind=kind, calls=0)
    for (a, b), calls in runtime.items():
        a, b = a.strip(), b.strip()
        if a in SUPPORT or b in SUPPORT:
            continue
        if g.has_edge(a, b):
            g[a][b].update(source="both", calls=calls)
        else:
            g.add_edge(a, b, source="runtime-only", calls=calls)
    for a, b in overrides.get("remove_edges") or []:
        if g.has_edge(a, b):
            g.remove_edge(a, b)
    for a, b in overrides.get("add_edges") or []:
        g.add_edge(a, b, source="manual")

    queues = overrides.get("queues") or {}
    for a, b, d in g.edges(data=True):
        # async = goes through a message queue; the sender does not wait for the reader.
        d["async"] = a in queues or b in queues
        # Readers depend on the queue, but data flows queue -> reader, so draw it that way round.
        d["drawn_reversed"] = b in queues and a in (queues[b].get("consumers") or [])
        # "Start B before A" (depends_on) without A actually calling B: keep in data, hide in picture.
        d["hidden"] = d.get("source") == "static" and d.get("static_kind") == "startup-order"

    # Real dependencies only (hidden start-up-order links don't make a service fail).
    real = nx.DiGraph()
    real.add_nodes_from(g.nodes)
    real.add_edges_from((a, b) for a, b, d in g.edges(data=True) if not d["hidden"])
    # How many services break (directly or indirectly) if this one dies = everyone that can reach it.
    impact = {n: sorted(nx.ancestors(real, n) - ENTRY) for n in real.nodes}
    nodes = [{"name": n,
              "role": "entry" if n in ENTRY else ("datastore" if n in {"astronomy-db", "valkey-cart", "kafka"} else "service"),
              "depends_on": sorted(real.successors(n)),
              "depended_on_by": sorted(real.predecessors(n)),
              "impacted_if_down": impact[n],
              "impact_count": len(impact[n])}
             for n in sorted(real.nodes)]
    edges = [{"from": a, "to": b, **d} for a, b, d in g.edges(data=True)]
    result = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "runtime_view_available": bool(runtime),
        "nodes": sorted(nodes, key=lambda n: -n["impact_count"]),
        "edges": edges,
        "only_in_config": [e for e in edges if e["source"] == "static" and not e["hidden"]] if runtime else [],
        "only_in_traffic": [e for e in edges if e["source"] == "runtime-only"],
        "excluded_support_services": sorted(SUPPORT),
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "dependency_map.json").write_text(json.dumps(result, indent=2))
    draw_map(result, REPORTS / "dependency_map.png")
    return result


if __name__ == "__main__":
    res = build()
    print(f"Map built: {len(res['nodes'])} services, {len(res['edges'])} connections "
          f"(runtime view: {'yes' if res['runtime_view_available'] else 'NO'})")
    print("Most critical (most services hurt if it fails):")
    for n in res["nodes"][:6]:
        print(f"  {n['name']:16} -> {n['impact_count']} services impacted: {', '.join(n['impacted_if_down'])}")
    if res["only_in_traffic"]:
        print("Seen in traffic but NOT in config:", [(e['from'], e['to']) for e in res["only_in_traffic"]])
    if res["only_in_config"]:
        print("In config but NOT seen in traffic:", [(e['from'], e['to']) for e in res["only_in_config"]])
    sys.exit(0)
