# Progress — Milestone 1 (due 5:00 PM, internal deadline 4:30 PM, Sat 10 Oct 2026)

| # | Item | Status | Time | Evidence |
|---|------|--------|------|----------|
| 1 | Setup & app selection — sample app running end to end | ✅ done | 12:06 | All 28 containers Up; shop, Locust, Grafana, Jaeger return HTTP 200 |
| 2 | Application mapping — services, dependencies, data flows | ✅ done | 12:28 | `reports/dependency_map.png` — config + real-traffic (Jaeger) views merged |
| 3 | Monitoring baseline — error rate, latency, health under load | ✅ done | 13:08 | `reports/baseline.json` — 15 users, 180 s, 36 readings: 0.00% errors, 517 ms avg response, 2.7 req/s, all containers Up |
| 4 | First failure injection — triggered and observed | ✅ done | 13:11 | `reports/experiments.jsonl` line 1 — `safety.py kill recommendation`, run by the team; errors up to 20%, avg response up to 3.7 s |
| 5 | Safety controls — auto stop/rollback, tested at least once | ✅ done | 13:12 | Same run: automatic ABORT after 6 bad checks (30 s), reason `errors 9.1% > 5.0%; avg response 1745 ms > 1034 ms`; container restarted by the controller, fault active 41 s instead of 90 s |
| 6 | Day-1 checkpoint demo | ⬜ | | |

## Log
- **11:28** Docker Desktop was not running → started it. Cloned OTel Demo (image version 3.1.0).
  Found that this version splits services across several compose files; we use the same set as the
  demo's official `make start`: `compose.yaml` + `compose.full.yaml` + `compose.observability.yaml` + `compose.extras.yaml`.
- **12:06** All 28 containers up (frontend-proxy image was built locally — not published for `latest`).
- **12:08** Metrics decision: Prometheus span metrics only refresh every ~60 s → too slow for a 5 s safety loop.
  Safety controller uses Locust live stats (~2 s refresh, what shoppers feel); Prometheus used for per-service reports.
  `/prompt` (optional AI-chatbot add-on, not deployed) excluded from error rate. Load was only 5 users (~1 rps) → raise before baseline.
- **12:24** Team's first manual crash: `docker kill recommendation` → Docker did NOT auto-restart it (RestartCount 0); manual `docker start` restored it. Finding: no self-healing on kill despite `restart: unless-stopped`.
- **12:28** Runtime map: all 19 service-to-service calls confirmed by traffic; browser (`frontend-web`) seen only in traffic; database/Kafka links seen only in config (tracing blind spot).
- **12:31 UNPLANNED EXPERIMENT (traffic spike):** load raised to 50 users → 48% errors, 9.5 s avg response.
  `astronomy-db` OOMKilled=true (memory limit only 80 MB) → product-catalog requests returned 504 Gateway Timeout.
  Load generator itself at ~880% CPU / 99.7% memory (OOM flag) → 50 users is beyond what the load generator can drive.
  Finding: the #1 critical service on our map (astronomy-db) is the first to fail under a spike. Fix idea: raise DB memory limit / add connection pooling / cache product catalog.
- **13:07 Confirmed from database logs:** at 12:30:35 one Postgres worker was killed by the out-of-memory killer
  (`client backend (PID 106) was terminated by signal 9: Killed`). Postgres then reset ALL its connections and
  ran crash recovery; 122 connection attempts were refused ("in recovery mode") until 12:30:37. The container
  itself never restarted (RestartCount 0), so `docker ps` showed it "Up" the whole time — the failure was invisible
  at the container level. At 15 users the DB still uses 60 of its 80 MB (75%).
- **13:08 Baseline captured** (15 users, 3 min): 0.00% errors, median avg response 517 ms (5 s readings swing 275–880 ms),
  2.7 req/s; frontend p95 658 ms, product-catalog p95 681 ms, checkout p95 3.5 s (Prometheus).
  Safety limits derived: abort if errors > 5% or avg response > 1,034 ms for 30 s.
  Note: at 5 users avg response was ~115 ms; at 15 users it is ~517 ms → the shop already slows 4–5× under modest load.
- **13:12 Recovery check changed** to a 30 s average (was: six 5 s readings in a row) because healthy readings alone
  swing 275–880 ms — about 1 in 4 healthy readings exceeds the 620 ms "recovered" bar. Tested on sample data, not yet live.
- **13:11–13:13 Experiment 1 — kill `recommendation` (limit 90 s), team ran `controller/safety.py`.**
  First 10 s fine; from +15 s every check breached (avg response 1.2–3.7 s, errors up to 20%) → **automatic ABORT at +41 s**,
  controller restarted recommendation (13:12:08). Recovery (30 s average back within 20% of baseline): **66 s after restore**.
  All 28 containers Up afterwards (checked 13:14).
  Findings: (1) a "leaf" service nobody depends on still hurt 1 in 5 shopper requests — the frontend has no fallback for missing recommendations.
  (2) recommendation was ready at 13:12:08 but got its first request only at 13:12:29, then ~10 at once (logs) —
  likely the frontend's connection retry waiting ("backoff") then releasing queued requests. (3) AFTERSHOCK: 30–60 s after the restore,
  a second wave hit (25–50% errors, 6–9.7 s responses). Cause NOT yet confirmed: database did not crash and product-catalog logged no errors.
  Hypothesis: the burst of queued recommendation requests (each one asks product-catalog for products) overloaded product-catalog. To check in Jaeger.
- **13:33 Published:** https://github.com/NemesisWaVe/faultline-bosch-hackathon-2026 (public, MIT license, README with deploy steps).
  Commit author changed to GitHub's private no-reply address before the first push, so no personal email is public.
- **13:45 CORRECTION to the 12:24 finding:** `docker kill` is treated by Docker as a deliberate stop by the operator, so the
  restart policy is skipped — that's normal Docker behaviour, not "no self-healing". Evidence: product-catalog crashed on its
  own at 12:40 and Docker DID auto-restart it (RestartCount 1; not OOM-flagged; 16.5 of 20 MB memory in use; cause unknown).
- **13:45 Emergency stop fixed + tested:** `stop_all.ps1` used to run a network-cleanup container against all 28 containers
  (incl. monitoring) and would have pulled an unverified image. Now: only the 17 allowlisted targets, and only if a network
  fault ever ran. Test run with nothing broken: 5.4 s, no changes, 28/28 Up. Not yet tested on a broken container.
- **13:45** `docs/DEMO_SCRIPT.md` written (3 min, roles, exact commands, fallbacks, judge Q&A).
- **14:20 Docker engine froze** (no answer for >60 s, shop down; laptop had 13 GB free and did not sleep; cause unknown).
  Fix in our controller: every Docker command now times out after 60 s and reports it instead of hanging — tested against the real hang.
- **14:41 After Docker Desktop restart only 4 of 28 containers came back** on their own; the restart policy did not cover this
  case. Re-ran the compose start command → 28/28 Up at 14:42; load set back to 15 users; shopper numbers (0% errors,
  258–744 ms) match the 13:08 baseline, so the baseline is still valid.
- **14:52 Rehearsal run (kill recommendation, 90 s) — safety stop did NOT fire although shoppers were hurt:**
  errors up to 27% and avg response up to 3.7 s in 8 of 18 checks, but the damage came in bursts; the longest run of bad
  checks was 4, and every single normal reading reset the "6 in a row" counter. Fault undone by the 90 s timer; recovery 10 s.
- **15:00 Abort rule changed to a 30 s rolling average** (`abort_window_checks: 6`). Replayed on all real data:
  run 1 → aborts at +31 s (old rule +41 s); rehearsal run → aborts at +31 s (old rule never); healthy baseline → no false alarm
  (worst 30 s average 572 ms vs 1,034 ms limit). Replay-tested; not yet tested live.
- **15:00 Dashboard `dashboard/app.py` (Streamlit)** running at http://localhost:8501: live shopper numbers vs limits, map,
  experiment START + big STOP button, live referee output, experiment history with timelines. Read-only views tested in the
  browser; START/STOP not yet tested live. Controller additions: STOP file (checked every 1 s) and a one-experiment-at-a-time
  lock shared by dashboard and command line (both unit-tested).
- **15:03 Experiment 3 — kill recommendation, NEW 30 s-average rule, live:** safety stop fired at +31 s
  (`30 s average: errors 9.4% > 5.0%; avg response 2178 ms > 1034 ms`) → new rule tested live ✅.
  BUT after the restore the whole shop failed (up to 100% errors, Grafana 503) and did NOT recover within 5 min.
  Cause unknown — likely linked to the Docker engine degrading (it fully froze ~15:34). Unresolved finding.
- **15:34 Docker froze again**; our 60 s timeout made the next run fail safely BEFORE injecting anything. PC restarted ~16:00.
- **16:21 Dashboard security fix:** Streamlit was listening on the venue network (10.19.49.92:8501) — anyone on the Wi-Fi could
  have pressed START. Now bound to 127.0.0.1 only (verified: server reports only http://127.0.0.1:8501).
  Also: shows "Docker not answering" instead of 0/0, and explains a failed run in plain English.
