# CLAUDE.md — Bosch Hackathon: AI-Driven Chaos Engineering

> Read this whole file before doing anything. It is the single source of truth for this project.
> If something here conflicts with what you see on the machine, **trust the machine, tell us, and suggest an update to this file.**

---

## 0. Who you are working with and how to talk to us

You are helping a **5-person student team** at a 2-day **Bosch hackathon in Bengaluru (10–11 Oct 2026)**.
The prize that matters most: being shortlisted for **Bosch technical interviews on 12 Oct 2026**.
In those interviews **each of us must explain the project on our own**, without you in the room.

So your job is two things at once:
1. **Build** a working, safe chaos-engineering system with us.
2. **Teach** us what you built, in plain English, so any one of us can explain and defend it to a Bosch engineer.

**Understanding beats speed.** A feature we can't explain is worth less than a smaller one we can.

### 0.1 The plain-English rule (applies to EVERYTHING you say)
- Write as if explaining to a smart friend who has never used Docker, Prometheus or Kubernetes.
- **Every technical term gets a short definition in brackets the first time it appears in a response.**
  Example: "p95 latency (the response time that 95 out of 100 requests are faster than)".
- Prefer short sentences and numbered steps. No walls of text.
- Before running any command, say in **one line** what it does and why, in plain English.
- After running something, say what the output **means**, not just what it printed.
  Bad: "Exit code 0." Good: "It worked — all 15 services are up and healthy."
- When you make a design choice, say **what you chose, what the alternative was, and why** in 1–2 sentences.
  Judges love asking "why did you do it this way?"
- If you are unsure about anything (a URL, metric name, container name, command flag), **check it on the machine
  instead of guessing**, and tell us what you checked and what you found.

### 0.2 Mandatory "Explain it to the judges" block
**At the end of EVERY task you complete** (code written, command run, bug fixed, config changed, experiment run),
finish your response with this block:

```markdown
### 🗣️ Explain it to the judges
- **What we did (plain English):** 2–3 sentences, no jargon. If a technical word is unavoidable, define it in brackets.
- **Why it matters:** 1–2 sentences linking it to resilience / the Bosch problem statement.
- **Analogy:** one everyday comparison (e.g., "like a fire drill for software").
- **Say it like this:** a 1–2 sentence line we can say out loud to a judge, word for word.
- **Likely judge question + our answer:** one question a Bosch engineer might ask, with a short, honest answer.
- **Numbers to remember (if any):** e.g., "baseline error rate 0.4%, recovery time 38 s".
```

Then **append the same block to `docs/EXPLAINER.md`** (create the file and `docs/` folder if missing) with this header:

```markdown
---
## [YYYY-MM-DD HH:MM] <Task title> — <which milestone checklist item this helps>
```

`docs/EXPLAINER.md` becomes our single study guide for the final presentation and the interviews. Never delete
or rewrite old entries; only append. If a later task changes how something works, add a new entry that says
"This replaces the earlier explanation of X because Y."

### 0.2b Hands-on rule — "Your turn" steps
We are moving fast with heavy AI help, so we must still touch the system ourselves to really understand it.
At every natural checkpoint (app started, experiment ready, new script working), add a short section:

```markdown
### 🧑‍💻 Your turn (2–5 min)
1. `<command>` — what it does in one line. **Look for:** what a good result looks like.
2. ...
```
- Prefer small, safe, observable things: launching the app, opening a dashboard, running a status command,
  triggering the first manual failure ourselves, reading a log line.
- Always list the key commands you ran (or would run) so we can repeat them without you during the demo or interview.
- Never put destructive commands in "Your turn" without a bold warning.

### 0.3 Keep a glossary
Maintain `docs/GLOSSARY.md`: every time you introduce a new technical term, add a one-line plain-English definition
(alphabetical). Seed it with the glossary in section 10 of this file.

### 0.4 Honesty rules
- Never claim something works unless you ran it and saw it work. Say "tested" vs "written but not yet tested".
- If a result is weak or surprising, say so — an honest "we found that X did not recover" is a great finding for judges.
- Never fake metrics, screenshots, or logs for the demo.

---

## 1. The problem statement (from Bosch)

**Title:** AI-Driven Chaos Engineering for Cloud-Native Resilience.
**Goal:** Build an AI system that intelligently introduces controlled failures into a cloud-native application
and analyzes how the system responds, to improve its resilience.

**Plain English:** Chaos engineering means *breaking parts of a system on purpose, in a controlled way*
(e.g., shutting down one server, or making the network slow) to find out whether the whole system survives and
recovers — **before** a real outage finds the weakness for you. It's a fire drill for software.

Our system must decide **what to break, when, and how safely**, then **explain what the failure revealed and how to fix it.**

The solution should:
1. **Select and understand a sample app** — map its services, dependencies and data flows (automatically or semi-automatically).
2. **Plan failure experiments intelligently** — riskiest / most informative first, based on the dependency map and observed behaviour.
3. **Inject controlled failures with safety limits** — stop automatically if error rate, latency or blast radius exceed thresholds.
4. **Observe behaviour** — capture errors, slowdowns, recovery time.
5. **Analyze and report** — weaknesses, recommended fixes, ideally a ranked resilience score.

### Rules
- Sample app: public GitHub repo, free/open-source license, cloud-native (containerized, ideally multi-service,
  deployable with Docker Compose or Kubernetes), runs **entirely in our own local sandbox**.
- Submission must document the **repository link and deployment steps**.
- Example failures allowed: container crash, slow/lossy network, full disk, overloaded DB, failed dependency, traffic spike.
- **OUT OF SCOPE (never do these):** attacking real/production systems; anything outside our own sandbox;
  any failure that could affect other participants or the shared venue infrastructure/Wi-Fi/network.

---

## 2. Schedule

**Day 1 — Sat 10 Oct: Build the foundation**
- 1:00 PM Pitstop (mentor check-in) · **5:00 PM Milestone 1** · 5–6 PM Submission & shortlisting.
- Our internal deadline: **submit by 4:30 PM.**

**Day 2 — Sun 11 Oct: Enhance, analyze, showcase**
- 9 AM mentor feedback + new challenges · 1 PM pitstop · 4 PM Milestone 2 · 4–6 PM final presentation.

**Mon 12 Oct:** technical interviews for shortlisted participants (individual explanations — see section 0).

### Milestone 1 checklist (keep this updated in `docs/PROGRESS.md`)
- [ ] **Setup & app selection:** sample app running end to end in the sandbox.
- [ ] **Application mapping:** services, dependencies, data flows mapped (manual corrections allowed).
- [ ] **Monitoring baseline:** normal error rate, latency and health captured under steady load.
- [ ] **First failure injection:** at least one failure (e.g., container crash or network delay) triggered and observed.
- [ ] **Safety controls:** automatic stop or rollback on threshold breach, **tested at least once**.
- [ ] **Day-1 checkpoint:** short demo — app running, one safe failure injected, impact visible.

**Day-1 MINIMUM:** a running app, a dependency map, and one safe failure injection with a working kill switch.
**Do not start Day-2 features until every box above is ticked.** If we ask for a Day-2 feature early, remind us.

When you tick a box, update `docs/PROGRESS.md` with the time and the evidence (file path, screenshot, log line).

---

## 3. Environment

- Main machine: **Windows 11**, **PowerShell**, user folder `C:\Users\ASUS`.
- **Our project folder (this repo): `F:\Hacka`** — this is the "chaos controller" repo; all our code goes here.
- Docker 28.3.3, Docker Compose v2.39.2 (Docker Desktop, WSL2 backend).
- 32 GB RAM, GPU with 16 GB VRAM (reserved for a local LLM on Day 2).
- Bash scripts need Git Bash or WSL; **prefer PowerShell (`.ps1`) or Python** for anything we run on Windows.
- Python: always use a virtual environment:
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```
  Keep `requirements.txt` up to date whenever you add a library.
- Windows gotchas to watch for: path separators, PowerShell execution policy for `.ps1` files,
  line endings in shell scripts, and Docker Desktop needing to be running before any `docker` command.

### 3.1 Target app (the "victim")
**Primary:** OpenTelemetry Demo ("Astronomy Shop") — `https://github.com/open-telemetry/opentelemetry-demo` (Apache 2.0).
- Intended clone location: `C:\Users\ASUS\opentelemetry-demo` (**check it exists; if not, tell us and offer to clone it**).
- Started with `docker compose up -d` from inside that folder.
- **Plain English:** a fake online telescope shop built from ~15 small programs (microservices) that talk to each
  other — like a restaurant where the waiter, chef, cashier and delivery driver are separate people.
- Services include: frontend, cart, checkout, payment, product catalog, recommendation, ad, currency, shipping,
  email, quote, accounting, fraud detection, Kafka (message queue), valkey/redis cache, etc.
- Built-in tooling: **Prometheus** (collects numbers/metrics), **Grafana** (dashboards/graphs),
  **Jaeger** (traces — follows one request across services, plus a service graph), **Locust** (fake shoppers / load generator).
- Expected URLs (verify): `http://localhost:8080` (shop), `/grafana`, `/jaeger/ui`, `/loadgen`.
- **Verify real container/service names with `docker compose ps` before writing any code that targets them.**
  Put the verified names in `config/targets.yaml`; never hard-code guessed names.
- **Do NOT use the demo's built-in failure feature flags (flagd)** for our experiments — judges could see that as
  flipping a switch the app already had. We inject **real infrastructure faults ourselves**.
- The demo is heavy. If the laptop struggles, tell us the RAM/CPU usage and suggest which non-essential services to disable.

**Backup option (timeboxed until ~11:45 AM Day 1):** `https://github.com/Arsterid/ticket-booking-system`
(MIT, FastAPI + Postgres + KeyDB + TaskIQ workers, Prometheus/Grafana, Locust). Only switch if the team decides to.

---

## 4. Architecture of OUR project (the "chaos controller")

The OTel Demo is just the target. **What we build — and get judged on — is the controller around it.**

```
[Mapper] → dependency graph ─┐
[Baseline] → normal metrics ─┼→ [Planner] → picks experiment → [Injector] → breaks one thing
                             │                                     │
                             └──────── [Safety Controller] ◄───────┘  watches metrics every 5 s,
                                          aborts + restores on threshold breach
                                                   │
                                            [Reporter] → results, fixes, resilience score
```

**Plain-English version (use this in the pitch):**
1. **Mapper** — draws a map of who talks to whom inside the app.
2. **Baseline** — measures what "healthy" looks like, so we know what "broken" looks like.
3. **Planner** — the "brain": picks which part to break next, starting with the most useful and safest test.
4. **Injector** — actually breaks that one part (crash it, freeze it, slow its network).
5. **Safety Controller** — a referee watching the scoreboard every 5 seconds; if things get too bad, it blows
   the whistle, stops the experiment, and puts everything back.
6. **Reporter** — writes up what happened, what it means, how to fix it, and a resilience score.

### Repo layout (this repo, `F:\Hacka`, will be pushed to our public GitHub)
```
F:\Hacka\
  CLAUDE.md                 # this file
  README.md                 # repo link, target-app link, deploy steps, how to run a demo
  requirements.txt
  config/
    thresholds.yaml         # abort thresholds
    targets.yaml            # ALLOWLIST of breakable services + DENYLIST (verified names)
    map_overrides.yaml      # manual fixes to the dependency map
  mapper/build_map.py       # dependency map → reports/dependency_map.png + .json
  baseline/capture.py       # baseline metrics → reports/baseline.json
  chaos/inject.py           # injection functions (kill, pause, delay)
  chaos/stop_all.ps1        # manual emergency restore of everything
  controller/safety.py      # monitor loop + automatic abort/rollback
  dashboard/app.py          # optional Streamlit UI with big STOP button
  reports/experiments.jsonl # one line per experiment
  docs/EXPLAINER.md         # judge-ready explanations (section 0.2)
  docs/GLOSSARY.md          # plain-English definitions (section 0.3)
  docs/PROGRESS.md          # milestone checklist with evidence
  docs/DEMO_SCRIPT.md       # 3-minute demo script
```

Every Python file starts with a short docstring: **what it does in plain English, how to run it, what it outputs.**
Comments explain *why*, not just *what*. Code should be simple enough for a teammate to walk a judge through.

---

## 5. Safety rules (non-negotiable)

1. **Blast-radius DENYLIST — never break these:** observability and control-plane containers
   (otel-collector, prometheus, grafana, jaeger, opensearch, load-generator, flagd, frontend-proxy)
   and **anything not belonging to the OTel Demo compose project**. Breaking monitoring would blind our kill switch.
2. **Only ever target containers in our own compose project on this laptop.** Never touch the venue network,
   other laptops, or anything on the internet. Network faults apply **only inside a target container, never to the host.**
3. **Two layers of safety on every experiment:**
   - **Time limit:** every injection has a hard max duration (default 120 s) after which it auto-reverts.
   - **Threshold abort:** the safety controller aborts early on breach.
4. **One experiment at a time.** Never stack failures on Day 1.
5. **Always restore:** after any experiment, confirm with `docker compose ps` that every service is back to running/healthy,
   and say so in plain English.
6. **Ask us before** running anything destructive: `docker compose down -v`, deleting volumes/images, pruning,
   editing the OTel Demo's own files, changing Docker Desktop settings, or installing system-level software.
7. **Log every experiment** to `reports/experiments.jsonl` (start time, target, fault type, parameters,
   baseline values, peak error rate, peak p95 latency, whether abort fired and why, time to recover).

### Default thresholds (`config/thresholds.yaml`, tune from baseline)
- Abort if **error rate > max(5%, 3× baseline)** OR **p95 latency > 2× baseline**
  for **30 seconds** (6 consecutive checks at 5 s interval).
- Hard max experiment duration: **120 s**.
- "Recovered" = error rate and p95 back within 20% of baseline for 30 s.

**Plain English for judges:** "We never break anything without two seat belts: a timer that always undoes the
damage after 2 minutes, and a referee that undoes it sooner if users are getting hurt too much."

---

## 6. Implementation guidance

### 6.1 Metrics source (verify before coding)
- Prefer the **Prometheus HTTP API** (`/api/v1/query`). Find whether/where Prometheus is exposed to the host by
  checking the OTel Demo `docker-compose.yml` and `docker compose ps`.
- Metric names differ by version. **Discover them** via `/api/v1/label/__name__/values` and look for
  span-metrics (calls / duration histogram) or HTTP server metrics. **Show us the PromQL you chose and explain it in plain English.**
- Fallback if Prometheus is awkward: Locust's JSON stats endpoint behind `/loadgen`
  (failure ratio, response-time percentiles). Verify the exact path.

### 6.2 Dependency map
- **Runtime view:** Jaeger's dependencies/service-graph data (verify the API path through the proxy).
- **Static view:** parse the OTel Demo `docker-compose.yml` (`depends_on`, `*_ADDR` env vars).
- Merge both; **highlight edges that appear in one but not the other** — that's an insight for judges
  ("the config says X talks to Y, but in real traffic it never does" or vice versa).
- Output: `reports/dependency_map.png` (networkx + matplotlib, readable on a projector) and `reports/dependency_map.json`.
- Allow manual corrections via `config/map_overrides.yaml`.
- Also compute, per service: how many services depend on it (directly and indirectly). This feeds the Day-2 planner.

### 6.3 Fault injection (Docker-level)
- **Container crash:** `docker kill <container>` → restore with `docker start <container>`.
- **Freeze:** `docker pause` / `docker unpause`.
- **Network delay/loss:** **Pumba** (`gaiaadm/pumba` / `alexei-led/pumba` — verify the current image) run as a container
  with the Docker socket mounted, using its `netem` commands with `--duration` so it auto-reverts.
  Verify current syntax and the helper `tc` image before using it.
- Start with the **smallest blast radius**: a leaf service (e.g., recommendation or ad), then progress to
  a delay on a more central service (e.g., product catalog).
- Every injection function returns a matching **restore** function, so the safety controller can always undo it.

### 6.4 Safety controller (`controller/safety.py`)
- Loop every 5 s: query error rate + p95; compare to baseline + thresholds; track consecutive breaches.
- Print one clear, timestamped line per check (good for the live demo), e.g.
  `12:41:05  errors 7.2% (limit 5.0%)  p95 840 ms (limit 600 ms)  breach 3/6`.
- On breach: stop the injection, restore the container (start / unpause / remove netem), log `abort_fired: true`
  with the reason, then keep monitoring until "recovered" and record recovery time.
- Manual STOP: Ctrl+C handler that restores everything, plus `chaos/stop_all.ps1` as an emergency button.
- **We must demo the abort firing at least once** — design one experiment deliberately strong enough to trip it.

### 6.5 Baseline
- With the load generator running and nothing broken, sample metrics for 3–5 minutes.
- Save mean/p95 latency, error rate and container health to `reports/baseline.json`; remind us to screenshot Grafana.

---

## 7. Day-1 work plan (team of 5)

| Who | Owns |
|---|---|
| Lead (main laptop) | Safety controller, integration, presenting |
| Infra | App running, dashboards, baseline capture |
| Chaos | Injection scripts + `stop_all.ps1` |
| Mapping | Dependency map (static + runtime), `map_overrides.yaml` |
| Docs + Demo | README, EXPLAINER, GLOSSARY, slides, demo script, backup demo video |

Checkpoints: **11:30** app running · **13:00** map + baseline + first manual injection observed ·
**15:00** automatic abort tested · **16:30** submitted (README, map, baseline, experiment log, demo video backup).

If something is blocked for **>20 minutes**, propose the simplest workaround and keep moving. Tell us plainly
what we lose by taking the workaround.

**Everyone must be able to explain every part**, not only their own. When you finish a component, suggest a
30-second "teach-back" summary the owner can use to brief the rest of the team.

---

## 8. Day-2 direction (do NOT start before Milestone 1 is done)

- **Planner (the "intelligence"):** rank experiments by **risk = dependency centrality** (how many services rely on it)
  **× traffic share × past fragility**. Explain every choice in plain English
  ("We test the product catalog first because 6 services depend on it and it handles 40% of traffic").
- **Local LLM** (Ollama on the 16 GB GPU, e.g., a 7–14B model): turn experiment logs into findings,
  root-cause hypotheses and concrete fixes (timeouts, retries, circuit breakers, fallbacks, replicas).
  Runs **fully offline inside our sandbox**. Always show the raw data next to the LLM's conclusion so judges can see
  it's grounded, and be honest that the LLM suggests — humans decide.
- **Resilience score per service** (0–100) from error impact, latency impact, blast radius and recovery time;
  ranked table. Document the exact formula in plain English in `docs/EXPLAINER.md`.
- **Before/after story:** apply one fix (e.g., a timeout or restart policy), rerun the same experiment, show the score improving.
- Incorporate mentor feedback from the 9 AM session first.

---

## 9. Definition of done for the Day-1 demo (3 minutes)
1. Show the shop running + Grafana baseline.
2. Show the dependency map and say which service we target and why.
3. Start the experiment; show errors/latency rising live.
4. Show the safety controller detecting the breach and restoring automatically (with the log line + timestamp).
5. Show recovery time and one sentence on what we learned.

Keep `docs/DEMO_SCRIPT.md` in sync with this, including **who says what** and the exact commands to run.

---

## 10. Starter glossary (copy into `docs/GLOSSARY.md`)
- **Blast radius** — how much of the system a failure can affect. Small blast radius = only one small part gets hurt.
- **Baseline** — measurements of the system when everything is normal; our "healthy" reference point.
- **Chaos engineering** — breaking things on purpose, safely, to find weaknesses before real outages do.
- **Circuit breaker** — code that stops calling a broken service for a while, like a fuse that trips to protect the house.
- **Container** — a sealed box containing one program and everything it needs to run; Docker runs these boxes.
- **Dependency** — when service A needs service B to do its job (checkout needs payment).
- **Docker Compose** — a recipe file that starts many containers together with one command.
- **Error rate** — the percentage of requests that fail.
- **Fallback** — a backup answer when a service is down (e.g., show default recommendations instead of none).
- **Kill switch** — a way to instantly stop an experiment and undo the damage.
- **Latency** — how long a request takes to get an answer.
- **Load generator (Locust)** — a tool that pretends to be many shoppers using the site at once.
- **Microservice** — one small program that does one job; the shop is made of ~15 of them.
- **netem** — a Linux feature that can add artificial delay or packet loss to network traffic.
- **Observability** — being able to see what's happening inside a system through metrics, logs and traces.
- **p95 latency** — the response time that 95 out of 100 requests are faster than; shows the "slow tail" users feel.
- **Prometheus / PromQL** — a database of system numbers over time / the query language to ask it questions.
- **Recovery time** — how long the system takes to get back to normal after the failure is removed.
- **Resilience** — a system's ability to keep working (maybe degraded) and bounce back when parts fail.
- **Retry** — automatically trying a failed request again.
- **Timeout** — a maximum wait time; after it, give up instead of hanging forever.
- **Trace (Jaeger)** — the full journey of one request through all the services it touched.

---

## 11. Quick reminder checklist for you (Claude) on every task
1. Did I verify names/URLs/flags on the machine instead of guessing?
2. Did I explain each command in one plain-English line before running it?
3. Is it safe? (allowlisted target, one experiment, time limit, restore confirmed)
4. Did I say whether it's **tested** or **untested**?
5. Did I end with the **🗣️ Explain it to the judges** block?
6. Did I append that block to `docs/EXPLAINER.md`, add new terms to `docs/GLOSSARY.md`, and update `docs/PROGRESS.md`?
