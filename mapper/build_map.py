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

import matplotlib
matplotlib.use("Agg")  # draw to a file, no window needed
import matplotlib.pyplot as plt
import networkx as nx
import requests
import yaml

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


def apply_overrides(graph):
    """Manual corrections from config/map_overrides.yaml (add_edges / remove_edges as [from, to] pairs)."""
    path = ROOT / "config" / "map_overrides.yaml"
    if not path.exists():
        return
    o = yaml.safe_load(path.read_text()) or {}
    for a, b in o.get("remove_edges") or []:
        if graph.has_edge(a, b):
            graph.remove_edge(a, b)
    for a, b in o.get("add_edges") or []:
        graph.add_edge(a, b, source="manual")


def build():
    services = load_compose()
    static = static_edges(services)
    runtime = runtime_edges()

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
    apply_overrides(g)

    # How many services break (directly or indirectly) if this one dies = everyone that can reach it.
    impact = {n: sorted(nx.ancestors(g, n) - ENTRY) for n in g.nodes}
    nodes = [{"name": n,
              "role": "entry" if n in ENTRY else ("datastore" if n in {"astronomy-db", "valkey-cart", "kafka"} else "service"),
              "depends_on": sorted(g.successors(n)),
              "depended_on_by": sorted(g.predecessors(n)),
              "impacted_if_down": impact[n],
              "impact_count": len(impact[n])}
             for n in sorted(g.nodes)]
    edges = [{"from": a, "to": b, **d} for a, b, d in g.edges(data=True)]
    result = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "runtime_view_available": bool(runtime),
        "nodes": sorted(nodes, key=lambda n: -n["impact_count"]),
        "edges": edges,
        "only_in_config": [e for e in edges if e["source"] == "static"] if runtime else [],
        "only_in_traffic": [e for e in edges if e["source"] == "runtime-only"],
        "excluded_support_services": sorted(SUPPORT),
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "dependency_map.json").write_text(json.dumps(result, indent=2))
    draw(g, impact, bool(runtime))
    return result


def draw(g, impact, have_runtime):
    # Left-to-right layers: traffic enters on the left, databases end up on the right.
    layer = {}
    for n in nx.topological_sort(g) if nx.is_directed_acyclic_graph(g) else g.nodes:
        preds = list(g.predecessors(n))
        layer[n] = 0 if not preds else max(layer.get(p, 0) for p in preds) + 1
    nx.set_node_attributes(g, layer, "layer")
    pos = nx.multipartite_layout(g, subset_key="layer")

    colors = {"both": "#2b8a3e", "static": "#868e96", "runtime-only": "#e8590c", "manual": "#7048e8"}
    plt.figure(figsize=(16, 9))
    for src, col in colors.items():
        es = [(a, b) for a, b, d in g.edges(data=True) if d["source"] == src]
        nx.draw_networkx_edges(g, pos, edgelist=es, edge_color=col, arrows=True, arrowsize=14,
                               width=2 if src != "static" else 1.2, connectionstyle="arc3,rad=0.05",
                               style="solid" if src != "static" else "dashed",
                               min_source_margin=18, min_target_margin=18)
    sizes = [700 + 260 * len(impact[n]) for n in g.nodes]  # bigger circle = more services hurt if it dies
    fill = ["#a5d8ff" if n in ENTRY else "#ffd8a8" if n in {"astronomy-db", "valkey-cart", "kafka"}
            else "#ffffff" for n in g.nodes]
    nx.draw_networkx_nodes(g, pos, node_size=sizes, node_color=fill, edgecolors="#212529")
    nx.draw_networkx_labels(g, pos, font_size=9)
    legend = [plt.Line2D([], [], color=colors["both"], lw=2, label="in config AND seen in traffic"),
              plt.Line2D([], [], color=colors["static"], lw=1.2, ls="--",
                         label="in config only" + ("" if have_runtime else " (runtime view not yet captured)")),
              plt.Line2D([], [], color=colors["runtime-only"], lw=2, label="seen in traffic only"),
              plt.Line2D([], [], marker="o", ls="", markersize=10, markerfacecolor="#ffd8a8",
                         markeredgecolor="#212529", label="data store / queue")]
    plt.legend(handles=legend, loc="lower left", fontsize=9)
    plt.title("Astronomy Shop dependency map — circle size = how many services are hurt if it fails")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(REPORTS / "dependency_map.png", dpi=150)


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
