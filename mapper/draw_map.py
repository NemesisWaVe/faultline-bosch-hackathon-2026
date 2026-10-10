"""Draws the dependency map picture from reports/dependency_map.json.

Plain English: services are placed in columns from left (where traffic enters) to right (databases),
like a flowchart. Long arrows get invisible waypoints so they curve around boxes instead of through them,
and each column is re-ordered a few times to reduce arrows crossing each other (the standard
"layered graph drawing" method used by tools like Graphviz).

Run on its own to redraw without Docker:  python mapper/draw_map.py
"""
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Patch
from matplotlib.path import Path as MPath

ROOT = Path(__file__).resolve().parents[1]

BOX_W, BOX_H = 2.4, 0.8      # every box is wide enough for the longest name ("product-catalog")
COL_GAP = 3.8                # horizontal distance between columns
REAL_H, DUMMY_H = 1.3, 0.45  # vertical space a box / an arrow waypoint needs
FILL = {"entry": "#d0ebff", "service": "#ffffff", "datastore": "#ffe8cc"}
EDGE_COLOR = {"both": "#2b8a3e", "static": "#495057", "runtime-only": "#e8590c", "manual": "#7048e8"}


def _layers(g):
    """Column number = length of the longest chain of arrows leading into the service."""
    dag = g.copy()
    while not nx.is_directed_acyclic_graph(dag):  # safety net: ignore loops when choosing columns
        dag.remove_edge(*nx.find_cycle(dag)[0][:2])
    layer = {}
    for n in nx.topological_sort(dag):
        layer[n] = max((layer[p] + 1 for p in dag.predecessors(n)), default=0)
    return layer


def _crossings(cols, og, idx):
    c = 0
    for col in cols.values():
        es = [(idx[u], idx[v]) for u in col for v in og.successors(u)]
        c += sum(1 for i in range(len(es)) for j in range(i + 1, len(es))
                 if (es[i][0] - es[j][0]) * (es[i][1] - es[j][1]) < 0)
    return c


def _place(desired, gaps):
    """Keep the column's order and minimum spacing while staying close to the desired heights."""
    down = desired[:]
    for i in range(1, len(down)):
        down[i] = max(down[i], down[i - 1] + gaps[i])
    up = desired[:]
    for i in range(len(up) - 2, -1, -1):
        up[i] = min(up[i], up[i + 1] - gaps[i + 1])
    res = [(a + b) / 2 for a, b in zip(down, up)]
    for i in range(1, len(res)):
        res[i] = max(res[i], res[i - 1] + gaps[i])
    return res


def layout(nodes, edges):
    g = nx.DiGraph()
    g.add_nodes_from(nodes)
    g.add_edges_from(edges)
    layer = _layers(g)

    # Long arrows get one invisible waypoint per column they pass through.
    og, chains = nx.DiGraph(), {}
    og.add_nodes_from(nodes)
    for a, b in edges:
        path = [a] + [("wp", a, b, L) for L in range(layer[a] + 1, layer[b])] + [b]
        for wp in path[1:-1]:
            layer[wp] = wp[3]
        chains[(a, b)] = path
        og.add_edges_from(zip(path, path[1:]))

    cols = defaultdict(list)
    for n in sorted(og.nodes, key=lambda n: (isinstance(n, tuple), str(n))):
        cols[layer[n]].append(n)
    idx = {n: i for col in cols.values() for i, n in enumerate(col)}
    best = (_crossings(cols, og, idx), {L: c[:] for L, c in cols.items()})
    last = max(cols)
    for it in range(40):  # sweep left->right then right->left, sorting by neighbours' average position
        down = it % 2 == 0
        for L in (range(1, last + 1) if down else range(last - 1, -1, -1)):
            def bary(n):
                nb = [idx[m] for m in (og.predecessors(n) if down else og.successors(n))]
                return sum(nb) / len(nb) if nb else idx[n]
            cols[L].sort(key=bary)
            idx.update({n: i for i, n in enumerate(cols[L])})
        c = _crossings(cols, og, idx)
        if c < best[0]:
            best = (c, {L: col[:] for L, col in cols.items()})
    cols = best[1]

    def h(n):
        return DUMMY_H if isinstance(n, tuple) else REAL_H
    y = {}
    for col in cols.values():
        total = sum(h(n) for n in col)
        acc = -total / 2
        for n in col:
            y[n] = acc + h(n) / 2
            acc += h(n)
    und = og.to_undirected()
    for _ in range(60):  # pull each box toward the height of its neighbours -> straighter arrows
        for col in cols.values():
            desired = [sum(y[m] for m in und[n]) / len(und[n]) if len(und[n]) else y[n] for n in col]
            gaps = [0] + [(h(a) + h(b)) / 2 for a, b in zip(col, col[1:])]
            for n, v in zip(col, _place(desired, gaps)):
                y[n] = v
    mid = sum(y[n] for n in nodes) / len(nodes)
    pos = {n: (layer[n] * COL_GAP, y[n] - mid) for n in og.nodes}
    return pos, chains


def _curve(points):
    """Smooth S-curves through the points, leaving and entering every point horizontally."""
    verts, codes = [points[0]], [MPath.MOVETO]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        dx = (x1 - x0) * 0.5
        verts += [(x0 + dx, y0), (x1 - dx, y1), (x1, y1)]
        codes += [MPath.CURVE4] * 3
    return MPath(verts, codes)


def draw_map(result, out_path):
    nodes_info = {n["name"]: n for n in result["nodes"]}
    shown = [e for e in result["edges"] if not e.get("hidden")]
    # Draw arrows in the direction data flows (queue -> consumer for async readers).
    flow = [((e["to"], e["from"]) if e.get("drawn_reversed") else (e["from"], e["to"]), e) for e in shown]
    pos, chains = layout(list(nodes_info), [ab for ab, _ in flow])
    # Y grows downward in the layout; flip so the first box is at the top.
    pos = {n: (x, -y) for n, (x, y) in pos.items()}

    # Spread arrow attachment points along each box side, sorted by where the arrow goes.
    out_port, in_port = {}, {}
    by_src, by_dst = defaultdict(list), defaultdict(list)
    for (a, b), _ in flow:
        path = chains[(a, b)]
        by_src[a].append(((a, b), pos[path[1]][1]))
        by_dst[b].append(((a, b), pos[path[-2]][1]))
    for store, groups in ((out_port, by_src), (in_port, by_dst)):
        for lst in groups.values():
            lst.sort(key=lambda t: -t[1])
            k = len(lst)
            for i, (key, _) in enumerate(lst):
                store[key] = 0 if k == 1 else (0.28 - 0.56 * i / (k - 1)) * BOX_H

    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    width = max(xs) - min(xs) + BOX_W + 1.2
    height = max(ys) - min(ys) + BOX_H + 2.6
    fig, ax = plt.subplots(figsize=(width * 0.95, height * 0.95))
    ax.set_xlim(min(xs) - BOX_W / 2 - 0.6, max(xs) + BOX_W / 2 + 0.6)
    ax.set_ylim(min(ys) - BOX_H / 2 - 1.2, max(ys) + BOX_H / 2 + 1.0)
    ax.set_aspect("equal")
    ax.axis("off")

    for (a, b), e in flow:
        path = chains[(a, b)]
        pts = [(pos[a][0] + BOX_W / 2, pos[a][1] + out_port[(a, b)])]
        for wp in path[1:-1]:  # run straight and level past the boxes in a column, curve only between columns
            wx, wy = pos[wp]
            pts += [(wx - BOX_W / 2, wy), (wx + BOX_W / 2, wy)]
        pts += [(pos[b][0] - BOX_W / 2 - 0.04, pos[b][1] + in_port[(a, b)])]
        ax.add_patch(FancyArrowPatch(path=_curve(pts), arrowstyle="-|>", mutation_scale=16,
                                     color=EDGE_COLOR.get(e["source"], "#495057"), lw=1.6,
                                     linestyle=(0, (5, 3)) if e.get("async") else "solid",
                                     alpha=0.85, zorder=1))

    max_impact = max(n["impact_count"] for n in nodes_info.values()) or 1
    for name, info in nodes_info.items():
        x, y = pos[name]
        crit = info["impact_count"]
        ax.add_patch(FancyBboxPatch((x - BOX_W / 2, y - BOX_H / 2), BOX_W, BOX_H,
                                    boxstyle="round,pad=0,rounding_size=0.18",
                                    fc=FILL[info["role"]], ec="#212529",
                                    lw=1.2 + 1.8 * crit / max_impact, zorder=3))
        ax.text(x, y, name, ha="center", va="center", fontsize=12, zorder=4,
                fontweight="bold" if crit == max_impact else "normal")
        if crit:
            shade = plt.cm.Reds(0.45 + 0.5 * crit / max_impact)
            bx, by = x + BOX_W / 2 - 0.5, y + BOX_H / 2  # clear of the arrow exits on the right edge
            ax.add_patch(Circle((bx, by), 0.24, fc=shade, ec="white", lw=1.5, zorder=5))
            ax.text(bx, by, str(crit), ha="center", va="center", color="white",
                    fontsize=10, fontweight="bold", zorder=6)

    ax.annotate("", xy=(max(xs), max(ys) + BOX_H / 2 + 0.6), xytext=(min(xs), max(ys) + BOX_H / 2 + 0.6),
                arrowprops=dict(arrowstyle="-|>", color="#adb5bd", lw=1.5))
    ax.text((min(xs) + max(xs)) / 2, max(ys) + BOX_H / 2 + 0.75,
            "requests flow left → right:  traffic in  →  web front  →  business services  →  data stores",
            ha="center", va="bottom", fontsize=11, color="#868e96")

    runtime = result.get("runtime_view_available")
    hidden = sum(1 for e in result["edges"] if e.get("hidden"))
    legend = [
        Line2D([], [], color=EDGE_COLOR["both"], lw=2, label="in config AND seen in real traffic"),
        Line2D([], [], color=EDGE_COLOR["static"], lw=2,
               label="in config only" + ("" if runtime else " (traffic view not captured yet)")),
        Line2D([], [], color=EDGE_COLOR["runtime-only"], lw=2, label="seen in traffic only"),
        Line2D([], [], color="#495057", lw=2, ls=(0, (5, 3)), label="async via message queue"),
        Patch(fc=FILL["entry"], ec="#212529", label="traffic entry"),
        Patch(fc=FILL["service"], ec="#212529", label="service"),
        Patch(fc=FILL["datastore"], ec="#212529", label="database / queue"),
        Line2D([], [], marker="o", ls="", markersize=13, markerfacecolor=plt.cm.Reds(0.8),
               markeredgecolor="white", label="N = services hurt if this fails"),
    ]
    ax.legend(handles=legend, loc="lower center", ncol=4, fontsize=10, frameon=False,
              bbox_to_anchor=(0.5, -0.02))
    ax.set_title("Astronomy Shop — service dependency map", fontsize=16, pad=12)
    fig.text(0.5, 0.01, f"Not shown: monitoring / feature-flag tools (never targeted) and {hidden} "
             f"start-up-order-only links.  Generated {result['generated_at']}.",
             ha="center", fontsize=9, color="#868e96")
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    data = json.loads((ROOT / "reports" / "dependency_map.json").read_text())
    draw_map(data, ROOT / "reports" / "dependency_map.png")
    print("Redrew reports/dependency_map.png")
