# Demo script — Day-1 checkpoint (3 minutes)

Goal (CLAUDE.md §9): shop running + baseline → map + why this target → experiment live → automatic abort → recovery + lesson.
Roles from CLAUDE.md §7. Swap names in when we decide who speaks.

---

## Before the judges arrive (T-10 min) — Infra + Lead

| ✔ | Check | Command / place | Good result |
|---|---|---|---|
| ☐ | All shop containers up | `docker ps --filter "label=com.docker.compose.project=opentelemetry-demo" -q \| Measure-Object -Line` | **28** |
| ☐ | Load running at 15 users for ≥ 2 min | http://localhost:8080/loadgen/ | Users 15, failures ~0 |
| ☐ | Baseline file present | `reports/baseline.json` | 0.00% errors, 517 ms |
| ☐ | Terminal 1 open in `F:\Hacka`, venv active | `.venv\Scripts\Activate.ps1` | prompt shows `(.venv)` |
| ☐ | Terminal 2 ready with the emergency stop typed (NOT run) | `powershell -ExecutionPolicy Bypass -File chaos\stop_all.ps1` | — |
| ☐ | Browser tabs, in order | 1 Shop `localhost:8080` · 2 Grafana `/grafana` · 3 `reports/dependency_map.png` · 4 Locust **Charts** `/loadgen/` | — |
| ☐ | Backup video file on the desktop | `faultline_demo_backup.mp4` | plays |
| ☐ | Laptop on charger, notifications off, font size up in terminal | — | — |

---

## The 3 minutes

### 0:00–0:30 — The app and "healthy" (Infra)
*Show tab 1 (shop), then tab 2 (Grafana).*
> "This is a real online shop made of 28 containers — a frontend, cart, checkout, payment, a database, a message queue and more. Fifteen simulated shoppers are using it right now.
> Before breaking anything we measured healthy: **zero errors, about half a second per request, 2.7 requests a second.** That's our reference point for 'too much damage'."

### 0:30–1:00 — The map and why this target (Mapping)
*Show tab 3 (dependency map).*
> "Our mapper drew this automatically from two sources: the config files and real traffic traces. The red numbers are how many services break if this one breaks — the database is the most critical with 5.
> We start with the **smallest blast radius**: `recommendation`, the 'you may also like' box. The map says only **one** service depends on it — so in theory almost nobody should notice."

### 1:00–2:00 — Break it, live (Chaos)
*Terminal 1, then switch to tab 4 (Locust charts).*
```powershell
python controller\safety.py kill recommendation --duration 90
```
> "Our safety controller crashes it, with two seat belts: a hard 90-second timer, and a referee that checks what shoppers feel every five seconds.
> Limits: more than **5% errors** or responses over **1 second** for **30 seconds** → it stops the test by itself."
*Point at the lines as they appear: `breach 1/6`, `2/6`… and the Locust failure chart rising.*

### 2:00–2:30 — The referee blows the whistle (Lead)
*Point at the `!!! ABORT` and `RESTORED` lines.*
> "There — after 30 seconds of real damage it aborted **on its own**, well before the 90-second timer, and restarted the service. No human touched anything.
> Every experiment is logged with its numbers in `reports/experiments.jsonl`."

### 2:30–3:00 — Recovery and what we learned (Docs + Demo)
*Wait for `RECOVERED: ... s` (or, if still recovering, show line 1 of `reports/experiments.jsonl`).*
> "This morning the same test: abort after **41 seconds**, and the shop needed **66 seconds** after the restart to feel normal again.
> The lesson: the map said only one service depends on recommendations, but **one in five shopper requests failed** — the frontend has no fallback. A small optional feature can hurt the whole shop. Tomorrow our AI planner uses findings like this to choose what to test next."

---

## If something goes wrong (say it honestly — it's still a result)

| Situation | What to do / say |
|---|---|
| Abort does **not** fire (damage stayed under limits) | "This time the shop absorbed it — the timer undid the fault at 90 s. Here's this morning's run where the referee fired" → open `reports/experiments.jsonl` line 1. |
| Recovery takes long (up to 5 min) | Keep talking over it: "the second wave of failures after the fix is a real finding we're investigating." Don't wait in silence; show the log. |
| Script crashes / anything looks stuck | Terminal 2: run `stop_all.ps1` (Enter). Then `docker ps` → 28 Up. "That's our emergency button." |
| Shop/laptop is slow or the Wi-Fi is down | Everything is local — Wi-Fi doesn't matter. If the laptop itself struggles, play the backup video. |

## After the demo (Infra)
```powershell
docker ps --filter "label=com.docker.compose.project=opentelemetry-demo" --format "table {{.Names}}\t{{.Status}}"
```
Confirm all 28 are Up and say so out loud: "Everything is back to normal."

## Likely judge questions (anyone should be able to answer)
- **"Where is the AI?"** — "Day 1 is the safety foundation: an AI that breaks things needs a referee it can't outrun. Day 2 adds the planner that ranks targets by map criticality, traffic and past fragility, and a local AI model that turns the logs into fixes."
- **"Why use the load generator's numbers, not Prometheus?"** — "Prometheus updates about once a minute — too slow for a 5-second safety check. The load generator tells us every few seconds exactly what shoppers feel."
- **"Why 15 users?"** — "At 100 users the database ran out of memory and our load tool maxed out; at 5 users one failure looks like 17% errors."
- **"Isn't killing a container too simple?"** — "It's the smallest, safest first step — and it already found a real weakness. Freeze and network-delay faults are built next."
