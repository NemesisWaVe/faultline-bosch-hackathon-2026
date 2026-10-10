# Progress — Milestone 1 (due 5:00 PM, internal deadline 4:30 PM, Sat 10 Oct 2026)

| # | Item | Status | Time | Evidence |
|---|------|--------|------|----------|
| 1 | Setup & app selection — sample app running end to end | ✅ done | 12:06 | All 28 containers Up; shop, Locust, Grafana, Jaeger return HTTP 200 |
| 2 | Application mapping — services, dependencies, data flows | ✅ done | 12:28 | `reports/dependency_map.png` — config + real-traffic (Jaeger) views merged |
| 3 | Monitoring baseline — error rate, latency, health under load | ⬜ | | |
| 4 | First failure injection — triggered and observed | ⬜ | | |
| 5 | Safety controls — auto stop/rollback, tested at least once | ⬜ | | |
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
