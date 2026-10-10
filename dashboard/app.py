"""Faultline control room — the web dashboard for our chaos experiments.

Plain English: one page that shows
  1. how shoppers are doing RIGHT NOW, next to the healthy baseline and the safety limits,
  2. the dependency map (who depends on whom),
  3. a panel to start ONE experiment under the safety controller, with a big red STOP button,
  4. the history of every experiment, with its timeline.
The page never breaks anything itself: START runs controller/safety.py — the same referee we use on the
command line — so every safety rule (allowlist, time limit, automatic abort, one-at-a-time lock) still applies.

Run:     .venv\\Scripts\\streamlit run dashboard\\app.py --server.address 127.0.0.1
         (opens http://localhost:8501; the address flag keeps it reachable from THIS laptop only, never the venue Wi-Fi)
Outputs: reports/live_run.log (the referee's live output); experiments still go to reports/experiments.jsonl
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "controller"))
sys.path.insert(0, str(ROOT / "chaos"))
import safety  # noqa: E402  (limits, lock and STOP file live there: one source of truth)
from metrics import locust_counters, locust_window  # noqa: E402

REPORTS = ROOT / "reports"
LIVE_LOG = REPORTS / "live_run.log"
TARGETS = yaml.safe_load((ROOT / "config" / "targets.yaml").read_text())
PROJECT = TARGETS["compose_project"]
RED, GREY, BLUE = "#d62728", "#9e9e9e", "#1f77b4"

st.set_page_config(page_title="Faultline control room", page_icon="🧯", layout="wide")
st.markdown(f"""<style>
  .st-key-stop button {{ background:{RED}; color:white; border:none; font-size:1.3rem; font-weight:700; height:3.6rem; }}
  .st-key-stop button:disabled {{ background:#e9b3b3; }}
  .block-container {{ padding-top:2rem; }}
</style>""", unsafe_allow_html=True)


# ---------- helpers ----------
def experiment_running():
    """True while a safety-controller run keeps its lock fresh (also catches runs started from the command line)."""
    return safety.LOCK.exists() and time.time() - safety.LOCK.stat().st_mtime < safety.LOCK_STALE_SECONDS


def containers():
    """{name: status} for every container in our compose project, or None if Docker isn't answering."""
    try:
        out = subprocess.run(["docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={PROJECT}",
                              "--format", "{{.Names}}|{{.Status}}"], capture_output=True, text=True, timeout=10).stdout
    except subprocess.TimeoutExpired:
        return None
    if not out.strip():  # Docker engine down or unreachable (an empty project would never be our setup)
        return None
    return dict(line.split("|", 1) for line in out.splitlines() if "|" in line)


@st.cache_data(ttl=60)
def impact_counts():
    """How many services get hurt if each one fails — from the mapper's output."""
    try:
        nodes = json.loads((REPORTS / "dependency_map.json").read_text())["nodes"]
        return {n["name"]: n.get("impact_count", 0) for n in nodes}
    except Exception:
        return {}


def experiments():
    path = REPORTS / "experiments.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def limit_chart(df, field, title, limit, baseline, fmt):
    """Line of live readings + red dashed safety limit + grey baseline."""
    base = alt.Chart(df).encode(x=alt.X("time:T", title=None, axis=alt.Axis(format="%H:%M:%S")))
    line = base.mark_line(point=True, color=BLUE).encode(
        y=alt.Y(f"{field}:Q", title=title), tooltip=[alt.Tooltip("time:T", format="%H:%M:%S"), alt.Tooltip(f"{field}:Q", format=fmt)])
    rules = pd.DataFrame({"y": [limit, baseline], "what": ["safety limit", "healthy baseline"]})
    rule = alt.Chart(rules).mark_rule(strokeDash=[6, 4], size=2).encode(
        y="y:Q", color=alt.Color("what:N", scale=alt.Scale(domain=["safety limit", "healthy baseline"], range=[RED, GREY]),
                                 legend=alt.Legend(orient="top", title=None)))
    return (line + rule).properties(height=230)


limits = safety.load_limits()

# ---------- header ----------
st.title("🧯 Faultline — chaos control room")
st.caption("Breaks one part of the Astronomy Shop on purpose, watches what shoppers feel every 5 s, "
           "and undoes the damage automatically if it crosses the safety limits.")


# ---------- live scoreboard (refreshes itself every 5 s) ----------
@st.fragment(run_every=5)
def scoreboard():
    ss = st.session_state
    ss.setdefault("history", [])
    try:
        cur = locust_counters()
        s = locust_window(ss["prev"], cur) if "prev" in ss else {}
        ss["prev"] = cur
        if s.get("mean_ms") is not None:
            ss["history"] = (ss["history"] + [{"time": pd.Timestamp.now(), "errors_pct": 100 * s["error_rate"],
                                               "avg_ms": s["mean_ms"], "rps": s["rps"]}])[-120:]  # last 10 min
        shop_ok = True
    except Exception as exc:
        s, shop_ok = {}, False
        st.error(f"Can't read the load generator — is the shop running? ({exc.__class__.__name__})")

    cs = containers()
    running = experiment_running()
    c1, c2, c3, c4, c5 = st.columns(5)
    if cs is None:
        c1.metric("Shop containers", "Docker not answering")
    else:
        up = sum(v.startswith("Up") for v in cs.values())
        c1.metric("Shop containers up", f"{up} / {len(cs)}")
    c2.metric("Simulated shoppers", s.get("users", cur["users"] if shop_ok else "—"))
    err = s.get("error_rate")
    c3.metric(f"Failed requests (limit {limits['max_error_rate']:.0%})", "…" if err is None else f"{err:.1%}",
              delta=None if err is None or abs(err - limits['baseline_error_rate']) < 0.0005
              else f"{100 * (err - limits['baseline_error_rate']):+.1f} pts vs healthy",
              delta_color="inverse")
    ms = s.get("mean_ms")
    c4.metric(f"Avg response (limit {limits['max_mean_ms']:.0f} ms)", "…" if ms is None else f"{ms} ms",
              delta=None if ms is None else f"{ms - limits['baseline_mean_ms']:+.0f} ms vs healthy", delta_color="inverse")
    c5.metric("Experiment", "🔴 RUNNING" if running else "🟢 idle")

    if ss["history"]:
        df = pd.DataFrame(ss["history"])
        left, right = st.columns(2)
        left.altair_chart(limit_chart(df, "errors_pct", "failed requests (%)", 100 * limits["max_error_rate"],
                                      100 * limits["baseline_error_rate"], ".1f"), use_container_width=True)
        right.altair_chart(limit_chart(df, "avg_ms", "avg response (ms)", limits["max_mean_ms"],
                                       limits["baseline_mean_ms"], ".0f"), use_container_width=True)
    else:
        st.info("Collecting the first readings (one every 5 s)…")
    if cs:
        down = {k: v for k, v in cs.items() if not v.startswith("Up")}
        if down:
            st.warning("Not running right now: " + ", ".join(f"**{k}** ({v})" for k, v in down.items()))


scoreboard()


# ---------- experiment control (sidebar) ----------
with st.sidebar:
    st.header("Run one experiment")
    impact = impact_counts()
    allow = sorted(TARGETS["allowlist"], key=lambda n: (impact.get(n, 0), n))
    target = st.selectbox("Target (smallest blast radius first)", allow,
                          index=allow.index("recommendation") if "recommendation" in allow else 0,
                          format_func=lambda n: f"{n} — {impact.get(n, '?')} service(s) depend on it")
    kind = st.radio("Fault", ["kill", "pause"], horizontal=True,
                    captions=["crash it (like pulling the plug)", "freeze it (running but silent)"])
    st.caption("Network delay / packet loss: built, not yet tested — not offered here.")
    duration = st.slider("Hard time limit (seconds)", 30, int(safety.CFG["max_experiment_seconds"]), 90, step=10)
    st.caption(f"Auto-abort if failed requests > {limits['max_error_rate']:.0%} or avg response > "
               f"{limits['max_mean_ms']:.0f} ms, averaged over the last {safety.CFG['abort_window_checks'] * safety.CFG['check_interval_seconds']} s.")

    running = experiment_running()
    if st.button(f"▶ START: {kind} {target}", type="primary", disabled=running, use_container_width=True):
        LIVE_LOG.parent.mkdir(exist_ok=True)
        log = open(LIVE_LOG, "w", encoding="utf-8")
        # -u = print each line immediately, so the page can show the referee's output live
        subprocess.Popen([sys.executable, "-u", str(ROOT / "controller" / "safety.py"), kind, target,
                          "--duration", str(duration)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        for _ in range(20):  # wait (max 10 s) until the referee has taken the lock
            if experiment_running():
                break
            time.sleep(0.5)
        st.rerun()

    if st.button("⏹ STOP EXPERIMENT", key="stop", disabled=not running, use_container_width=True):
        safety.STOP_FILE.write_text(time.strftime("%H:%M:%S"))
        st.toast("STOP sent — the referee undoes the fault within ~1 s")

    with st.expander("Emergency: restore everything"):
        st.caption("Runs chaos/stop_all.ps1 — unfreezes/starts every shop container. Safe any time.")
        if st.button("Run emergency restore", use_container_width=True):
            with st.spinner("Restoring…"):
                out = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "chaos" / "stop_all.ps1")],
                                     capture_output=True, text=True, timeout=180)
            st.code(out.stdout[-3000:] or out.stderr[-3000:])


# ---------- tabs ----------
live_tab, map_tab, hist_tab = st.tabs(["🎬 Live referee", "🗺️ Dependency map", "📜 Experiment history"])

with live_tab:
    @st.fragment(run_every=2)
    def referee():
        if not LIVE_LOG.exists():
            st.info("No experiment started from this page yet. Press START in the sidebar.")
            return
        text = LIVE_LOG.read_text(encoding="utf-8", errors="replace")
        if "Traceback" in text and "INJECT" not in text:
            st.warning("The last run stopped with an error BEFORE injecting anything — nothing was broken. "
                       "Most likely Docker was not answering (see the last line below).")
        elif "Traceback" in text:
            st.error("The referee stopped with an error during the experiment — run the emergency restore to be sure.")
        if "!!! ABORT" in text:
            st.error("🚨 SAFETY STOP FIRED — the last 30 s averaged over a limit, so the fault was undone automatically.")
        elif "!!! STOP pressed" in text:
            st.warning("⏹ Stopped by hand — the fault was undone.")
        elif "Time limit reached" in text:
            st.success("⏱ Time limit reached without breaching the limits — fault undone as planned.")
        if "RECOVERED:" in text:
            st.success("✅ " + re.search(r"RECOVERED: (.*)", text).group(1))
        elif "NOT RECOVERED" in text:
            st.error("❌ Not recovered within 5 minutes — serious finding.")
        avgs = re.findall(r"30s avg: errors ([\d.]+)% \(limit ([\d.]+)%\)\s+avg (\d+) ms \(limit (\d+) ms\)", text)
        if experiment_running() and "RESTORED" not in text:
            if avgs:
                e, el, m, ml = map(float, avgs[-1])
                st.progress(min(e / el, 1.0), text=f"Failed requests, 30 s average: {e:.1f}% of the {el:.0f}% limit")
                st.progress(min(m / ml, 1.0), text=f"Avg response, 30 s average: {m:.0f} ms of the {ml:.0f} ms limit")
            else:
                st.info("Fault active — collecting the first 30 s of readings before the referee can judge.")
        st.code("\n".join(text.splitlines()[-22:]) or "starting…", language=None)
    referee()

with map_tab:
    st.image(str(REPORTS / "dependency_map.png"), use_container_width=True)
    st.caption("Red badge = how many services get hurt if this one fails. Green = seen in config AND real traffic; "
               "grey = config only; dashed = asynchronous via the Kafka message queue.")

with hist_tab:
    exps = experiments()
    if not exps:
        st.info("No experiments logged yet.")
    else:
        table = pd.DataFrame([{
            "started": e["started_at"], "fault": e["fault"], "target": e["target"],
            "safety stop": "🚨 yes" if e["abort_fired"] else "no", "why": e.get("abort_reason") or "—",
            "peak errors": f"{e['peak_error_rate']:.0%}", "peak avg response": f"{e['peak_mean_ms']} ms",
            "fault active": f"{e.get('fault_active_s', '?')} s",
            "recovery": "not recovered" if e.get("recovery_time_s") is None else f"{e['recovery_time_s']} s",
        } for e in exps][::-1])
        st.dataframe(table, hide_index=True, use_container_width=True)

        pick = st.selectbox("Show timeline of", range(len(exps))[::-1],
                            format_func=lambda i: f"{exps[i]['started_at']} — {exps[i]['fault']} {exps[i]['target']}")
        e = exps[pick]
        tl = pd.DataFrame([x for x in e["timeline"] if x.get("mean_ms") is not None])
        if not tl.empty:
            tl["errors_pct"] = 100 * tl["error_rate"]
            shade = alt.Chart(pd.DataFrame({"start": [0], "end": [e.get("fault_active_s", 0)]})).mark_rect(
                color=RED, opacity=0.08).encode(x="start:Q", x2="end:Q")
            for field, title, lim, fmt in (("errors_pct", "failed requests (%)", 100 * e["max_error_rate"], ".1f"),
                                           ("mean_ms", "avg response (ms)", e["max_mean_ms"], ".0f")):
                line = alt.Chart(tl).mark_line(point=True, color=BLUE).encode(
                    x=alt.X("t:Q", title="seconds since the fault was injected"), y=alt.Y(f"{field}:Q", title=title),
                    tooltip=["t", "phase", alt.Tooltip(f"{field}:Q", format=fmt)])
                rule = alt.Chart(pd.DataFrame({"y": [lim]})).mark_rule(color=RED, strokeDash=[6, 4], size=2).encode(y="y:Q")
                st.altair_chart((shade + line + rule).properties(height=220), use_container_width=True)
            st.caption("Shaded = fault active (until the safety stop / time limit). Red dashed = safety limit.")
