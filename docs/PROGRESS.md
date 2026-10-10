# Progress — Milestone 1 (due 5:00 PM, internal deadline 4:30 PM, Sat 10 Oct 2026)

| # | Item | Status | Time | Evidence |
|---|------|--------|------|----------|
| 1 | Setup & app selection — sample app running end to end | ✅ done | 12:06 | All 28 containers Up; shop, Locust, Grafana, Jaeger return HTTP 200 |
| 2 | Application mapping — services, dependencies, data flows | 🟡 static view done | 11:44 | `reports/dependency_map.png`, `.json` (clean flowchart layout; runtime view pending app start) |
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
