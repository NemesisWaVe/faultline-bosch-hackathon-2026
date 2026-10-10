# Progress — Milestone 1 (due 5:00 PM, internal deadline 4:30 PM, Sat 10 Oct 2026)

| # | Item | Status | Time | Evidence |
|---|------|--------|------|----------|
| 1 | Setup & app selection — sample app running end to end | 🟡 in progress | 11:28 | OTel Demo v3.1.0 cloned to `C:\Users\ASUS\opentelemetry-demo` |
| 2 | Application mapping — services, dependencies, data flows | 🟡 static view done | 11:44 | `reports/dependency_map.png`, `.json` (runtime view pending app start) |
| 3 | Monitoring baseline — error rate, latency, health under load | ⬜ | | |
| 4 | First failure injection — triggered and observed | ⬜ | | |
| 5 | Safety controls — auto stop/rollback, tested at least once | ⬜ | | |
| 6 | Day-1 checkpoint demo | ⬜ | | |

## Log
- **11:28** Docker Desktop was not running → started it. Cloned OTel Demo (image version 3.1.0).
  Found that this version splits services across several compose files; we use the same set as the
  demo's official `make start`: `compose.yaml` + `compose.full.yaml` + `compose.observability.yaml` + `compose.extras.yaml`.
