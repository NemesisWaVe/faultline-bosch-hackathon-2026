# Faultline — AI-driven chaos engineering with a safety referee

**Faultline breaks parts of a cloud-native app on purpose, in a controlled way, to find weaknesses before a real outage does — and stops itself automatically if real users would get hurt.**

Built for the **Bosch hackathon "AI-Driven Chaos Engineering for Cloud-Native Resilience"**, Bengaluru, 10–11 Oct 2026.
*Not an official Bosch project.*

- **This repo (the chaos controller):** https://github.com/NemesisWaVe/faultline-bosch-hackathon-2026
- **Target app ("the victim"):** [OpenTelemetry Demo / Astronomy Shop](https://github.com/open-telemetry/opentelemetry-demo) (Apache 2.0) — a 28-container online shop made of microservices, run entirely on our own laptop.

---

## How it works (plain English)

```
[Mapper] → dependency map ──┐
[Baseline] → "healthy" numbers ┼→ [Planner*] → picks an experiment → [Injector] → breaks ONE thing
                             │                                          │
                             └──── [Safety controller] ◄────────────────┘  checks shoppers every 5 s,
                                     aborts + restores on threshold breach
                                              │
                                        [Reporter*] → findings, fixes, resilience score
```
\* Planner and Reporter (local AI model) are Day-2 work; everything else is working today.

| Part | What it does | File |
|---|---|---|
| Mapper | Draws who-talks-to-whom from the config files **and** real traffic (Jaeger traces), and counts how many services depend on each one | `mapper/build_map.py` → `reports/dependency_map.png/.json` |
| Baseline | Measures "healthy" with fake shoppers running and nothing broken | `baseline/capture.py` → `reports/baseline.json` |
| Injector | Breaks one allowlisted container: crash (`kill`), freeze (`pause`), network delay/loss (Pumba — not yet tested) | `chaos/inject.py` |
| Safety controller | Runs one experiment; aborts and restores if errors or slowness stay over the limits for 30 s; then measures recovery time; logs everything | `controller/safety.py` → `reports/experiments.jsonl` |
| Emergency stop | Undoes every possible fault on every shop container | `chaos/stop_all.ps1` |

### Safety rules (seat belts)
1. **Allowlist/denylist** (`config/targets.yaml`): only shop services in our own Docker Compose project can be targeted; monitoring, the load generator and the proxy can never be broken.
2. **Hard time limit:** every fault is undone after at most 120 s.
3. **Threshold abort** (`config/thresholds.yaml`): stop early if errors > max(5%, 3× baseline) or average response > 2× baseline for 30 s.
4. **Ctrl+C** restores immediately; `chaos/stop_all.ps1` is the big red button.
5. **One experiment at a time**, never anything outside this laptop.

---

## Results so far (real runs, 10 Oct 2026)

**Baseline** (15 simulated shoppers, 3 min): 0.00% errors, 517 ms average response, 2.7 requests/s → abort limits 5% errors / 1,034 ms.

**Experiment 1 — crash `recommendation` (90 s limit):**
- From +15 s, up to 20% of shopper requests failed and responses reached 3.7 s.
- **The safety controller aborted automatically at +41 s** (`errors 9.1% > 5.0%; avg response 1745 ms > 1034 ms`) and restarted the service.
- Shop back to normal (30 s average within 20% of baseline) **66 s** after the restart.
- Findings: a small, optional service hurt 1 in 5 requests (no fallback); a second wave of failures arrived 30–60 s *after* the fix (cause under investigation).

**Unplanned traffic spike (100 shoppers):** the database ran out of memory (80 MB limit) and errors hit 56%, while Docker still reported the container as "Up" — the crash was only visible in the database logs and in what shoppers felt.

Full log with evidence: [`docs/PROGRESS.md`](docs/PROGRESS.md). Plain-English explanations: [`docs/EXPLAINER.md`](docs/EXPLAINER.md), [`docs/GLOSSARY.md`](docs/GLOSSARY.md).

---

## Deploy it yourself

Tested on Windows 11 + PowerShell, Docker Desktop 28.3 (Compose v2.39), Python 3, 32 GB RAM.
The OTel Demo is heavy: give Docker at least ~8 GB of memory.

### 1. Start the target app (OpenTelemetry Demo)
```powershell
cd $HOME
git clone https://github.com/open-telemetry/opentelemetry-demo.git
cd opentelemetry-demo
docker compose --env-file .env --env-file .env.override -f compose.yaml -f compose.full.yaml -f compose.observability.yaml -f compose.extras.yaml up -d --remove-orphans
```
This is the same set of services as the demo's official `make start`. If the `frontend-proxy` image cannot be pulled (it happened to us with the `latest` tag), build it locally with the same command but `build frontend-proxy` instead of `up -d --remove-orphans`, then run `up` again.

Check it: `docker compose ps` should show all 28 containers Up. Then open:
| What | URL |
|---|---|
| Shop | http://localhost:8080 |
| Load generator (Locust) | http://localhost:8080/loadgen/ |
| Grafana dashboards | http://localhost:8080/grafana |
| Jaeger traces | http://localhost:8080/jaeger/ui |

In Locust, set **15 users** (ramp up 5).

### 2. Set up Faultline
```powershell
git clone https://github.com/NemesisWaVe/faultline-bosch-hackathon-2026.git
cd faultline-bosch-hackathon-2026
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If the OTel Demo is not in `$HOME\opentelemetry-demo`, set `$env:OTEL_DEMO_DIR = "<path>"`.

### 3. Run it
```powershell
python mapper\build_map.py                                   # dependency map  -> reports\dependency_map.png
python baseline\capture.py --seconds 180                     # healthy numbers -> reports\baseline.json
python controller\safety.py kill recommendation --duration 90   # one safe experiment -> reports\experiments.jsonl
powershell -ExecutionPolicy Bypass -File chaos\stop_all.ps1  # emergency: undo everything
```
Always confirm afterwards with `docker compose ps` (in the OTel Demo folder) that every service is back Up.

---

## Repo layout
```
config/      thresholds.yaml (abort limits) · targets.yaml (allow/deny lists) · map_overrides.yaml (manual map fixes)
mapper/      build_map.py (static + runtime map) · draw_map.py (layered drawing)
baseline/    capture.py
chaos/       inject.py · stop_all.ps1
controller/  metrics.py (where numbers come from) · safety.py (the referee)
reports/     baseline, dependency map, experiment log
docs/        PROGRESS (milestones + evidence) · EXPLAINER (judge-ready explanations) · GLOSSARY
CLAUDE.md    the project brief and safety rules we gave our AI coding assistant
```

## Honesty notes
- We built this with heavy help from an AI coding assistant (see `CLAUDE.md`); every result above comes from real runs on our laptop, logged in `reports/`.
- Network delay/loss via Pumba is written but not yet tested; `chaos/stop_all.ps1` is not yet tested.

## License
MIT — see [LICENSE](LICENSE). The OpenTelemetry Demo is a separate project under Apache 2.0.
