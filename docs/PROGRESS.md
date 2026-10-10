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
- **13:40 Published:** https://github.com/NemesisWaVe/faultline-bosch-hackathon-2026 (public, MIT license, README with deploy steps).
  Commit author changed to GitHub's private no-reply address before the first push, so no personal email is public.
